#!/usr/bin/env python3
"""Bounded public RSS/Atom metadata and explicit blog body parsing.

This module fetches nothing. Feed summaries are metadata, never article bodies.
Callers must use SafeFetcher and explicitly approved publisher hosts.
"""

from email.utils import parsedate_to_datetime
import ipaddress
import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
import xml.etree.ElementTree as ET

from researchdesk_sources import SourceError, TRACKING_KEYS, _Document, _clean, _date, _record


MAX_INPUT = 2_000_000
MAX_ENTRIES = 2000
MAX_FIELD = 100_000
ATOM = '{http://www.w3.org/2005/Atom}'
CONTENT = '{http://purl.org/rss/1.0/modules/content/}encoded'
DC = '{http://purl.org/dc/elements/1.1/}creator'


def _url(value, base, allowed_hosts):
    if not isinstance(value, str) or len(value) > 4096 or re.search(r'[\x00-\x20\\]', value):
        raise SourceError('Invalid feed source URL')
    value = urljoin(base, value)
    try:
        parts = urlsplit(value)
        host = parts.hostname
        if (parts.scheme not in {'http', 'https'} or host not in set(allowed_hosts)
                or parts.username is not None or parts.password is not None
                or parts.port not in (None, 80 if parts.scheme == 'http' else 443)):
            raise SourceError('Feed URL is outside approved publisher hosts')
        try:
            ipaddress.ip_address(host)
        except ValueError:
            if not host or '.' not in host or host.endswith(('.local', '.localhost')):
                raise SourceError('Feed publisher must use a public hostname')
        else:
            raise SourceError('Feed publisher cannot be an IP address')
    except (ValueError, TypeError) as exc:
        raise SourceError('Invalid feed source URL') from exc
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith('utm_') and k.lower() not in TRACKING_KEYS]
    # Some official Atom publishers still emit HTTP links. Only upgrade an
    # already approved host; the actual request remains HTTPS through SafeFetcher.
    return urlunsplit(('https', host, parts.path or '/', urlencode(query), ''))


def _identity(url):
    parts = urlsplit(url)
    return parts.hostname, parts.path.rstrip('/'), parts.query


def _plain(value):
    if not value:
        return ''
    return _Document(value[:MAX_FIELD]).root.text()[:MAX_FIELD]


def _explicit_date(value):
    if not value:
        return None
    if not isinstance(value, str):
        raise SourceError('Explicit source date must be a string')
    value = _clean(value)
    try:
        return _date(value)
    except SourceError:
        try:
            return parsedate_to_datetime(value).date().isoformat()
        except (ValueError, TypeError, OverflowError) as exc:
            raise SourceError('Invalid explicit feed date') from exc


def _xml_content(node):
    if node is None:
        return None
    # CDATA/escaped HTML and Atom XHTML use different representations.
    content = (node.text or '') + ''.join(ET.tostring(c, encoding='unicode') for c in node)
    if len(content) > MAX_FIELD:
        return None  # Do not call a truncated feed payload complete content.
    return content if _plain(content) else None


