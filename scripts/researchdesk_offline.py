#!/usr/bin/env python3
"""Fixture-only ResearchDesk runner. No network, real model, Git or production writer."""

import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import date, datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit
from uuid import uuid4

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from workflows.validate import UniqueKeyLoader, canonical_url


class OfflineError(ValueError):
    """Input, integrity or protection gate failed; nothing may bypass this gate."""


class SimulatedInterruption(RuntimeError):
    """Explicit acceptance-test interruption after durable checkpointing."""


NOTICE = '> TEST：离线虚构样例，不可作为正式研究证据。'
SAFE_ID = re.compile(r'[a-z0-9][a-z0-9-]{0,100}\Z')
TERMINAL = {'test_accepted', 'update_proposed', 'rejected', 'blocked', 'duplicate'}


def digest(value):
    if not isinstance(value, bytes):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(value).hexdigest()


def load_yaml(path):
    try:
        value = yaml.load(Path(path).read_text(encoding='utf-8'), Loader=UniqueKeyLoader)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise OfflineError('无法读取 YAML: %s: %s' % (path, exc)) from exc
    if not isinstance(value, dict):
        raise OfflineError('YAML 顶层必须是映射: %s' % path)
    return value


def safe_path(root, relative):
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts or '\\' in str(relative):
        raise OfflineError('拒绝越界路径: %s' % relative)
    parts = path.parts
    allowed = (len(parts) >= 4 and parts[:3] in
               {('sources', 'papers', 'test'), ('sources', 'blogs', 'test')}) or (
                   len(parts) >= 3 and parts[:2] == ('reports', 'test'))
    if not allowed:
        raise OfflineError('离线 writer 只允许来源/回执测试目录: %s' % relative)
    current = root
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise OfflineError('拒绝符号链接: %s' % current)
    if not current.resolve().is_relative_to(root):
        raise OfflineError('输出不在选定仓库内')
    return current


def create(root, relative, content):
    path = safe_path(root, relative)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = content.encode('utf-8') if isinstance(content, str) else content
    if path.exists():
        if path.read_bytes() != payload:
            raise OfflineError('已有文件受保护，不覆盖: %s' % relative)
        return digest(payload)
    try:
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
        with os.fdopen(fd, 'wb') as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise OfflineError('无法独占创建输出: %s' % relative) from exc
    return digest(payload)


def save_yaml(root, relative, value):
    payload = yaml.safe_dump(value, allow_unicode=True, sort_keys=False)
    result = create(root, relative, payload)
    create(root, str(relative) + '.sha256', result + '\n')
    return result


def checked_yaml(root, relative):
    path = safe_path(root, relative)
    marker = safe_path(root, str(relative) + '.sha256')
    if not marker.is_file() or marker.read_text().strip() != digest(path.read_bytes()):
        raise OfflineError('检查点被修改或写入未完成，保留现场: %s' % relative)
    return load_yaml(path)


@contextmanager
def topic_lock(root, topic):
    path = safe_path(root, 'reports/test/%s/.offline.lock' % topic)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise OfflineError('该方向有另一个离线运行，稍后补跑') from exc
        yield
    finally:
        os.close(fd)


def frontmatter(path):
    text = path.read_text(encoding='utf-8')
    if not text.startswith('---\n'):
        return None
    try:
        data = yaml.load(text.split('\n---', 1)[0][4:], Loader=UniqueKeyLoader)
    except yaml.YAMLError as exc:
        raise OfflineError('已有来源 Frontmatter 无效: %s' % path) from exc
    if not isinstance(data, dict):
        raise OfflineError('已有来源 Frontmatter 不是映射: %s' % path)
    return data


