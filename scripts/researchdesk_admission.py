#!/usr/bin/env python3
"""Create-only formal admission of a reviewed real Research -> Insight cycle.

The analysis host prepares an immutable plan after public-source verification.
A publisher reuses that plan offline, checks every bound input again, and writes
the accepted marker last. No OAuth client, model request or Git command lives here.
"""

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import fcntl
import json
import os
from pathlib import Path
import posixpath
import re
import sys
import tempfile
from uuid import uuid4

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import researchdesk_offline as store
import researchdesk_batch as research
import researchdesk_insight as insight
import researchdesk_insight_inputs as inputs
import researchdesk_retired as retired


NOTICE = '> AI 自动研究记录，已通过独立模型审阅；阅读范围及证据限制见正文，未复现实验。'
RECOVERY_NOTICE = '程序仅解析完整JSON对象后唯一多余的结束对象括号，原始响应未修改；请同时核对raw_response与candidate。你的审阅JSON除既有五字段外必须增加format_normalization_acknowledged布尔字段；仅当确认唯一变化是尾部多余括号且所有内容保留时为true。未确认、存在语义改变或证据问题不得pass。'


def _location(root, relative):
    if not isinstance(relative, str):
        raise store.OfflineError('准入路径必须为字符串')
    path = Path(relative)
    if (path.is_absolute() or not path.parts
            or '..' in path.parts or '\\' in relative or path.as_posix() != relative):
        raise store.OfflineError('准入路径必须是仓库内规范相对路径')
    current = root
    for part in path.parts:
        current /= part
        if current.is_symlink():
            raise store.OfflineError('准入拒绝符号链接: ' + relative)
    if not current.resolve().is_relative_to(root):
        raise store.OfflineError('准入路径超出工作台')
    return current


def _base(topic, cycle_id):
    if (not isinstance(topic, str) or not re.fullmatch(r'[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*', topic)
            or not isinstance(cycle_id, str) or not store.SAFE_ID.fullmatch(cycle_id)):
        raise store.OfflineError('准入研究方向或轮次ID无效')
    return 'reports/%s/admissions/%s' % (topic, cycle_id)


def _allowed(relative, topic, cycle_id):
    parts = Path(relative).parts
    if (len(parts) == 4 and parts[:3] == ('sources', 'originals', topic)
            and re.fullmatch(r'(?:paper|blog)-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}-[0-9a-f]{64}\.md', parts[3])):
        return True
    if (len(parts) == 4 and parts[:2] in {('sources', 'papers'), ('sources', 'blogs')}
            and parts[2] == topic and parts[3].endswith('.md')):
        return True
    return (len(parts) == 3 and parts[0] in {'reports', 'insights', 'articles'}
            and parts[1] == topic and parts[2].startswith(cycle_id + '-')
            and parts[2].endswith('.md'))


