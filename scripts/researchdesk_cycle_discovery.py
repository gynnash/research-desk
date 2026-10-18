#!/usr/bin/env python3
"""Bounded, read-only discovery and historical selection for a research cycle.

Only the orchestrator persists the returned snapshot. A single public listing
is a bounded observation, never a claim that an entire publisher was scanned.
"""

from datetime import datetime, timezone
from pathlib import Path
import re
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
import xml.etree.ElementTree as ET

import researchdesk_offline as store
from researchdesk_sources import (SafeFetcher, SourceError, parse_arxiv_feed,
                                  parse_blog_article, parse_blog_list, validate_url)


SOURCE_ID = re.compile(r'(?:paper|blog)-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z')
SOURCE_IDS = re.compile(r'\b(?:paper|blog)-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b')
DEFAULT_ENTRIES = {
    'arxiv': 'https://export.arxiv.org/api/query',
    'letta': 'https://www.letta.com/blog/',
    'langchain': 'https://www.langchain.com/blog',
}


def _instant(value):
    if not isinstance(value, str):
        raise store.OfflineError('Cycle 时间必须是显式 ISO 日期或带时区的时间')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise store.OfflineError('Cycle 时间格式无效') from exc
    if parsed.tzinfo is None:
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            raise store.OfflineError('Cycle 时间缺少时区')
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _content(response, xml=False):
    kind = response.get('content_type', '').split(';', 1)[0].strip().lower()
    expected = {'application/atom+xml', 'application/xml', 'text/xml'} if xml else {
        'text/html', 'application/xhtml+xml'}
    if kind not in expected:
        raise SourceError('Discovery response has an unexpected content type')


def _context(root, config):
    relative = config.get('topics_file', 'config/research_topics.yaml')
    path = Path(relative)
    if (path.is_absolute() or '..' in path.parts or not path.parts
            or path.parts[0] != 'config' or '\\' in str(relative)):
        raise store.OfflineError('研究方向配置必须位于 config 内')
    current = root
    for part in path.parts:
        current /= part
        if current.is_symlink():
            raise store.OfflineError('研究方向配置不可包含符号链接')
    topic = config.get('topic')
    topics = store.load_yaml(current).get('topics', {})
    selected = topics.get(topic)
    if not isinstance(selected, dict) or selected.get('enabled') is not True:
        raise store.OfflineError('研究方向不存在或未启用')
    keywords = selected.get('keywords')
    if (not isinstance(keywords, list) or not keywords
            or any(not isinstance(word, str) or not word.strip() for word in keywords)):
        raise store.OfflineError('研究方向缺少可用关键词')
    return selected


def _arxiv_url(entry, keywords, limit):
    entry = validate_url(entry)
    parts = urlsplit(entry)
    if parts.hostname not in {'arxiv.org', 'export.arxiv.org'} or parts.path != '/api/query':
        raise store.OfflineError('Cycle arXiv 来源必须是官方 API 查询')
    query = parse_qs(parts.query, keep_blank_values=True)
    if 'id_list' in query:
        raise store.OfflineError('Cycle 自动发现禁止固定 arXiv ID 种子')
    search = query.get('search_query', [None])[0]
    if not search:
        search = ' OR '.join('all:"%s"' % re.sub(r'["\\]', '', word) for word in keywords)
    return urlunsplit(('https', parts.hostname, parts.path, urlencode({
        'search_query': search, 'sortBy': 'lastUpdatedDate', 'sortOrder': 'descending',
        'start': 0, 'max_results': limit}), ''))


def _window_reason(record, start, end):
    published = record['metadata'].get('published_at')
    if published is None:
        return None, 'unknown_publication_date'
    date = _instant(published)
    updated = record.get('upstream_updated_at')
    update_date = _instant(updated) if updated else None
    if start <= date < end:
        return 'published', None
    if date < end and update_date is not None and start <= update_date < end:
        return 'updated', None
    return None, 'outside_window'