def parse_feed(text, feed_url, allowed_hosts):
    """Return flat metadata candidates; no RSS summary becomes original text.

    Optional ``feed_content`` is the exact publisher-supplied content field,
    explicitly labelled publisher_feed_content. It does not prove full-article
    coverage: publishers can abbreviate even a content:encoded field.
    """
    feed_url = _url(feed_url, feed_url, allowed_hosts)
    if not isinstance(text, str) or len(text.encode('utf-8')) > MAX_INPUT:
        raise SourceError('Feed exceeds input limit')
    if re.search(r'<!\s*(?:DOCTYPE|ENTITY)\b', text, re.I):
        raise SourceError('DTD and entities are not allowed in public feeds')
    try:
        root = ET.fromstring(text)
    except (ET.ParseError, ValueError) as exc:
        raise SourceError('Malformed RSS/Atom feed') from exc
    pending, count = [(root, 0)], 0
    while pending:
        node, depth = pending.pop()
        count += 1
        if count > 30_000 or depth > 100:
            raise SourceError('Feed exceeds XML structure limit')
        pending.extend((child, depth + 1) for child in node)
    if root.tag == 'rss':
        channel = root.find('channel')
        if channel is None:
            raise SourceError('RSS channel is missing')
        entries = channel.findall('item')
        publisher = _plain(channel.findtext('title'))
        atom = False
    elif root.tag == ATOM + 'feed':
        entries = root.findall(ATOM + 'entry')
        publisher = _plain(root.findtext(ATOM + 'title'))
        atom = True
    else:
        raise SourceError('Unsupported RSS/Atom root')
    if len(entries) > MAX_ENTRIES:
        raise SourceError('Feed exceeds entry limit')
    result, seen = [], set()
    for entry in entries:
        prefix = ATOM if atom else ''
        title = _plain(entry.findtext(prefix + 'title'))[:1000]
        if atom:
            links = [n.attrib.get('href', '') for n in entry.findall(ATOM + 'link')
                     if n.attrib.get('rel', 'alternate') == 'alternate'
                     and n.attrib.get('type', 'text/html') in {'text/html', 'application/xhtml+xml'}]
            link = next(iter(links), '')
            authors = [_plain(n.findtext(ATOM + 'name')) for n in entry.findall(ATOM + 'author')]
            published = entry.findtext(ATOM + 'published')
            updated = entry.findtext(ATOM + 'updated')
            summary = entry.findtext(ATOM + 'summary')
            content_node = entry.find(ATOM + 'content')
            if content_node is not None and (content_node.attrib.get('src')
                    or content_node.attrib.get('type', 'text') not in {'html', 'xhtml', 'text'}):
                content_node = None
        else:
            link = entry.findtext('link') or ''
            authors = [_plain(n.text) for n in entry.findall(DC) + entry.findall('author')]
            published = entry.findtext('pubDate')
            updated = None
            summary = entry.findtext('description')
            content_node = entry.find(CONTENT)
        if not title or not link:
            continue
        try:
            url = _url(link.strip(), feed_url, allowed_hosts)
        except SourceError:
            continue  # Syndicated external links are not approved publisher articles.
        key = _identity(url)
        if key in seen:
            continue
        seen.add(key)
        item = {'title': title, 'source': publisher or urlsplit(feed_url).hostname,
                'source_url': url, 'authors': list(dict.fromkeys(a[:120] for a in authors if a))[:20],
                'published_at': _explicit_date(published), 'upstream_updated_at': updated,
                'feed_url': feed_url, 'feed_summary': _plain(summary)}
        if updated:
            _explicit_date(updated)
        content = _xml_content(content_node)
        if content:
            item.update(feed_content=content, feed_content_coverage='publisher_feed_content',
                        feed_content_origin=feed_url)
        result.append(item)
    return result


def _json_identity(article, requested, base, allowed_hosts):
    values = [article.get('url'), article.get('@id'), article.get('mainEntityOfPage')]
    for value in values:
        if isinstance(value, dict):
            value = value.get('@id') or value.get('url')
        if isinstance(value, str) and value:
            if _identity(_url(value, base, allowed_hosts)) != _identity(requested):
                return False
    return True


