#!/usr/bin/env python3
"""Choose a stable due slot; no model calls, credential access or file mutation."""

import argparse
from datetime import datetime, time, timedelta, timezone
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import offline as store
import batch_inputs as common
import cycle


MAX_TOPICS = 8
DEFAULT_WEEKLY = {'weekdays': [2, 5], 'time': '03:00', 'timezone': 'Asia/Shanghai'}
_CLOCK = re.compile(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]')
_ZONE = re.compile(r'[A-Za-z0-9_+-]+(?:/[A-Za-z0-9_+-]+)*')


def instant(value):
    try:
        return _utc(datetime.fromisoformat(value.replace('Z', '+00:00')))
    except (AttributeError, ValueError):
        raise store.OfflineError('调度时间必须带时区') from None


def _utc(value):
    if value.utcoffset() is None:
        raise store.OfflineError('调度时间必须带时区')
    return value.astimezone(timezone.utc)


def validate_weekly(value):
    common.fields(value, {'weekdays', 'time', 'timezone'}, '每周研究日程')
    days, clock, zone = (value[key] for key in ('weekdays', 'time', 'timezone'))
    if (not isinstance(days, list) or not 1 <= len(days) <= 7
            or any(type(day) is not int or not 1 <= day <= 7 for day in days)
            or len(set(days)) != len(days)):
        raise store.OfflineError('请选择 1–7 个不同的星期，星期一为 1，星期日为 7')
    if not isinstance(clock, str) or not _CLOCK.fullmatch(clock):
        raise store.OfflineError('每周运行时间须使用 24 小时制 HH:MM')
    if (not isinstance(zone, str) or not _ZONE.fullmatch(zone) or len(zone) > 100
            or zone.split('/')[0] in {'localtime', 'posixrules', 'posix', 'right'}):
        raise store.OfflineError('请使用 IANA 时区，例如 Asia/Shanghai')
    try:
        ZoneInfo(zone)
    except (ZoneInfoNotFoundError, ValueError):
        raise store.OfflineError('请使用有效的 IANA 时区，例如 Asia/Shanghai') from None
    return {'weekdays': sorted(days), 'time': clock, 'timezone': zone}


def weekly(config):
    """Read the selected schedule, or the original Beijing weekly schedule."""
    return validate_weekly(config.get('weekly', DEFAULT_WEEKLY))


def workflow_cron(rule):
    """GitHub interprets this cron expression in the rule's IANA time zone."""
    rule = validate_weekly(rule)
    hour, minute = map(int, rule['time'].split(':'))
    days = ','.join(str(day) for day in sorted(day % 7 for day in rule['weekdays']))
    return f'{minute} {hour} * * {days}'


def _local_instant(day, clock, zone):
    wall = datetime.combine(day, clock)
    # On a spring-forward day, advance to the first valid local minute. On a
    # fall-back day fold=0 picks the first occurrence of the same logical slot.
    for _ in range(24 * 60 + 1):
        actual = _utc(wall.replace(tzinfo=zone, fold=0))
        if actual.astimezone(zone).replace(tzinfo=None) == wall:
            return actual
        wall += timedelta(minutes=1)
    raise store.OfflineError('无法解析日程对应的本地时间')


def _slots_between(rule, start, end):
    if end < start:
        return
    zone = ZoneInfo(rule['timezone'])
    clock = time.fromisoformat(rule['time'])
    suffix = rule['time'].replace(':', '')
    # A time-zone transition can advance a skipped slot past local midnight.
    cursor = start.astimezone(zone).date() - timedelta(days=1)
    last = end.astimezone(zone).date()
    while cursor <= last:
        if cursor.isoweekday() in rule['weekdays']:
            actual = _local_instant(cursor, clock, zone)
            if start <= actual <= end:
                yield f'{cursor:%Y%m%d}-{suffix}', actual
        cursor += timedelta(days=1)


