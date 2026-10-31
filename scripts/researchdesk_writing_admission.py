#!/usr/bin/env python3
"""Create-only, zero-contact admission of three previously reviewed Writing files.

This command does no writing, approval, model discovery or publication. A current
owner instruction authorizes the mechanical promotion; the original page's TEST
scope and every TEST checkpoint remain unchanged. Historical reads grant no new
execution rights and may still show admitted files after a later revocation.
"""

import argparse
import json
from pathlib import Path
import posixpath
import re
import sys
from urllib.parse import urlsplit

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import researchdesk_offline as store
import researchdesk_admission as admission
import researchdesk_batch as shared
import researchdesk_confirmation as confirmation
import researchdesk_confirmation_inputs as previews
import researchdesk_writing_member as writing
import researchdesk_writing_member_inputs as inputs
import researchdesk_writing_job as job


DEFAULT_CONFIG = 'config/writing_admission.yaml'
NOTICE = '> 正式研究稿件：基于页面确认选题生成，三阶段均已通过独立模型审阅；保留事实与推断及证据范围，尚未发布，亦未获得公众号发布授权。'
TRANSFORM = ['assign_distinct_formal_id', 'mark_formal_accepted_unpublished',
             'replace_test_notice', 'relocate_relative_citations_without_changing_targets']
LABELS = {'outline': '正式文章大纲', 'draft': '正式文章初稿', 'candidate': '正式发布候选稿（未发布）'}


def _dump(value):
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False).encode('utf-8')


def _policy_value(value):
    expected = {'schema_version', 'topics', 'confirmation_config', 'output_mode',
                'create_only', 'preserve_test', 'new_model_calls', 'publish_authorized'}
    if (not isinstance(value, dict) or set(value) != expected
            or type(value['schema_version']) is not int or value['schema_version'] != 1
            or value['output_mode'] != 'formal_articles' or value['create_only'] is not True
            or value['preserve_test'] is not True or type(value['new_model_calls']) is not int
            or value['new_model_calls'] != 0 or value['publish_authorized'] is not False
            or not isinstance(value['topics'], list) or not value['topics']
            or len(set(value['topics'])) != len(value['topics'])
            or any(not isinstance(topic, str) or not previews.TOPIC.fullmatch(topic) for topic in value['topics'])
            or not isinstance(value['confirmation_config'], str)):
        raise store.OfflineError('Writing 正式准入仅允许新增保留、零模型调用和不发布策略')
    return value


def _config(root, relative):
    path = admission._location(root, relative)
    if Path(relative).parts[:1] != ('config',) or path.suffix not in {'.yaml', '.yml'}:
        raise store.OfflineError('正式 Writing 准入配置必须在 config 下')
    value = _policy_value(store.load_yaml(path))
    confirmation.load_config(root, value['confirmation_config'])
    return {'path': relative, 'sha256': store.digest(path.read_bytes()),
            'text': path.read_text(encoding='utf-8'), 'value': value}


def _frozen_policy(root, policy):
    if (set(policy) != {'path', 'sha256', 'text', 'value'}
            or Path(policy['path']).parts[:1] != ('config',)
            or not isinstance(policy['text'], str)
            or store.digest(policy['text'].encode('utf-8')) != policy['sha256']
            or yaml.safe_load(policy['text']) != policy['value']):
        raise store.OfflineError('正式 Writing 冻结准入策略已变化')
    admission._location(root, policy['path'])
    _policy_value(policy['value'])
    return policy


def _base(topic, approval_id):
    if (not isinstance(topic, str) or not previews.TOPIC.fullmatch(topic)
            or not isinstance(approval_id, str) or not inputs.APPROVAL.fullmatch(approval_id)):
        raise store.OfflineError('正式 Writing 准入需要有效方向和真实页面确认 ID')
    return 'reports/%s/writing-admissions/%s' % (topic, writing.stable_batch_id(approval_id))


def _proof_paths(root, bundle):
    """Bind exactly the consumed Writing proof, not unrelated later checks."""
    base = 'reports/test/%s/writing-runs/%s' % (bundle['topic'], bundle['batch_id'])
    events = store.read_events(root, base)
    paths = {base + '/' + name for name in ('manifest.yaml', 'receipt.yaml', 'artifact-plan.yaml')}
    for event in events:
        if event['type'] == 'call_completed':
            paths.add(event['response_path'])
        elif event['type'] == 'stage_accepted':
            paths.add(event['result_path'])
    paths |= {path.relative_to(root).as_posix()
              for path in admission._location(root, base + '/events').glob('*.yaml')}
    paths |= {path + '.sha256' for path in paths}
    paths |= {'articles/test/%s/%s/%s.md' % (bundle['topic'], bundle['batch_id'], stage)
              for stage in writing.STAGES}
    return paths