def identities(metadata):
    keys = set()
    url = metadata.get('source_url')
    if not isinstance(url, str):
        raise OfflineError('来源缺少 URL')
    try:
        keys.add('url:' + canonical_url(url))
    except ValueError as exc:
        raise OfflineError('来源 URL 无效') from exc
    match = re.search(r'https?://(?:www\.|export\.)?arxiv\.org/(?:abs|pdf|html)/([^?#]+)', url, re.I)
    arxiv_values = [v for v in (metadata.get('arxiv_id'), match.group(1) if match else None) if v]
    normalized_arxiv = set()
    for arxiv in arxiv_values:
        arxiv = re.sub(r'\.pdf$', '', str(arxiv).strip(), flags=re.I)
        arxiv = re.sub(r'v\d+$', '', arxiv, flags=re.I).lower()
        if not re.fullmatch(r'(?:\d{4}\.\d{4,5}|[a-z][a-z0-9.-]*/\d{7})', arxiv):
            raise OfflineError('arXiv 身份无效')
        normalized_arxiv.add(arxiv)
        keys.add('arxiv:' + arxiv)
    if len(normalized_arxiv) > 1:
        raise OfflineError('显式 arXiv ID 与来源 URL 冲突')
    doi_url = unquote(urlsplit(url).path.lstrip('/')) if urlsplit(url).hostname.lower() in {'doi.org', 'dx.doi.org'} else None
    normalized_doi = set()
    for doi in [v for v in (metadata.get('doi'), doi_url) if v]:
        doi = re.sub(r'^(?:doi:\s*|https?://(?:dx\.)?doi\.org/)', '', str(doi).strip(), flags=re.I).lower()
        if not re.fullmatch(r'10\.\d{4,9}/\S+', doi):
            raise OfflineError('DOI 身份无效')
        normalized_doi.add(doi)
        keys.add('doi:' + doi)
    if len(normalized_doi) > 1:
        raise OfflineError('显式 DOI 与来源 URL 冲突')
    return sorted(keys)


def source_index(root):
    index = {}
    for folder in ('papers', 'blogs'):
        for path in sorted((root / 'sources' / folder).rglob('*.md')):
            if path.is_symlink():
                raise OfflineError('来源不可为符号链接')
            data = frontmatter(path)
            if data is None:
                legacy = load_yaml(root / 'config/legacy_sources.yaml').get('files', [])
                if path.relative_to(root).as_posix() not in {x['path'] for x in legacy}:
                    raise OfflineError('非豁免来源缺少 Frontmatter: %s' % path)
                continue
            for key in identities(data):
                index.setdefault(key, {})[data['id']] = (path.relative_to(root).as_posix(), data)
    return index


def protected_snapshot(root):
    result = {}
    for folder in ('sources', 'reports', 'insights', 'articles'):
        for path in (root / folder).rglob('*.md'):
            parts = path.relative_to(root).parts
            # Tests are isolated, but the legacy sources/papers/test.md stays protected.
            is_test = (parts[0] == 'sources' and len(parts) > 3 and parts[2] == 'test') or (
                parts[0] != 'sources' and len(parts) > 2 and parts[1] == 'test')
            if is_test or path.name == 'README.md':
                continue
            if path.is_symlink():
                raise OfflineError('正式资料不可为符号链接')
            result[path.relative_to(root).as_posix()] = digest(path.read_bytes())
    return result


def read_events(root, batch_dir):
    events = []
    parent = safe_path(root, batch_dir + '/events')
    for path in sorted(parent.glob('*.yaml')):
        expected = '%06d.yaml' % (len(events) + 1)
        if path.name != expected:
            raise OfflineError('执行日志序列不连续')
        events.append(checked_yaml(root, path.relative_to(root)))
    for event in events:
        if event['type'] == 'call_completed':
            response = safe_path(root, event['response_path'])
            if not response.is_file() or digest(response.read_bytes()) != event['response_sha256']:
                raise OfflineError('模拟响应检查点被修改')
        if event['type'] == 'item_finished' and event.get('output'):
            output = safe_path(root, event['output'])
            if not output.is_file() or digest(output.read_bytes()) != event['output_sha256']:
                raise OfflineError('已生成产物被人工修改，停止覆盖: %s' % event['output'])
    return events


