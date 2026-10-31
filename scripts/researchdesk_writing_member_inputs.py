"""Read-only admission gate for page-confirmed, membership-backed test Writing.

An approval is never manufactured here. The caller refreshes origin/main before
execution; this module verifies the existing local ref, original confirmation,
formal Research/Insight proof and every frozen input without network access.
"""

import json
import hashlib
from pathlib import Path
import re
import subprocess

import researchdesk_offline as store
import researchdesk_admission as admission
import researchdesk_batch as shared
import researchdesk_confirmation as confirmation
import researchdesk_confirmation_inputs as inputs
import researchdesk_retired as retired


STAGES = ['outline', 'draft', 'candidate']
APPROVAL = re.compile(r'approval-[0-9]{8}-[0-9]{6}-[a-f0-9]{12}\Z')
COMMIT = re.compile(r'(?:[a-f0-9]{40}|[a-f0-9]{64})\Z')


def _git(root, *arguments):
    """Run only explicit, read-only Git commands; never fetch, commit or push."""
    try:
        result = subprocess.run(['git', '-C', str(root), *arguments],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise store.OfflineError('无法核验已同步的 main 写作输入') from exc
    if result.returncode:
        raise store.OfflineError('写作输入必须已提交并同步到 origin/main')
    return result.stdout


def _main(root):
    if _git(root, 'branch', '--show-current').decode().strip() != 'main':
        raise store.OfflineError('真实 Writing 只读取 main 上的人类确认')
    _git(root, 'rev-parse', '--verify', 'refs/remotes/origin/main^{commit}')


def _git_entries(payload, index=False):
    result = {}
    for entry in payload.split(b'\0'):
        if not entry:
            continue
        header, name = entry.split(b'\t', 1)
        mode, middle, last = header.decode('ascii').split()
        path = name.decode('utf-8')
        if path in result:
            raise store.OfflineError('Git 索引存在未解决冲突，停止真实写作')
        result[path] = (mode, middle if index else last, last if index else middle)
    return result


def _synced_hashes(root, hashes):
    """Compare complete frozen inputs with index/main/remote in bounded reads."""
    index = _git_entries(_git(root, 'ls-files', '--stage', '-z'), index=True)
    local = _git_entries(_git(root, 'ls-tree', '-r', '-z', '--full-tree', 'refs/heads/main'))
    remote = _git_entries(_git(root, 'ls-tree', '-r', '-z', '--full-tree', 'refs/remotes/origin/main'))
    algorithm = _git(root, 'rev-parse', '--show-object-format').decode().strip()
    if algorithm not in {'sha1', 'sha256'}:
        raise store.OfflineError('不支持此仓库的 Git 对象格式')
    required, missing = dict(hashes), set()
    for relative, expected in hashes.items():
        target = admission._location(root, relative)
        if not target.is_file() and retired.missing_hash(root, relative, expected) is not None:
            if any(relative in entries for entries in (index, local, remote)):
                raise store.OfflineError('退休笔记删除尚未完整同步到 main: ' + relative)
            missing.add(relative)
            registry = admission._location(root, retired.CONFIG)
            required[retired.CONFIG] = store.digest(registry.read_bytes())
    for relative, expected in sorted(required.items()):
        if relative in missing:
            continue
        target = admission._location(root, relative)
        if not target.is_file():
            raise store.OfflineError('写作冻结输入不存在: ' + relative)
        payload = target.read_bytes()
        if store.digest(payload) != expected:
            raise store.OfflineError('写作冻结输入已变化: ' + relative)
        blob = hashlib.new(algorithm, b'blob ' + str(len(payload)).encode() + b'\0' + payload).hexdigest()
        staged = index.get(relative)
        if (staged is None or staged[0] not in {'100644', '100755'}
                or staged[1] != blob or staged[2] != '0'
                or local.get(relative) != (staged[0], blob, 'blob')
                or remote.get(relative) != (staged[0], blob, 'blob')):
            raise store.OfflineError('写作冻结输入尚未完整同步到 main: ' + relative)


def _synced(root, relative):
    payload = admission._location(root, relative).read_bytes()
    sha = store.digest(payload)
    _synced_hashes(root, {relative: sha})
    return sha


def _base(root, config, approval_id):
    if not isinstance(approval_id, str) or not APPROVAL.fullmatch(approval_id):
        raise store.OfflineError('真实 Writing 只接受页面生成的确认 ID')
    matches = []
    for topic in config['topics']:
        relative = 'reports/%s/writing-approvals/%s' % (topic, approval_id)
        path = admission._location(root, relative + '/confirmed.yaml')
        if path.exists():
            matches.append((topic, relative))
    if len(matches) != 1:
        raise store.OfflineError('未找到唯一、有效研究方向的页面确认')
    return matches[0]


def _revocations(root, base):
    """Fail closed on any local or latest fetched remote cancellation."""
    relative = base + '/revocations'
    folder = admission._location(root, relative)
    if folder.exists():
        if not folder.is_dir():
            raise store.OfflineError('撤回目录无效，不能启动写作')
        # Even a partial or unsynchronized cancellation stops local execution;
        # do not wait for a valid event/checksum pair or ignore unknown files.
        if any(folder.iterdir()):
            raise store.OfflineError('该页面确认已撤回或正在同步撤回，不能继续写作')
    remote = _git(root, 'ls-tree', '-r', '--name-only',
                  'refs/remotes/origin/main', '--', relative).strip()
    if remote:
        raise store.OfflineError('origin/main 已收到撤回，不能继续或重用旧写作结果')


def _record(root, config, approval_id):
    topic, base = _base(root, config, approval_id)
    _revocations(root, base)
    record_path, preview_path = base + '/confirmed.yaml', base + '/preview.yaml'
    record = admission._checked(root, record_path)
    preview = admission._checked(root, preview_path)
    required_record = {'schema_version', 'mode', 'origin', 'id', 'topic', 'topic_id',
                       'title', 'created_at', 'decision', 'preview_sha256',
                       'writing_scope', 'writing_authorized', 'writing_started',
                       'publish_authorized'}
    required_preview = {'schema_version', 'mode', 'workbench_id', 'base_commit', 'payload'}
    if set(record) != required_record or set(preview) != required_preview:
        raise store.OfflineError('写作只接受原始页面确认及冻结预览的完整字段')
    payload = preview.get('payload')
    if not isinstance(payload, dict):
        raise store.OfflineError('页面冻结预览缺少真实选题材料')
    if (type(record['schema_version']) is not int or record['schema_version'] != 1
            or type(preview['schema_version']) is not int or preview['schema_version'] != 1
            or record['mode'] != 'human_topic_confirmation'
            or record['origin'] != 'local_confirmation_page'
            or record['decision'] != 'confirmed' or record['id'] != approval_id
            or record['topic'] != topic or payload.get('topic') != topic
            or record['topic_id'] != payload.get('topic_id')
            or record['title'] != payload.get('title')
            or record['writing_scope'] != STAGES
            or record['writing_authorized'] is not True
            or record['writing_started'] is not False
            or record['publish_authorized'] is not False
            or preview['mode'] != 'human_topic_preview'
            or preview['workbench_id'] != config['workbench_id']
            or record['preview_sha256'] != store.digest(preview)
            or payload.get('stages') != STAGES
            or payload.get('output_mode') != 'test_only'
            or payload.get('approval_required') is not True
            or payload.get('writing_started') is not False
            or payload.get('publish_authorized') is not False):
        raise store.OfflineError('原确认不允许这项真实、仅 test 的三阶段写作')
    if not isinstance(preview['base_commit'], str) or not COMMIT.fullmatch(preview['base_commit']):
        raise store.OfflineError('页面确认没有绑定有效 main 基线')
    _git(root, 'merge-base', '--is-ancestor', preview['base_commit'], 'refs/remotes/origin/main')
    # This invokes the actual cached formal admission verifier. A YAML digest
    # alone cannot turn a fixture or an unreviewed topic into real evidence.
    fresh = inputs.validate_preview(root, config, payload)
    hashes = dict(fresh['snapshot']['hashes'])
    for relative in (record_path, record_path + '.sha256', preview_path, preview_path + '.sha256'):
        hashes[relative] = store.digest(admission._location(root, relative).read_bytes())
    _synced_hashes(root, hashes)
    # Recheck after the proof and Git reads, so cancellation observed during a
    # lengthy proof validation also prevents material being returned.
    _revocations(root, base)
    return topic, base, record, preview, fresh, hashes


def _material(payload):
    evidence = []
    for original in payload['evidence']:
        item = dict(original)
        if (item.get('origin') not in {'reviewed_research', 'human_baseline'}
                or 'test' in Path(item['path']).parts
                or any('test' in Path(path).parts for path in item['source_paths'])
                or item.get('coverage') == 'fixture'
                or re.search(r'^> TEST[:：]', item.get('text', ''), re.M)):
            raise store.OfflineError('真实写作证据不可来自测试或模拟材料')
        # A historical synthesis is useful context, but cannot become an
        # original experimental fact merely because it was stored in Markdown.
        if (item.get('can_support_original_facts') is not True
                or item['origin'] != 'reviewed_research'):
            item['kind'] = 'inference'
        elif item.get('claims') and all(claim.get('kind') == 'author_claim'
                                        for claim in item['claims']):
            item['kind'] = 'author_claim'
        else:
            item['kind'] = 'fact'
        evidence.append(item)
    material = {'topic': payload['topic'], 'topic_card': {
        'id': payload['topic_id'], **payload['choices'],
        'key_questions': payload['key_questions'], 'why_now': payload['why_now'],
        'evidence_gaps': payload['evidence_gaps']},
        'evidence': evidence, 'insights': payload['insights'],
        'coverage_note': payload['coverage_note'],
        'fact_boundary': '只在证据实际覆盖范围内陈述事实。来源作者主张、人工历史推断及本文推断须分别标明；摘要或节选不等于全文复核，未复现实验。'}
    size = len(json.dumps(material, ensure_ascii=False))
    if size > payload['writing']['budget']['max_input_chars']:
        raise store.OfflineError('已确认完整证据超过 Writing 输入预算，不截断或替换证据')
    return material


def prepare_bundle(root, approval_id, config_path='config/confirmation.yaml'):
    """Freeze one original, synchronized page approval without granting one."""
    root = Path(root).resolve()
    _main(root)
    config = confirmation.load_config(root, config_path)
    topic, base, record, preview, payload, hashes = _record(root, config, approval_id)
    topics_path = 'config/research_topics.yaml'
    topics = store.load_yaml(admission._location(root, topics_path))
    selected_topic = topics.get('topics', {}).get(topic)
    if (type(topics.get('schema_version')) is not int or topics['schema_version'] != 1
            or not isinstance(selected_topic, dict) or selected_topic.get('enabled') is not True):
        raise store.OfflineError('已确认的研究方向不存在或当前已停用')
    hashes[topics_path] = _synced(root, topics_path)
    material = _material(payload)
    monthly = shared.membership_monthly_limit(root)
    if monthly is None:
        raise store.OfflineError('真实会员 Writing 必须配置共享月度调用上限')
    policy_path = 'config/membership_budget.yaml'
    hashes[policy_path] = _synced(root, policy_path)
    result = {'schema_version': 1, 'mode': 'real_writing_input', 'backend': 'chatgpt_plan',
        'topic': topic, 'approval_id': approval_id, 'batch_id': 'writing-' + approval_id,
        'topic_card': material['topic_card'], 'choices': payload['choices'],
        'evidence': material['evidence'], 'insights': payload['insights'],
        'questions': payload['key_questions'], 'gaps': payload['evidence_gaps'],
        'coverage_note': payload['coverage_note'], 'writing': payload['writing'],
        'models': payload['writing']['models'], 'budget': payload['writing']['budget'],
        'month_max_calls': monthly, 'stages': STAGES,
        'confirmation': record, 'confirmation_path': base + '/confirmed.yaml',
        'confirmation_sha256': hashes[base + '/confirmed.yaml'],
        'preview': preview, 'preview_path': base + '/preview.yaml',
        'preview_sha256': hashes[base + '/preview.yaml'],
        'config': payload['config'], 'snapshot': {'hashes': dict(sorted(hashes.items())),
            'fingerprint': store.digest(hashes)}, 'material': material,
        'output_mode': 'test_only', 'publish_authorized': False}
    result['input_fingerprint'] = store.digest(result)
    return result


def verify_active(root, bundle):
    """Recheck original confirmation, all evidence and current local ref revokes."""
    if (not isinstance(bundle, dict) or bundle.get('mode') != 'real_writing_input'
            or not isinstance(bundle.get('config'), dict)
            or not isinstance(bundle['config'].get('path'), str)):
        raise store.OfflineError('Writing 输入不是原始真实冻结包')
    expected = dict(bundle)
    fingerprint = expected.pop('input_fingerprint', None)
    if store.digest(expected) != fingerprint:
        raise store.OfflineError('Writing 冻结输入内容已变化')
    fresh = prepare_bundle(root, bundle.get('approval_id'), bundle['config'].get('path'))
    if fresh != bundle:
        raise store.OfflineError('页面确认、配置、证据或共享预算已变化，不能重用旧写作结果')
    return fresh


def assert_active(root, bundle, refresh=None):
    """Optional caller-owned refresh before the pure authorization recheck."""
    if refresh is not None and refresh() is False:
        raise store.OfflineError('远端确认状态刷新未完成，停止真实写作')
    return verify_active(root, bundle)


def eligible(root, config_path='config/confirmation.yaml'):
    """List only valid, synced page confirmations; stale records grant nothing."""
    root = Path(root).resolve()
    _main(root)
    config = confirmation.load_config(root, config_path)
    result, topic_ids = [], set()
    identifiers = set()
    for topic in config['topics']:
        folder = admission._location(root, 'reports/%s/writing-approvals' % topic)
        for path in sorted(folder.glob('*/confirmed.yaml')):
            identifiers.add(path.parent.name)
    for identifier in sorted(identifiers):
        try:
            bundle = prepare_bundle(root, identifier, config_path)
        except (store.OfflineError, OSError, ValueError, KeyError, TypeError):
            continue
        card = bundle['topic_card']
        if card['id'] in topic_ids:
            raise store.OfflineError('同一选题存在多个有效确认，停止自动选择')
        topic_ids.add(card['id'])
        result.append({'id': identifier, 'approval_id': identifier, 'batch_id': bundle['batch_id'],
            'topic': bundle['topic'], 'topic_id': card['id'], 'title': card['title'],
            'created_at': bundle['confirmation']['created_at'],
            'confirmation_path': bundle['confirmation_path'],
            'input_fingerprint': bundle['input_fingerprint']})
    return result
