#!/usr/bin/env python3
"""Run collection -> Research -> SDK Insight on one persistent host.

Only explicit run/collect operations contact sources or models. Scheduling and
configuration are read on this host; Writing is never launched here.
"""

import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import tempfile

import researchdesk_cycle as cycle
import researchdesk_batch as request_budget
import researchdesk_harness as harness
import researchdesk_offline as store
import researchdesk_research as research
import researchdesk_runner as runner
import researchdesk_schedule as schedule
import researchdesk_workbench as workbench


SUCCESS_STATUSES = {'healthy', 'skipped', 'cached', 'complete', 'collected', 'no_new', 'no_insight', 'empty'}


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
    slots = list(schedule.due_slots(config, now))
    return f'{topic}-{slots[-1][0]}' if slots else ''


def _catchup_slot(root, config, topic, now, admission_enabled=False):
    for slot, _ in schedule.due_slots(config, now):
        identity = f'{topic}-{slot}'
        base = _base(topic, identity)
        if not (root / base / 'receipt.yaml').exists():
            return identity
        accepted = store.checked_yaml(root, base + '/receipt.yaml')
        attempts = sorted((root / base / 'attempts').glob('*.yaml'))
        latest = store.checked_yaml(root, attempts[-1].relative_to(root)) if attempts else accepted
        if (latest.get('terminal') is False or admission_enabled
                and latest.get('production_accepted') is not True
                and latest.get('simulation') is not True
                and latest.get('stages', {}).get('insight', {}).get('status') in {'complete', 'no_insight'}):
            return identity
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


def _fingerprint(effective, *, selected_only=True):
    # Only settings used by the pipeline. A Writing preference does not change
    # a frozen research task. Other directions also have separate evidence.
    settings = {key: effective[key] for key in (
        'workbench_id', 'research_topics', 'research', 'insight', 'runtime', 'membership_budget')}
    if selected_only:
        topic = effective['research']['topic']
        catalog = settings['research_topics']
        settings['research_topics'] = {**catalog, 'topics': {topic: catalog['topics'][topic]}}
    return store.digest(settings)


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


def _research_limit_increase(effective, context):
    frozen = context['research_config']['budget']
    current = effective['research']['budget']
    increase = current['research_max_calls'] - frozen['research_max_calls']
    if increase <= 0 or current['max_calls_per_cycle'] != frozen['max_calls_per_cycle'] + increase:
        return None
    original = deepcopy(effective)
    for key in ('research_max_calls', 'max_calls_per_cycle'):
        original['research']['budget'][key] = frozen[key]
    if context['config_fingerprint'] in (_fingerprint(original), _fingerprint(original, selected_only=False)):
        return current['research_max_calls']
    return None


def _model_budget_change(effective, context):
    original = deepcopy(effective)
    research = effective['research']['budget']
    frozen_research = context['research_config']['budget']
    keys = ('max_calls_per_cycle', 'research_max_calls', 'insight_max_calls', 'max_calls_per_item')
    for key in keys:
        if key in frozen_research:
            original['research']['budget'][key] = frozen_research[key]
        else:
            original['research']['budget'].pop(key, None)
    frozen_codex = context['insight_config'].get('codex', {})
    original_codex = original['insight'].get('codex', {})
    task_key = 'max_requests_per_task'
    if task_key in frozen_codex:
        original_codex[task_key] = frozen_codex[task_key]
    else:
        original_codex.pop(task_key, None)
    if context['config_fingerprint'] not in (_fingerprint(original), _fingerprint(original, selected_only=False)):
        return None
    return {
        **{key: research[key] for key in keys if key != 'max_calls_per_item'},
        'max_calls_per_item': research.get('max_calls_per_item', 2 * (research['max_revisions'] + 1)),
        'insight_max_requests_per_task': effective['insight'].get('codex', {}).get(task_key, 100),
    }


def _context(root, effective, topic, identity, base, fingerprint, publisher_context, allow_budget_extension):
    path = root / base / 'context.yaml'
    if path.exists():
        value = store.checked_yaml(root, base + '/context.yaml')
        if value.get('topic') != topic or value.get('cycle_id') != identity:
            raise store.OfflineError('冻结上下文不属于当前研究轮次')
        saved_fingerprint = value.get('config_fingerprint')
        research_limit = None
        model_limits = None
        if saved_fingerprint != fingerprint and saved_fingerprint != _fingerprint(effective, selected_only=False):
            if allow_budget_extension:
                research_limit = _research_limit_increase(effective, value)
                if research_limit is None:
                    model_limits = _model_budget_change(effective, value)
            if research_limit is None and model_limits is None:
                return None
        private = workbench._read(workbench._path(root, 'config/local/automation/' + identity + '/snapshot.yaml'))
        if private.get('config_fingerprint') != saved_fingerprint:
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
        if research_limit is not None:
            request_budget.extend_cycle_research_budget(root, topic, identity, research_limit)
        if model_limits is not None:
            request_budget.extend_cycle_model_budget(root, topic, identity, model_limits)
        return value
    return _freeze(root, effective, topic, identity, base, fingerprint, publisher_context)