def append_event(root, batch_dir, events, event):
    save_yaml(root, '%s/events/%06d.yaml' % (batch_dir, len(events) + 1), event)
    events.append(event)


def spend(events):
    reservations = {e['reservation_id']: e['cost_units'] for e in events if e['type'] == 'call_reserved'}
    for event in events:
        if event['type'] == 'call_completed':
            reservations[event['reservation_id']] = event['cost_units']
    return len(reservations), sum(reservations.values())


def monthly_spend(root, topic, month):
    total = 0
    # Batch directory is directly under topic; only directories containing manifest count.
    parent = safe_path(root, 'reports/test/%s' % topic)
    for manifest in sorted(parent.glob('*/manifest.yaml')):
        batch_dir = manifest.parent.relative_to(root).as_posix()
        checked_yaml(root, manifest.relative_to(root))
        events = read_events(root, batch_dir)
        relevant = [e for e in events if e.get('month') == month]
        total += spend(relevant)[1]
    return total


def monthly_limit(root, topic, month, configured):
    relative = 'reports/test/%s/budget-%s.yaml' % (topic, month)
    if safe_path(root, relative).exists():
        policy = checked_yaml(root, relative)
        return min(configured, policy['max_cost_units'])
    save_yaml(root, relative, {'mode': 'offline', 'month': month, 'max_cost_units': configured,
                             'unit': 'virtual_fixture_unit', 'real_api_cost': 0})
    return configured


def validate_fixture(root, fixture):
    if fixture.get('schema_version') != 1 or not fixture.get('fixture_notice'):
        raise OfflineError('必须使用声明虚构的 Schema 1 离线样例')
    models = fixture.get('models', {})
    if set(models) != {'research', 'review'} or any(not isinstance(v, str) or not v.startswith('mock-') for v in models.values()):
        raise OfflineError('只支持 mock-* 模型，无真实模型适配器')
    if models['research'] == models['review']:
        raise OfflineError('研究和审阅必须使用独立模拟模型 ID')
    budget = fixture.get('budget', {})
    required = {'max_calls', 'max_cost_units', 'month_max_cost_units', 'reservation_cost_units'}
    if set(budget) != required or any(type(v) is not int or v <= 0 for v in budget.values()):
        raise OfflineError('预算必须是正整数虚拟单位')
    if budget['max_calls'] > 12:
        raise OfflineError('每批最多 12 次请求尝试')
    candidates = fixture.get('candidates')
    if not isinstance(candidates, list) or not candidates:
        raise OfflineError('需要固定候选样例')
    topics = load_yaml(root / 'config/research_topics.yaml')['topics']
    keys, topic_ids = set(), set()
    for c in candidates:
        key, topic = c.get('key', ''), c.get('topic', '')
        if not isinstance(key, str) or not SAFE_ID.fullmatch(key) or key in keys:
            raise OfflineError('候选 key 无效或重复')
        if not isinstance(topic, str) or not SAFE_ID.fullmatch(topic) or topic not in topics or not topics[topic]['enabled']:
            raise OfflineError('未知或停用研究方向')
        keys.add(key)
        topic_ids.add(topic)
        if c.get('kind') not in {'paper', 'blog'}:
            raise OfflineError('候选类型无效')
        m = c.get('metadata', {})
        allowed = {'title', 'source', 'source_url', 'authors', 'published_at'}
        if c['kind'] == 'paper':
            allowed |= {'arxiv_id', 'doi', 'source_version'}
        if set(m) - allowed:
            raise OfflineError('元数据包含不支持的字段')
        for name in ('title', 'source', 'source_url'):
            if not isinstance(m.get(name), str) or not m[name].strip():
                raise OfflineError('元数据缺少 %s' % name)
        if not isinstance(m.get('authors'), list) or any(not isinstance(x, str) or not x.strip() for x in m['authors']):
            raise OfflineError('作者必须是字符串列表')
        if len(m['authors']) != len(set(m['authors'])):
            raise OfflineError('作者不得重复')
        if m.get('source_version') is not None and (not isinstance(m['source_version'], str) or not m['source_version'].strip()):
            raise OfflineError('source_version 必须为非空字符串或 null')
        if m.get('published_at') is not None:
            try:
                date.fromisoformat(m['published_at'])
            except (ValueError, TypeError) as exc:
                raise OfflineError('发布日期无效') from exc
        identities(m)
        evidence = c.get('evidence', {})
        if evidence.get('coverage') not in {'full_text', 'excerpt', 'abstract_only'} or not isinstance(evidence.get('text'), str):
            raise OfflineError('原始证据/阅读范围无效')
        locators = evidence.get('locators', [])
        if not locators or len({x.get('id') for x in locators}) != len(locators):
            raise OfflineError('证据定位不能为空或重复')
        for locator in locators:
            if not all(isinstance(locator.get(k), str) and locator[k].strip() for k in ('id', 'location', 'quote')) or locator['quote'] not in evidence['text']:
                raise OfflineError('证据摘录不匹配原文')
        for role, field in (('research', 'research'), ('review', 'reviews')):
            if not isinstance(c.get(field), list) or not c[field]:
                raise OfflineError('缺少模拟响应: %s' % field)
    if len(topic_ids) != 1:
        raise OfflineError('一次离线批次只运行一个研究方向')
    return next(iter(topic_ids))