def _historical_bundle(root, bundle):
    """Recheck original evidence and page proof without granting active rights."""
    value = dict(bundle)
    fingerprint = value.pop('input_fingerprint', None)
    if store.digest(value) != fingerprint:
        raise store.OfflineError('准入冻结 Writing 输入已变化')
    config = confirmation.load_config(root, bundle['config']['path'])
    record = admission._checked(root, bundle['confirmation_path'])
    preview = admission._checked(root, bundle['preview_path'])
    payload = preview['payload']
    if (record != bundle['confirmation'] or preview != bundle['preview']
            or record.get('mode') != 'human_topic_confirmation'
            or record.get('origin') != 'local_confirmation_page' or record.get('decision') != 'confirmed'
            or record.get('id') != bundle['approval_id'] or record.get('topic') != bundle['topic']
            or record.get('topic_id') != payload.get('topic_id') or record.get('title') != payload.get('title')
            or record.get('writing_scope') != list(writing.STAGES) or record.get('writing_authorized') is not True
            or record.get('writing_started') is not False or record.get('publish_authorized') is not False
            or record.get('preview_sha256') != store.digest(preview)
            or preview.get('mode') != 'human_topic_preview' or preview.get('workbench_id') != config['workbench_id']
            or payload.get('output_mode') != 'test_only' or payload.get('stages') != list(writing.STAGES)
            or payload.get('approval_required') is not True or payload.get('writing_started') is not False
            or payload.get('publish_authorized') is not False):
        raise store.OfflineError('正式历史稿未绑定原始页面确认')
    fresh = previews.validate_preview(root, config, payload)
    material = inputs._material(fresh)
    expected = {'topic_card': material['topic_card'], 'material': material, 'evidence': material['evidence'],
                'models': fresh['writing']['models'], 'budget': fresh['writing']['budget'],
                'writing': fresh['writing'], 'choices': fresh['choices'], 'insights': fresh['insights'],
                'coverage_note': fresh['coverage_note'], 'questions': fresh['key_questions'],
                'gaps': fresh['evidence_gaps'], 'config': fresh['config']}
    if 'style_profile' in fresh:
        expected['style_profile'] = fresh['style_profile']
    elif 'style_profile' in bundle:
        raise store.OfflineError('正式历史稿不能追加未经原页面确认的写作风格')
    if (any(bundle.get(key) != item for key, item in expected.items())
            or bundle.get('backend') != 'chatgpt_plan' or bundle.get('mode') != 'real_writing_input'
            or bundle.get('output_mode') != 'test_only' or bundle.get('publish_authorized') is not False
            or bundle.get('batch_id') != writing.stable_batch_id(bundle['approval_id'])
            or len(set(bundle['models'].values())) != 2):
        raise store.OfflineError('正式历史稿的证据、模型或确认范围已变化')
    # Resolve the frozen version even for a read-only history check. Unknown
    # profiles must never fall back to the legacy prompts or rendering.
    writing.instructions(bundle, 'writing')
    writing.instructions(bundle, 'review')
    admission._verify_hashes(root, bundle['snapshot']['hashes'])


