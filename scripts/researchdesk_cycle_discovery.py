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
from researchdesk_sources import (HOSTS, SafeFetcher, SourceError, parse_arxiv_feed,
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
    expected = {'application/atom+xml', 'application/xml', 'text/xml', 'application/rss+xml'} if xml else {
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


def _arxiv_url(entry, keywords, limit, start=None, end=None, offset=0):
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
    if start is not None:
        search = '(%s) AND submittedDate:[%s TO %s]' % (
            search, start.strftime('%Y%m%d%H%M'), end.strftime('%Y%m%d%H%M'))
    return urlunsplit(('https', parts.hostname, parts.path, urlencode({
        'search_query': search, 'sortBy': 'submittedDate' if start is not None else 'lastUpdatedDate',
        'sortOrder': 'descending', 'start': offset, 'max_results': limit}), ''))


def _window_reason(record, start, end, published_only=False):
    published = record['metadata'].get('published_at')
    if published is None:
        return None, 'unknown_publication_date'
    date = _instant(published)
    updated = record.get('upstream_updated_at')
    update_date = _instant(updated) if updated else None
    if start <= date < end:
        return 'published', None
    if not published_only and date < end and update_date is not None and start <= update_date < end:
        return 'updated', None
    return None, 'outside_window'


def _blog_archive(fetcher, entry, adapter, max_pages=5):
    """Read a bounded official sitemap, without treating lastmod as publication.

    The index can be complete while the later article inspection is truncated.
    Sorting by modification date only gives recent articles a chance to enter
    that bounded inspection; older/unknown modification dates are never dropped.
    """
    if type(max_pages) is not int or not 1 <= max_pages <= 10:
        raise SourceError('Sitemap page limit must be between one and ten')
    hosts = ({'letta.com', 'www.letta.com'} if adapter == 'letta' else
             {'langchain.com', 'www.langchain.com', 'blog.langchain.com'})

    def official(url):
        checked = validate_url(url)
        if urlsplit(checked).hostname not in hosts:
            raise SourceError('Sitemap is outside its publisher')
        return checked

    namespace = '{http://www.sitemaps.org/schemas/sitemap/0.9}'
    queue, requested, seen, articles, errors = [official(entry)], [], set(), {}, []
    response_hashes = {}
    truncated, metadata_errors = False, 0
    while queue and len(requested) < max_pages:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        requested.append(url)
        try:
            response = fetcher.fetch(url)
            official(response['url'])
            _content(response, xml=True)
            text = response['text']
            response_hashes[url] = response.get('sha256') or store.digest(text.encode('utf-8'))
            if re.search(r'<!\s*(?:DOCTYPE|ENTITY)', text, re.I):
                raise SourceError('DTD and entities are not accepted in sitemaps')
            root = ET.fromstring(text)
            prefix = namespace if root.tag.startswith(namespace) else ''
            if root.tag not in {prefix + 'urlset', prefix + 'sitemapindex'}:
                raise SourceError('Official archive is not a sitemap')
            if root.tag == prefix + 'sitemapindex':
                for child in root.findall(prefix + 'sitemap'):
                    target = child.findtext(prefix + 'loc', '').strip()
                    try:
                        target = official(target)
                    except SourceError:
                        errors.append('SourceError')
                        continue
                    if target not in seen and target not in queue:
                        if len(queue) < 5000:
                            queue.append(target)
                        else:
                            truncated = True
                continue
            for child in root.findall(prefix + 'url'):
                target = child.findtext(prefix + 'loc', '').strip()
                try:
                    target = official(target)
                except SourceError:
                    # A site-wide sitemap may also contain non-blog locations.
                    continue
                path = urlsplit(target).path
                if (not re.fullmatch(r'/blog/[^/]+/?', path)
                        or path.startswith(('/blog/tag/', '/blog/author/', '/blog/category/'))):
                    continue
                lastmod = child.findtext(prefix + 'lastmod')
                try:
                    order = _instant(lastmod).timestamp() if lastmod else None
                except store.OfflineError:
                    metadata_errors += 1
                    order = None
                existing = articles.get(target)
                if existing is None:
                    if len(articles) >= 5000:
                        truncated = True
                        continue
                    articles[target] = {'url': target, 'lastmod': lastmod, 'order': order}
                elif order is not None and (existing['order'] is None or order > existing['order']):
                    articles[target] = {'url': target, 'lastmod': lastmod, 'order': order}
        except (SourceError, ET.ParseError) as exc:
            errors.append(type(exc).__name__)
    if queue:
        truncated = True
    if not articles:
        raise SourceError('Official sitemap has no recognized blog articles')
    rows = sorted(articles.values(), key=lambda item: (
        item['order'] is None, -(item['order'] or 0), item['url']))
    return [item['url'] for item in rows], {
        'requested_urls': requested, 'sitemap_pages': len(requested),
        'sitemap_response_hashes': response_hashes,
        'sitemap_index_complete': not truncated and not errors,
        'sitemap_metadata_errors': metadata_errors,
        'error_types': errors,
    }


def previously_selected(root, topic, cycle_id):
    """Build one in-memory identity ledger, never a new persistent database.

    A rolling discovery does not pick an old version/update/failed selection
    again. Recovery stays in the original frozen cycle; deliberate deepening
    remains a separate explicit batch. Mock-only source notes are excluded.
    """
    from researchdesk_identity import source_index
    root = Path(root).resolve()
    used = set()
    state_path = root / 'config/research_state.yaml'
    if state_path.exists():
        if state_path.is_symlink():
            raise store.OfflineError('历史去重状态不可使用符号链接')
        state = store.load_yaml(state_path)
        retained = state.get('selected_identity_keys') if isinstance(state, dict) else None
        if (not isinstance(state, dict) or type(state.get('schema_version')) is not int
                or state['schema_version'] != 1 or not isinstance(retained, list)
                or any(not isinstance(key, str) or not key.strip() for key in retained)):
            raise store.OfflineError('历史去重状态无效，停止候选选择')
        used.update(retained)
    for key, values in source_index(root).items():
        if any('test' not in Path(path).parts for path, _ in values.values()):
            used.add(key)
    import researchdesk_batch as batch
    current = 'reports/test/%s/research-batches/%s' % (topic, cycle_id)
    for _, candidate, _, _ in batch.previous_candidates(root, current, 'chatgpt_plan'):
        used.update(store.identities(candidate['metadata']))
    for path in (root / ('reports/test/' + topic + '/cycles')).glob('*/selection.yaml'):
        if path.parent.name == cycle_id:
            continue
        manifest_path = path.parent / 'manifest.yaml'
        if not manifest_path.is_file():
            continue
        manifest = store.checked_yaml(root, manifest_path.relative_to(root))
        if manifest.get('backend') != 'chatgpt_plan' or manifest.get('mode') != 'research_cycle_test':
            continue
        selection = store.checked_yaml(root, path.relative_to(root))
        for item in selection.get('candidates', []):
            metadata = item.get('metadata')
            if metadata:
                used.update(store.identities(metadata))
    return used


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
    rolling = config.get('window', {}).get('mode') == 'rolling'
    bounds = {'max_candidates': (1, 100 if rolling else 20), 'max_documents': (1, 5),
              'max_per_source': (1, 5 if rolling else 2), 'evidence_max_chars': (200, 10000)}
    values = {}
    for key, (low, high) in bounds.items():
        value = limits.get(key, 6000 if key == 'evidence_max_chars' else None)
        if type(value) is not int or not low <= value <= high:
            raise store.OfflineError('Cycle 发现限制无效: ' + key)
        values[key] = value
    sources = limits.get('sources', [{'id': key, 'adapter': key, 'entry_url': url}
                                     for key, url in DEFAULT_ENTRIES.items()])
    if (not isinstance(sources, list) or not 1 <= len(sources) <= 12
            or any(not isinstance(source, dict) for source in sources)):
        raise store.OfflineError('Cycle 来源清单无效')
    adapters = [source.get('adapter', source.get('id')) for source in sources]
    source_ids = [source.get('id', adapter) for source, adapter in zip(sources, adapters)]
    fixed = [adapter for adapter in adapters if adapter != 'rss']
    if (any(not isinstance(identifier, str) or not store.SAFE_ID.fullmatch(identifier) for identifier in source_ids)
            or len(set(source_ids)) != len(source_ids) or len(set(fixed)) != len(fixed)
            or any(adapter not in set(DEFAULT_ENTRIES) | {'rss'} for adapter in adapters)):
        raise store.OfflineError('Cycle 来源重复或未实现')
    if fetcher is None:
        hosts = set(HOSTS)
        for source, adapter in zip(sources, adapters):
            if adapter == 'rss':
                hosts.update(source.get('allowed_hosts', []))
        fetcher = SafeFetcher(retries=1, allowed_hosts=hosts)
    candidates, deferred, statuses, eligible = [], [], [], []
    seen = set()
    used = previously_selected(root, config['topic'], cycle_id) if rolling else set()
    for source, adapter in zip(sources, adapters):
        source_id = source.get('id', adapter)
        entry = source.get('entry_url', DEFAULT_ENTRIES.get(adapter))
        entry = (validate_url(entry, allowed_hosts=source.get('allowed_hosts', [])) if adapter == 'rss'
                 else validate_url(entry))
        status = {'id': source.get('id', adapter), 'adapter': adapter, 'entry_url': entry, 'status': 'failed',
                  'discovered': 0, 'inspected': 0, 'eligible': 0, 'selected': 0,
                  'complete_window': False, 'error_types': []}
        statuses.append(status)
        records, feed_bindings = [], {}
        try:
            cap = values['max_candidates']
            if adapter == 'arxiv':
                if rolling:
                    total, complete, requests = None, False, []
                    for offset in range(0, cap, 20):
                        page_size = min(20, cap - offset)
                        query = _arxiv_url(entry, topic['keywords'], page_size, start, end, offset)
                        requests.append(query)
                        try:
                            response = fetcher.fetch(query)
                            _content(response, xml=True)
                            page = parse_arxiv_feed(response['text'])
                            feed = ET.fromstring(response['text'])
                            count = feed.findtext('{http://a9.com/-/spec/opensearch/1.1/}totalResults')
                            if count and count.isdigit():
                                total = int(count)
                            records.extend(page[:page_size])
                            if len(page) < page_size or (total is not None and offset + len(page) >= total):
                                complete = True
                                break
                        except SourceError as exc:
                            status['error_types'].append(type(exc).__name__)
                            status['error_type'] = type(exc).__name__
                            break
                    status.update(discovered=total if total is not None else len(records),
                        inspected=len(records), status=('complete' if complete else 'truncated' if records else 'failed'),
                        complete_window=complete, requested_urls=requests, coverage='bounded_published_window')
                else:
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
            elif adapter == 'rss':
                from researchdesk_feeds import parse_feed, parse_article
                allowed_hosts = source['allowed_hosts']
                response = fetcher.fetch(entry)
                _content(response, xml=True)
                entries = parse_feed(response['text'], response['url'], allowed_hosts)
                entries.sort(key=lambda item: (
                    item.get('published_at') is None and item.get('upstream_updated_at') is None,
                    -_instant(item.get('published_at') or item.get('upstream_updated_at')).timestamp()
                    if item.get('published_at') or item.get('upstream_updated_at') else 0,
                    item['source_url']))
                status.update(discovered=len(entries), status='truncated',
                              requested_url=entry, coverage='publisher_feed_window_unproven',
                              feed_response_hash=response.get('sha256') or store.digest(response['text'].encode('utf-8')))
                for item in entries[:cap]:
                    url = item['source_url']
                    status['inspected'] += 1
                    try:
                        article_response = fetcher.fetch(url)
                        _content(article_response)
                        feed_metadata = {'published_at': item['published_at'], 'feed_url': item['feed_url'],
                                         'response_sha256': status['feed_response_hash']}
                        record = parse_article(article_response['text'], article_response['url'],
                                               source['publisher'], allowed_hosts,
                                               feed_metadata=feed_metadata)
                        records.append(record)
                        feed_bindings[record['metadata']['source_url']] = feed_metadata
                    except Exception as exc:
                        status['error_types'].append(type(exc).__name__)
                        deferred.append({'adapter': adapter, 'source_id': source_id, 'url': url,
                                         'reason': 'article_failed', 'error_type': type(exc).__name__})
                if not records and status['error_types']:
                    status['status'] = 'failed'
                    status['error_type'] = status['error_types'][-1]
            else:
                if urlsplit(entry).hostname not in ({'letta.com', 'www.letta.com'} if adapter == 'letta' else
                                                     {'langchain.com', 'www.langchain.com', 'blog.langchain.com'}):
                    raise SourceError('Cycle blog listing is outside its publisher')
                if source.get('sitemap_url') is not None:
                    urls, archive = _blog_archive(fetcher, source['sitemap_url'], adapter,
                                                 source.get('sitemap_max_pages', 5))
                    status.update(archive, discovered=len(urls), status='truncated',
                                  coverage='official_sitemap_bounded_article_inspection')
                else:
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
                elif source.get('sitemap_url') is not None:
                    complete = (status['sitemap_index_complete'] and len(urls) <= cap
                                and not status['error_types'])
                    status.update(status='complete' if complete else 'truncated',
                                  complete_window=complete)
                # A listing alone exposes no exhaustive window. A sitemap is
                # complete only when every indexed article was inspected; a
                # recent lastmod cannot establish the first publication date.
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
                    event, reason = _window_reason(record, start, end, published_only=rolling)
                if reason == 'unknown_publication_date' and status.get('complete_window'):
                    status.update(status='truncated', complete_window=False)
                item = {'adapter': adapter, 'source_id': source_id, 'kind': record['kind'], 'url': url,
                        'metadata': metadata, 'published_at': metadata.get('published_at'),
                        'upstream_updated_at': record.get('upstream_updated_at'),
                        'content_hash': record['content_hash'], 'identity_keys': keys,
                        'discovery_event': event, 'coverage': record['coverage']}
                if reason is None and seen.intersection(keys):
                    reason = 'same_cycle_duplicate'
                if reason is None and used.intersection(keys):
                    reason = 'previously_selected'
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
                    identity = store.digest(keys if len(source_id) <= 80 else [source_id, keys])[:12]
                    item['source'] = {'id': '%s-%s' % (source_id[:80], identity),
                                      'adapter': adapter, 'kind': record['kind'], 'url': research_url,
                                      'evidence_max_chars': values['evidence_max_chars']}
                    if 'reading' in config and (adapter == 'arxiv'
                            or config['reading']['mode'] == 'full_text_required'):
                        item['source'].update(reading={'mode': config['reading']['mode']},
                            evidence_max_chars=config['reading']['paper_max_chars'] if adapter == 'arxiv'
                                               else config['reading'].get('blog_max_chars', 200000))
                    if adapter == 'rss':
                        item['source'].update(publisher=source['publisher'],
                                              allowed_hosts=source['allowed_hosts'],
                                              feed_metadata=feed_bindings[url])
                    eligible.append(item)
        except Exception as exc:
            status.update(status='failed', complete_window=False)
            status['error_types'].append(type(exc).__name__)
            status['error_type'] = type(exc).__name__
    # Source order is deliberate: one paper and one publisher by default. Each
    # source sorts by newest explicit publication/update, with URL as a tie-break.
    attention_summary = None
    if 'selection' in config:
        from researchdesk_attention import rank_candidates
        # Alternate publishers before applying a shared lookup budget.
        groups = [[item for item in eligible if item['source_id'] == key] for key in source_ids]
        from itertools import zip_longest
        balanced = [item for row in zip_longest(*groups) for item in row if item is not None]
        ranked, attention_summary = rank_candidates(balanced, fetcher, config['selection'],
                                                    start.isoformat(), end.isoformat())
        deferred.extend(attention_summary.pop('deferred'))
        counts = {}
        for item in ranked:
            source_id = item['source_id']
            if counts.get(source_id, 0) >= values['max_per_source']:
                deferred.append(dict(item, reason='per_source_limit'))
            elif len(candidates) >= values['max_documents']:
                deferred.append(dict(item, reason='cycle_document_limit'))
            else:
                candidates.append(item)
                counts[source_id] = counts.get(source_id, 0) + 1
                next(s for s in statuses if s['id'] == source_id)['selected'] += 1
    for source_id in source_ids if 'selection' not in config else []:
        items = [item for item in eligible if item['source_id'] == source_id]
        items.sort(key=lambda item: (item.get('upstream_updated_at') or item['published_at'], item['url']), reverse=True)
        for index, item in enumerate(items):
            if index >= values['max_per_source']:
                deferred.append(dict(item, reason='per_source_limit'))
            elif len(candidates) >= values['max_documents']:
                deferred.append(dict(item, reason='cycle_document_limit'))
            else:
                candidates.append(item)
                next(status for status in statuses if status['id'] == source_id)['selected'] += 1
    failures = [status for status in statuses if status['status'] == 'failed']
    state = ('failed' if len(failures) == len(statuses) else 'partial' if failures or any(
        status['status'] == 'truncated' for status in statuses) else 'complete')
    if attention_summary is not None and attention_summary.get('status') != 'complete' and state == 'complete':
        state = 'partial'
    result = {'schema_version': 1, 'mode': 'cycle_discovery_test', 'topic': config['topic'],
            'cycle_id': cycle_id, 'window_start': config['window_start'], 'window_end': config['window_end'],
            'status': state, 'source_status': statuses, 'candidates': candidates, 'deferred': deferred,
            'production_accepted': False}
    if attention_summary is not None:
        result['selection'] = attention_summary
    return result


def select_history(root, topic, max_documents=6, lookback_days=None, as_of=None):
    """Select current-topic formal notes, including every cited source UUID.

    A report/insight is skipped when dependencies are missing or do not fit the
    bound. The resulting explicit SHA-bound list is compatible with Insight's
    strict historical input reader, without treating old notes as fresh facts.
    """
    root = Path(root).resolve()
    limit = 40 if lookback_days is not None else 10
    if type(max_documents) is not int or not 1 <= max_documents <= limit:
        raise store.OfflineError('历史资料上限必须是 1–%s' % limit)
    window = None
    if lookback_days is not None:
        from datetime import timedelta
        if type(lookback_days) is not int or not 90 <= lookback_days <= 180 or as_of is None:
            raise store.OfflineError('历史选择须明确90–180天范围与截至时刻')
        end = _instant(as_of).date()
        window = {'start': (end - timedelta(days=lookback_days)).isoformat(),
                  'end': end.isoformat(), 'lookback_days': lookback_days}
    topics = store.load_yaml(root / 'config/research_topics.yaml').get('topics', {})
    selected_topic = topics.get(topic)
    if not isinstance(selected_topic, dict):
        raise store.OfflineError('历史资料研究方向不存在')
    name = selected_topic.get('name', topic)
    from researchdesk_identity import accepted_records
    admissions = [record for record in accepted_records(root) if record.get('topic') == topic]
    admitted = {path for record in admissions
                for path in record.get('output_hashes',{})}
    source_paths, notes, details, source_metadata = {}, [], {}, {}
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
            # Reader-facing formatting copies share the original evidence;
            # selecting them again would count the same research twice.
            if isinstance(metadata, dict) and metadata.get('kind') == 'reading_note':
                continue
            # Marker-last admission can leave files after an interrupted
            # install. Only admitted AI records may become later history.
            # Human edits of an admitted note remain a new human baseline.
            generated = (isinstance(metadata, dict) and metadata.get('status') == 'accepted'
                         and str(metadata.get('id', '')).startswith(('research-', 'formal-')))
            if ('> AI 自动研究记录，已通过独立模型审阅' in text or generated) and relative.as_posix() not in admitted:
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
                source_metadata[identifier] = metadata
            elif explicit or re.search(r'(?:研究主题|主题)\s*[:：]\s*(?:%s|%s)(?:\s|$)' % (
                    re.escape(name), re.escape(topic)), text):
                refs = sorted(set(SOURCE_IDS.findall(text)))
                if refs:
                    notes.append((relative.as_posix(), store.digest(payload), refs))
            if window is not None:
                details[relative.as_posix()] = (metadata, payload)
    if window is not None:
        from researchdesk_insight_inputs import history_details
        descriptions = {path: history_details(root, path, metadata, payload, source_metadata, admissions)
                        for path, (metadata, payload) in details.items()}
        def eligible(path):
            when = descriptions[path]['research_date']
            return when is not None and window['start'] <= when <= window['end']
        # One pass per observed calendar month before taking another record
        # from the same month. A source UUID remains one underlying source,
        # even when its report, synthesis and insight repeat its claims.
        months = {}
        for note in notes:
            if eligible(note[0]) and all(identifier in source_paths for identifier in note[2]):
                months.setdefault(descriptions[note[0]]['research_date'][:7], []).append(note)
        chosen, seen = {}, set()
        while months:
            progress = False
            for month in sorted(list(months), reverse=True):
                values = months[month]
                values.sort(key=lambda note: (len(set(note[2]) - seen),
                    descriptions[note[0]]['research_date'], note[0]), reverse=True)
                for note in list(values):
                    path, digest, refs = note
                    dependencies = [source_paths[key] for key in refs if source_paths[key][0] not in chosen]
                    if len(chosen) + len(dependencies) + 1 <= max_documents:
                        for source_path, source_hash in dependencies:
                            chosen[source_path] = source_hash
                        chosen[path] = digest
                        seen.update(refs)
                        values.remove(note)
                        progress = True
                        break
                if not values:
                    del months[month]
            if not progress or len(chosen) >= max_documents:
                break
        # Direct source notes can fill remaining room, ordered by explicit
        # collection/research day rather than UUID spelling or file mtime.
        sources = [(identifier, path, digest) for identifier, (path, digest) in source_paths.items()
                   if eligible(path) and path not in chosen]
        source_months = {}
        for item in sources:
            source_months.setdefault(descriptions[item[1]]['research_date'][:7], []).append(item)
        while source_months and len(chosen) < max_documents:
            for month in sorted(list(source_months), reverse=True):
                values = source_months[month]
                values.sort(key=lambda item: (item[0] not in seen, descriptions[item[1]]['research_date'], item[1]), reverse=True)
                identifier, path, digest = values.pop(0)
                chosen[path] = digest
                seen.add(identifier)
                if not values:
                    del source_months[month]
                if len(chosen) >= max_documents:
                    break
        return [dict(path=path, sha256=digest, origin='human_baseline', **descriptions[path],
                     history_window=dict(window)) for path, digest in chosen.items()]
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