def history(root, topic):
    result = []
    for path in sorted(safe_path(root, 'reports/test/%s' % topic).glob('*/manifest.yaml')):
        manifest = checked_yaml(root, path.relative_to(root))
        events = read_events(root, path.parent.relative_to(root).as_posix())
        states = {e['item_key']: e['status'] for e in events if e['type'] == 'item_finished'}
        for item in manifest['items']:
            calls = sum(e['type'] == 'call_reserved' and e['item_key'] == item['key'] for e in events)
            result.append(dict(item, prior_status=states.get(item['key'], 'pending'), prior_calls=calls))
    return result


def plan(root, fixture, fixture_hash, topic, batch_id):
    index, prior, planned, seen = source_index(root), history(root, topic), [], {}
    deep = 0
    for candidate in fixture['candidates']:
        keys = identities(candidate['metadata'])
        evidence_hash = digest(candidate['evidence'])
        matches = {}
        for key in keys:
            matches.update(index.get(key, {}))
        previous = [p for p in prior if set(keys) & set(p['identity_keys'])]
        known_ids = set(matches) | {p['reserved_id'] for p in previous if p['reserved_id']}
        same_batch = set().union(*(seen.get(k, set()) for k in keys))
        known_ids |= same_batch
        stable_id = next(iter(known_ids)) if len(known_ids) == 1 else None
        item = {'key': candidate['key'], 'identity_keys': keys, 'evidence_sha256': evidence_hash,
                'reserved_id': stable_id, 'action': 'new', 'existing_path': None,
                'target_version': candidate['metadata'].get('source_version')}
        same_evidence = [p for p in previous if p['evidence_sha256'] == evidence_hash
                         and p.get('target_version') == item['target_version']]
        if len(known_ids) > 1:
            item.update(action='blocked', reason='identity_conflict')
        elif same_batch:
            item.update(action='duplicate', reason='same_batch_identity')
        elif stable_id and not stable_id.startswith(candidate['kind'] + '-'):
            item.update(action='blocked', reason='kind_conflict')
        elif any(p['prior_status'] in {'rejected', 'blocked'} for p in same_evidence):
            prior_state = next(p['prior_status'] for p in reversed(same_evidence)
                               if p['prior_status'] in {'rejected', 'blocked'})
            item.update(action=prior_state, reason='same_evidence_terminal')
        elif any(p['prior_status'] in {'test_accepted', 'update_proposed'} for p in same_evidence):
            item.update(action='duplicate', reason='same_evidence_already_processed')
        elif any(p['prior_status'] == 'pending' or
                 (p['prior_status'] == 'deferred' and p['prior_calls'] > 0) for p in previous):
            item.update(action='blocked', reason='resume_original_batch_first')
        elif matches:
            record_id, (existing_path, data) = next(iter(matches.items()))
            item.update(reserved_id=record_id, existing_path=existing_path,
                        existing_sha256=digest((root / existing_path).read_bytes()),
                        existing_version=data.get('source_version'))
            version = candidate['metadata'].get('source_version')
            item['action'] = 'update' if version and version != data.get('source_version') else 'duplicate'
        if not item['reserved_id'] and item['action'] == 'new':
            item['reserved_id'] = candidate['kind'] + '-' + str(uuid4())
        for key in keys:
            seen.setdefault(key, set()).update(known_ids)
            if item['reserved_id']:
                seen[key].add(item['reserved_id'])
        if item['action'] in {'new', 'update'}:
            deep += 1
            if deep > 3:
                item.update(action='deferred', reason='research_quota')
        planned.append(item)
    return {'schema_version': 1, 'mode': 'offline', 'production_accepted': False,
            'batch_id': batch_id, 'topic': topic, 'fixture_sha256': fixture_hash,
            'fixed_date': date.today().isoformat(), 'models': fixture['models'], 'budget': fixture['budget'],
            'protected_files': protected_snapshot(root), 'items': planned}