def discover(root, config, cycle_id, fetcher=None):
    """Return metadata-only candidates and honest per-source scan boundaries.

    ``config`` supplies topic/topics_file, window_start/window_end, and a
    ``discovery`` mapping with max_candidates, max_documents, max_per_source,
    evidence_max_chars and optional sources [{id, adapter, entry_url}].
    No dates, cursors, candidates or credentials are written by this function.
    """
    root = Path(root).resolve()
    if not isinstance(cycle_id, str) or not store.SAFE_ID.fullmatch(cycle_id):
        raise store.OfflineError('Cycle ID 无效')
    topic = _context(root, config)
    limits = config['discovery']
    start, end = _instant(config['window_start']), _instant(config['window_end'])
    if start >= end:
        raise store.OfflineError('Cycle 时间窗必须递增')
    bounds = {'max_candidates': (1, 20), 'max_documents': (1, 5),
              'max_per_source': (1, 2), 'evidence_max_chars': (200, 10000)}
    values = {}
    for key, (low, high) in bounds.items():
        value = limits.get(key, 6000 if key == 'evidence_max_chars' else None)
        if type(value) is not int or not low <= value <= high:
            raise store.OfflineError('Cycle 发现限制无效: ' + key)
        values[key] = value
    sources = limits.get('sources', [{'id': key, 'adapter': key, 'entry_url': url}
                                     for key, url in DEFAULT_ENTRIES.items()])
    if not isinstance(sources, list) or not 1 <= len(sources) <= 3:
        raise store.OfflineError('Cycle 来源清单无效')
    adapters = [source.get('adapter', source.get('id')) for source in sources]
    if len(set(adapters)) != len(adapters) or any(adapter not in DEFAULT_ENTRIES for adapter in adapters):
        raise store.OfflineError('Cycle 来源重复或未实现')
    fetcher = fetcher or SafeFetcher(retries=1)
    candidates, deferred, statuses, eligible = [], [], [], []
    seen = set()
    for source, adapter in zip(sources, adapters):
        entry = source.get('entry_url', DEFAULT_ENTRIES[adapter])
        entry = validate_url(entry)
        status = {'id': source.get('id', adapter), 'adapter': adapter, 'entry_url': entry, 'status': 'failed',
                  'discovered': 0, 'inspected': 0, 'eligible': 0, 'selected': 0,
                  'complete_window': False, 'error_types': []}
        statuses.append(status)
        records = []
        try:
            cap = values['max_candidates']
            if adapter == 'arxiv':
                query = _arxiv_url(entry, topic['keywords'], cap)
                response = fetcher.fetch(query)
                _content(response, xml=True)
                records = parse_arxiv_feed(response['text'])
                # The first page may end before the requested window is covered.
                feed = ET.fromstring(response['text'])
                total_text = feed.findtext('{http://a9.com/-/spec/opensearch/1.1/}totalResults')
                total = int(total_text) if total_text and total_text.isdigit() else None
                oldest = min((_instant(r.get('upstream_updated_at') or r['metadata']['published_at'])
                              for r in records if r.get('upstream_updated_at') or r['metadata'].get('published_at')),
                             default=None)
                truncated = len(records) >= cap and (total is None or total > len(records))
                complete = not truncated or (oldest is not None and oldest < start)
                status.update(discovered=total if total is not None else len(records),
                              inspected=min(len(records), cap), status='complete' if complete else 'truncated',
                              complete_window=complete, requested_url=query)
                records = records[:cap]
            else:
                if urlsplit(entry).hostname not in ({'letta.com', 'www.letta.com'} if adapter == 'letta' else
                                                     {'langchain.com', 'www.langchain.com', 'blog.langchain.com'}):
                    raise SourceError('Cycle blog listing is outside its publisher')
                response = fetcher.fetch(entry)
                _content(response)
                urls = parse_blog_list(response['text'], response['url'], adapter)
                status.update(discovered=len(urls), status='truncated',
                              coverage='bounded_listing_only_no_archive_cursor')
                # Every listed article can affect relevance/date selection; URL
                # keyword ranking is not a substitute for reading its metadata.
                for url in urls[:cap]:
                    status['inspected'] += 1
                    try:
                        article = fetcher.fetch(url)
                        _content(article)
                        records.append(parse_blog_article(article['text'], article['url'], adapter))
                    except Exception as exc:
                        status['error_types'].append(type(exc).__name__)
                        deferred.append({'adapter': adapter, 'url': url, 'reason': 'article_failed',
                                         'error_type': type(exc).__name__})
                if not records and status['error_types']:
                    status['status'] = 'failed'
                    status['error_type'] = status['error_types'][-1]
                # Blog pages expose no verified exhaustive window or updated
                # ordering. Even a short listing cannot advance a full cursor.
            for record in records:
                metadata = record['metadata']
                url = metadata['source_url']
                keys = store.identities(metadata)
                reason, event = None, None
                haystack = re.sub(r'[-_]+', ' ', ' '.join([
                    metadata.get('title', ''), record.get('body_text', ''), url])).lower()
                relevant = any(re.sub(r'[-_]+', ' ', word.lower()) in haystack for word in topic['keywords'])
                if not relevant:
                    reason = 'topic_mismatch'
                else:
                    event, reason = _window_reason(record, start, end)
                item = {'adapter': adapter, 'kind': record['kind'], 'url': url,
                        'metadata': metadata, 'published_at': metadata.get('published_at'),
                        'upstream_updated_at': record.get('upstream_updated_at'),
                        'content_hash': record['content_hash'], 'identity_keys': keys,
                        'discovery_event': event, 'coverage': record['coverage']}
                if reason is None and seen.intersection(keys):
                    reason = 'same_cycle_duplicate'
                seen.update(keys)
                if reason:
                    deferred.append(dict(item, reason=reason))
                else:
                    status['eligible'] += 1
                    # Version-pin papers so the later Research fetch cannot
                    # silently substitute a newer version after discovery.
                    research_url = url
                    if adapter == 'arxiv':
                        version = metadata.get('source_version')
                        if not version:
                            deferred.append(dict(item, reason='unknown_arxiv_version'))
                            continue
                        research_url = 'https://arxiv.org/abs/' + metadata['arxiv_id'] + version
                    item['source'] = {'id': '%s-%s' % (adapter, store.digest(keys)[:12]),
                                      'adapter': adapter, 'kind': record['kind'], 'url': research_url,
                                      'evidence_max_chars': values['evidence_max_chars']}
                    eligible.append(item)
        except Exception as exc:
            status.update(status='failed', complete_window=False)
            status['error_types'].append(type(exc).__name__)
            status['error_type'] = type(exc).__name__
    # Source order is deliberate: one paper and one publisher by default. Each
    # source sorts by newest explicit publication/update, with URL as a tie-break.
    for adapter in adapters:
        items = [item for item in eligible if item['adapter'] == adapter]
        items.sort(key=lambda item: (item.get('upstream_updated_at') or item['published_at'], item['url']), reverse=True)
        for index, item in enumerate(items):
            if index >= values['max_per_source']:
                deferred.append(dict(item, reason='per_source_limit'))
            elif len(candidates) >= values['max_documents']:
                deferred.append(dict(item, reason='cycle_document_limit'))
            else:
                candidates.append(item)
                next(status for status in statuses if status['adapter'] == adapter)['selected'] += 1
    failures = [status for status in statuses if status['status'] == 'failed']
    state = ('failed' if len(failures) == len(statuses) else 'partial' if failures or any(
        status['status'] == 'truncated' for status in statuses) else 'complete')
    return {'schema_version': 1, 'mode': 'cycle_discovery_test', 'topic': config['topic'],
            'cycle_id': cycle_id, 'window_start': config['window_start'], 'window_end': config['window_end'],
            'status': state, 'source_status': statuses, 'candidates': candidates, 'deferred': deferred,
            'production_accepted': False}