@contextmanager
def _lock(root):
    path = Path(tempfile.gettempdir()) / ('researchdesk-admission-' + store.digest(str(root).encode())[:24] + '.lock')
    fd = os.open(str(path), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise store.OfflineError('另一个正式准入正在执行') from exc
        yield
    finally:
        os.close(fd)


def _create(root, relative, payload):
    target = _location(root, relative)
    payload = payload.encode('utf-8') if isinstance(payload, str) else payload
    if target.exists():
        if not target.is_file() or target.read_bytes() != payload:
            raise store.OfflineError('保留已有文件，准入目标冲突: ' + relative)
        return store.digest(payload)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Recheck parents immediately before the exclusive create.
    _location(root, relative)
    fd = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    with os.fdopen(fd, 'wb') as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    return store.digest(payload)


def _save(root, relative, value):
    payload = yaml.safe_dump(value, allow_unicode=True, sort_keys=False).encode('utf-8')
    sha = _create(root, relative, payload)
    _create(root, relative + '.sha256', sha + '\n')
    return sha


def _checked(root, relative):
    target = _location(root, relative)
    sidecar = _location(root, relative + '.sha256')
    if (not target.is_file() or not sidecar.is_file()
            or sidecar.read_text().strip() != store.digest(target.read_bytes())):
        raise store.OfflineError('准入输入缺失或 SHA-256 不一致: ' + relative)
    return store.load_yaml(target)


def _hashes(root, paths):
    result = {}
    for relative in sorted(set(paths)):
        path = _location(root, relative)
        if path.is_file():
            result[relative] = store.digest(path.read_bytes())
        else:
            previous = retired.missing_hash(root, relative)
            if previous is None:
                raise store.OfflineError('准入所绑定的输入不存在: ' + relative)
            result[relative] = previous
    return result


def _verify_hashes(root, hashes):
    for relative, expected in hashes.items():
        path = _location(root, relative)
        if not path.is_file() and retired.missing_hash(root, relative, expected) is not None:
            continue
        if not path.is_file() or store.digest(path.read_bytes()) != expected:
            raise store.OfflineError('准入所绑定的输入已变化: ' + relative)


def _auth(manifest):
    auth = manifest.get('authorization', {})
    models = manifest.get('models', {})
    if (manifest.get('backend') != 'chatgpt_plan' or auth.get('authenticated') is not True
            or auth.get('plan_permission') is not True or auth.get('authorization') != 'official_chatgpt_oauth'
            or not auth.get('account_fingerprint') or len(set(models.values())) != 2
            or any(not isinstance(x, str) or x.startswith('mock-') for x in models.values())):
        raise store.OfflineError('只有真实官方会员及不同实际模型的独立审阅可准入')


def _insight_proof(root, config, bundle, cycle_id, bind_requests, allow_failure=False):
    base = 'reports/test/%s/insight-runs/%s' % (config['topic'], cycle_id)
    manifest = store.checked_yaml(root, base + '/manifest.yaml')
    receipt = store.checked_yaml(root, base + '/receipt.yaml')
    _auth(manifest)
    generation_instructions, review_instructions = insight.instructions_for(config)
    fingerprint = store.digest({'config': config, 'input_fingerprint': bundle['input_fingerprint'],
        'authorization': manifest['authorization'], 'generation_prompt': generation_instructions,
        'review_prompt': review_instructions})
    if (manifest.get('mode') != 'insight_test' or manifest.get('topic') != config['topic']
            or manifest.get('batch_id') != cycle_id or manifest.get('fingerprint') != fingerprint
            or manifest.get('models') != config['models'] or manifest.get('budget') != config['budget']
            or manifest.get('input_fingerprint') != bundle['input_fingerprint']
            or manifest.get('provenance') != bundle['provenance'] or manifest.get('writing_started') is not False
            or receipt.get('status') not in ({'revise', 'reject', 'blocked'} if allow_failure else {'test_accepted'})
            or receipt.get('backend') != 'chatgpt_plan'
            or receipt.get('topic') != config['topic'] or receipt.get('batch_id') != cycle_id
            or receipt.get('production_accepted') is not False or receipt.get('writing_started') is not False
            or receipt.get('publish_authorized') is not False or receipt.get('approval_required') is not True):
        raise store.OfflineError('Insight 不是当前绑定输入的通过结果')
    events = store.read_events(root, base)
    if not insight.verify_ledger(root, base, events, manifest, bundle, prompt_version=config['prompts']['version']):
        raise store.OfflineError('存在未知真实请求，不得准入')
    completed = [e for e in events if e['type'] == 'call_completed']
    if (receipt.get('reserved_calls') != len(completed) or receipt.get('completed_calls') != len(completed)
            or receipt.get('models') != manifest['models']
            or receipt.get('actual_models') != sorted(set(manifest['models'].values()))
            or receipt.get('usage') != [e.get('usage') for e in completed]):
        raise store.OfflineError('Insight 回执与真实请求账本不一致')
    final_revision = receipt.get('revision_count')
    if type(final_revision) is not int or final_revision not in (0, 1):
        raise store.OfflineError('Insight 修订次数无效')
    model_payload = inputs.model_payload(bundle, config['prompts']['version']) if bind_requests else None
    previous_candidate = previous_review = None
    for revision in range(final_revision + 1):
        generation = store.checked_yaml(root, '%s/checkpoints/generation-%s.yaml' % (base, revision))
        request = dict(model_payload) if bind_requests else None
        if bind_requests and revision:
            request.update(previous_candidate=previous_candidate, previous_review=previous_review)
        def read(role, instructions, payload):
            checkpoint = store.checked_yaml(root, '%s/checkpoints/%s-%s.yaml' % (base, role, revision))
            if bind_requests:
                expected = store.digest({'fingerprint': manifest['fingerprint'], 'role': role, 'revision': revision,
                    'instructions': instructions, 'input': json.dumps(payload, ensure_ascii=False)})
                if checkpoint.get('binding') != expected:
                    raise store.OfflineError('Insight 检查点未绑定同一份原文和候选')
            return checkpoint['result']['text']
        raw = read('generation', generation_instructions, request)
        recovery = {}
        try:
            candidate = insight.parse_response(raw, 'generation')
        except insight.GenerationFormatError as exc:
            if revision == 0:
                if final_revision != 1:
                    raise store.OfflineError('未完成修订的格式错误不得准入')
                previous_candidate = raw
                previous_review = {'decision': 'revise', 'origin': 'deterministic_validation',
                    'issues': [{'reason': str(exc), 'suggestion': '仅返回一个符合约定字段的合法 JSON 对象；修正结束括号及结构，不使用围栏或附加文字。'}]}
                continue
            candidate = insight.normalize_final_object_brace(raw)
            recovery = {'format_recovery': {'operation': 'remove_single_redundant_final_object_brace',
                'raw_response': raw, 'raw_sha256': store.digest(raw.encode()),
                'candidate_sha256': store.digest(candidate), 'notice': RECOVERY_NOTICE}}
        if not insight.validate_candidate(candidate, bundle, prompt_version=config['prompts']['version']):
            raise store.OfflineError('证据不足不能准入')
        review_payload = dict(model_payload, candidate=candidate, **recovery) if bind_requests else None
        review = insight.parse_response(read('review', review_instructions, review_payload), 'review')
        decision = insight.validate_review(candidate, review, bundle, format_recovery=bool(recovery),
                                           allow_deferred_normalization=True)
        if recovery and decision == 'pass' and 'format_normalization_acknowledged' not in review:
            payload = {'stage': 'format_review', 'raw_response': raw, 'candidate': candidate,
                       'operation': recovery['format_recovery']['operation']}
            confirmation = insight.parse_response(read('format_review', insight.FORMAT_REVIEW_INSTRUCTIONS, payload), 'review')
            insight.fields(confirmation, {'decision', 'format_normalization_acknowledged', 'reason'}, '独立格式确认')
            insight.text(confirmation['reason'], '格式确认原因')
            if confirmation['decision'] != 'pass' or confirmation['format_normalization_acknowledged'] is not True:
                raise store.OfflineError('格式恢复没有获得独立确认')
        if revision < final_revision and decision != 'revise':
            raise store.OfflineError('额外修订未得到独立审阅支持')
        previous_candidate, previous_review = candidate, review
    expected_decision = receipt['status'] if allow_failure else 'pass'
    if previous_review is None or previous_review['decision'] != expected_decision:
        raise store.OfflineError('最后一轮独立审阅与所需终态不一致')
    if allow_failure and (receipt.get('output_hashes') or receipt.get('outputs') != {'report': None, 'insights': [], 'topics': []}):
        raise store.OfflineError('失败 Insight 不得已有接受产物')
    expected_roles = {(e['role'], e['revision']) for e in completed}
    allowed = {('generation', n) for n in range(final_revision + 1)}
    allowed |= {('review', n) for n in range(final_revision + 1)
                if any(e['role'] == 'review' and e['revision'] == n for e in completed)}
    if recovery and 'format_normalization_acknowledged' not in previous_review:
        allowed.add(('format_review', final_revision))
    if expected_roles != allowed:
        raise store.OfflineError('存在未消费的额外模型请求')
    return previous_candidate, receipt, manifest, base


def _frontmatter(metadata, body):
    return '---\n' + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) + '---\n\n' + body