def due_slots(config, now=None):
    """Yield (nominal date and HHMM, actual UTC instant) from oldest to latest."""
    now = _utc(now or datetime.now(timezone.utc))
    start = max(instant(config['activated_at']), now - timedelta(days=config['catchup']['lookback_days']))
    yield from _slots_between(weekly(config), start, now)


def next_run(rule, now=None, *, activated_at=None):
    """Return the first actual UTC slot strictly after now, on or after activation."""
    rule = validate_weekly(rule)
    now = _utc(now or datetime.now(timezone.utc))
    try:
        start = now + timedelta(microseconds=1)
        if activated_at is not None:
            start = max(start, instant(activated_at))
        # Allow a full weekly interval plus a day for clock changes.
        _, actual = next(_slots_between(rule, start, start + timedelta(days=8)))
    except (StopIteration, OverflowError):
        raise store.OfflineError('无法计算下一次预计运行时间') from None
    return actual


def load_config(root):
    path = common.config_path(root, 'config/automation.yaml')
    config = store.load_yaml(path)
    common.fields(config, {'schema_version', 'enabled', 'timezone', 'schedule_utc', 'activated_at',
                          'cycle_config', 'admission_config', 'catchup'} |
                  ({'topics', 'weekly'} & config.keys()), '调度配置')
    if (type(config['schema_version']) is not int or config['schema_version'] != 1
            or type(config['enabled']) is not bool or config['timezone'] != 'Asia/Shanghai'
            or config['schedule_utc'] != '0 19 * * 1,4'):
        raise store.OfflineError('旧版调度字段须保留周二/周五北京时间 03:00 的默认值')
    common.fields(config['catchup'], {'lookback_days', 'max_slots_per_run'}, '补跑配置')
    common.positive(config['catchup']['lookback_days'], 1, 30, 'lookback_days')
    if type(config['catchup']['max_slots_per_run']) is not int or config['catchup']['max_slots_per_run'] != 1:
        raise store.OfflineError('每次仅补跑一个到期轮次')
    common.config_path(root, config['admission_config'])
    instant(config['activated_at'])
    if 'weekly' in config:
        config['weekly'] = weekly(config)
    if 'topics' in config:
        selected = config['topics']
        if (not isinstance(selected, list) or not 1 <= len(selected) <= MAX_TOPICS
                or any(not isinstance(topic, str) or not store.SAFE_ID.fullmatch(topic + '-20000101-0300')
                       for topic in selected) or len(set(selected)) != len(selected)):
            raise store.OfflineError('定时研究须选择 1–8 个不同的有效研究方向')
        primary = cycle.load_config(root, config['cycle_config'])
        directions = store.load_yaml(common.config_path(root, primary['topics_file'])).get('topics', {})
        if selected[0] != primary['topic']:
            raise store.OfflineError('第一个定时研究方向须与手动研究方向一致')
        if any(not isinstance(directions.get(topic), dict) or directions[topic].get('enabled') is not True
               for topic in selected):
            raise store.OfflineError('定时研究方向不存在或尚未启用')
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
    topic = cycle.load_config(root, config['cycle_config'])['topic']
    for slot, actual in due_slots(config, now):
        cycle_id = f'{topic}-{slot}'
        accepted = 'reports/%s/admissions/%s/accepted.yaml' % (topic, cycle_id)
        if (root / accepted).exists():
            marker = accepted_marker(root, accepted)
            if marker.get('production_accepted') is not True:
                raise store.OfflineError('正式准入标记无效，保留现场')
        else:
            receipt_path = 'reports/test/%s/cycles/%s/receipt.yaml' % (topic, cycle_id)
            receipt = store.checked_yaml(root, receipt_path) if (root / receipt_path).exists() else None
            # Successful-but-unpublished runs resume admission with no inference.
            terminal = receipt is not None and not all(
                receipt.get('stages', {}).get(stage, {}).get('status') == 'test_accepted'
                for stage in ('research', 'insight'))
            if not terminal:
                return {'cycle_id': cycle_id, 'cycle_config': config['cycle_config'],
                        'operation': 'run', 'slot_utc': actual.isoformat()}
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
