#!/usr/bin/env python3
"""Choose a stable due slot; no model calls, credential access or file mutation."""

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import researchdesk_offline as store
import researchdesk_batch_inputs as common
import researchdesk_cycle as cycle


def instant(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise store.OfflineError('调度时间必须带时区')
    return result.astimezone(timezone.utc)


def load_config(root):
    path = common.config_path(root, 'config/automation.yaml')
    config = store.load_yaml(path)
    common.fields(config, {'schema_version', 'enabled', 'timezone', 'schedule_utc', 'activated_at',
                          'cycle_config', 'admission_config', 'catchup'}, '调度配置')
    if (type(config['schema_version']) is not int or config['schema_version'] != 1
            or type(config['enabled']) is not bool or config['timezone'] != 'Asia/Shanghai'
            or config['schedule_utc'] != '0 19 * * 1,4'):
        raise store.OfflineError('当前调度仅支持周二/周五北京时间03:00')
    common.fields(config['catchup'], {'lookback_days', 'max_slots_per_run'}, '补跑配置')
    common.positive(config['catchup']['lookback_days'], 1, 30, 'lookback_days')
    if type(config['catchup']['max_slots_per_run']) is not int or config['catchup']['max_slots_per_run'] != 1:
        raise store.OfflineError('每次仅补跑一个到期轮次')
    common.config_path(root, config['admission_config'])
    instant(config['activated_at'])
    return config


def accepted_marker(root, relative):
    path = root / relative
    for part in (path,) + tuple(path.parents):
        if part == root:
            break
        if part.is_symlink():
            raise store.OfflineError('正式准入标记拒绝符号链接')
    marker = Path(str(path) + '.sha256')
    if (marker.is_symlink() or not marker.is_file()
            or marker.read_text().strip() != store.digest(path.read_bytes())):
        raise store.OfflineError('正式准入标记散列无效')
    return store.load_yaml(path)


def due_slot(root, config, now=None):
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise store.OfflineError('当前时间必须带时区')
    now = now.astimezone(timezone.utc)
    topic = cycle.load_config(root, config['cycle_config'])['topic']
    start = max(instant(config['activated_at']), now - timedelta(days=config['catchup']['lookback_days']))
    local_zone = ZoneInfo(config['timezone'])
    local_start = start.astimezone(local_zone)
    local_now = now.astimezone(local_zone)
    cursor = local_start.replace(hour=3, minute=0, second=0, microsecond=0)
    if cursor < local_start:
        cursor += timedelta(days=1)
    while cursor <= local_now:
        if cursor.weekday() in (1, 4):
            cycle_id = '%s-%s-0300' % (topic, cursor.strftime('%Y%m%d'))
            accepted = 'reports/%s/admissions/%s/accepted.yaml' % (topic, cycle_id)
            if (root / accepted).exists():
                marker = accepted_marker(root, accepted)
                if marker.get('production_accepted') is not True:
                    raise store.OfflineError('正式准入标记无效，保留现场')
            else:
                receipt_path = 'reports/test/%s/cycles/%s/receipt.yaml' % (topic, cycle_id)
                receipt = store.checked_yaml(root, receipt_path) if (root / receipt_path).exists() else None
                # A terminal no-new/rejected/blocked run should notify through
                # its original job, not consume calls again at every trigger.
                # Successful-but-unpublished runs resume admission with no inference.
                terminal = receipt is not None and not all(
                    receipt.get('stages', {}).get(stage, {}).get('status') == 'test_accepted'
                    for stage in ('research', 'insight'))
                if not terminal:
                    return {'cycle_id': cycle_id, 'cycle_config': config['cycle_config'],
                            'operation': 'run', 'slot_utc': cursor.astimezone(timezone.utc).isoformat()}
        cursor += timedelta(days=1)
    return {'cycle_id': '', 'cycle_config': config['cycle_config'], 'operation': 'run', 'slot_utc': ''}


def plan(root, event, requested_cycle_id='', requested_config='', requested_operation='', now=None, run_id='manual'):
    root = Path(root).resolve()
    # A fresh/public checkout contains no operator settings. Never infer an
    # enabled schedule from an example or silently provision a hosted runner.
    if not (root / 'config/automation.yaml').exists():
        if event == 'schedule' or requested_operation == 'catchup':
            return {'cycle_id': '', 'cycle_config': '', 'operation': 'run', 'slot_utc': ''}
        raise store.OfflineError('请先在执行主机初始化本地工作台；云端手动研究暂未配置')
    if event == 'schedule' or requested_operation == 'catchup':
        config = load_config(root)
        if config['enabled'] is not True:
            return {'cycle_id': '', 'cycle_config': config['cycle_config'], 'operation': 'run', 'slot_utc': ''}
        return due_slot(root, config, now)
    if event != 'workflow_dispatch':
        raise store.OfflineError('研究任务只接受定时或受信任手动派发')
    operation = requested_operation or 'health'
    if operation not in {'health', 'discover', 'run', 'admit'}:
        raise store.OfflineError('未知手动操作')
    path = requested_config or 'config/cycles/default.yaml'
    selected = cycle.load_config(root, path)
    cycle_id = requested_cycle_id or '%s-gh-%s' % (selected['topic'], run_id)
    cycle.base_path(selected, cycle_id)
    return {'cycle_id': cycle_id, 'cycle_config': path, 'operation': operation, 'slot_utc': ''}


def main():
    import os
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    commands = parser.add_subparsers(dest='command', required=True)
    command = commands.add_parser('plan')
    command.add_argument('--event', required=True)
    command.add_argument('--requested-cycle-id', default='')
    command.add_argument('--requested-config', default='')
    command.add_argument('--requested-operation', default='')
    command.add_argument('--github-output', type=Path)
    args = parser.parse_args()
    try:
        result = plan(args.root, args.event, args.requested_cycle_id, args.requested_config,
                      args.requested_operation, run_id=os.environ.get('GITHUB_RUN_ID', 'manual'))
        if args.github_output:
            with args.github_output.open('a', encoding='utf-8') as handle:
                for key in ('cycle_id', 'cycle_config', 'operation'):
                    value = result[key]
                    if '\n' in value or '\r' in value:
                        raise store.OfflineError('调度输出无效')
                    handle.write('%s=%s\n' % (key, value))
        print(json.dumps(result))
        return 0
    except Exception:
        print(json.dumps({'error': 'schedule_plan_failed'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