def _receipt(root, value):
    base = _base(value['topic'], value['cycle_id'])
    return {'schema_version': 1, 'mode': 'formal_admission', 'topic': value['topic'], 'cycle_id': value['cycle_id'],
        'status': 'accepted', 'production_accepted': True, 'source_id_map': value['source_id_map'],
        'plan_path': base + '/plan.yaml', 'plan_sha256': store.digest(_location(root, base + '/plan.yaml').read_bytes()),
        'input_hashes': value['input_hashes'], 'output_hashes': value['output_hashes'],
        'writing_started': False, 'publish_authorized': False, 'new_model_calls': 0}


def _repair_changes(value):
    changes, contents = {}, {}
    topic, cycle_id = value['topic'], value['cycle_id']
    accepted_path = _base(topic, cycle_id) + '/accepted.yaml'
    for relative, content in value['files'].items():
        parts = Path(relative).parts
        if len(parts) != 4 or parts[:2] not in {('sources', 'papers'), ('sources', 'blogs')} or parts[2] != topic:
            continue
        metadata = yaml.safe_load(content.split('---', 2)[1])
        if metadata.get('id') != Path(relative).stem:
            raise store.OfflineError('来源身份与准入目标不匹配')
        report = metadata.get('related_notes', [None])[0]
        if report not in value['files'] or not str(report).startswith('reports/%s/%s-research-' % (topic, cycle_id)):
            raise store.OfflineError('来源没有绑定原机器研究报告')
        corrected = _source_footer_links(content, relative, report, accepted_path)
        if corrected != content:
            changes[relative] = {'old_sha256': store.digest(content.encode()),
                                 'new_sha256': store.digest(corrected.encode())}
            contents[relative] = corrected
    return changes, contents


def _repair_record(root, value):
    relative = _base(value['topic'], value['cycle_id']) + '/link-repair.yaml'
    if not _location(root, relative).exists():
        return None, {}
    record = _checked(root, relative)
    changes, contents = _repair_changes(value)
    expected_receipt = _receipt(root, value)
    receipt_bytes = yaml.safe_dump(expected_receipt, allow_unicode=True, sort_keys=False).encode()
    expected = {'schema_version': 1, 'mode': 'formal_source_footer_link_repair',
        'topic': value['topic'], 'cycle_id': value['cycle_id'],
        'operation': 'rebase_two_generated_source_footer_links',
        'plan_sha256': expected_receipt['plan_sha256'], 'accepted_sha256': store.digest(receipt_bytes),
        'changes': changes, 'writing_started': False, 'publish_authorized': False}
    if not changes or record != expected:
        raise store.OfflineError('链接纠正记录不等于原计划的纯机械变换')
    accepted_path = _base(value['topic'], value['cycle_id']) + '/accepted.yaml'
    if _location(root, accepted_path).exists():
        if (_checked(root, accepted_path) != expected_receipt
                or store.digest(_location(root, accepted_path).read_bytes()) != record['accepted_sha256']):
            raise store.OfflineError('旧准入回执与链接纠正证明不一致')
    return record, contents


def effective_files(root, value):
    """Validate an append-only repair and return the intended current bytes."""
    root = Path(root).resolve()
    repair_path = _base(value['topic'], value['cycle_id']) + '/link-repair.yaml'
    if _location(root, repair_path).exists():
        # Public plan() may already expose effective bytes. The immutable plan,
        # rather than the projection passed by a caller, proves the repair.
        value = _checked(root, _base(value['topic'], value['cycle_id']) + '/plan.yaml')
    _, corrected = _repair_record(root, value)
    return dict(value['files'], **corrected)


def effective_output_hashes(root, value):
    return {path: store.digest(content.encode()) for path, content in effective_files(root, value).items()}


def _check_links(root, files, accepted_path):
    """Reject broken local Markdown references before formal files are installed."""
    for relative, content in files.items():
        if Path(relative).parts[:2] == ('sources', 'originals'):
            # Extracted original prose/code is not repository navigation.
            # These bytes are independently rebuilt from the bound archive.
            continue
        for target in re.findall(r'\[[^\]]+\]\(([^)\n]+)\)', content):
            if '://' in target or target.startswith(('#', 'mailto:')):
                continue
            target = target.split('#', 1)[0]
            destination = posixpath.normpath(posixpath.join(posixpath.dirname(relative), target))
            if destination == accepted_path or destination in files:
                continue
            path = _location(root, destination)
            parts = Path(destination).parts
            if (not parts or parts[0] not in {'sources', 'reports', 'insights', 'articles'}
                    or not path.is_file() or path.suffix != '.md' or 'test' in parts):
                raise store.OfflineError('正式材料相对链接无效: %s -> %s' % (relative, target))


