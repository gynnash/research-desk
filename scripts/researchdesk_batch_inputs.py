#!/usr/bin/env python3
"""Portable YAML configuration and bounded, public-source research inputs.

No inference, credential access, scheduling, Git or knowledge writer lives here.
Source material stays in memory unless its caller explicitly captures an archive.
"""

from copy import deepcopy
from datetime import date
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import researchdesk_offline as store
from researchdesk_sources import (SourceError, SOURCE_HOSTS, SafeFetcher, validate_url,
                                 parse_arxiv_feed, parse_arxiv_abstract, parse_blog_article)


FULLTEXT_PROMPT_VERSIONS = {'research-batch-v2', 'research-batch-v3', 'research-batch-v4', 'research-batch-v5'}


def config_path(root, relative):
    root = Path(root).resolve()
    path = Path(relative)
    if path.is_absolute():
        try:
            path = path.relative_to(root)
        except ValueError as exc:
            raise store.OfflineError('配置必须位于选定工作台的 config 目录') from exc
    runtime = bool(re.fullmatch(r'reports/test/[a-z0-9_-]+/cycles/[a-z0-9_-]+/configs/(?:research|insight)\.yaml', path.as_posix()))
    if (not path.parts or (path.parts[0] != 'config' and not runtime) or '..' in path.parts
            or '\\' in str(path) or path.suffix not in {'.yaml', '.yml'}):
        raise store.OfflineError('配置须位于 config 或受限轮次配置快照，禁止越界路径')
    current = root
    for part in path.parts:
        current = current / part
        if current.is_symlink():
            raise store.OfflineError('配置路径不可含符号链接')
    if not current.is_file():
        raise store.OfflineError('配置文件不存在: ' + path.as_posix())
    return current


def fields(value, expected, name):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise store.OfflineError(name + ' 字段缺失或包含未知字段')