def validate_research(candidate, response):
    limitations = response.get('limitations')
    if not isinstance(response.get('summary'), str) or not response['summary'].strip() or not isinstance(limitations, list) or not limitations or any(not isinstance(x, str) or not x.strip() for x in limitations):
        raise OfflineError('研究结果缺少摘要或限制')
    locators = {x['id']: x for x in candidate['evidence']['locators']}
    claims = response.get('claims')
    if not isinstance(claims, list) or not claims:
        raise OfflineError('研究结果必须有带证据的主张')
    for claim in claims:
        if not isinstance(claim, dict) or not isinstance(claim.get('text'), str) or not claim['text'].strip() or claim.get('kind') not in {'fact', 'inference', 'author_claim'}:
            raise OfflineError('主张文本或事实/推断标识无效')
        refs = claim.get('evidence_ids')
        if not isinstance(refs, list) or not refs or any(not isinstance(k, str) or k not in locators for k in refs):
            raise OfflineError('主张引用缺失证据')


def validate_review(candidate, research, response):
    decision = response.get('decision')
    if decision not in {'pass', 'revise', 'reject', 'blocked'} or not isinstance(response.get('issues'), list):
        raise OfflineError('审阅结果格式不合法')
    for issue in response['issues']:
        if not isinstance(issue, dict) or issue.get('severity') not in {'info', 'warning', 'blocking', 'critical', 'error'}:
            raise OfflineError('审阅问题的严重程度未知')
        if any(not isinstance(issue.get(k), str) or not issue[k].strip() for k in ('location', 'reason', 'suggestion')):
            raise OfflineError('审阅问题缺少位置、理由或建议')
    if decision == 'pass':
        if any(x.get('severity') in {'blocking', 'critical', 'error'} for x in response['issues']):
            raise OfflineError('带阻塞问题的 pass 无效')
        checks = response.get('checks')
        if not isinstance(checks, list) or any(not isinstance(c, dict) or not isinstance(c.get('evidence_ids'), list) or any(not isinstance(k, str) for k in c['evidence_ids']) for c in checks):
            raise OfflineError('pass 缺少逐项主张核查')
        for i, claim in enumerate(research['claims']):
            matching = [c for c in checks if type(c.get('claim_index')) is int and c['claim_index'] == i]
            if not matching or any(c.get('verdict') != 'supported' for c in matching):
                raise OfflineError('pass 包含未支持或未检查主张')
            if not set(claim['evidence_ids']).issubset(set(matching[0].get('evidence_ids', []))):
                raise OfflineError('审阅核查与主张证据不一致')
    return decision


