#!/usr/bin/env python3
"""Explicit, read-only inputs for test-only Insight synthesis.

Only named Research receipts and named historical notes are read. Original
public material is fetched into memory and must match the reviewed evidence;
historical notes retain their human-baseline status. No model or writer lives
in this module.
"""

import json
from pathlib import Path
import re
import tempfile
from uuid import UUID

import researchdesk_offline as store
import researchdesk_batch as batch
import researchdesk_batch_inputs as research_inputs
from researchdesk_sources import SafeFetcher


HASH = re.compile(r'[0-9a-f]{64}\Z')
SOURCE_ID = re.compile(r'(?:paper|blog)-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z')
SOURCE_ID_IN_TEXT = re.compile(r'\b(?:paper|blog)-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b')


def _relative(root, value, name):
    if not isinstance(value, str) or not value:
        raise store.OfflineError(name + ' 必须是明确的相对路径')
    path = Path(value)
    if (path.is_absolute() or '..' in path.parts or '\\' in value
            or path.as_posix() != value or not path.parts):
        raise store.OfflineError(name + ' 禁止越界或非规范路径')
    current = root
    for part in path.parts:
        current /= part
        if current.is_symlink():
            raise store.OfflineError(name + ' 不可包含符号链接')
    if not current.is_file() or not current.resolve().is_relative_to(root):
        raise store.OfflineError(name + ' 文件不存在或不在选定工作台')
    return current


def _receipt_path(root, value, topic):
    path = _relative(root, value, 'Research 回执')
    pattern = r'reports/test/%s/research-batches/[a-z0-9][a-z0-9-]{0,100}/receipt-attempt-[1-9][0-9]*\.yaml' % re.escape(topic)
    if not re.fullmatch(pattern, value):
        raise store.OfflineError('Research 回执必须位于同一主题的 research-batches 测试目录')
    return path


def _history_path(root, value, topic=None):
    path = _relative(root, value, '历史资料')
    parts = Path(value).parts
    allowed = ((len(parts) >= 3 and parts[:2] in {('sources', 'papers'), ('sources', 'blogs')})
               or (len(parts) >= 2 and parts[0] in {'reports', 'insights'}))
    if (not allowed or 'test' in parts or path.suffix != '.md' or path.name == 'README.md'):
        raise store.OfflineError('历史输入仅允许显式登记的正式 source/report/insight Markdown')
    topic_directory = parts[2] if parts[0] == 'sources' and len(parts) > 3 else (
        parts[1] if parts[0] in {'reports', 'insights'} and len(parts) > 2 else None)
    if topic is not None and topic_directory is not None and topic_directory != topic:
        raise store.OfflineError('历史资料不可来自其他研究方向的目录')
    return path


def _topic_context(root, config):
    topics_path = research_inputs.config_path(root, config['topics_file'])
    topics = store.load_yaml(topics_path)
    if (type(topics.get('schema_version')) is not int or topics['schema_version'] != 1
            or not isinstance(topics.get('topics'), dict)):
        raise store.OfflineError('研究方向 YAML 格式无效')
    selected = topics['topics'].get(config['topic'])
    if not isinstance(selected, dict) or selected.get('enabled') is not True:
        raise store.OfflineError('研究方向不存在或已停用')
    for key in ('name', 'description'):
        if not isinstance(selected.get(key), str) or not selected[key].strip():
            raise store.OfflineError('研究方向缺少名称或说明')
    for key in ('scope', 'keywords'):
        value = selected.get(key)
        if (not isinstance(value, list) or not value
                or any(not isinstance(x, str) or not x.strip() for x in value)):
            raise store.OfflineError('研究方向 scope/keywords 必须是非空字符串列表')
    return topics_path, selected


