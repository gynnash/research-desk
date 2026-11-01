#!/usr/bin/env python3
"""Run the configured collection -> Research -> SDK Insight on one persistent host.

Only explicit run/collect operations contact sources or models. Scheduling and
configuration are read on this host; Writing is never launched here.
"""

import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from zoneinfo import ZoneInfo

import yaml

import researchdesk_cycle as cycle
import researchdesk_harness as harness
import researchdesk_offline as store
import researchdesk_research as research
import researchdesk_runner as runner
import researchdesk_schedule as schedule
import researchdesk_workbench as workbench


def _now():
    return datetime.now(timezone.utc)


@contextmanager
def pipeline_lock(root):
    # Separate from the per-request global budget lock: child stages own it.
    path = Path(tempfile.gettempdir()) / ('researchdesk-automatic-' + store.digest(str(root))[:24] + '.lock')
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise store.OfflineError('当前持久工作台已有自动研究任务') from exc
        yield
    finally:
        os.close(descriptor)


def _base(topic, identity):
    if any(not isinstance(value, str) or not store.SAFE_ID.fullmatch(value) for value in (topic, identity)):
        raise store.OfflineError('自动研究主题或批次 ID 无效')
    return 'reports/test/%s/automation/%s' % (topic, identity)


def _latest_slot(config, topic, now):
    if now.tzinfo is None:
        raise store.OfflineError('调度时间必须带时区')
    now = now.astimezone(timezone.utc)
    start = max(schedule.instant(config['activated_at']),
                now - timedelta(days=config['catchup']['lookback_days']))
    cursor = now.astimezone(ZoneInfo(config['timezone'])).replace(hour=3, minute=0, second=0, microsecond=0)
    if cursor > now.astimezone(cursor.tzinfo):
        cursor -= timedelta(days=1)
    while cursor.astimezone(timezone.utc) >= start:
        if cursor.weekday() in (1, 4):
            return '%s-%s-0300' % (topic, cursor.strftime('%Y%m%d'))
        cursor -= timedelta(days=1)
    return ''


def _catchup_slot(root, config, topic, now):
    if now.tzinfo is None:
        raise store.OfflineError('调度时间必须带时区')
    now = now.astimezone(timezone.utc)
    start = max(schedule.instant(config['activated_at']),
                now - timedelta(days=config['catchup']['lookback_days']))
    cursor = start.astimezone(ZoneInfo(config['timezone'])).replace(hour=3, minute=0, second=0, microsecond=0)
    if cursor.astimezone(timezone.utc) < start:
        cursor += timedelta(days=1)
    while cursor.astimezone(timezone.utc) <= now:
        if cursor.weekday() in (1, 4):
            identity = '%s-%s-0300' % (topic, cursor.strftime('%Y%m%d'))
            base = _base(topic, identity)
            if not (root / base / 'receipt.yaml').exists():
                return identity
            store.checked_yaml(root, base + '/receipt.yaml')
        cursor += timedelta(days=1)
    return ''


def _activation(root, config):
    result = deepcopy(config)
    path = workbench._path(root, 'config/local/deployment-started-at.json')
    if path.exists():
        marker = json.loads(path.read_text())
        if not isinstance(marker, dict) or not isinstance(marker.get('started_at'), str):
            raise store.OfflineError('部署起始时间标记无效')
        start = max(schedule.instant(config['activated_at']), schedule.instant(marker['started_at']))
        result['activated_at'] = start.isoformat()
    return result


def _fingerprint(effective):
    # Only settings used by the pipeline. A Writing preference does not change
    # a frozen research task; account/runtime and budget changes do.
    return store.digest({key: effective[key] for key in (
        'workbench_id', 'research_topics', 'research', 'insight', 'runtime', 'membership_budget')})


def _private_create(root, relative, payload):
    path = workbench._path(root, relative)
    if path.exists():
        if path.read_bytes() != payload:
            raise store.OfflineError('保留已有冻结配置，不替换该批次输入')
    else:
        workbench._write(path, payload)