def _finish(root, base, result):
    # Attempt records are immutable. A terminal receipt is only created once,
    # so retries never overwrite a checkpoint already saved on GitHub.
    # Use reservations rather than completed phase summaries, including calls
    # whose SDK result was lost. A damaged ledger is never reported as zero.
    result = dict(result)
    try:
        usage = request_budget.cycle_request_usage(root, result['topic'], result['cycle_id'])
        result.update(research_reserved_requests=usage['research'],
                      insight_model_request_count=usage['insight'],
                      reserved_model_requests=usage['total'])
    except store.OfflineError:
        result.update(research_reserved_requests=None, insight_model_request_count=None,
                      reserved_model_requests=None, budget_ledger_status='invalid')
    existing = sorted((root / base / 'attempts').glob('*.yaml'))
    relative = base + '/attempts/%06d.yaml' % (len(existing) + 1)
    result = dict(result, attempt=len(existing) + 1)
    store.save_yaml(root, relative, result)
    if result['terminal'] and not (root / base / 'receipt.yaml').exists():
        relative = base + '/receipt.yaml'
        store.save_yaml(root, relative, result)
    return dict(result, receipt_path=relative)


def _admit(root, effective, result, admitter=None):
    """Promote reviewed real results; no collection or model operation lives here."""
    result = dict(result, production_accepted=False)
    if result.get('simulation') is True:
        return dict(result, admission_status='simulation')
    if effective['admission']['enabled'] is not True:
        return dict(result, admission_status='disabled')
    if admitter is None:
        from researchdesk_insight_admission import admit
        admitter = admit
    accepted = admitter(root, result['topic'], result['cycle_id'])
    if accepted.get('production_accepted') is not True:
        raise store.OfflineError('正式准入未完成')
    result.update(production_accepted=True, admission_status='accepted',
                  admission_receipt_path=accepted['receipt_path'])
    result['stages'] = dict(result['stages'], admission={
        'status': 'accepted', 'receipt_path': accepted['receipt_path']})
    return result


def _cached_result(root, base, effective, admitter=None):
    """Keep the first terminal receipt immutable and surface later admission attempts."""
    initial_path = base + '/receipt.yaml'
    attempts = sorted((root / base / 'attempts').glob('*.yaml'))
    latest_path = attempts[-1].relative_to(root).as_posix() if attempts else initial_path
    if not (root / initial_path).exists():
        initial_path = latest_path
    initial = store.checked_yaml(root, initial_path)
    result = store.checked_yaml(root, latest_path)
    relative = initial_path if result == initial else latest_path
    if result.get('production_accepted') is True:
        if admitter is None:
            from researchdesk_insight_admission import load
            load(root, result['topic'], result['cycle_id'])
        return dict(result, receipt_path=relative, cached=True)
    insight_status = result.get('stages', {}).get('insight', {}).get('status')
    if (effective['admission']['enabled'] is True and result.get('simulation') is not True
            and insight_status in {'complete', 'no_insight'}):
        # Enabling admission after a successful test or retrying failed export
        # must not rerun sources, Research, SDK generation or its review.
        promoted = dict(result, status=insight_status, terminal=True)
        promoted.pop('failure_type', None)
        promoted.pop('failed_stage', None)
        try:
            promoted = _admit(root, effective, promoted, admitter)
        except Exception as exc:
            promoted = dict(result, status='failed', terminal=False, failed_stage='admission',
                            failure_type=type(exc).__name__)
        return _finish(root, base, promoted)
    return dict(result, receipt_path=relative, cached=True)


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


def _empty(topic):
    return {'schema_version': 1, 'topic': topic, 'cycle_id': '', 'status': 'skipped',
            'terminal': False, 'receipt_path': None, 'writing_started': False,
            'publish_authorized': False, 'production_accepted': False, 'model_calls': 0}