def load_config(root, path):
    root = Path(root).resolve()
    path = research_inputs.config_path(root, path)
    config = store.load_yaml(path)
    research_inputs.fields(config, {'schema_version', 'mode', 'backend', 'topic', 'topics_file',
        'models', 'budget', 'prompts', 'research_inputs', 'historical_inputs'}, 'Insight 配置')
    if type(config['schema_version']) is not int or config['schema_version'] != 1:
        raise store.OfflineError('仅支持 Insight schema_version: 1')
    if config['mode'] != 'insight_test' or config['backend'] != 'chatgpt_plan':
        raise store.OfflineError('Insight 仅支持显式 chatgpt_plan 的 insight_test 模式')
    topic = config['topic']
    if not isinstance(topic, str) or not re.fullmatch(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*', topic) or not store.SAFE_ID.fullmatch(topic):
        raise store.OfflineError('研究主题必须是稳定的小写 ID')
    if not isinstance(config['topics_file'], str) or Path(config['topics_file']).is_absolute():
        raise store.OfflineError('topics_file 必须是 config 下的相对路径')
    topics_path, selected = _topic_context(root, config)
    research_inputs.fields(config['models'], {'generation', 'review'}, 'Insight 模型')
    if any(not isinstance(v, str) or not re.fullmatch(r'[A-Za-z0-9._:/-]{1,200}', v) for v in config['models'].values()):
        raise store.OfflineError('模型必须是明确的目录 slug')
    if config['models']['generation'] == config['models']['review']:
        raise store.OfflineError('Insight 生成与独立审阅须为不同的实际模型')
    ranges = {'max_calls': (2, 4), 'month_max_calls': (2, 1000), 'max_input_chars': (1000, 60000),
              'max_output_chars': (1000, 12000), 'timeout_seconds': (1, 120), 'max_revisions': (0, 1)}
    research_inputs.fields(config['budget'], ranges, 'Insight 预算')
    for name, (low, high) in ranges.items():
        research_inputs.positive(config['budget'][name], low, high, name)
    if config['budget']['max_calls'] > config['budget']['month_max_calls']:
        raise store.OfflineError('Insight 请求上限不可超过月度上限')
    research_inputs.fields(config['prompts'], {'version'}, 'Insight 提示词')
    if config['prompts']['version'] not in {'insight-v1', 'insight-v2'}:
        raise store.OfflineError('未知 Insight 提示词版本')
    if not isinstance(config['research_inputs'], list) or not 1 <= len(config['research_inputs']) <= 4:
        raise store.OfflineError('须明确登记 1–4 个通过审阅的 Research 批次')
    receipts = set()
    for entry in config['research_inputs']:
        research_inputs.fields(entry, {'receipt', 'config', 'item_keys'} if 'item_keys' in entry else {'receipt', 'config'}, 'Research 输入')
        if 'item_keys' in entry and (not isinstance(entry['item_keys'], list) or not entry['item_keys']
                or any(not isinstance(key, str) or not store.SAFE_ID.fullmatch(key) for key in entry['item_keys'])
                or len(set(entry['item_keys'])) != len(entry['item_keys'])):
            raise store.OfflineError('Research 选定单项必须是非空、唯一的稳定ID列表')
        _receipt_path(root, entry['receipt'], topic)
        if (not isinstance(entry['config'], str) or Path(entry['config']).is_absolute()
                or Path(entry['config']).as_posix() != entry['config']):
            raise store.OfflineError('Research 配置必须使用 config 下的规范相对路径')
        research_inputs.config_path(root, entry['config'])
        if entry['receipt'] in receipts:
            raise store.OfflineError('Research 输入回执重复')
        receipts.add(entry['receipt'])
    if not isinstance(config['historical_inputs'], list) or not 1 <= len(config['historical_inputs']) <= 10:
        raise store.OfflineError('须明确登记 1–10 份历史资料，不遍历整个知识库')
    histories = set()
    for entry in config['historical_inputs']:
        research_inputs.fields(entry, {'path', 'sha256', 'origin'}, '历史输入')
        _history_path(root, entry['path'], topic)
        if entry['origin'] != 'human_baseline' or not isinstance(entry['sha256'], str) or not HASH.fullmatch(entry['sha256']):
            raise store.OfflineError('历史输入必须明确标为 human_baseline 并固定 SHA-256')
        if entry['path'] in histories:
            raise store.OfflineError('历史输入重复')
        histories.add(entry['path'])
    config.update(_config_sha256=store.digest(path.read_bytes()), _topics_sha256=store.digest(topics_path.read_bytes()),
        _config_path=path.relative_to(root).as_posix(), _topics_path=topics_path.relative_to(root).as_posix(),
        topic_name=selected['name'], topic_description=selected['description'],
        topic_scope=selected['scope'], topic_keywords=selected['keywords'])
    return config


def _read_events(root, base):
    # Check path ownership before read_events follows checkpoint references.
    directory = store.safe_path(root, base + '/events')
    for path in sorted(directory.glob('*.yaml')):
        event = store.checked_yaml(root, path.relative_to(root))
        for key in ('response_path', 'result_path', 'output'):
            if event.get(key) is not None:
                value = event[key]
                if (not isinstance(value, str) or not value.startswith(base + '/')
                        or '..' in Path(value).parts or '\\' in value or Path(value).as_posix() != value):
                    raise store.OfflineError('Research 检查点不可引用其他批次或主题')
    return store.read_events(root, base)


def _checked_research(root, config, entry):
    receipt_path = _receipt_path(root, entry['receipt'], config['topic'])
    base = receipt_path.parent.relative_to(root).as_posix()
    receipt = store.checked_yaml(root, entry['receipt'])
    manifest_path = base + '/manifest.yaml'
    manifest = store.checked_yaml(root, manifest_path)
    original_config = research_inputs.load_config(root, entry['config'])
    for value in (receipt, manifest, original_config):
        if (value.get('backend') != 'chatgpt_plan' or value.get('mode') != 'research_batch_test'
                or value.get('topic') != config['topic']):
            raise store.OfflineError('Insight 仅接受同主题真实会员 Research 批次')
    auth = manifest.get('authorization', {})
    if (not isinstance(auth, dict) or auth.get('authenticated') is not True or auth.get('plan_permission') is not True
            or auth.get('authorization') != 'official_chatgpt_oauth'
            or not isinstance(auth.get('account_fingerprint'), str) or not auth['account_fingerprint']):
        raise store.OfflineError('Research 缺少已验证的官方会员授权记录')
    if (type(manifest.get('schema_version')) is not int or manifest.get('schema_version') != 1
            or type(receipt.get('schema_version')) is not int or receipt.get('schema_version') != 1
            or manifest.get('production_accepted') is not False or receipt.get('production_accepted') is not False
            or receipt.get('status') not in ({'test_accepted', 'partial'} if 'item_keys' in entry else {'test_accepted'}) or receipt.get('receipt_path') != entry['receipt']
            or receipt.get('batch_id') != Path(base).name or manifest.get('batch_id') != Path(base).name
            or manifest.get('config_sha256') != original_config['_config_sha256']
            or manifest.get('topics_sha256') != original_config['_topics_sha256']
            or original_config['_topics_sha256'] != config['_topics_sha256']
            or manifest.get('models') != original_config['models']
            or receipt.get('models') != manifest.get('models') or receipt.get('authorization') != auth
            or manifest.get('budget') != original_config['budget']
            or manifest.get('prompt_version') != original_config['prompts']['version']):
        raise store.OfflineError('Research 回执、配置、研究方向、授权或模型绑定不一致')
    fingerprint = store.digest({'config': original_config, 'authorization': auth,
        'research_prompt': batch.RESEARCH_INSTRUCTIONS, 'review_prompt': batch.REVIEW_INSTRUCTIONS})
    if manifest.get('fingerprint') != fingerprint:
        raise store.OfflineError('Research 清单未绑定当前可验证的配置与提示词')
    events = _read_events(root, base)
    batch.verify_events(root, base, events, manifest)
    reserved = [event for event in events if event['type'] == 'call_reserved']
    completed = [event for event in events if event['type'] == 'call_completed']
    finished = [event for event in events if event['type'] == 'item_finished']
    expected_keys = [source['id'] for source in original_config['sources']]
    selected_keys = set(entry.get('item_keys', expected_keys))
    if not selected_keys.issubset(expected_keys):
        raise store.OfflineError('选定 Research 单项不属于该批次')
    actual_models = sorted({event['model_id'] for event in completed})
    if (not reserved or ('item_keys' not in entry and len(reserved) != len(completed))
            or receipt.get('reserved_calls') != len(reserved) or receipt.get('completed_calls') != len(completed)
            or receipt.get('actual_models') != actual_models or actual_models != sorted(set(manifest['models'].values()))
            or receipt.get('usage') != [event.get('usage') for event in completed]
            or not isinstance(receipt.get('items'), list) or any(not isinstance(item, dict) for item in receipt['items'])
            or [item.get('key') for item in receipt['items']] != expected_keys
            or (('item_keys' not in entry and len(finished) != len(expected_keys))
                or not selected_keys.issubset({event['key'] for event in finished})
                or not {event['key'] for event in finished}.issubset(expected_keys))):
        raise store.OfflineError('Research 汇总与真实请求及逐项终态不一致')
    for item in receipt['items']:
        key = item['key']
        if key not in selected_keys:
            continue
        result_path = '%s/items/%s/result.yaml' % (base, key)
        result = store.checked_yaml(root, result_path)
        event = next(event for event in finished if event['key'] == key)
        if (event['result_path'] != result_path or result != item or item.get('status') != 'test_accepted'
                or item.get('production_accepted') is not False
                or item.get('report_path') != '%s/items/%s/report.md' % (base, key)):
            raise store.OfflineError('Research 输入包含未通过、重复、待办或不完整单项')
    proof = {'receipt': entry['receipt'], 'receipt_sha256': store.digest(receipt_path.read_bytes()),
        'manifest': manifest_path, 'manifest_sha256': store.digest(store.safe_path(root, manifest_path).read_bytes()),
        'config': original_config['_config_path'], 'config_sha256': original_config['_config_sha256'],
        'topics_sha256': original_config['_topics_sha256'], 'models': manifest['models'],
        'events': [{'path': '%s/events/%06d.yaml' % (base, i + 1),
                    'sha256': store.digest(store.safe_path(root, '%s/events/%06d.yaml' % (base, i + 1)).read_bytes())}
                   for i in range(len(events))]}
    if 'item_keys' in entry:
        proof['item_keys'] = entry['item_keys']
    return base, manifest, original_config, receipt, proof


def _checkpoint_binding(root, base, manifest, config, candidate, material, revision_count):
    previous_research, previous_review = None, None
    context = {'name': config['topic_name'], 'scope': config['topic_scope'], 'keywords': config['topic_keywords']}
    proofs = []
    for revision in range(revision_count + 1):
        common = {'topic': config['topic'], 'research_context': context, 'metadata': candidate['metadata'],
                  'coverage': candidate['evidence']['coverage'], 'original_material': material}
        request = dict(common)
        if revision:
            request.update(previous_research=previous_research, previous_review=previous_review)
        for role, instructions in (('research', batch.RESEARCH_INSTRUCTIONS), ('review', batch.REVIEW_INSTRUCTIONS)):
            if role == 'review':
                request = dict(common, candidate=previous_research)
            path = '%s/items/%s/checkpoints/%s-%s.yaml' % (base, candidate['key'], role, revision)
            checkpoint = store.checked_yaml(root, path)
            binding = store.digest({'manifest': manifest['fingerprint'], 'candidate': candidate,
                'material_sha256': store.digest(material.encode()), 'role': role, 'revision': revision,
                'instructions': instructions, 'input': json.dumps(request, ensure_ascii=False)})
            if checkpoint.get('binding') != binding:
                raise store.OfflineError('Research 模型检查点未绑定该份原文、候选和提示词')
            value = batch.parse_result(checkpoint['result']['text'])
            if role == 'research':
                previous_research = value
            else:
                previous_review = value
            proofs.append({'role': role, 'revision': revision, 'path': path,
                           'sha256': store.digest(store.safe_path(root, path).read_bytes())})
    return previous_research, previous_review, proofs


def _research_evidence(root, config, fetcher):
    evidence, provenance, seen = [], [], set()
    for entry in config['research_inputs']:
        base, manifest, original_config, receipt, proof = _checked_research(root, config, entry)
        for source, item in zip(original_config['sources'], receipt['items']):
            if 'item_keys' in entry and item['key'] not in entry['item_keys']:
                continue
            path = '%s/items/%s/candidate.yaml' % (base, item['key'])
            plan = store.checked_yaml(root, path)
            candidate = plan.get('candidate', {})
            source_id = candidate.get('source_id')
            if (plan.get('action') not in {'research', 'update'}
                    or not isinstance(source_id, str) or not SOURCE_ID.fullmatch(source_id)
                    or source_id != item.get('source_id') or candidate.get('key') != item['key']
                    or candidate.get('topic') != config['topic'] or candidate.get('kind') != source['kind']
                    or not source_id.startswith(source['kind'] + '-')
                    or candidate.get('identity_keys') != store.identities(candidate.get('metadata', {}))):
                raise store.OfflineError('Research 来源身份链无效')
            UUID(source_id.split('-', 1)[1])
            if seen.intersection(candidate['identity_keys']):
                raise store.OfflineError('重复 Research 来源不能冒充独立证据')
            seen.update(candidate['identity_keys'])
            # fetch_candidate normally searches a Vault for note identities. An
            # isolated empty root disables that scan; the reviewed ID is kept.
            with tempfile.TemporaryDirectory(prefix='researchdesk-insight-input-') as empty:
                fresh, material = research_inputs.fetch_candidate(Path(empty), original_config, source, fetcher)
            fields = ('key', 'kind', 'topic', 'metadata', 'evidence', 'identity_keys',
                      'content_hash', 'metadata_hash', 'upstream_updated_at')
            if (any(candidate.get(key) != fresh.get(key) for key in fields)
                    or plan.get('material_sha256') != store.digest(material.encode())
                    or candidate.get('evidence', {}).get('evidence_sha256') != plan.get('material_sha256')
                    or candidate['evidence'].get('content_hash') != candidate.get('content_hash')
                    or candidate['evidence'].get('source_url') != candidate['metadata'].get('source_url')
                    or item.get('coverage') != candidate['evidence'].get('coverage')):
                raise store.OfflineError('原文、版本或证据范围已变化，须先重新 Research 审阅，不能静默更新 Insight 输入')
            research, review, checkpoints = _checkpoint_binding(root, base, manifest, original_config,
                candidate, material, item['revision_count'])
            if store.validate_review(candidate, research, review) != 'pass' or review.get('coverage_acknowledged') is not True:
                raise store.OfflineError('Research 独立审阅未通过或未确认覆盖范围')
            report = store.safe_path(root, item['report_path'])
            if not report.is_file() or store.digest(report.read_bytes()) != item.get('report_sha256'):
                raise store.OfflineError('Research 报告已修改，拒绝沿用旧审阅')
            if report.read_text(encoding='utf-8') != batch.render(manifest, candidate, research, review, item['revision_count']):
                raise store.OfflineError('Research 报告不再对应已审阅的结构化结果')
            identifier = 'R%s' % (len(evidence) + 1)
            source_url = candidate['metadata']['source_url']
            if candidate['kind'] == 'paper' and candidate['metadata'].get('arxiv_id'):
                source_url = 'https://arxiv.org/abs/' + candidate['metadata']['arxiv_id'] + candidate['metadata']['source_version']
            record = {'id': identifier, 'origin': 'reviewed_research', 'path': item['report_path'],
                'sha256': item['report_sha256'], 'source_ids': [source_id], 'source_id': source_id,
                'source_url': source_url, 'source_urls': [source_url], 'coverage': candidate['evidence']['coverage'],
                'identity_keys': candidate['identity_keys'],
                'source_identities': [{'source_id': source_id, 'identity_keys': candidate['identity_keys']}],
                'independently_reviewed': True, 'can_support_original_facts': True,
                'metadata': candidate['metadata'], 'text': report.read_text(encoding='utf-8'),
                'research_summary': research['summary'], 'research_claims': research['claims'],
                'research_limitations': research['limitations'], 'original_material': material,
                'locators': candidate['evidence']['locators']}
            evidence.append(record)
            provenance.append({'id': identifier, **proof, 'path': record['path'], 'sha256': record['sha256'],
                'source_id': source_id, 'source_ids': [source_id], 'source_url': source_url,
                'identity_keys': candidate['identity_keys'],
                'source_identities': [{'source_id': source_id, 'identity_keys': candidate['identity_keys']}],
                'coverage': record['coverage'], 'origin': record['origin'],
                'candidate_path': path, 'candidate_sha256': store.digest(store.safe_path(root, path).read_bytes()),
                'content_sha256': candidate['content_hash'], 'metadata_sha256': candidate['metadata_hash'],
                'evidence_sha256': candidate['evidence']['evidence_sha256'],
                'original_material_sha256': store.digest(material.encode()), 'checkpoints': checkpoints})
    return evidence, provenance


def _historical_evidence(root, config):
    entries, sources = [], {}
    for entry in config['historical_inputs']:
        path = _history_path(root, entry['path'], config['topic'])
        if path.stat().st_size > 100000:
            raise store.OfflineError('历史资料超过单份输入界限')
        payload = path.read_bytes()
        if len(payload) > 100000 or store.digest(payload) != entry['sha256']:
            raise store.OfflineError('历史资料超出界限或与显式登记的 SHA-256 不一致')
        try:
            text = payload.decode('utf-8')
        except UnicodeError as exc:
            raise store.OfflineError('历史资料必须为 UTF-8 Markdown') from exc
        metadata = store.frontmatter(path)
        if Path(entry['path']).parts[0] == 'sources':
            expected_kind = 'paper' if Path(entry['path']).parts[1] == 'papers' else 'blog'
            if (not isinstance(metadata, dict) or metadata.get('kind') != expected_kind
                    or not isinstance(metadata.get('id'), str) or not SOURCE_ID.fullmatch(metadata['id'])
                    or not metadata['id'].startswith(expected_kind + '-') or path.stem != metadata['id']
                    or not isinstance(metadata.get('topics'), list) or config['topic'] not in metadata['topics']):
                raise store.OfflineError('历史来源缺少匹配主题和稳定身份的 Frontmatter')
            store.identities(metadata)
            if metadata['id'] in sources:
                raise store.OfflineError('历史来源稳定 ID 重复')
            sources[metadata['id']] = metadata
        elif not re.search(r'(?:研究主题|主题)\s*[:：]\s*(?:%s|%s)(?:\s|$)' % (
                re.escape(config['topic_name']), re.escape(config['topic'])), text):
            if (not isinstance(metadata, dict) or not isinstance(metadata.get('topics'), list)
                    or config['topic'] not in metadata['topics']):
                raise store.OfflineError('历史报告或洞察未明确属于当前研究主题')
        entries.append((entry, text, metadata))
    evidence, provenance = [], []
    for entry, text, metadata in entries:
        is_source = Path(entry['path']).parts[0] == 'sources'
        source_ids = [metadata['id']] if is_source else sorted(set(SOURCE_ID_IN_TEXT.findall(text)))
        if not source_ids or set(source_ids) - set(sources):
            raise store.OfflineError('历史报告或洞察引用的来源须同时显式登记；不自动打开其他知识库文件')
        urls = sorted({sources[source_id]['source_url'] for source_id in source_ids})
        identifier = 'H%s' % (len(evidence) + 1)
        proof = {'id': identifier, 'origin': 'human_baseline', 'path': entry['path'], 'sha256': entry['sha256'],
                 'source_ids': source_ids, 'source_urls': urls, 'source_url': urls[0] if len(urls) == 1 else None,
                 'identity_keys': sorted({key for source_id in source_ids for key in store.identities(sources[source_id])}),
                 'source_identities': [{'source_id': source_id, 'identity_keys': store.identities(sources[source_id])}
                                       for source_id in source_ids],
                 'coverage': 'historical_note', 'independently_reviewed': False, 'can_support_original_facts': False}
        evidence.append(dict(proof, text=text, historical_status='历史人工基线，含 AI 辅助内容；未经本次独立原文审阅。推断与旧主张均不可升格为新核验事实。'))
        provenance.append(proof)
    return evidence, provenance


HISTORICAL_REFERENCE = re.compile(r'(?<![A-Za-z0-9_])([RH][1-9][0-9]*)(?![A-Za-z0-9_])')


def historical_destinations(text):
    """Protect link bytes, including nested parentheses and reference links."""
    spans = []
    for match in re.finditer(r'^ {0,3}\[[^\]\r\n]+\]:[ \t]*(?:\r?\n[ \t]*)?(<[^>\r\n]*>|[^\s]+)', text, re.MULTILINE):
        spans.append(match.span(1))
    for match in re.finditer(r'\b(?:href|src)\s*=\s*("[^"]*"|\'[^\']*\'|[^\s>]+)', text, re.IGNORECASE):
        spans.append(match.span(1))
    for match in re.finditer(r'\]\(', text):
        start, cursor, depth = match.end(), match.end(), 1
        while cursor < len(text) and depth:
            if text[cursor] == '\\':
                cursor += 2
                continue
            if text[cursor] == '<':
                closing = text.find('>', cursor + 1)
                if closing >= 0:
                    cursor = closing + 1
                    continue
            if text[cursor] == '(':
                depth += 1
            elif text[cursor] == ')':
                depth -= 1
            cursor += 1
        if not depth:
            spans.append((start, cursor - 1))
    # Bare links need balanced parentheses, but must not absorb adjacent prose
    # after a Markdown closing delimiter or Chinese sentence punctuation.
    for match in re.finditer(r'https?://', text):
        start, cursor, depth = match.start(), match.end(), 0
        if any(left <= start < right for left, right in spans):
            continue
        while cursor < len(text):
            char = text[cursor]
            if char.isspace() or char in '<>"\'，。；：！？、':
                break
            if char == '(':
                depth += 1
            elif char == ')':
                if not depth:
                    break
                depth -= 1
            cursor += 1
        spans.append((start, cursor))
    merged = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def scoped_history(record):
    """Namespace document-local aliases only in the model-facing projection.

    Older syntheses retain their own R/H labels. They must never be interpreted
    as labels in today's evidence bundle. Keep URLs/link destinations and the
    original, hash-bound note untouched; retain every other character.
    """
    aliases = set()
    def replace(match):
        alias = match.group(1)
        scoped = 'historical-%s-%s' % (record['id'], alias)
        aliases.add(scoped)
        return scoped
    text, parts, cursor = record['text'], [], 0
    for start, end in historical_destinations(text):
        parts.extend((HISTORICAL_REFERENCE.sub(replace, text[cursor:start]), text[start:end]))
        cursor = end
    parts.append(HISTORICAL_REFERENCE.sub(replace, text[cursor:]))
    return ''.join(parts), sorted(aliases)


def evidence_title(record):
    if record['origin'] == 'reviewed_research':
        return record['metadata']['title']
    heading = re.search(r'^#\s+(.+)$', record['text'], re.MULTILINE)
    return heading.group(1) if heading else Path(record['path']).stem


def model_payload(bundle, prompt_version='insight-v1'):
    """One shared projection for generation, review and input-size preflight.

    Evidence text is never truncated. Research reports duplicate the structured
    claims and original material, so their rendered text and integrity proofs
    stay in the full bundle instead of being sent a second time to the model.
    """
    if prompt_version not in {'insight-v1', 'insight-v2'}:
        raise store.OfflineError('未知 Insight 提示词版本')
    payload = {'topic': bundle['topic'], 'research_context': bundle['research_context'], 'evidence': []}
    if prompt_version == 'insight-v2':
        payload['evidence_index'] = {
            record['id']: dict(title=evidence_title(record), **{
                key: record[key] for key in ('origin', 'coverage', 'source_ids', 'source_urls')})
            for record in bundle['evidence']}
    for record in bundle['evidence']:
        keys = {'id', 'origin', 'path', 'source_ids', 'source_url', 'source_urls', 'coverage', 'historical_status'}
        keys |= ({'metadata', 'research_summary', 'research_claims', 'research_limitations', 'original_material'}
                 if record['origin'] == 'reviewed_research' else {'text'})
        projected = {key: value for key, value in record.items() if key in keys}
        if prompt_version == 'insight-v2' and record['origin'] == 'human_baseline':
            projected['text'], projected['historical_reference_ids'] = scoped_history(record)
        payload['evidence'].append(projected)
    return payload


def prepare_bundle(root, config, fetcher=None):
    root = Path(root).resolve()
    # A caller cannot reuse a stale loaded configuration after an edit.
    fresh = load_config(root, config['_config_path'])
    if fresh != config:
        raise store.OfflineError('Insight 配置或研究方向在准备输入前已变化')
    historical, historical_provenance = _historical_evidence(root, config)
    research, research_provenance = _research_evidence(root, config, fetcher or SafeFetcher(retries=0))
    bundle = {'topic': config['topic'], 'research_context': {'name': config['topic_name'],
        'description': config['topic_description'], 'scope': config['topic_scope'], 'keywords': config['topic_keywords']},
        'evidence': research + historical,
        'provenance': {'research_inputs': research_provenance, 'historical_inputs': historical_provenance}}
    if len(json.dumps(model_payload(bundle, config['prompts']['version']), ensure_ascii=False)) > config['budget']['max_input_chars']:
        raise store.OfflineError('显式登记输入超过字符预算；停止而不截断原文或隐瞒覆盖范围')
    bundle['input_fingerprint'] = store.digest(bundle)
    return bundle