def select_history(root, topic, max_documents=6):
    """Select current-topic formal notes, including every cited source UUID.

    A report/insight is skipped when dependencies are missing or do not fit the
    bound. The resulting explicit SHA-bound list is compatible with Insight's
    strict historical input reader, without treating old notes as fresh facts.
    """
    root = Path(root).resolve()
    if type(max_documents) is not int or not 1 <= max_documents <= 10:
        raise store.OfflineError('历史资料上限必须是 1–10')
    topics = store.load_yaml(root / 'config/research_topics.yaml').get('topics', {})
    selected_topic = topics.get(topic)
    if not isinstance(selected_topic, dict):
        raise store.OfflineError('历史资料研究方向不存在')
    name = selected_topic.get('name', topic)
    from researchdesk_identity import accepted_records
    admitted = {path for record in accepted_records(root) if record.get('topic')==topic
                for path in record.get('output_hashes',{})}
    source_paths, notes = {}, []
    for folder in ('sources/papers', 'sources/blogs', 'reports', 'insights'):
        for path in sorted((root / folder).rglob('*.md')):
            relative = path.relative_to(root)
            if ('test' in relative.parts or path.name == 'README.md' or path.is_symlink()
                    or any(parent.is_symlink() for parent in path.parents if parent != root and root in parent.parents)):
                continue
            if path.stat().st_size > 100000:
                continue
            # Match Insight's topic-directory rule as well as its content rule.
            parts = relative.parts
            directory = parts[2] if parts[0] == 'sources' and len(parts) > 3 else (
                parts[1] if parts[0] in {'reports', 'insights'} and len(parts) > 2 else None)
            if directory is not None and directory != topic:
                continue
            payload = path.read_bytes()
            try:
                text = payload.decode('utf-8')
                metadata = store.frontmatter(path)
            except (UnicodeError, store.OfflineError):
                continue
            # Marker-last admission can leave files after an interrupted
            # install. Only admitted AI records may become later history.
            # Human edits of an admitted note remain a new human baseline.
            if '> AI 自动研究记录，已通过独立模型审阅' in text and relative.as_posix() not in admitted:
                continue
            explicit = isinstance(metadata, dict) and isinstance(metadata.get('topics'), list) and topic in metadata['topics']
            if parts[0] == 'sources':
                kind = 'paper' if parts[1] == 'papers' else 'blog'
                identifier = metadata.get('id') if isinstance(metadata, dict) else None
                if (not explicit or not isinstance(identifier, str) or not SOURCE_ID.fullmatch(identifier)
                        or metadata.get('kind') != kind or not identifier.startswith(kind + '-') or path.stem != identifier):
                    continue
                try:
                    store.identities(metadata)
                except store.OfflineError:
                    continue
                if identifier in source_paths:
                    raise store.OfflineError('正式历史来源存在重复稳定 ID')
                source_paths[identifier] = (relative.as_posix(), store.digest(payload))
            elif explicit or re.search(r'(?:研究主题|主题)\s*[:：]\s*(?:%s|%s)(?:\s|$)' % (
                    re.escape(name), re.escape(topic)), text):
                refs = sorted(set(SOURCE_IDS.findall(text)))
                if refs:
                    notes.append((relative.as_posix(), store.digest(payload), refs))
    chosen = {}
    # Recent reports then insights provide a coherent context; dependencies are
    # inserted before the note. File names provide deterministic ordering, not
    # a guessed publication timestamp.
    notes.sort(key=lambda note: (note[0].startswith('reports/'), Path(note[0]).name, note[0]), reverse=True)
    for path, digest, refs in notes:
        if any(identifier not in source_paths for identifier in refs):
            continue
        needed = [source_paths[identifier] for identifier in refs if source_paths[identifier][0] not in chosen]
        if len(chosen) + len(needed) + 1 > max_documents:
            continue
        for source_path, source_hash in needed:
            chosen[source_path] = source_hash
        chosen[path] = digest
    for path, digest in sorted(source_paths.values()):
        if len(chosen) >= max_documents:
            break
        chosen.setdefault(path, digest)
    return [{'path': path, 'sha256': digest, 'origin': 'human_baseline'} for path, digest in chosen.items()]