def _feed_date_evidence(value, allowed_hosts):
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {'published_at', 'feed_url', 'response_sha256'}:
        raise SourceError('Publisher feed date requires exact date, URL and response hash evidence')
    published, feed_url, digest = value['published_at'], value['feed_url'], value['response_sha256']
    if ((published is not None and (not isinstance(published, str)
            or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', published)))
            or not isinstance(feed_url, str) or urlsplit(feed_url).scheme != 'https'
            or not isinstance(digest, str) or not re.fullmatch(r'[a-f0-9]{64}', digest)):
        raise SourceError('Invalid publisher feed publication evidence')
    return {'published_at': _date(published),
            'feed_url': _url(feed_url, feed_url, allowed_hosts), 'response_sha256': digest}


def parse_article(text, url, publisher, allowed_hosts, retain_full=False, feed_metadata=None):
    """Parse one explicit publisher article boundary or matching JSON-LD body.

    A whole page, navigation, RSS summary, or a script-rendered shell is never a
    fallback body. The three verified publisher layouts have narrow selectors.
    """
    requested = _url(url, url, allowed_hosts)
    feed_date = _feed_date_evidence(feed_metadata, allowed_hosts)
    if not isinstance(text, str) or len(text.encode('utf-8')) > MAX_INPUT:
        raise SourceError('Article exceeds input limit')
    doc = _Document(text)
    canonical = requested
    declarations = [n.attrs.get('href', '') for n in doc.nodes if n.tag == 'link'
                    and 'canonical' in n.attrs.get('rel', '').split()]
    if len(declarations) > 1:
        raise SourceError('Ambiguous article canonical identity')
    if declarations:
        canonical = _url(declarations[0], requested, allowed_hosts)
        if _identity(canonical) != _identity(requested):
            raise SourceError('Canonical article identity differs from requested source')
    host = urlsplit(requested).hostname
    selector = {'huggingface.co': 'blog-content', 'tech.meituan.com': 'vp-page-content',
                'www.ruanyifeng.com': 'entry-content', 'ruanyifeng.com': 'entry-content'}.get(host)
    bodies = [n for n in doc.nodes if selector and n.has_class(selector)]
    if not bodies:
        bodies = [n for n in doc.nodes if n.tag == 'article']
    articles = [a for a in doc.articles_json() if _json_identity(a, canonical, requested, allowed_hosts)]
    if len(articles) > 1:
        raise SourceError('Ambiguous matching JSON-LD articles')
    article = articles[0] if articles else {}
    headings = [n.text() for n in doc.nodes if n.tag == 'h1' and n.text()]
    if len(headings) > 1:
        raise SourceError('Ambiguous article heading')
    title = headings[0] if headings else _clean(article.get('headline') if isinstance(article.get('headline'), str) else '')
    if len(bodies) == 1:
        body = bodies[0].text(evidence=True)
        boundary = selector or 'article'
    elif not bodies and isinstance(article.get('articleBody'), str):
        body = _Document(article['articleBody']).root.text()
        boundary = 'matching_jsonld_articleBody'
    else:
        raise SourceError('Missing or ambiguous explicit article body')
    published = article.get('datePublished') or next(iter(doc.meta('article:published_time')), None)
    if not published:
        published = next((n.attrs['datetime'] for n in doc.nodes
                          if n.tag == 'time' and n.attrs.get('datetime')
                          and n.attrs.get('itemprop') == 'datePublished'), None)
    if not published and host == 'tech.meituan.com':
        dates = [n.text() for n in doc.nodes if n.has_class('vp-post-date')]
        if len(dates) == 1:
            published = dates[0]
    date_basis = 'article' if published else None
    if not published and feed_date and feed_date['published_at']:
        published, date_basis = feed_date['published_at'], 'publisher_feed'
    updated = article.get('dateModified') or next(iter(doc.meta('article:modified_time')), None)
    if updated:
        _explicit_date(updated)
    authors = article.get('author', [])
    if isinstance(authors, (str, dict)):
        authors = [authors]
    if not isinstance(authors, list):
        authors = []
    authors = [a.get('name') if isinstance(a, dict) else a for a in authors]
    authors = [_clean(a) for a in authors if isinstance(a, str)]
    if not authors:
        authors = [_clean(a) for a in doc.meta('author')]
    metadata = {'title': title[:1000], 'source': publisher, 'source_url': canonical,
                'authors': list(dict.fromkeys(a[:120] for a in authors if a))[:20],
                'published_at': _explicit_date(published)}
    record = (_record('blog', metadata, body, 'fulltext', updated, retain_full=True)
              if retain_full else _record('blog', metadata, body, 'fulltext', updated))
    record['extraction'] = {'kind': 'official_html', 'boundary': boundary, 'url': requested}
    record['publication_date_basis'] = date_basis
    if date_basis == 'publisher_feed':
        record['publication_date_evidence'] = feed_date
    return record