def _test_proof(root, bundle):
    """Replay local completed responses and independent reviews; no provider."""
    _historical_bundle(root, bundle)
    base = 'reports/test/%s/writing-runs/%s' % (bundle['topic'], bundle['batch_id'])
    manifest = store.checked_yaml(root, base + '/manifest.yaml')
    auth = manifest.get('authorization', {})
    budget = dict(bundle['budget'], month_max_calls=bundle['month_max_calls'])
    fingerprint = store.digest({'input_fingerprint': bundle['input_fingerprint'], 'models': bundle['models'],
        'budget': budget, 'authorization': auth,
        'writing_prompt': writing.instructions(bundle, 'writing'),
        'review_prompt': writing.instructions(bundle, 'review')})
    expected = {'schema_version': 1, 'mode': 'writing_member_test', 'backend': 'chatgpt_plan',
        'topic': bundle['topic'], 'batch_id': bundle['batch_id'], 'approval_id': bundle['approval_id'],
        'fingerprint': fingerprint, 'input_fingerprint': bundle['input_fingerprint'], 'models': bundle['models'],
        'budget': budget, 'authorization': auth, 'confirmation_path': bundle['confirmation_path'],
        'confirmation_sha256': bundle['confirmation_sha256'], 'publish_authorized': False}
    if (set(auth) != {'authenticated', 'plan_permission', 'authorization', 'account_fingerprint'}
            or auth.get('authenticated') is not True or auth.get('plan_permission') is not True
            or auth.get('authorization') != 'official_chatgpt_oauth'
            or not isinstance(auth.get('account_fingerprint'), str) or not auth['account_fingerprint']
            or set(manifest) != set(expected) | {'created_at', 'protected_notes'}
            or any(manifest.get(key) != item for key, item in expected.items())):
        raise store.OfflineError('正式 Writing 缺少原始官方会员及独立模型证明')
    events = store.read_events(root, base)
    if not writing.verify_ledger(root, base, events, manifest, bundle):
        raise store.OfflineError('存在未知 Writing 请求，不能正式准入')
    candidates = job._verify_bindings(root, base, events, manifest, bundle)
    if set(candidates) != set(writing.STAGES):
        raise store.OfflineError('三个阶段没有全部通过独立审阅')
    files = dict(writing.render(stage, candidates[stage], bundle, bundle['batch_id']) for stage in writing.STAGES)
    hashes = {path: store.digest(text.encode()) for path, text in files.items()}
    receipt = store.checked_yaml(root, base + '/receipt.yaml')
    if (receipt.get('status') != 'test_accepted' or receipt.get('production_accepted') is not False
            or receipt.get('publish_authorized') is not False or receipt.get('output_hashes') != hashes
            or receipt.get('models') != bundle['models']
            or receipt.get('actual_models') != sorted(bundle['models'].values())
            or receipt.get('approval_id') != bundle['approval_id']
            or receipt.get('completed_calls') != sum(e['type'] == 'call_completed' for e in events)
            or receipt.get('reserved_calls') != receipt.get('completed_calls')
            or store.checked_yaml(root, base + '/artifact-plan.yaml') != {'files': hashes}):
        raise store.OfflineError('正式 Writing 与原审阅回执或三稿散列不一致')
    admission._verify_hashes(root, hashes)
    return files


def _promote(root, relative, content, topic, batch_id, stage):
    """Keep all model prose byte-identical; only move program-generated links."""
    target = 'articles/%s/%s-%s.md' % (topic, batch_id, stage)
    front, metadata_text, body = content.split('---', 2)
    if front:
        raise store.OfflineError('Writing 产物缺少标准 Frontmatter')
    metadata = yaml.safe_load(metadata_text)
    metadata.update(id='formal-' + batch_id + '-' + stage, status='accepted', production_accepted=True)
    if body.count(writing.NOTICE) != 1:
        raise store.OfflineError('Writing 产物没有唯一原始 TEST 说明')
    body = body.replace(writing.NOTICE, NOTICE, 1)
    def relocate(match):
        destination = match.group(1)
        parsed = urlsplit(destination)
        if parsed.scheme or parsed.netloc or destination.startswith('#'):
            return match.group(0)
        if parsed.query or parsed.fragment or '\\' in destination or destination.startswith('/'):
            raise store.OfflineError('Writing 引用必须是规范相对路径或来源 URL')
        absolute = posixpath.normpath(posixpath.join(posixpath.dirname(relative), destination))
        if 'test' in Path(absolute).parts or not admission._location(root, absolute).is_file():
            raise store.OfflineError('正式 Writing 正文不可指向 TEST 或缺失材料')
        return '](' + posixpath.relpath(absolute, posixpath.dirname(target)) + ')'
    body = re.sub(r'\]\(([^)]+)\)', relocate, body)
    if re.search(r'^> TEST[:：]', body, re.M):
        raise store.OfflineError('正式 Writing 不能保留 TEST 标识')
    return target, '---\n' + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) + '---' + body