def repair(root, topic, cycle_id, dry_run=False):
    """Correct only proven generated footer links, guarding old/new SHA bytes."""
    root = Path(root).resolve()
    with _lock(root):
        base = _base(topic, cycle_id)
        value = _checked(root, base + '/plan.yaml')
        _verify_plan(root, value, topic, cycle_id)
        original_receipt = _receipt(root, value)
        if _checked(root, base + '/accepted.yaml') != original_receipt:
            raise store.OfflineError('仅纠正已正式接受且证明未变的机器来源文件')
        changes, contents = _repair_changes(value)
        if not changes:
            return {'status': 'not_needed', 'changes': {}, 'new_model_calls': 0}
        receipt_bytes = yaml.safe_dump(original_receipt, allow_unicode=True, sort_keys=False).encode()
        record = {'schema_version': 1, 'mode': 'formal_source_footer_link_repair',
            'topic': topic, 'cycle_id': cycle_id, 'operation': 'rebase_two_generated_source_footer_links',
            'plan_sha256': original_receipt['plan_sha256'], 'accepted_sha256': store.digest(receipt_bytes),
            'changes': changes, 'writing_started': False, 'publish_authorized': False}
        # Validate every target before persisting the recovery journal.
        for relative, change in changes.items():
            actual = store.digest(_location(root, relative).read_bytes())
            if actual not in {change['old_sha256'], change['new_sha256']}:
                raise store.OfflineError('来源已有人工变化，拒绝链接纠正: ' + relative)
        _check_links(root, dict(value['files'], **contents), base + '/accepted.yaml')
        if dry_run:
            return dict(record, status='planned', new_model_calls=0)
        _save(root, base + '/link-repair.yaml', record)
        for relative, content in contents.items():
            target = _location(root, relative)
            expected = changes[relative]
            if store.digest(target.read_bytes()) == expected['new_sha256']:
                continue
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(dir=str(target.parent), prefix='.researchdesk-link-repair-', delete=False) as handle:
                    temporary = Path(handle.name)
                    os.fchmod(handle.fileno(), target.stat().st_mode & 0o777)
                    handle.write(content.encode())
                    handle.flush()
                    os.fsync(handle.fileno())
                if store.digest(_location(root, relative).read_bytes()) != expected['old_sha256']:
                    raise store.OfflineError('纠正前发现人工修改，停止替换: ' + relative)
                os.replace(str(temporary), str(target))
                temporary = None
            finally:
                if temporary is not None:
                    temporary.unlink()
        _verify_plan(root, value, topic, cycle_id)
        return dict(record, status='repaired', effective_output_hashes=effective_output_hashes(root, value), new_model_calls=0)


def _source_footer_links(content, source_path, report_path, accepted_path, require_old=False):
    """Relocate only the two generated footer links; preserve every other byte."""
    metadata = yaml.safe_load(content.split('---', 2)[1])
    identifier = metadata['id']
    old_source = '正式来源：[%s](%s)。' % (
        identifier, posixpath.relpath(source_path, posixpath.dirname(report_path)))
    new_source = '正式来源：[%s](%s)。' % (
        identifier, posixpath.relpath(source_path, posixpath.dirname(source_path)))
    old_audit = '准入记录：[输入、审阅与输出散列](%s)。' % posixpath.relpath(
        accepted_path, posixpath.dirname(report_path))
    new_audit = '准入记录：[输入、审阅与输出散列](%s)。' % posixpath.relpath(
        accepted_path, posixpath.dirname(source_path))
    if content.count(old_source) == 1 and content.count(old_audit) == 1:
        return content.replace(old_source, new_source).replace(old_audit, new_audit)
    if not require_old and content.count(new_source) == 1 and content.count(new_audit) == 1:
        return content
    raise store.OfflineError('来源脚注不是预期的两条机器链接，拒绝自动纠正')


def _source_card(source, original, source_path, report_path, synthesis_path, accepted_path):
    """A source has one reference card; detailed analysis lives in reports."""
    directory = posixpath.dirname(source_path)
    evidence = original['evidence']
    url = original['metadata']['source_url']
    if original['kind'] == 'paper' and original['metadata'].get('source_version'):
        url = 'https://arxiv.org/abs/' + original['metadata']['arxiv_id'] + original['metadata']['source_version']
    labels = {'full_text': '完整抽取正文', 'excerpt': '节选', 'abstract_only': '摘要'}
    lines = ['# ' + source['title'], '', NOTICE, '', '## 原文与取材记录', '',
             '- [打开原文](%s)。' % url,
             '- 本次分析范围：%s；来源卡不保存原文全文副本。' % labels[evidence['coverage']],
             '- [单篇详细研究](%s) · [本轮综合报告](%s)。' % (
                 posixpath.relpath(report_path, directory), posixpath.relpath(synthesis_path, directory)),
             '', '正式来源：[%s](%s)。' % (source['id'], posixpath.basename(source_path)),
             '准入记录：[输入、审阅与输出散列](%s)。' % posixpath.relpath(accepted_path, directory),
             '', '## 人工笔记', '']
    return _frontmatter(source, '\n'.join(lines))


