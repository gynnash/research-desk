#!/usr/bin/env python3
"""Portable YAML configuration and bounded, public-source research inputs.

No inference, credential access, scheduling, Git or knowledge writer lives here.
Source material remains in memory; candidates retain short quotes and hashes.
"""

from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import researchdesk_offline as store
from researchdesk_sources import (SourceError, SOURCE_HOSTS, validate_url,
                                 parse_arxiv_feed, parse_arxiv_abstract, parse_blog_article)


def config_path(root, relative):
    root = Path(root).resolve()
    path = Path(relative)
    if path.is_absolute():
        try:
            path = path.relative_to(root)
        except ValueError as exc:
            raise store.OfflineError('配置必须位于选定工作台的 config 目录') from exc
    if (not path.parts or path.parts[0] != 'config' or '..' in path.parts
            or '\\' in str(path) or path.suffix not in {'.yaml', '.yml'}):
        raise store.OfflineError('配置必须是 config 下的 YAML，禁止越界路径')
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
    if not isinstance(topic, str) or not re.fullmatch(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*', topic):
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
    ranges = {'max_documents': (1, 10), 'max_calls_per_item': (2, 4), 'max_calls_per_batch': (2, 40),
              'month_max_calls': (2, 1000), 'max_input_chars': (1000, 30000),
              'max_output_chars': (1000, 12000), 'timeout_seconds': (1, 120), 'max_revisions': (0, 1)}
    fields(config['budget'], ranges, '预算配置')
    for name, (low, high) in ranges.items():
        positive(config['budget'][name], low, high, name)
    if config['budget']['max_calls_per_batch'] > config['budget']['max_calls_per_item'] * config['budget']['max_documents']:
        raise store.OfflineError('批次请求上限超过单项与资料数的乘积')
    if config['budget']['max_calls_per_batch'] > config['budget']['month_max_calls']:
        raise store.OfflineError('批次请求上限不可超过月度上限')
    fields(config['prompts'], {'version'}, '提示词配置')
    if config['prompts']['version'] != 'research-batch-v1':
        raise store.OfflineError('未知提示词版本')
    sources = config['sources']
    if not isinstance(sources, list) or not 1 <= len(sources) <= config['budget']['max_documents']:
        raise store.OfflineError('来源数须在 max_documents 范围内')
    ids, urls = set(), set()
    for source in sources:
        fields(source, {'id', 'adapter', 'kind', 'url', 'evidence_max_chars'}, '来源配置')
        if not isinstance(source['id'], str) or not store.SAFE_ID.fullmatch(source['id']) or source['id'] in ids:
            raise store.OfflineError('来源 ID 无效或重复')
        ids.add(source['id'])
        if source['adapter'] not in {'arxiv', 'letta', 'langchain'}:
            raise store.OfflineError('来源适配器未实现')
        expected = 'paper' if source['adapter'] == 'arxiv' else 'blog'
        if source['kind'] != expected:
            raise store.OfflineError('来源类型与适配器不匹配')
        try:
            url = validate_url(source['url'])
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
        elif parts.hostname not in SOURCE_HOSTS[source['adapter']]:
            raise store.OfflineError('博客域名与来源适配器不匹配')
        positive(source['evidence_max_chars'], 200, 10000, 'evidence_max_chars')
    config.update(_config_sha256=store.digest(path.read_bytes()), _topics_sha256=store.digest(topics_path.read_bytes()),
                  _config_path=path.relative_to(root).as_posix(), _topics_path=topics_path.relative_to(root).as_posix(),
                  topic_name=selected['name'], topic_scope=selected['scope'], topic_keywords=selected['keywords'])
    return config


def fetch_candidate(root, config, source, fetcher):
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
        else:
            if content_type not in {'text/html', 'application/xhtml+xml'}:
                raise SourceError('arXiv abstract did not return HTML')
            record = parse_arxiv_abstract(response['text'], response['url'])
        if not record['metadata'].get('source_version'):
            raise SourceError('arXiv version is unknown')
    else:
        if content_type not in {'text/html', 'application/xhtml+xml'}:
            raise SourceError('Blog article did not return HTML')
        record = parse_blog_article(response['text'], response['url'], source['adapter'])
    if record['kind'] != source['kind']:
        raise SourceError('Parsed source kind changed')
    text = record['body_text']
    cap = source['evidence_max_chars']
    coverage = 'abstract_only' if record['kind'] == 'paper' else 'excerpt'
    if coverage == 'abstract_only' and len(text) > cap:
        raise SourceError('Abstract exceeds configured input bound; cannot claim full abstract coverage')
    selected = text[:cap]
    if len(text) > cap:
        boundary = max(selected.rfind('. '), selected.rfind('。'))
        if boundary > cap // 2:
            selected = selected[:boundary + 1]
    sentences = [s.strip() for s in re.split(r'(?<=[.!?。！？])\s+(?=[A-Z0-9\u4e00-\u9fff])', selected) if s.strip()]
    locators, remaining, material = [], 25, []
    for i, sentence in enumerate(sentences):
        locator = 'A%s' % (i + 1)
        quote = ' '.join(sentence.split()[:remaining])[:400]
        remaining -= len(quote.split())
        locators.append({'id': locator, 'location': '%s sentence %s' % (coverage, i + 1),
                         'text_sha256': store.digest(sentence.encode()), 'quote': quote})
        material.append('%s: %s' % (locator, sentence))
    if not locators:
        raise SourceError('No readable evidence')
    material = '\n'.join(material)
    metadata = record['metadata']
    identity_keys = store.identities(metadata)
    matches = {}
    for key in identity_keys:
        matches.update(store.source_index(Path(root).resolve()).get(key, {}))
    if len(matches) > 1:
        raise store.OfflineError('来源身份键指向不同笔记，停止研究')
    if matches:
        source_id, (existing_path, existing_metadata) = next(iter(matches.items()))
        if not source_id.startswith(record['kind'] + '-'):
            raise store.OfflineError('来源身份与类型冲突')
    else:
        source_id, existing_path = record['kind'] + '-' + str(uuid4()), None
        existing_metadata = None
    evidence = {'coverage': coverage, 'extraction_coverage': record['coverage'],
                'source_url': metadata['source_url'], 'source_version': metadata.get('source_version'),
                'content_hash': record['content_hash'], 'evidence_sha256': store.digest(material.encode()),
                'locators': locators}
    candidate = {'key': source['id'], 'kind': record['kind'], 'topic': config['topic'], 'metadata': metadata,
                 'evidence': evidence, 'identity_keys': identity_keys, 'source_id': source_id,
                 'existing_source_path': existing_path, 'existing_source_metadata': existing_metadata,
                 'content_hash': record['content_hash'], 'metadata_hash': store.digest({
                     'metadata': metadata, 'upstream_updated_at': record.get('upstream_updated_at')}),
                 'upstream_updated_at': record.get('upstream_updated_at')}
    return candidate, material