def _build(root, bundle, policy, previous=None):
    topic, approval_id, batch = bundle['topic'], bundle['approval_id'], bundle['batch_id']
    if topic not in policy['value']['topics']:
        raise store.OfflineError('研究方向未启用正式 Writing 准入')
    originals = _test_proof(root, bundle)
    files = dict(_promote(root, 'articles/test/%s/%s/%s.md' % (topic, batch, stage),
                          originals['articles/test/%s/%s/%s.md' % (topic, batch, stage)], topic, batch, stage)
                 for stage in writing.STAGES)
    paths = set(bundle['snapshot']['hashes']) | _proof_paths(root, bundle)
    hashes = admission._hashes(root, paths)
    notes = previous['protected_notes'] if previous is not None else shared.notes_snapshot(root)
    source_commit = previous['source_commit'] if previous is not None else inputs._git(root, 'rev-parse', 'HEAD').decode().strip()
    if not isinstance(source_commit, str) or not inputs.COMMIT.fullmatch(source_commit):
        raise store.OfflineError('正式 Writing 计划未绑定有效 Git 基线')
    inputs._git(root, 'merge-base', '--is-ancestor', source_commit, 'refs/remotes/origin/main')
    return {'schema_version': 1, 'mode': 'formal_writing_admission_plan', 'topic': topic,
        'approval_id': approval_id, 'batch_id': batch,
        'created_at': previous['created_at'] if previous is not None else shared.now(),
        'source_commit': source_commit,
        'authorization': 'explicit_owner_instruction_for_deterministic_admission',
        'original_confirmation_scope': 'test_only', 'policy': policy, 'confirmation_path': bundle['confirmation_path'],
        'verification_bundle': bundle, 'input_hashes': hashes, 'protected_notes': notes,
        'transformation': TRANSFORM, 'files': files,
        'output_hashes': {path: store.digest(content.encode()) for path, content in files.items()},
        'production_accepted': True, 'publish_authorized': False, 'new_model_calls': 0}


def _receipt(value):
    path = _base(value['topic'], value['approval_id']) + '/plan.yaml'
    return {'schema_version': 1, 'mode': 'formal_writing_admission', 'topic': value['topic'],
        'approval_id': value['approval_id'], 'batch_id': value['batch_id'], 'status': 'accepted',
        'plan_path': path, 'plan_sha256': store.digest(_dump(value)),
        'confirmation_path': value['confirmation_path'],
        'input_hashes': value['input_hashes'], 'output_hashes': value['output_hashes'],
        'production_accepted': True, 'publish_authorized': False, 'new_model_calls': 0}


def _payloads(value):
    base = _base(value['topic'], value['approval_id'])
    result = {path: content.encode('utf-8') for path, content in value['files'].items()}
    for name, item in (('plan', value), ('accepted', _receipt(value))):
        path = base + '/' + name + '.yaml'
        result[path] = _dump(item)
        result[path + '.sha256'] = (store.digest(result[path]) + '\n').encode()
    return result


def _preflight(root, payloads):
    # Inspect every target, including marker sidecars, before creating anything.
    for relative, payload in payloads.items():
        target = admission._location(root, relative)
        for parent in target.parents:
            if parent == root:
                break
            if parent.exists() and not parent.is_dir():
                raise store.OfflineError('保留已有文件，正式 Writing 目标父目录冲突: ' + relative)
        if target.exists() and (not target.is_file() or target.read_bytes() != payload):
            raise store.OfflineError('保留已有文件，正式 Writing 目标冲突: ' + relative)


def _read_plan(root, topic, approval_id, historical):
    base = _base(topic, approval_id)
    value = admission._checked(root, base + '/plan.yaml')
    bundle = value['verification_bundle']
    if bundle.get('topic') != topic or bundle.get('approval_id') != approval_id:
        raise store.OfflineError('正式 Writing 计划不属于此确认')
    policy = (_frozen_policy(root, value['policy']) if historical
              else _config(root, value['policy']['path']))
    if historical:
        _historical_bundle(root, bundle)
    else:
        fresh = inputs.prepare_bundle(root, approval_id, policy['value']['confirmation_config'])
        if fresh != bundle:
            raise store.OfflineError('当前页面确认或写作证据已变化，不能继续正式准入')
        result = job.verify_result(root, bundle)
        if result['status'] != 'test_accepted' or result.get('unknown_requests') is not False:
            raise store.OfflineError('当前真实 Writing 没有完成三阶段独立审阅')
        inputs._synced_hashes(root, value['input_hashes'])
        shared.verify_notes(root, value['protected_notes'])
    expected = _build(root, bundle, policy, previous=value)
    if value != expected:
        raise store.OfflineError('正式 Writing 计划与原审阅、机械转换或输入散列不同')
    _preflight(root, _payloads(value))
    return value


def verify(root, topic, approval_id, historical=False):
    """Read-only acceptance proof. Historical checks never authorize execution."""
    root = Path(root).resolve()
    value = _read_plan(root, topic, approval_id, historical)
    receipt = admission._checked(root, _base(topic, approval_id) + '/accepted.yaml')
    if receipt != _receipt(value):
        raise store.OfflineError('正式 Writing 准入回执与原始计划不同')
    admission._verify_hashes(root, value['output_hashes'])
    return receipt