def _archive_file(root, original, source_id):
    import researchdesk_archive as archive
    _, _, snapshot = archive.load(root, original)
    content = archive.render_markdown(snapshot, formal=True)
    frontmatter, body = content[4:].split('\n---\n', 1)
    metadata = yaml.safe_load(frontmatter)
    metadata['source_id'] = source_id
    content = _frontmatter(metadata, body.lstrip())
    path = archive.relative_path(dict(original, source_id=source_id))
    source_path = 'sources/%s/%s/%s.md' % (
        'papers' if original['kind'] == 'paper' else 'blogs', original['topic'], source_id)
    content += '\n## 关联来源\n\n[来源卡与研究链接](%s)。\n' % posixpath.relpath(source_path, posixpath.dirname(path))
    return path, content


def _render(root, topic, cycle_id, config, bundle, candidate, records, source_map=None):
    from researchdesk_identity import source_index
    index = source_index(root)
    # Keep every reserved UUID, including aliases collapsed for comparison.
    all_ids = {identifier for values in store.source_index(root).values() for identifier in values}
    formal = {}
    for key, values in index.items():
        formal[key] = {identifier: value for identifier, value in values.items()
                       if Path(value[0]).parts[2:3] != ('test',)}
    source_map = dict(source_map or {})
    path_map, sources = {}, {}
    simple = config['prompts']['version'] in {'insight-v5', 'insight-v6'}
    synthesis_path = '%s/%s/%s-synthesis.md' % ('insights' if simple else 'reports', topic, cycle_id)
    accepted_path = _base(topic, cycle_id) + '/accepted.yaml'
    for record in records:
        original = record['candidate']
        old_id = original['source_id']
        matches = {identifier: value for key in original['identity_keys'] for identifier, value in formal.get(key, {}).items()}
        if len(matches) > 1:
            raise store.OfflineError('正式来源身份键冲突，不自动合并')
        if matches:
            aliases = {identifier for key in original['identity_keys'] for identifier in index.get(key, {})} - set(matches)
            if aliases:
                raise store.OfflineError('正式与测试来源存在多个身份ID，须先显式解决冲突')
            identifier, (source_path, metadata) = next(iter(matches.items()))
            if metadata['kind'] != original['kind']:
                raise store.OfflineError('正式来源类型冲突')
            existing = True
        else:
            identifier = source_map.get(old_id, old_id)
            test_matches = {identifier for key in original['identity_keys'] for identifier in index.get(key, {})}
            if len(test_matches) > 1:
                raise store.OfflineError('测试来源存在多个身份ID，须先显式解决冲突')
            if test_matches or identifier in all_ids:
                if not test_matches:
                    raise store.OfflineError('预留UUID已被不同来源占用，不能猜测对应关系')
                identifier = original['kind'] + '-' + str(uuid4())
                while identifier in all_ids:
                    identifier = original['kind'] + '-' + str(uuid4())
                for test_id in test_matches:
                    source_map[test_id] = identifier
            source_path = 'sources/%s/%s/%s.md' % ('papers' if original['kind'] == 'paper' else 'blogs', topic, identifier)
            existing = False
        source_map[old_id] = identifier
        all_ids.add(identifier)
        report_path = 'reports/%s/%s-%s-%s.md' % (topic, cycle_id, 'update' if existing else 'research', identifier)
        path_map[record['report_path']] = report_path
        sources[old_id] = {'id': identifier, 'path': source_path, 'existing': existing, 'report': report_path}
    old_paths, old_contents = insight.render_outputs(root, 'reports/test/%s/insight-runs/%s' % (topic, cycle_id),
                                                   config, cycle_id, candidate, bundle)
    path_map[old_paths['report']] = synthesis_path
    for category in ('insights', 'topics'):
        folder, label = ('insights', 'insight') if category == 'insights' else ('articles', 'topic')
        for number, path in enumerate(old_paths[category], 1):
            path_map[path] = '%s/%s/%s-%s-%s.md' % (folder, topic, cycle_id, label, number)
    id_map = {}
    for old_path, content in old_contents.items():
        metadata = yaml.safe_load(content.split('---', 2)[1])
        id_map[metadata['id']] = 'formal-' + metadata['id']
    files = {}
    for old_path, content in old_contents.items():
        metadata = yaml.safe_load(content.split('---', 2)[1])
        body = content.split('---', 2)[2].lstrip()
        metadata.update(id=id_map[metadata['id']], topics=[topic])
        if simple:
            metadata['source_ids'] = [source_map.get(identifier, identifier)
                                      for identifier in metadata.get('source_ids', [])]
        metadata['status'] = 'proposed' if metadata['kind'] == 'topic_proposal' else 'accepted'
        new_path = path_map[old_path]
        def rebase(match):
            label, target = match.group(1), match.group(2)
            if '://' in target or target.startswith('#'):
                return match.group(0)
            resolved = posixpath.normpath(posixpath.join(posixpath.dirname(old_path), target))
            destination = path_map.get(resolved, resolved)
            if '/test/' in destination or destination.startswith('../'):
                raise store.OfflineError('正式材料不能将测试正文作为研究依据')
            return '[%s](%s)' % (label, posixpath.relpath(destination, posixpath.dirname(new_path)))
        body = re.sub(r'\[([^\]]+)\]\(([^)\n]+)\)', rebase, body)
        body = '\n'.join(NOTICE if line.startswith('> TEST：') else line for line in body.splitlines()
                         if not (simple and line.startswith('> TEST：'))) + '\n'
        for old_id, new_id in {**source_map, **id_map}.items():
            body = body.replace(old_id, new_id)
        if not simple:
            body += '\n## 准入记录\n\n[独立审阅与输入输出散列](%s)。\n' % posixpath.relpath(accepted_path, posixpath.dirname(new_path))
        files[new_path] = _frontmatter(metadata, body)
    collected = datetime.now(timezone(timedelta(hours=8))).date().isoformat()
    for record in records:
        original, result = record['candidate'], record['research']
        target = sources[original['source_id']]
        archive_path = None
        if 'archive' in original:
            archive_path, archive_content = _archive_file(root, original, target['id'])
            files[archive_path] = archive_content
        metadata = {'schema_version': 1, 'id': 'research-%s-%s' % (cycle_id, target['id']),
            'kind': 'research_update' if target['existing'] else 'research_report',
            'title': original['metadata']['title'], 'topic': topic, 'topics': [topic],
            'status': 'accepted', 'source_id': target['id'], 'coverage': original['evidence']['coverage']}
        body = research.render(record['manifest'], original, result, record['review'], record['revision'])
        lines = body.splitlines()
        lines[0] = '# ' + original['metadata']['title']
        lines = [NOTICE if line.startswith('> TEST：') else line for line in lines
                 if not line.startswith('- 资料标识：') and line != '逐项核查、证据摘要与实际用量见同目录检查点及单项回执。'
                 and not (simple and line.startswith('> TEST：'))]
        body = '\n'.join(lines) + '\n'
        if not simple:
            body += '\n正式来源：[%s](%s)。\n' % (target['id'], posixpath.relpath(target['path'], posixpath.dirname(target['report'])))
        if target['existing'] and not simple:
            body += '\n本文件为独立更新或补充研究；原来源笔记、阅读状态与人工关联保持不变。\n'
        if archive_path:
            if simple:
                body += '\n[原始资料](%s)。\n' % posixpath.relpath(archive_path, posixpath.dirname(target['report']))
            else:
                body += '\n原文归档：[本次完整可用抽取正文](%s)；实际研究范围见上文。\n' % posixpath.relpath(archive_path, posixpath.dirname(target['report']))
        if not simple:
            body += '\n准入记录：[输入、审阅与输出散列](%s)。\n' % posixpath.relpath(accepted_path, posixpath.dirname(target['report']))
        files[target['report']] = _frontmatter(metadata, body)
        if not target['existing']:
            source = {'schema_version': 1, 'id': target['id'], 'kind': original['kind'],
                **original['metadata'], 'authors': original['metadata'].get('authors', []),
                'published_at': original['metadata'].get('published_at'), 'collected_at': collected,
                'updated_at': collected, 'topics': [topic], 'status': 'inbox',
                'related_sources': [], 'related_notes': [target['report'], synthesis_path]}
            if config['prompts']['version'] in {'insight-v4', 'insight-v5', 'insight-v6'}:
                files[target['path']] = _source_card(source, original, target['path'], target['report'],
                                                     synthesis_path, accepted_path)
            else:
                source_content = _frontmatter(source, body + '\n## 人工笔记\n\n')
                files[target['path']] = _source_footer_links(
                    source_content, target['path'], target['report'], accepted_path)
            if archive_path:
                files[target['path']] = files[target['path']].replace('\n## 人工笔记',
                    '\n[本地原文快照](%s)。\n\n## 人工笔记' % posixpath.relpath(archive_path, posixpath.dirname(target['path'])), 1)
    return files, source_map