def _freeze(root, effective, topic, identity, base, fingerprint, publisher_context):
    directory = 'config/local/automation/' + identity
    topics_path, research_path, insight_path = (directory + '/' + name for name in (
        'topics.yaml', 'cycle.yaml', 'insight.yaml'))
    topics = {'schema_version': 1, 'topics': {
        topic: deepcopy(effective['research_topics']['topics'][topic])}}
    research_config, insight_config = deepcopy(effective['research']), deepcopy(effective['insight'])
    research_config['topics_file'] = insight_config['topics_file'] = topics_path
    # Preserve runtime namespace/settings only in the ignored host snapshot.
    insight_config.setdefault('runtime', {})['workbench_id'] = effective['workbench_id']
    for relative, value in ((topics_path, topics), (research_path, research_config),
                            (insight_path, insight_config)):
        _private_create(root, relative, workbench._yaml(value))
    private = {'schema_version': 1, 'config_fingerprint': fingerprint,
               'hashes': {relative: store.digest((root / relative).read_bytes())
                          for relative in (topics_path, research_path, insight_path)}}
    _private_create(root, directory + '/snapshot.yaml', workbench._yaml(private))
    public_insight = deepcopy(insight_config)
    public_insight.pop('runtime', None)
    public_insight_text = workbench._yaml(public_insight).decode()
    context = {'schema_version': 1, 'topic': topic, 'cycle_id': identity,
               'config_fingerprint': fingerprint, 'selected_topic': topics,
               'topics_path': topics_path, 'topics_yaml_text': (root / topics_path).read_text(),
               'topics_sha256': store.digest((root / topics_path).read_bytes()),
               'research_config_path': research_path,
               'research_config': research_config,
               'research_config_yaml_text': (root / research_path).read_text(),
               'research_config_sha256': store.digest((root / research_path).read_bytes()),
               'insight_config_path': insight_path, 'insight_config': public_insight,
               'insight_config_yaml_text': public_insight_text,
               'insight_config_sha256': store.digest(public_insight_text.encode()),
               'writing_started': False, 'publish_authorized': False}
    if publisher_context and publisher_context.get('base_commit'):
        commit = publisher_context['base_commit']
        if not isinstance(commit, str) or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', commit):
            raise store.OfflineError('发布上下文 commit 无效')
        context['base_commit'] = commit
    store.save_yaml(root, base + '/context.yaml', context)
    return context


def _context(root, effective, topic, identity, base, fingerprint, publisher_context):
    path = root / base / 'context.yaml'
    if path.exists():
        value = store.checked_yaml(root, base + '/context.yaml')
        if value.get('topic') != topic or value.get('cycle_id') != identity:
            raise store.OfflineError('冻结上下文不属于当前研究轮次')
        if value.get('config_fingerprint') != fingerprint:
            return None
        private = workbench._read(workbench._path(root, 'config/local/automation/' + identity + '/snapshot.yaml'))
        if private.get('config_fingerprint') != fingerprint:
            raise store.OfflineError('冻结配置标识已变化')
        prefix = 'config/local/automation/' + identity + '/'
        expected_paths = {prefix + name for name in ('topics.yaml', 'cycle.yaml', 'insight.yaml')}
        if (set(private.get('hashes', {})) != expected_paths
                or value.get('topics_path') != prefix + 'topics.yaml'
                or value.get('research_config_path') != prefix + 'cycle.yaml'
                or value.get('insight_config_path') != prefix + 'insight.yaml'):
            raise store.OfflineError('冻结配置路径不属于当前轮次')
        for relative, digest in private['hashes'].items():
            path = workbench._path(root, relative)
            if not path.is_file() or store.digest(path.read_bytes()) != digest:
                raise store.OfflineError('冻结配置已被修改，保留现场')
        return value
    return _freeze(root, effective, topic, identity, base, fingerprint, publisher_context)