def render(candidate, item, research, manifest):
    m = candidate['metadata']
    fields = {'schema_version': 1, 'id': item['reserved_id'], 'kind': candidate['kind'],
              'title': m['title'], 'source': m['source'], 'source_url': canonical_url(m['source_url']),
              'authors': m['authors'], 'published_at': m.get('published_at'),
              'collected_at': manifest['fixed_date'], 'updated_at': manifest['fixed_date'],
              'topics': [candidate['topic']], 'status': 'inbox', 'related_sources': [], 'related_notes': []}
    if candidate['kind'] == 'paper':
        keys = identities(m)
        fields.update(arxiv_id=next((k[6:] for k in keys if k.startswith('arxiv:')), None),
                      doi=next((k[4:] for k in keys if k.startswith('doi:')), None), source_version=m.get('source_version'))
    lines = ['---', yaml.safe_dump(fields, allow_unicode=True, sort_keys=False).rstrip(), '---', '', NOTICE, '',
             '# ' + m['title'], '', '## 摘要', '', research['summary'], '',
             '## 关键结论与证据', '', '阅读范围：`%s`；证据散列：`%s`。' % (candidate['evidence']['coverage'], item['evidence_sha256'])]
    evidence = {x['id']: x for x in candidate['evidence']['locators']}
    for claim in research['claims']:
        lines += ['', '- [%s] %s' % (claim['kind'], claim['text'])]
        for key in claim['evidence_ids']:
            loc = evidence[key]
            lines += ['  - %s，%s；[虚构原文](%s)：%s' % (key, loc['location'], m['source_url'], loc['quote'])]
    lines += ['', '## 局限与待验证问题', ''] + ['- ' + str(x) for x in research['limitations']]
    lines += ['', '## 审阅记录', '', '仅通过不同模拟模型的离线审阅，不是真实模型判断或正式入库。',
              '批次：`%s`；研究：`%s`；审阅：`%s`。' % (manifest['batch_id'], manifest['models']['research'], manifest['models']['review']),
              '', '## 人工笔记', '', '## 更新记录', '', '离线验收创建；不修改任何正式资料。', '']
    if item['action'] == 'update':
        lines = [NOTICE, '', '# 独立更新建议（离线模拟）', '',
                 '原记录：`%s`；原路径：`%s`。原文件保留。' % (item['reserved_id'], item['existing_path']),
                 '旧版本：`%s`；建议核查版本：`%s`；旧文件散列：`%s`。' % (
                     item.get('existing_version'), item.get('target_version'), item.get('existing_sha256')), ''] + lines[5:]
    return '\n'.join(lines)