def _verify_source_revalidations(root, value):
    """Validate timestamp-only blog checks without changing reviewed evidence."""
    if 'source_revalidations' not in value:
        return  # Historical immutable plans predate this optional audit.
    records = value['source_revalidations']
    if not isinstance(records, list):
        raise store.OfflineError('来源复核记录必须为列表')
    bound = {proof['candidate_path']: proof['candidate_sha256']
             for proof in value['verification_bundle']['provenance']['research_inputs']}
    fields = {'candidate_path', 'candidate_sha256', 'source_url',
              'reviewed_upstream_updated_at', 'observed_upstream_updated_at',
              'reviewed_metadata_hash', 'observed_metadata_hash', 'content_hash',
              'material_sha256', 'checked_at'}
    seen = set()
    for record in records:
        if not isinstance(record, dict) or set(record) != fields:
            raise store.OfflineError('来源复核记录字段无效')
        path = record['candidate_path']
        if not isinstance(path, str) or path not in bound or path in seen:
            raise store.OfflineError('来源复核记录未绑定本轮唯一候选')
        seen.add(path)
        payload = _checked(root, path)
        candidate = payload['candidate']
        observed = record['observed_upstream_updated_at']
        try:
            checked = datetime.fromisoformat(record['checked_at'].replace('Z', '+00:00'))
            if checked.tzinfo is None:
                raise ValueError('timezone required')
            if observed is not None:
                datetime.fromisoformat(observed.replace('Z', '+00:00'))
        except (AttributeError, TypeError, ValueError) as exc:
            raise store.OfflineError('来源复核时间无效') from exc
        expected = {
            'candidate_path': path, 'candidate_sha256': bound[path],
            'source_url': candidate['metadata']['source_url'],
            'reviewed_upstream_updated_at': candidate.get('upstream_updated_at'),
            'observed_upstream_updated_at': observed,
            'reviewed_metadata_hash': candidate['metadata_hash'],
            'observed_metadata_hash': store.digest({
                'metadata': candidate['metadata'], 'upstream_updated_at': observed}),
            'content_hash': candidate['content_hash'],
            'material_sha256': payload['material_sha256'], 'checked_at': record['checked_at']}
        if (record != expected or candidate.get('kind') != 'blog'
                or record['candidate_sha256'] != store.digest(_location(root, path).read_bytes())
                or observed == candidate.get('upstream_updated_at')
                or candidate['metadata_hash'] != store.digest({
                    'metadata': candidate['metadata'],
                    'upstream_updated_at': candidate.get('upstream_updated_at')})
                or candidate['evidence']['evidence_sha256'] != payload['material_sha256']
                or candidate['evidence']['content_hash'] != candidate['content_hash']):
            raise store.OfflineError('来源复核记录与已审阅候选不一致')