def _finish(root, base, result):
    # Attempt records are immutable. A terminal receipt is only created once,
    # so retries never overwrite a checkpoint already saved on GitHub.
    existing = sorted((root / base / 'attempts').glob('*.yaml'))
    relative = base + '/attempts/%06d.yaml' % (len(existing) + 1)
    result = dict(result, attempt=len(existing) + 1)
    store.save_yaml(root, relative, result)
    if result['terminal']:
        relative = base + '/receipt.yaml'
        store.save_yaml(root, relative, result)
    return dict(result, receipt_path=relative)


def _health(root, effective):
    from researchdesk_membership import MembershipClient
    from researchdesk_codex import CodexBackend
    host = runner.load_config(root)
    client = MembershipClient(host['_profile'], root)
    status = client.status()
    catalog = {entry['slug'] for entry in client.models()}
    required = {effective['research']['models'][role] for role in ('research', 'review')}
    required |= set(effective['insight']['models'].values())
    if (status.get('authenticated') is not True or status.get('plan_permission') is not True
            or not required.issubset(catalog)):
        raise store.OfflineError('会员授权或已选模型不可用')
    runtime = effective['insight'].get('runtime', {})
    directory = Path(runtime.get('state_directory',
        '~/Library/Application Support/ResearchDesk/runs')).expanduser()
    directory /= effective['workbench_id'] + '-' + store.digest(str(root))[:12]
    directory /= effective['research']['topic'] + '/health'
    capability = CodexBackend(profile={**effective['insight'].get('codex', {}),
                                      'run_directory': str(directory.resolve())}, root=root).preflight()
    if capability.get('live_ready') is not True:
        raise store.OfflineError('SDK 运行条件未满足')
    return {'membership_authorized': True, 'configured_models_available': True,
            'sdk_live_ready': capability.get('live_ready', False), 'model_calls': 0}