def request(root, batch_dir, events, candidate, role, revision, manifest, binding, fail_after, role_input=None):
    key = candidate['key']
    completed = [e for e in events if e['type'] == 'call_completed' and e['item_key'] == key and e['role'] == role and e['revision'] == revision]
    if completed:
        data = checked_yaml(root, completed[-1]['response_path'])
        if data['binding'] != binding:
            raise OfflineError('候选/证据/基线变化，不能复用审阅')
        return data['response']
    used = [e for e in events if e['type'] == 'call_reserved' and e['item_key'] == key and e['role'] == role]
    calls, cost = spend(events)
    budget = manifest['budget']
    reserve = budget['reservation_cost_units']
    month = datetime.now(timezone.utc).strftime('%Y-%m')
    ceiling = monthly_limit(root, manifest['topic'], month, budget['month_max_cost_units'])
    if len(used) >= 2 or calls >= budget['max_calls'] or cost + reserve > budget['max_cost_units'] or monthly_spend(root, manifest['topic'], month) + reserve > ceiling:
        return None
    reservation = str(uuid4())
    append_event(root, batch_dir, events, {'type': 'call_reserved', 'reservation_id': reservation, 'item_key': key,
                 'role': role, 'revision': revision, 'model_id': manifest['models'][role], 'month': month, 'cost_units': reserve})
    if fail_after == 'after_reservation':
        raise SimulatedInterruption('已持久化预留；模拟请求结果未知，不返还额度')
    responses = candidate['research' if role == 'research' else 'reviews']
    if revision >= len(responses):
        append_event(root, batch_dir, events, {'type': 'call_failed', 'reservation_id': reservation, 'item_key': key,
                     'role': role, 'month': month, 'reason': 'missing_mock_response'})
        return None
    response = deepcopy(responses[revision])
    if response.get('error'):
        append_event(root, batch_dir, events, {'type': 'call_failed', 'reservation_id': reservation, 'item_key': key,
                     'role': role, 'month': month, 'reason': str(response['error'])})
        return None
    if response.get('model_id') != manifest['models'][role] or not response.get('request_id'):
        raise OfflineError('模拟响应身份不符合角色配置，预留额度保守消耗')
    usage = response.get('usage', {})
    if any(type(usage.get(k)) is not int or usage[k] < 0 for k in ('cost_units', 'input_tokens', 'output_tokens')) or usage['cost_units'] > reserve or usage['input_tokens'] > 16000 or usage['output_tokens'] > 2000:
        raise OfflineError('模拟用量无效或超过预留/输入输出上限')
    relative = '%s/checkpoints/%s/%s-%s.yaml' % (batch_dir, key, role, revision)
    # Save the original evidence separately in both role inputs: no shared conversation.
    response_hash = save_yaml(root, relative, {'binding': binding, 'response': response,
                  'input': dict({'role': role, 'original_evidence': candidate['evidence'],
                                 'candidate_sha256': binding.get('candidate_sha256'),
                                 'independent_context': True}, **(role_input or {}))})
    append_event(root, batch_dir, events, {'type': 'call_completed', 'reservation_id': reservation, 'item_key': key,
                 'role': role, 'revision': revision, 'month': month, 'cost_units': usage['cost_units'],
                 'response_path': relative, 'response_sha256': response_hash})
    return response