def positive(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise store.OfflineError('%s 必须是 %s–%s 的整数' % (name, low, high))


def load_config(root, path):
    root = Path(root).resolve()
    path = config_path(root, path)
    config = store.load_yaml(path)
    fields(config, {'schema_version', 'mode', 'backend', 'topic', 'topics_file', 'models',
                    'budget', 'sources', 'prompts'}, '批次配置')
    if type(config['schema_version']) is not int or config['schema_version'] != 1:
        raise store.OfflineError('仅支持配置 schema_version: 1')
    if config['mode'] != 'research_batch_test' or config['backend'] not in {'chatgpt_plan', 'mock'}:
        raise store.OfflineError('仅支持 research_batch_test 与显式会员/模拟后端')
    topic = config['topic']
    if not isinstance(topic, str) or not store.SAFE_ID.fullmatch(topic) or not re.fullmatch(r'[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*', topic):
        raise store.OfflineError('主题必须是稳定的小写 ID')
    if not isinstance(config['topics_file'], str) or Path(config['topics_file']).is_absolute():
        raise store.OfflineError('topics_file 必须是 config 下的相对路径')
    topics_path = config_path(root, config['topics_file'])
    topics = store.load_yaml(topics_path)
    if type(topics.get('schema_version')) is not int or topics['schema_version'] != 1 or not isinstance(topics.get('topics'), dict):
        raise store.OfflineError('研究方向 YAML 格式无效')
    selected = topics['topics'].get(topic)
    if not isinstance(selected, dict) or selected.get('enabled') is not True:
        raise store.OfflineError('研究方向不存在或已停用')
    for key in ('name', 'description'):
        if not isinstance(selected.get(key), str) or not selected[key].strip():
            raise store.OfflineError('研究方向缺少名称或说明')
    for key in ('scope', 'keywords'):
        if not isinstance(selected.get(key), list) or not selected[key] or any(not isinstance(v, str) or not v.strip() for v in selected[key]):
            raise store.OfflineError('研究方向 scope/keywords 必须是非空字符串列表')
    fields(config['models'], {'research', 'review'}, '模型配置')
    if any(not isinstance(v, str) or not re.fullmatch(r'[A-Za-z0-9._:/-]{1,200}', v) for v in config['models'].values()):
        raise store.OfflineError('模型必须是明确的目录 slug')
    if config['models']['research'] == config['models']['review']:
        raise store.OfflineError('研究与独立审阅必须使用不同模型')
    fields(config['prompts'], {'version'}, '提示词配置')
    version = config['prompts']['version']
    if not isinstance(version, str) or version not in {'research-batch-v1', *FULLTEXT_PROMPT_VERSIONS}:
        raise store.OfflineError('未知提示词版本')
    max_timeout = 300 if version in {'research-batch-v4', 'research-batch-v5'} else 120
    ranges = {'max_documents': (1, 10), 'max_calls_per_item': (2, 1000), 'max_calls_per_batch': (2, 1000),
              'month_max_calls': (2, 1000), 'max_input_chars': (1000, 600000),
              'max_output_chars': (1000, 24000), 'timeout_seconds': (1, max_timeout), 'max_revisions': (0, 1)}
    fields(config['budget'], ranges, '预算配置')
    for name, (low, high) in ranges.items():
        positive(config['budget'][name], low, high, name)
    if config['budget']['max_calls_per_batch'] > config['budget']['max_calls_per_item'] * config['budget']['max_documents']:
        raise store.OfflineError('批次请求上限超过单项与资料数的乘积')
    if config['budget']['max_calls_per_batch'] > config['budget']['month_max_calls']:
        raise store.OfflineError('批次请求上限不可超过月度上限')
    sources = config['sources']
    if not isinstance(sources, list) or not 1 <= len(sources) <= config['budget']['max_documents']:
        raise store.OfflineError('来源数须在 max_documents 范围内')
    ids, urls = set(), set()
    for source in sources:
        fields(source, {'id', 'adapter', 'kind', 'url', 'evidence_max_chars'} |
               ({'reading'} if 'reading' in source else set()) |
               ({'archive'} if 'archive' in source else set()) |
               ({'publisher', 'allowed_hosts'} if source.get('adapter') == 'rss' else set()) |
               ({'feed_metadata'} if source.get('adapter') == 'rss' and 'feed_metadata' in source else set()), '来源配置')
        if 'archive' in source and source['archive'] is not True:
            raise store.OfflineError('归档配置仅支持显式 archive: true')
        if 'reading' in source:
            fields(source['reading'], {'mode'}, '全文阅读配置')
            reading_mode = source['reading']['mode']
            if (reading_mode not in {'full_text_preferred', 'full_text_required'}
                    or (reading_mode == 'full_text_preferred' and source['adapter'] != 'arxiv')
                    or version not in FULLTEXT_PROMPT_VERSIONS):
                raise store.OfflineError('全文阅读需要已支持的正文模式与全文研究提示词')
            if reading_mode == 'full_text_required' and source.get('archive') is not True:
                raise store.OfflineError('必须阅读全文的来源须同时启用原文归档 archive: true')
        if not isinstance(source['id'], str) or not store.SAFE_ID.fullmatch(source['id']) or source['id'] in ids:
            raise store.OfflineError('来源 ID 无效或重复')
        ids.add(source['id'])
        if not isinstance(source['adapter'], str) or source['adapter'] not in {'arxiv', 'letta', 'langchain', 'rss'}:
            raise store.OfflineError('来源适配器未实现')
        if source['adapter'] == 'rss':
            if (not isinstance(source['publisher'], str) or not source['publisher'].strip()
                    or len(source['publisher']) > 200 or not isinstance(source['allowed_hosts'], list)
                    or not 1 <= len(source['allowed_hosts']) <= 20
                    or any(not isinstance(host, str) or not re.fullmatch(r'[a-z0-9]+(?:[.-][a-z0-9]+)*\.[a-z]{2,}', host)
                           for host in source['allowed_hosts'])
                    or len(source['allowed_hosts']) != len(set(source['allowed_hosts']))):
                raise store.OfflineError('RSS 来源须明确配置 publisher 和公开域名 allowed_hosts')
            if 'feed_metadata' in source:
                item = source['feed_metadata']
                fields(item, {'published_at', 'feed_url', 'response_sha256'}, 'RSS 日期来源')
                try:
                    if item['published_at'] is not None and (not isinstance(item['published_at'], str)
                            or date.fromisoformat(item['published_at']).isoformat() != item['published_at']):
                        raise ValueError('Invalid explicit feed date')
                    validate_url(item['feed_url'], allowed_hosts=source['allowed_hosts'])
                    if not isinstance(item['response_sha256'], str) or not re.fullmatch(r'[0-9a-f]{64}', item['response_sha256']):
                        raise ValueError('Invalid feed response hash')
                except (ValueError, TypeError, SourceError) as exc:
                    raise store.OfflineError('RSS 日期与原始 Feed 散列绑定无效') from exc
        expected = 'paper' if source['adapter'] == 'arxiv' else 'blog'
        if source['kind'] != expected:
            raise store.OfflineError('来源类型与适配器不匹配')
        try:
            url = (validate_url(source['url'], allowed_hosts=source['allowed_hosts'])
                   if source['adapter'] == 'rss' else validate_url(source['url']))
        except SourceError as exc:
            raise store.OfflineError(str(exc)) from exc
        if url in urls:
            raise store.OfflineError('来源 URL 重复')
        urls.add(url)
        parts = urlsplit(url)
        if source['adapter'] == 'arxiv':
            if parts.hostname not in {'arxiv.org', 'export.arxiv.org'} or not (
                    parts.path == '/api/query' or re.fullmatch(r'/abs/(?:\d{4}\.\d{4,5}|[a-z][a-z0-9.-]*/\d{7})(?:v[1-9]\d*)?', parts.path)):
                raise store.OfflineError('arXiv 必须使用官方 Atom 查询或摘要地址')
            if parts.path == '/api/query':
                query = parse_qs(parts.query)
                if not query.get('id_list') and not query.get('search_query'):
                    raise store.OfflineError('arXiv 查询缺少 ID 或研究问题')
                if query.get('id_list') and (len(query['id_list']) != 1 or ',' in query['id_list'][0]):
                    raise store.OfflineError('一个 arXiv 来源项只选择一个明确 ID；多篇请分别配置')
        elif source['adapter'] != 'rss' and parts.hostname not in SOURCE_HOSTS[source['adapter']]:
            raise store.OfflineError('博客域名与来源适配器不匹配')
        positive(source['evidence_max_chars'], 200, 200000 if 'reading' in source else 10000,
                 'evidence_max_chars')
    config.update(_config_sha256=store.digest(path.read_bytes()), _topics_sha256=store.digest(topics_path.read_bytes()),
                  _config_path=path.relative_to(root).as_posix(), _topics_path=topics_path.relative_to(root).as_posix(),
                  topic_name=selected['name'], topic_scope=selected['scope'], topic_keywords=selected['keywords'])
    return config


def default_fetcher(sources):
    """Restrict portable publisher access to explicitly configured hosts."""
    from researchdesk_sources import HOSTS
    extra = {host for source in sources for host in source.get('allowed_hosts', [])}
    return SafeFetcher(retries=0, **({'allowed_hosts': set(HOSTS) | extra} if extra else {}))


def _section_material(sections, cap):
    """Keep every section in order; long documents receive balanced excerpts.

    All headers and A locators count toward the configured input bound. Full
    text is claimed only when the complete extracted document fits unchanged.
    """
    def project(quota=None):
        blocks, locators, scope = [], [], []
        quote_words, quote_chars, selected_chars = 25, 400, 0
        for section in sections:
            original = section['text']
            selected = original if quota is None else original[:quota]
            selected_chars += len(selected)
            scope.append({key: section[key] for key in ('id', 'title', 'location')})
            scope[-1].update(total_chars=len(original), selected_chars=len(selected))
            blocks.append('[%s] %s (%s)' % (section['id'], section['title'], section['location']))
            offset = 0
            while offset < len(selected):
                end = min(offset + 1400, len(selected))
                if end < len(selected):
                    boundary = max(selected.rfind('. ', offset + 700, end),
                                   selected.rfind('。', offset + 700, end),
                                   selected.rfind('\n', offset + 700, end))
                    if boundary > offset:
                        end = boundary + 1
                chunk = selected[offset:end]
                identifier = 'A%s' % (len(locators) + 1)
                quote = ' '.join(chunk.split()[:quote_words])[:quote_chars]
                quote_words -= len(quote.split())
                quote_chars -= len(quote)
                locators.append({'id': identifier, 'section_id': section['id'],
                    'location': '%s; chars %s-%s' % (section['location'], offset + 1, end),
                    'text_sha256': store.digest(chunk.encode()), 'quote': quote})
                blocks.append('%s: %s' % (identifier, chunk))
                offset = end
        return '\n'.join(blocks), locators, scope, selected_chars

    full = project()
    if len(full[0]) <= cap:
        return (*full, False)
    low, high, best = 0, max(len(s['text']) for s in sections), None
    while low <= high:
        quota = (low + high) // 2
        result = project(quota)
        if len(result[0]) <= cap:
            best, low = result, quota + 1
        else:
            high = quota - 1
    if best is None or not best[1] or any(s['selected_chars'] == 0 for s in best[2]):
        raise SourceError('Section headings exceed evidence bound; increase evidence_max_chars')
    return (*best, True)


def project_material(record, document, source):
    """Rebuild exact reading evidence from an immutable extracted original."""
    text = record['body_text']
    cap = source['evidence_max_chars']
    required = source.get('reading', {}).get('mode') == 'full_text_required'
    coverage = 'abstract_only' if record['kind'] == 'paper' else 'excerpt'
    if document is None and coverage == 'abstract_only' and len(text) > cap:
        raise SourceError('Abstract exceeds configured input bound; cannot claim full abstract coverage')
    selected = text[:cap]
    if len(text) > cap:
        boundary = max(selected.rfind('. '), selected.rfind('。'))
        if boundary > cap // 2:
            selected = selected[:boundary + 1]
    sentences = [s.strip() for s in re.split(r'(?<=[.!?。！？])\s+(?=[A-Z0-9\u4e00-\u9fff])', selected) if s.strip()]
    locators, remaining, quote_chars, material = [], 25, 400, []
    for i, sentence in enumerate(sentences):
        locator = 'A%s' % (i + 1)
        quote = ' '.join(sentence.split()[:remaining])[:quote_chars]
        remaining -= len(quote.split())
        quote_chars -= len(quote)
        locators.append({'id': locator, 'location': '%s sentence %s' % (coverage, i + 1),
                         'text_sha256': store.digest(sentence.encode()), 'quote': quote})
        material.append('%s: %s' % (locator, sentence))
    if not locators:
        raise SourceError('No readable evidence')
    material = '\n'.join(material)
    metadata = record['metadata']
    content_hash = record['content_hash']
    evidence = {'coverage': coverage, 'extraction_coverage': record['coverage'],
                'source_url': metadata['source_url'], 'source_version': metadata.get('source_version'),
                'content_hash': content_hash, 'evidence_sha256': store.digest(material.encode()),
                'locators': locators}
    if required and record['kind'] == 'blog' and document is None:
        if (record['coverage'] != 'fulltext' or store.digest(text.encode()) != record['content_hash']
                or len(text) < 800):
            raise SourceError('Full blog body required; extracted article is incomplete or too short')
        material, locators, sections, selected_chars, truncated = _section_material([
            {'id': 'S1', 'title': record['metadata']['title'], 'text': text,
             'location': record['metadata']['source_url']}], cap)
        if truncated:
            raise SourceError('Full blog body exceeds evidence_max_chars; no excerpt accepted')
        evidence.update(coverage='full_text', extraction_coverage='full_text',
            evidence_sha256=store.digest(material.encode()), locators=locators,
            reading_profile='blog-fulltext-v1', format='html',
            document_url=record['metadata']['source_url'], sections=sections,
            total_chars=len(text), selected_chars=selected_chars, truncated=False,
            extraction_scope='complete readable text within the explicit publisher article body',
            limitations=['Public HTML article text only; embedded images, video, interactive content, '
                         'external links, and inaccessible content are not verified.'])
    if document is not None:
        abstract_content_hash = record['content_hash']
        material, locators, sections, selected_chars, truncated = _section_material(
            document['sections'], cap)
        if document['format'] == 'abstract' and truncated:
            raise SourceError('Abstract exceeds evidence bound; cannot claim complete abstract coverage')
        coverage = ('abstract_only' if document['format'] == 'abstract' else
                    'excerpt' if truncated or document['coverage'] != 'full_text' else 'full_text')
        if required and coverage != 'full_text':
            raise SourceError('Full paper text exceeds evidence_max_chars or extraction is incomplete; no excerpt accepted')
        content_hash = document['text_sha256']
        evidence.update(coverage=coverage, extraction_coverage=document['coverage'],
            abstract_content_hash=abstract_content_hash,
            content_hash=content_hash, evidence_sha256=store.digest(material.encode()),
            locators=locators, reading_profile='arxiv-fulltext-v1', format=document['format'],
            document_url=document['source_url'], sections=sections,
            total_chars=document['total_chars'], selected_chars=selected_chars, truncated=truncated,
            extraction_scope=document.get('extraction_scope', 'extracted text'),
            limitations=document.get('limitations', []))
    return evidence, material, content_hash


class _CaptureFetcher:
    def __init__(self, fetcher, responses):
        self.fetcher, self.responses = fetcher, responses

    def __getattr__(self, name):
        return getattr(self.fetcher, name)

    def _fetch(self, method, url):
        response = getattr(self.fetcher, method)(url)
        proof = {key: deepcopy(response[key]) for key in
                 ('url', 'requested_url', 'content_type', 'fetched_at', 'status', 'redirects', 'sha256')
                 if key in response}
        if 'sha256' not in proof:
            body = response.get('body')
            if isinstance(body, bytes):
                proof['sha256'] = store.digest(body)
            elif isinstance(response.get('text'), str):
                proof['sha256'] = store.digest(response['text'].encode())
        self.responses.append(proof)
        return response

    def fetch(self, url):
        return self._fetch('fetch', url)

    def fetch_pdf(self, url):
        if not callable(getattr(self.fetcher, 'fetch_pdf', None)):
            raise SourceError('Transport does not support bounded PDF fetching')
        return self._fetch('fetch_pdf', url)


def fetch_candidate(root, config, source, fetcher, binding=None, capture=None):
    if capture is not None:
        capture.clear()
        capture['responses'] = []
        fetcher = _CaptureFetcher(fetcher, capture['responses'])
    required = source.get('reading', {}).get('mode') == 'full_text_required'
    retain_full = source.get('archive') is True or required
    response = fetcher.fetch(source['url'])
    content_type = response.get('content_type', '').split(';')[0].strip().lower()
    if source['adapter'] == 'arxiv':
        if urlsplit(source['url']).path == '/api/query':
            if content_type not in {'application/atom+xml', 'application/xml', 'text/xml'}:
                raise SourceError('arXiv query did not return Atom')
            records = parse_arxiv_feed(response['text'])
            if not records:
                raise SourceError('arXiv query contains no selected paper')
            # Deliberately bounded selection, not a claim to have scanned all results.
            record = records[0]
            requested = parse_qs(urlsplit(source['url']).query).get('id_list', [None])[0]
            if requested:
                match = re.fullmatch(r'((?:\d{4}\.\d{4,5}|[a-z][a-z0-9.-]*/\d{7}))(v[1-9]\d*)?', requested, re.I)
                if (not match or record['metadata']['arxiv_id'] != match.group(1).lower()
                        or (match.group(2) and record['metadata'].get('source_version') != match.group(2))):
                    raise SourceError('arXiv response does not match requested paper/version')
        else:
            if content_type not in {'text/html', 'application/xhtml+xml'}:
                raise SourceError('arXiv abstract did not return HTML')
            record = parse_arxiv_abstract(response['text'], response['url'])
        if not record['metadata'].get('source_version'):
            raise SourceError('arXiv version is unknown')
    else:
        if content_type not in {'text/html', 'application/xhtml+xml'}:
            raise SourceError('Blog article did not return HTML')
        if source['adapter'] == 'rss':
            from researchdesk_feeds import parse_article
            record = parse_article(response['text'], response['url'], source['publisher'],
                                   source['allowed_hosts'], retain_full=retain_full,
                                   feed_metadata=source.get('feed_metadata'))
        else:
            record = (parse_blog_article(response['text'], response['url'], source['adapter'], retain_full=True)
                      if retain_full else
                      parse_blog_article(response['text'], response['url'], source['adapter']))
    if record['kind'] != source['kind']:
        raise SourceError('Parsed source kind changed')
    document = None
    if required and record['kind'] == 'blog':
        # A publisher article boundary is required by the parser. Reject known
        # access gates instead of calling a publicly visible teaser "full text".
        if re.search(r'(?:subscribe|sign in|log in) to (?:continue|read (?:the )?(?:full|rest))|'
                     r'登录后(?:查看|阅读)全文|付费(?:后)?阅读|订阅(?:后)?阅读', record['body_text'], re.I):
            raise SourceError('Full blog body unavailable: publisher article contains an access gate')
        if re.search(r'"isAccessibleForFree"\s*:\s*(?:false|"false")', response['text'], re.I):
            raise SourceError('Full blog body unavailable: publisher declares restricted article access')
    if 'reading' in source and record['kind'] == 'paper':
        from researchdesk_fulltext import acquire_paper
        bound_evidence = (binding or {}).get('evidence', {})
        expected = bound_evidence.get('format') if binding is not None else None
        if binding is not None and bound_evidence.get('reading_profile') != 'arxiv-fulltext-v1':
            raise SourceError('Bound paper does not match the full-text reading profile')
        document = acquire_paper(record, fetcher, expected_format=expected, require_full=required)
    evidence, material, content_hash = project_material(record, document, source)
    metadata = record['metadata']
    identity_keys = store.identities(metadata)
    matches = {}
    from researchdesk_identity import source_index
    index = source_index(Path(root).resolve())
    for key in identity_keys:
        matches.update(index.get(key, {}))
    if len(matches) > 1:
        raise store.OfflineError('来源身份键指向不同笔记，停止研究')
    if matches:
        source_id, (existing_path, existing_metadata) = next(iter(matches.items()))
        if not source_id.startswith(record['kind'] + '-'):
            raise store.OfflineError('来源身份与类型冲突')
    else:
        source_id, existing_path = record['kind'] + '-' + str(uuid4()), None
        existing_metadata = None
    candidate = {'key': source['id'], 'kind': record['kind'], 'topic': config['topic'], 'metadata': metadata,
                 'evidence': evidence, 'identity_keys': identity_keys, 'source_id': source_id,
                 'existing_source_path': existing_path, 'existing_source_metadata': existing_metadata,
                 'content_hash': content_hash, 'metadata_hash': store.digest({
                     'metadata': metadata, 'upstream_updated_at': record.get('upstream_updated_at')}),
                 'upstream_updated_at': record.get('upstream_updated_at')}
    if document is not None:
        # Dynamic HTTP attempts are audit data, not re-created evidence. A
        # resumed batch keeps its original audit and pins its selected format.
        candidate['acquisition_attempts'] = ((binding or {}).get('acquisition_attempts', document['attempts'])
                                             if binding is not None else document['attempts'])
    if capture is not None:
        capture.update(record=deepcopy(record), document=deepcopy(document))
    return candidate, material