def run(root, event='schedule', operation='run', cycle_id=None, publisher_context=None,
        collector=None, researcher=None, insight_runner=None, health_checker=None,
        now=None, prepare=None):
    root = Path(root).resolve()
    if event not in {'schedule', 'manual'} or operation not in {'health', 'collect', 'run', 'catchup'}:
        raise store.OfflineError('自动研究事件或操作无效')
    with pipeline_lock(root):
        if prepare is not None:
            prepare()
        workbench.apply(root)
        effective = workbench.load_effective(root)
        topic = effective['research']['topic']
        empty = {'schema_version': 1, 'topic': topic, 'cycle_id': '', 'status': 'skipped',
                 'terminal': False, 'receipt_path': None, 'writing_started': False,
                 'publish_authorized': False, 'model_calls': 0}
        if event == 'schedule' and effective['automation']['enabled'] is not True:
            return dict(empty, reason='automation_disabled')
        if operation == 'health':
            health = (health_checker or _health)(root, effective)
            return dict(empty, status='healthy', health=health)
        clock = now or _now()
        scheduling = _activation(root, effective['automation'])
        identity = cycle_id or (_catchup_slot(root, scheduling, topic, clock) if operation == 'catchup' else
                               _latest_slot(scheduling, topic, clock)
                               if event == 'schedule' else topic + '-manual-' + clock.strftime('%Y%m%d-%H%M%S'))
        if not identity:
            return dict(empty, reason='no_due_slot')
        base = _base(topic, identity)
        if (root / base / 'receipt.yaml').exists():
            receipt = store.checked_yaml(root, base + '/receipt.yaml')
            return dict(receipt, receipt_path=base + '/receipt.yaml', cached=True)
        fingerprint = _fingerprint(effective)
        context = _context(root, effective, topic, identity, base, fingerprint, publisher_context)
        initial = dict(empty, cycle_id=identity, config_fingerprint=fingerprint, stages={},
                       collection_count=0, summary_count=0)
        initial.pop('model_calls', None)
        if context is None:
            return _finish(root, base, dict(initial, status='blocked', reason='configuration_changed'))
        result = dict(initial, context_path=base + '/context.yaml',
                      context_sha256=store.digest((root / base / 'context.yaml').read_bytes()))
        phase = 'collection'
        try:
            collected = (collector or cycle.collect_originals)(root, context['research_config_path'], identity)
            result['collection_count'] = len(collected.get('records', []))
            result['stages']['collection'] = {'status': collected['status'],
                                             'count': result['collection_count']}
            if collected['status'] == 'empty':
                incomplete = collected.get('discovery_status') not in (None, 'complete')
                return _finish(root, base, dict(result,
                    status='collection_incomplete' if incomplete else 'no_new', terminal=not incomplete))
            if collected['status'] != 'collected':
                return _finish(root, base, dict(result, status='collection_failed'))
            if operation == 'collect':
                return _finish(root, base, dict(result, status='collected', model_calls=0))
            phase = 'health'
            result['health'] = (health_checker or _health)(root, effective)
            phase = 'research'
            profile = runner.load_config(root)['_profile']
            studied = (researcher or research.run)(root, context['research_config_path'], identity, profile=profile)
            result['summary_count'] = len(studied.get('summary_paths', []))
            result['stages']['research'] = {'status': studied['status'], 'count': result['summary_count']}
            result['research_reserved_calls'] = studied.get('reserved_calls')
            result['research_completed_calls'] = studied.get('completed_calls')
            finished_items = studied.get('items', [])
            settled = bool(finished_items) and all(item.get('status') in {'summarized', 'reject', 'rejected'}
                                                   for item in finished_items)
            if not result['summary_count']:
                return _finish(root, base, dict(result,
                    status='research_rejected' if settled else 'research_incomplete', terminal=settled))
            if studied['status'] != 'complete' and not settled:
                return _finish(root, base, dict(result, status='research_incomplete'))
            phase = 'insight'
            insight = (insight_runner or harness.run)(root, context['insight_config_path'], identity)
            result['stages']['insight'] = {'status': insight['status'],
                                           'receipt_path': insight.get('receipt_path')}
            insight_count = insight.get('model_request_count')
            result['insight_model_request_count'] = insight_count
            reserved = studied.get('reserved_calls')
            if type(reserved) is int and type(insight_count) is int:
                result['reserved_model_requests'] = reserved + insight_count
            if insight['status'] in {'complete', 'no_insight'}:
                return _finish(root, base, dict(result, status=insight['status'], terminal=True))
            reason = insight.get('reason')
            rejected = reason == 'accuracy_review_not_passed'
            return _finish(root, base, dict(result, status='insight_rejected' if rejected else 'insight_incomplete',
                                            terminal=rejected, reason=reason))
        except Exception as exc:
            # Never expose raw provider exceptions/private account paths in logs.
            return _finish(root, base, dict(result, status='failed', failed_stage=phase,
                                            failure_type=type(exc).__name__))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    commands = parser.add_subparsers(dest='command', required=True)
    execute = commands.add_parser('run')
    execute.add_argument('--event', choices=('schedule', 'manual'), default='schedule')
    execute.add_argument('--operation', choices=('health', 'collect', 'run', 'catchup'), default='run')
    execute.add_argument('--cycle-id')
    execute.add_argument('--github-output', type=Path)
    args = parser.parse_args(argv)
    try:
        result = run(args.root, args.event, args.operation, args.cycle_id)
        if args.github_output:
            with args.github_output.open('a') as handle:
                for key in ('topic', 'cycle_id', 'status', 'receipt_path'):
                    handle.write('%s=%s\n' % (key, result.get(key) or ''))
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result['status'] in {'skipped', 'healthy', 'complete', 'no_insight', 'no_new', 'collected'} else 1
    except (store.OfflineError, OSError, ValueError) as exc:
        print(json.dumps({'status': 'blocked', 'failure_type': type(exc).__name__, 'model_calls': 0}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