def run(root, fixture_path, batch_id, fail_after=None):
    root, fixture_path = Path(root).resolve(), Path(fixture_path).resolve()
    if not isinstance(batch_id, str) or not SAFE_ID.fullmatch(batch_id):
        raise OfflineError('批次 ID 只允许小写字母、数字和连字符')
    if fail_after not in {None, 'after_review', 'after_reservation'}:
        raise OfflineError('未知故障注入点')
    fixture = load_yaml(fixture_path)
    fixture_hash = digest(fixture_path.read_bytes())
    topic = validate_fixture(root, fixture)
    # Validate all fixed write roots before creating anything.
    for relative in ('sources/papers/test/%s' % topic, 'sources/blogs/test/%s' % topic, 'reports/test/%s' % topic):
        safe_path(root, relative)
    with topic_lock(root, topic):
        batch_dir = 'reports/test/%s/%s' % (topic, batch_id)
        manifest_path = batch_dir + '/manifest.yaml'
        if safe_path(root, manifest_path).exists():
            manifest = checked_yaml(root, manifest_path)
            if manifest['fixture_sha256'] != fixture_hash:
                raise OfflineError('原批次样例/证据/模型响应已变化，保留旧检查点')
            if manifest['protected_files'] != protected_snapshot(root):
                raise OfflineError('正式资料基线已变化，保留笔记并停止旧批次')
        else:
            manifest = plan(root, fixture, fixture_hash, topic, batch_id)
            save_yaml(root, manifest_path, manifest)
        events = read_events(root, batch_dir)
        by_key = {c['key']: c for c in fixture['candidates']}
        for item in manifest['items']:
            key = item['key']
            finished = [e for e in events if e['type'] == 'item_finished' and e['item_key'] == key]
            if finished and finished[-1]['status'] in TERMINAL:
                continue
            action = item['action']
            if action not in {'new', 'update'}:
                append_event(root, batch_dir, events, {'type': 'item_finished', 'item_key': key,
                             'status': action, 'reason': item.get('reason', action)})
                continue
            c = by_key[key]
            status = 'deferred'
            output = None
            feedback = None
            for revision in range(2):
                binding = {'evidence_sha256': item['evidence_sha256'], 'baseline_sha256': digest(manifest['protected_files']), 'revision': revision}
                research = request(root, batch_dir, events, c, 'research', revision, manifest, binding, fail_after,
                                   {'metadata': c['metadata'], 'revision_feedback': feedback})
                if research is None:
                    break
                try:
                    validate_research(c, research)
                    note = render(c, item, research, manifest)
                    review_binding = dict(binding, candidate_sha256=digest(note.encode()))
                    review = request(root, batch_dir, events, c, 'review', revision, manifest, review_binding, fail_after,
                                     {'candidate': {'metadata': c['metadata'], 'research': research, 'markdown': note}})
                    if review is None:
                        break
                    decision = validate_review(c, research, review)
                except OfflineError as exc:
                    status = 'blocked'
                    append_event(root, batch_dir, events, {'type': 'gate_failed', 'item_key': key, 'reason': str(exc)})
                    break
                if fail_after == 'after_review':
                    raise SimulatedInterruption('审阅已保存；模拟发布前中断')
                if decision == 'revise' and revision == 0:
                    feedback = {'previous_research': research, 'review': review}
                    continue
                if decision != 'pass':
                    status = 'rejected' if decision in {'reject', 'revise'} else 'blocked'
                    break
                output = (batch_dir + '/updates/' + item['reserved_id'] + '.md') if action == 'update' else (
                    'sources/%s/test/%s/%s.md' % ('papers' if c['kind'] == 'paper' else 'blogs', topic, item['reserved_id']))
                # Recheck all original notes immediately before the create-only gate.
                if manifest['protected_files'] != protected_snapshot(root):
                    raise OfflineError('写入前正式资料基线变化')
                output_hash = create(root, output, note)
                status = 'update_proposed' if action == 'update' else 'test_accepted'
                append_event(root, batch_dir, events, {'type': 'item_finished', 'item_key': key, 'status': status,
                             'output': output, 'output_sha256': output_hash, 'revision': revision})
                break
            if output is None:
                append_event(root, batch_dir, events, {'type': 'item_finished', 'item_key': key, 'status': status})
        states = {e['item_key']: e for e in events if e['type'] == 'item_finished'}
        counts = {s: 0 for s in ('test_accepted', 'duplicate', 'update_proposed', 'rejected', 'blocked', 'deferred')}
        items = []
        for item in manifest['items']:
            state = states.get(item['key'], {'status': 'deferred'})
            counts[state['status']] += 1
            items.append(dict(key=item['key'], reserved_id=item['reserved_id'], status=state['status'], output=state.get('output')))
        calls, cost = spend(events)
        summary = {'schema_version': 1, 'mode': 'offline', 'production_accepted': False, 'batch_id': batch_id,
                   'status': 'partial' if counts['blocked'] or counts['deferred'] else 'complete',
                   'counts': counts, 'calls': calls, 'cost_units': cost, 'items': items}
        attempt = len(list(safe_path(root, batch_dir).glob('summary-attempt-*.yaml'))) + 1
        save_yaml(root, '%s/summary-attempt-%s.yaml' % (batch_dir, attempt), summary)
        text = '# 离线验收回执\n\n%s\n\n- 批次：`%s`\n- 状态：`%s`\n- 模拟请求：%s\n- 虚拟费用单位：%s（实际 API 费用为 0）\n\n' % (NOTICE, batch_id, summary['status'], calls, cost)
        text += '\n'.join('- %s: %s' % (k, v) for k, v in counts.items()) + '\n'
        create(root, '%s/summary-attempt-%s.md' % (batch_dir, attempt), text)
        return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--batch-id', required=True)
    parser.add_argument('--fail-after', choices=['after_review', 'after_reservation'])
    args = parser.parse_args()
    try:
        summary = run(args.root, args.fixture, args.batch_id, args.fail_after)
    except (OfflineError, SimulatedInterruption) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(yaml.safe_dump(summary, allow_unicode=True, sort_keys=False))
    return 0 if summary['status'] == 'complete' else 1


if __name__ == '__main__':
    sys.exit(main())