def _verify_plan(root, value, topic, cycle_id):
    if (value.get('schema_version') != 1 or value.get('mode') != 'formal_admission_plan'
            or value.get('topic') != topic or value.get('cycle_id') != cycle_id):
        raise store.OfflineError('准入计划不属于当前轮次')
    _verify_hashes(root, value['input_hashes'])
    _verify_source_revalidations(root, value)
    research.verify_notes(root, value['protected_notes'])
    if set(value['files']) != set(value['output_hashes']):
        raise store.OfflineError('准入文件清单与输出散列集合不同')
    effective = effective_files(root, value)
    for relative, content in value['files'].items():
        if not _allowed(relative, topic, cycle_id) or not isinstance(content, str):
            raise store.OfflineError('准入计划包含未授权目标')
        if store.digest(content.encode()) != value['output_hashes'].get(relative):
            raise store.OfflineError('准入计划正文与输出散列不一致')
        target = _location(root, relative)
        allowed = {content.encode(), effective[relative].encode()}
        if target.exists() and (not target.is_file() or target.read_bytes() not in allowed):
            raise store.OfflineError('人工内容或同名文件冲突，停止覆盖: ' + relative)
    import researchdesk_recovery as recovery
    recovery.verify_if_present(root, topic, cycle_id, bundle=value['verification_bundle'])
    config = inputs.load_config(root, value['insight_config'])
    for entry in config['research_inputs']:
        inputs._checked_research(root, config, entry)
    expected_archives = {}
    for proof in value['verification_bundle']['provenance']['research_inputs']:
        original = store.checked_yaml(root, proof['candidate_path'])['candidate']
        if 'archive' in original:
            path, content = _archive_file(root, original, value['source_id_map'][original['source_id']])
            expected_archives[path] = content
    if expected_archives != {path: content for path, content in value['files'].items()
                             if Path(path).parts[:2] == ('sources', 'originals')}:
        raise store.OfflineError('正式原文与已审阅输入归档不一致')
    candidate, _, _, _ = _insight_proof(root, config, value['verification_bundle'], cycle_id, False)
    if candidate != value['candidate']:
        raise store.OfflineError('最终候选与准入计划不同')
    return value


def _plan(root, topic, cycle_id, fetcher=None):
    base = _base(topic, cycle_id)
    stored_path = base + '/plan.yaml'
    if _location(root, stored_path).exists():
        return _verify_plan(root, _checked(root, stored_path), topic, cycle_id)
    cycle_base = 'reports/test/%s/cycles/%s' % (topic, cycle_id)
    cycle = store.checked_yaml(root, cycle_base + '/receipt.yaml')
    if (cycle.get('mode') != 'research_cycle_test' or cycle.get('backend') != 'chatgpt_plan'
            or cycle.get('topic') != topic or cycle.get('cycle_id') != cycle_id
            or cycle.get('status') not in {'completed', 'partial'}
            or cycle.get('production_accepted') is not False or cycle.get('writing_started') is not False
            or cycle.get('publish_authorized') is not False
            or cycle.get('stages', {}).get('insight', {}).get('status') != 'test_accepted'):
        raise store.OfflineError('轮次没有真实审阅通过的 Research 与 Insight')
    _verify_hashes(root, cycle['input_hashes'])
    _verify_hashes(root, cycle['output_hashes'])
    config_path = cycle_base + '/configs/insight.yaml'
    config = inputs.load_config(root, config_path)
    source_revalidations = []
    bundle = inputs.prepare_bundle(root, config, fetcher=fetcher,
                                   blog_timestamp_revalidations=source_revalidations)
    import researchdesk_recovery as recovery
    recovery.verify_if_present(root, topic, cycle_id, bundle=bundle)
    candidate, receipt, manifest, insight_base = _insight_proof(root, config, bundle, cycle_id, True)
    old_paths, old_contents = insight.render_outputs(root, insight_base, config, cycle_id, candidate, bundle)
    if receipt.get('outputs') != old_paths or receipt.get('output_hashes') != {
            path: store.digest(content.encode()) for path, content in old_contents.items()}:
        raise store.OfflineError('Insight 文件与已审阅候选不一致')
    records = []
    for evidence, proof in zip([e for e in bundle['evidence'] if e['origin'] == 'reviewed_research'],
                               bundle['provenance']['research_inputs']):
        original = store.checked_yaml(root, proof['candidate_path'])['candidate']
        result_path = posixpath.dirname(proof['candidate_path']) + '/result.yaml'
        result = store.checked_yaml(root, result_path)
        research_base = proof['manifest'].rsplit('/', 1)[0]
        research_manifest = store.checked_yaml(root, proof['manifest'])
        _auth(research_manifest)
        research_result = store.checked_yaml(root, '%s/items/%s/checkpoints/research-%s.yaml' % (research_base, original['key'], result['revision_count']))
        review_result = store.checked_yaml(root, '%s/items/%s/checkpoints/review-%s.yaml' % (research_base, original['key'], result['revision_count']))
        records.append({'candidate': original, 'research': research.parse_result(research_result['result']['text']),
            'review': research.parse_result(review_result['result']['text']), 'revision': result['revision_count'],
            'report_path': evidence['path'], 'manifest': research_manifest})
    files, source_map = _render(root, topic, cycle_id, config, bundle, candidate, records)
    paths = set(cycle['input_hashes']) | set(cycle['output_hashes']) | {cycle_base + '/receipt.yaml', config_path}
    for folder in (cycle_base, insight_base):
        paths |= {path.relative_to(root).as_posix() for path in _location(root, folder).rglob('*')
                  if path.is_file() and path.suffix in {'.yaml', '.md'}}
    for proof in bundle['provenance']['research_inputs']:
        folder = proof['manifest'].rsplit('/', 1)[0]
        paths |= {path.relative_to(root).as_posix() for path in _location(root, folder).rglob('*')
                  if path.is_file() and path.suffix in {'.yaml', '.md'}}
    for entry in config['historical_inputs']:
        paths.add(entry['path'])
    lineage = recovery.verify_if_present(root, topic, cycle_id, bundle=bundle)
    if lineage:
        paths |= set(lineage['original_files']) | {lineage['request_path']}
    compact_bundle = {key: bundle[key] for key in ('topic', 'research_context', 'provenance', 'input_fingerprint')}
    compact_bundle['evidence'] = [{key: item for key, item in evidence.items()
        if key not in {'text', 'original_material'}} for evidence in bundle['evidence']]
    value = {'schema_version': 1, 'mode': 'formal_admission_plan', 'topic': topic, 'cycle_id': cycle_id,
        'source_id_map': source_map, 'insight_config': config_path, 'verification_bundle': compact_bundle,
        'candidate': candidate, 'input_hashes': _hashes(root, paths), 'protected_notes': research.notes_snapshot(root),
        'source_revalidations': source_revalidations,
        'files': files, 'output_hashes': {path: store.digest(content.encode()) for path, content in files.items()},
        'writing_started': False, 'publish_authorized': False}
    _verify_plan(root, value, topic, cycle_id)
    _check_links(root, value['files'], base + '/accepted.yaml')
    _save(root, stored_path, value)
    return value