def _run_topic(root, effective, identity, operation, publisher_context, collector, researcher,
               insight_runner, health_checker, admitter, allow_budget_extension=False):
    topic = effective['research']['topic']
    empty = _empty(topic)
    if not identity:
        return dict(empty, reason='no_due_slot')
    base = _base(topic, identity)
    attempts = sorted((root / base / 'attempts').glob('*.yaml'))
    admission_only = bool(attempts) and store.checked_yaml(
        root, attempts[-1].relative_to(root)).get('failed_stage') == 'admission'
    if (root / base / 'receipt.yaml').exists() or admission_only:
        return _cached_result(root, base, effective, admitter)
    fingerprint = _fingerprint(effective)
    context = _context(root, effective, topic, identity, base, fingerprint, publisher_context,
                       allow_budget_extension)
    initial = dict(empty, cycle_id=identity, config_fingerprint=fingerprint, stages={},
                   collection_count=0, summary_count=0)
    initial.pop('model_calls', None)
    if context is None:
        return _finish(root, base, dict(initial, status='blocked', reason='configuration_changed'))
    result = dict(initial, config_fingerprint=context['config_fingerprint'], context_path=base + '/context.yaml',
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
        max_revisions = context['research_config']['budget']['max_revisions']
        settled = bool(finished_items) and all(
            item.get('status') in {'summarized', 'reject', 'rejected'}
            or item.get('status') == 'revise' and item.get('revision_count') == max_revisions
            for item in finished_items)
        if not result['summary_count']:
            return _finish(root, base, dict(result,
                status='research_rejected' if settled else 'research_incomplete', terminal=settled))
        if studied['status'] != 'complete' and not settled:
            return _finish(root, base, dict(result, status='research_incomplete'))
        phase = 'insight'
        retry_options = {'retry_failed': True} if operation == 'catchup' else {}
        insight = (insight_runner or harness.run)(root, context['insight_config_path'], identity,
                                                 **retry_options)
        result['simulation'] = insight.get('simulation', False)
        result['stages']['insight'] = {'status': insight['status'],
                                       'receipt_path': insight.get('receipt_path')}
        insight_count = insight.get('model_request_count')
        result['insight_model_request_count'] = insight_count
        reserved = studied.get('reserved_calls')
        if type(reserved) is int and type(insight_count) is int:
            result['reserved_model_requests'] = reserved + insight_count
        if insight['status'] in {'complete', 'no_insight'}:
            phase = 'admission'
            result = _admit(root, effective,
                dict(result, status=insight['status'], terminal=True), admitter)
            return _finish(root, base, result)
        reason = insight.get('reason')
        rejected = reason == 'accuracy_review_not_passed'
        return _finish(root, base, dict(result, status='insight_rejected' if rejected else 'insight_incomplete',
                                        terminal=rejected, reason=reason))
    except Exception as exc:
        # Never expose raw provider exceptions/private account paths in logs.
        return _finish(root, base, dict(result, status='failed', failed_stage=phase,
                                        failure_type=type(exc).__name__))


def run(root, event='schedule', operation='run', cycle_id=None, publisher_context=None,
        collector=None, researcher=None, insight_runner=None, health_checker=None,
        now=None, prepare=None, admitter=None, trigger_cron=None, trigger_timezone=None):
    root = Path(root).resolve()
    if event not in {'schedule', 'manual'} or operation not in {'health', 'collect', 'run', 'catchup'}:
        raise store.OfflineError('自动研究事件或操作无效')
    with pipeline_lock(root):
        if prepare is not None:
            prepare()
        workbench.apply(root)
        effective = workbench.load_effective(root)
        primary = effective['research']['topic']
        automation = effective['automation']
        if event == 'schedule' and automation['enabled'] is not True:
            return dict(_empty(primary), reason='automation_disabled')
        if operation == 'health':
            health = (health_checker or _health)(root, effective)
            return dict(_empty(primary), status='healthy', health=health)
        if event == 'schedule' and trigger_cron:
            expected, zone = automation['schedule_utc'], 'UTC'
            if 'weekly' in automation:
                rule = schedule.weekly(automation)
                expected, zone = schedule.workflow_cron(rule), rule['timezone']
            if (not isinstance(trigger_cron, str) or ' '.join(trigger_cron.split()) != expected
                    or trigger_timezone is not None and trigger_timezone != zone):
                return dict(_empty(primary), reason='schedule_trigger_mismatch')
        clock = now or _now()
        scheduling = _activation(root, automation)

        def execute(identity, selected=None):
            config = effective if selected is None else {
                **effective, 'research': {**effective['research'], 'topic': selected},
                'insight': {**effective['insight'], 'topic': selected},
            }
            return _run_topic(root, config, identity, operation, publisher_context, collector,
                              researcher, insight_runner, health_checker, admitter,
                              allow_budget_extension=bool(cycle_id and event == 'manual'
                                                          and operation in {'run', 'catchup'}))

        directions = (scheduling.get('topics')
                      if event == 'schedule' and operation == 'run' and not cycle_id else None)
        if directions is None or len(directions) == 1:
            identity = cycle_id or (_catchup_slot(root, scheduling, primary, clock,
                                    admission_enabled=effective['admission']['enabled']) if operation == 'catchup' else
                                   _latest_slot(scheduling, primary, clock) if event == 'schedule' else
                                   primary + '-manual-' + clock.strftime('%Y%m%d-%H%M%S'))
            return execute(identity, primary if directions is not None else None)

        results = []
        for topic in directions:
            identity = _latest_slot(scheduling, topic, clock)
            try:
                result = execute(identity, topic)
            except Exception as exc:
                # For example a damaged saved context must not stop other topics.
                result = dict(_empty(topic), cycle_id=identity, status='failed', failed_stage='context',
                              failure_type=type(exc).__name__)
                result.pop('model_calls')
            results.append(result)
        successes = sum(result['status'] in SUCCESS_STATUSES for result in results)
        status = 'complete' if successes == len(results) else 'partial' if successes else 'failed'
        if all(result['status'] == 'skipped' for result in results):
            status = 'skipped'
        result = dict(_empty(primary), status=status, runs=results)
        result.pop('model_calls')
        return result


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
        return 0 if result['status'] in SUCCESS_STATUSES else 1
    except (store.OfflineError, OSError, ValueError) as exc:
        print(json.dumps({'status': 'blocked', 'failure_type': type(exc).__name__, 'model_calls': 0}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