def _run(root, approval_id, config_path=DEFAULT_CONFIG, refresh=None, fail_after=None):
    """Promote only an active synchronized approval, without any model contact."""
    root = Path(root).resolve()
    if fail_after not in {None, 'after_plan', 'after_first_output'}:
        raise store.OfflineError('正式 Writing 准入断点无效')
    with admission._lock(root):
        if refresh is not None and refresh() is False:
            raise store.OfflineError('无法刷新页面确认状态，停止正式 Writing 准入')
        policy = _config(root, config_path)
        bundle = inputs.prepare_bundle(root, approval_id, policy['value']['confirmation_config'])
        topic = bundle['topic']
        base = _base(topic, approval_id)
        plan = admission._location(root, base + '/plan.yaml')
        if plan.exists():
            value = _read_plan(root, topic, approval_id, historical=False)
            if value['policy'] != policy:
                raise store.OfflineError('正式 Writing 原准入策略已变化')
        else:
            result = job.verify_result(root, bundle)
            if result['status'] != 'test_accepted' or result.get('unknown_requests') is not False:
                raise store.OfflineError('真实 Writing 三阶段没有全部独立审阅通过')
            value = _build(root, bundle, policy)
            inputs._synced_hashes(root, value['input_hashes'])
        payloads = _payloads(value)
        _preflight(root, payloads)
        cached = admission._location(root, base + '/accepted.yaml').exists()
        if cached:
            return dict(verify(root, topic, approval_id), cached=True)
        # Plan first, final marker last. Exact same-byte files are resumable.
        admission._save(root, base + '/plan.yaml', value)
        if fail_after == 'after_plan':
            raise store.SimulatedInterruption('正式 Writing 计划已保存，可零调用补跑')
        for index, (relative, content) in enumerate(value['files'].items()):
            inputs.assert_active(root, bundle, refresh)
            admission._verify_hashes(root, value['input_hashes'])
            shared.verify_notes(root, value['protected_notes'])
            admission._create(root, relative, content)
            if index == 0 and fail_after == 'after_first_output':
                raise store.SimulatedInterruption('首个正式 Writing 稿已新增，可零调用补跑')
        inputs.assert_active(root, bundle, refresh)
        _read_plan(root, topic, approval_id, historical=False)
        admission._save(root, base + '/accepted.yaml', _receipt(value))
        return dict(verify(root, topic, approval_id), cached=False)


def run(root, approval_id, config_path=DEFAULT_CONFIG, refresh=None, fail_after=None):
    """Admit reviewed Writing, then refresh reader navigation outside its lock."""
    result = _run(root, approval_id, config_path, refresh, fail_after)
    import researchdesk_reading as reading
    reading.refresh(Path(root).resolve())
    return result


def inspect(root, topic, approval_id):
    """Small read-only page view; changed files remain untouched and hidden."""
    root = Path(root).resolve()
    result = {'status': 'not_admitted', 'documents': [], 'production_accepted': False,
              'batch_id': writing.stable_batch_id(approval_id), 'publish_authorized': False, 'new_model_calls': 0}
    try:
        base = _base(topic, approval_id)
        if not admission._location(root, base + '/accepted.yaml').exists():
            return result
        receipt = verify(root, topic, approval_id, historical=True)
        documents = []
        for stage in writing.STAGES:
            path = 'articles/%s/%s-%s.md' % (topic, result['batch_id'], stage)
            documents.append({'stage': stage, 'label': LABELS[stage], 'path': path,
                              'sha256': receipt['output_hashes'][path]})
        return dict(result, status='accepted', production_accepted=True, documents=documents)
    except (store.OfflineError, OSError, ValueError, KeyError, TypeError, RuntimeError):
        return dict(result, status='integrity_changed', reason='正式稿件或准入证明已变化；保留现有文件，暂停展示，不覆盖人工内容。')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['run', 'verify', 'inspect'])
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--approval-id', required=True)
    parser.add_argument('--config', default=DEFAULT_CONFIG)
    parser.add_argument('--topic', default='agent-memory')
    parser.add_argument('--historical', action='store_true')
    parser.add_argument('--fail-after', choices=['after_plan', 'after_first_output'])
    args = parser.parse_args()
    try:
        if args.command == 'run':
            result = run(args.root, args.approval_id, args.config,
                         refresh=lambda: writing.refresh_origin(args.root), fail_after=args.fail_after)
        elif args.command == 'verify':
            result = verify(args.root, args.topic, args.approval_id, args.historical)
        else:
            result = inspect(args.root, args.topic, args.approval_id)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except store.SimulatedInterruption as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except (store.OfflineError, job.JobError, OSError, ValueError, KeyError, TypeError) as exc:
        print('Writing 正式准入停止: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