def plan(root, topic, cycle_id, fetcher=None):
    """Return effective writer bytes; persisted plan/receipt hashes stay historical."""
    root = Path(root).resolve()
    with _lock(root):
        value = _plan(root, topic, cycle_id, fetcher=fetcher)
        files = effective_files(root, value)
        hashes = {path: store.digest(content.encode()) for path, content in files.items()}
        return dict(value, files=files, output_hashes=hashes, effective_output_hashes=hashes,
                    historical_output_hashes=value['output_hashes'], is_effective_projection=True)


def run(root, topic, cycle_id, fail_after=None, fetcher=None):
    root = Path(root).resolve()
    if fail_after not in (None, 'after_plan', 'after_first_output'):
        raise store.OfflineError('无效准入断点')
    with _lock(root):
        value = _plan(root, topic, cycle_id, fetcher=fetcher)
        accepted_path = _base(topic, cycle_id) + '/accepted.yaml'
        result = _receipt(root, value)
        files = effective_files(root, value)
        effective_hashes = {path: store.digest(content.encode()) for path, content in files.items()}
        _check_links(root, files, accepted_path)
        if _location(root, accepted_path).exists():
            previous = _checked(root, accepted_path)
            if previous != result:
                raise store.OfflineError('旧准入回执与当前计划不一致')
            for relative, content in files.items():
                target = _location(root, relative)
                if not target.is_file() or target.read_bytes() != content.encode():
                    raise store.OfflineError('正式产物缺失或链接纠正尚未完成；请先运行 repair 恢复: ' + relative)
            return dict(previous, cached=True, effective_output_hashes=effective_hashes)
        if fail_after == 'after_plan':
            raise store.SimulatedInterruption('准入计划已保存，尚未创建正式资料')
        for index, (relative, content) in enumerate(files.items()):
            _verify_hashes(root, value['input_hashes'])
            research.verify_notes(root, value['protected_notes'])
            _create(root, relative, content)
            if index == 0 and fail_after == 'after_first_output':
                raise store.SimulatedInterruption('首个正式文件已创建，补跑复用同SHA内容')
        _verify_plan(root, value, topic, cycle_id)
        _save(root, accepted_path, result)
        return dict(result, effective_output_hashes=effective_hashes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('command', choices=['plan', 'run', 'repair'])
    parser.add_argument('--topic', required=True)
    parser.add_argument('--cycle-id', required=True)
    parser.add_argument('--fail-after', choices=['after_plan', 'after_first_output'])
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'repair':
            result = repair(args.root, args.topic, args.cycle_id, dry_run=args.dry_run)
        else:
            result = plan(args.root, args.topic, args.cycle_id) if args.command == 'plan' else run(
                args.root, args.topic, args.cycle_id, fail_after=args.fail_after)
    except store.SimulatedInterruption as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except (store.OfflineError, OSError, ValueError) as exc:
        print('正式准入停止：' + str(exc), file=sys.stderr)
        return 2
    if args.command == 'plan':
        result = {key: item for key, item in result.items() if key not in {'files', 'verification_bundle', 'candidate', 'protected_notes'}}
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
