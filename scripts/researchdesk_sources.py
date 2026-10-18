#!/usr/bin/env python3
"""Small read-only adapters for public arXiv, Letta and LangChain sources.

No model, credential, repository writer or scheduler lives in this module.
HTML is treated as untrusted input. Missing article boundaries fail closed.
"""

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
from html import unescape
from html.parser import HTMLParser
import ipaddress
import json
import re
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
import xml.etree.ElementTree as ET


class SourceError(ValueError):
    """Source fetching or parsing failed; this is not an empty search result."""


HOSTS = frozenset({'arxiv.org', 'export.arxiv.org', 'www.letta.com', 'letta.com',
                   'www.langchain.com', 'langchain.com', 'blog.langchain.com'})
SOURCE_HOSTS = {'letta': {'letta.com', 'www.letta.com'},
                'langchain': {'langchain.com', 'www.langchain.com', 'blog.langchain.com'}}
SOURCE_NAMES = {'letta': 'Letta', 'langchain': 'LangChain'}
TRACKING_KEYS = {'fbclid', 'gclid', 'dclid', 'msclkid', 'mc_cid', 'mc_eid'}
ARXIV_ID = re.compile(r'(?P<base>(?:\d{4}\.\d{4,5}|[a-z][a-z.\-]+/\d{7}))(?P<version>v[1-9]\d*)?\Z', re.I)
MAX_TEXT = 100_000


def validate_url(url):
    if not isinstance(url, str) or len(url) > 4096 or re.search(r'[\x00-\x20\\]', url):
        raise SourceError('Invalid source URL')
    try:
        parts = urlsplit(url)
        if (parts.scheme != 'https' or parts.hostname not in HOSTS or parts.username is not None
                or parts.password is not None or parts.port not in (None, 443)):
            raise SourceError('Source URL must use HTTPS and an approved public host')
    except ValueError as exc:
        raise SourceError('Invalid source URL') from exc
    return urlunsplit(('https', parts.hostname, parts.path or '/', parts.query, ''))


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class SafeFetcher:
    """Bounded HTTPS GET with explicit redirects and injectable test transport."""

    def __init__(self, timeout=20, max_bytes=2_000_000, retries=2, arxiv_interval=3.0,
                 opener=None, sleep=None, monotonic=None, resolver=None):
        if not 0 < timeout <= 60 or not 1 <= max_bytes <= 4_000_000 or not 0 <= retries <= 2:
            raise SourceError('Invalid fetch limits')
        if arxiv_interval < 3.0:
            raise SourceError('arXiv requests require at least three seconds between starts')
        self.timeout, self.max_bytes, self.retries = timeout, max_bytes, retries
        self.arxiv_interval = arxiv_interval
        self.opener = opener or build_opener(_NoRedirect())
        self.sleep = sleep or time.sleep
        self.monotonic = monotonic or time.monotonic
        self.resolver = resolver or socket.getaddrinfo
        self.last_arxiv = None

    def _check_host(self, host):
        try:
            addresses = self.resolver(host, 443, type=socket.SOCK_STREAM)
            if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
                raise SourceError('Source hostname resolved to a non-public address')
        except (OSError, ValueError) as exc:
            raise SourceError('Cannot verify public source hostname: %s' % host) from exc

    def _wait_arxiv(self, host):
        if host not in {'arxiv.org', 'export.arxiv.org'}:
            return
        now = self.monotonic()
        if self.last_arxiv is not None:
            delay = self.arxiv_interval - (now - self.last_arxiv)
            if delay > 0:
                self.sleep(delay)
        self.last_arxiv = self.monotonic()

    @staticmethod
    def _retry_delay(headers, attempt):
        retry_after = headers.get('Retry-After', '') if headers else ''
        try:
            delay = float(retry_after)
        except (ValueError, TypeError):
            try:
                parsed = parsedate_to_datetime(retry_after)
                delay = (parsed - datetime.now(timezone.utc)).total_seconds()
            except (ValueError, TypeError, OverflowError):
                delay = 2 ** attempt
        # Do not ignore a server's long requested pause by retrying too early.
        if delay > 60:
            raise SourceError('Retry-After exceeds this bounded run; retry in a later run')
        return max(0, delay)

    def fetch(self, url):
        requested = validate_url(url)
        current, redirects = requested, []
        for _ in range(6):
            host = urlsplit(current).hostname
            self._check_host(host)
            response = None
            for attempt in range(self.retries + 1):
                self._wait_arxiv(host)
                request = Request(current, headers={
                    'User-Agent': 'ResearchDesk/0.1 (public-source test; no model calls)',
                    'Accept': 'text/html, application/atom+xml, application/xml;q=0.9',
                    'Accept-Encoding': 'identity'})
                try:
                    call = self.opener.open if hasattr(self.opener, 'open') else self.opener
                    response = call(request, timeout=self.timeout)
                    status = getattr(response, 'status', None) or response.getcode()
                except HTTPError as exc:
                    response, status = exc, exc.code
                except (URLError, OSError, TimeoutError) as exc:
                    if attempt == self.retries:
                        raise SourceError('Public source request failed: %s' % type(exc).__name__) from exc
                    self.sleep(2 ** attempt)
                    continue
                if status == 429 or 500 <= status <= 599:
                    headers = response.headers
                    response.close()
                    if attempt == self.retries:
                        raise SourceError('Public source HTTP %s after bounded retries' % status)
                    self.sleep(self._retry_delay(headers, attempt))
                    continue
                break
            if response is None:
                raise SourceError('Source returned no response')
            try:
                if status in {301, 302, 303, 307, 308}:
                    location = response.headers.get('Location')
                    if not location:
                        raise SourceError('Redirect lacks Location')
                    target = validate_url(urljoin(current, location))
                    redirects.append({'from': current, 'to': target, 'status': status})
                    current = target
                    continue
                if status != 200:
                    raise SourceError('Public source HTTP %s' % status)
                # A custom transport must not silently follow unvalidated redirects.
                actual = validate_url(response.geturl()) if hasattr(response, 'geturl') else current
                if actual != current:
                    raise SourceError('Transport followed an unvalidated redirect')
                content_type = response.headers.get('Content-Type', '').split(';', 1)[0].strip().lower()
                if content_type not in {'text/html', 'application/xhtml+xml', 'application/atom+xml',
                                        'application/xml', 'text/xml'}:
                    raise SourceError('Unexpected source Content-Type: %s' % content_type)
                encoding = response.headers.get('Content-Encoding', 'identity').lower()
                if encoding not in {'', 'identity'}:
                    raise SourceError('Unexpected compressed source response')
                length = response.headers.get('Content-Length')
                if length and (not length.isdigit() or int(length) > self.max_bytes):
                    raise SourceError('Source response exceeds byte limit or has invalid length')
                raw = response.read(self.max_bytes + 1)
                if len(raw) > self.max_bytes:
                    raise SourceError('Source response exceeds byte limit')
                if not raw:
                    raise SourceError('Empty source response')
                try:
                    text = raw.decode('utf-8-sig')
                except UnicodeError as exc:
                    raise SourceError('Source response is not valid UTF-8') from exc
                return {'url': current, 'requested_url': requested, 'content_type': content_type,
                        'text': text, 'fetched_at': datetime.now(timezone.utc).isoformat(),
                        'status': status, 'redirects': redirects,
                        'sha256': hashlib.sha256(raw).hexdigest()}
            finally:
                response.close()
        raise SourceError('Too many source redirects')


def _clean(value):
    return re.sub(r'\s+', ' ', unescape(value or '')).strip()


def _date(value):
    if not value:
        return None
    value = _clean(value).replace('/', '-')
    try:
        datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise SourceError('Invalid explicit source date') from exc
    return value[:10]


def _record(kind, metadata, body, coverage, updated=None):
    body = _clean(body)
    if not metadata.get('title') or len(body) < 30:
        raise SourceError('Missing source title or article text')
    # The complete extracted article is only held in memory by this adapter. The
    # caller persists bounded excerpts and this hash, never a full HTML archive.
    return {'kind': kind, 'metadata': metadata, 'body_text': body[:MAX_TEXT],
            'coverage': 'excerpt' if len(body) > MAX_TEXT else coverage,
            'upstream_updated_at': updated,
            'content_hash': hashlib.sha256(body.encode('utf-8')).hexdigest()}


def _arxiv_identity(value):
    value = _clean(value)
    if '://' in value:
        parsed = urlsplit(value)
        if parsed.hostname not in {'arxiv.org', 'export.arxiv.org'} or not parsed.path.startswith('/abs/'):
            raise SourceError('Invalid arXiv entry identity')
        value = parsed.path[5:]
    match = ARXIV_ID.fullmatch(value)
    if not match:
        raise SourceError('Invalid arXiv identifier')
    return match.group('base').lower(), match.group('version')


def parse_arxiv_feed(text):
    if re.search(r'<!\s*(?:DOCTYPE|ENTITY)', text, re.I):
        raise SourceError('DTD and entities are not accepted in source feeds')
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise SourceError('Malformed arXiv Atom response') from exc
    atom = '{http://www.w3.org/2005/Atom}'
    if root.tag != atom + 'feed':
        raise SourceError('arXiv API response is not an Atom feed')
    records = []
    for entry in root.findall(atom + 'entry'):
        identity = entry.findtext(atom + 'id', '')
        if 'api/errors' in identity or entry.findtext(atom + 'title', '').lower() == 'error':
            raise SourceError('arXiv API returned an error entry')
        base, version = _arxiv_identity(identity)
        metadata = {'title': _clean(entry.findtext(atom + 'title')), 'source': 'arXiv',
                    'source_url': 'https://arxiv.org/abs/' + base,
                    'authors': [_clean(item.findtext(atom + 'name')) for item in entry.findall(atom + 'author')
                                if _clean(item.findtext(atom + 'name'))],
                    'published_at': _date(entry.findtext(atom + 'published')),
                    'arxiv_id': base, 'source_version': version}
        doi = _clean(entry.findtext('{http://arxiv.org/schemas/atom}doi')).lower()
        if doi:
            metadata['doi'] = re.sub(r'^https?://(?:dx\.)?doi\.org/', '', doi)
        updated = _clean(entry.findtext(atom + 'updated')) or None
        if updated:
            _date(updated)
        records.append(_record('paper', metadata, entry.findtext(atom + 'summary'), 'abstract_only', updated))
    return records


class _Node:
    def __init__(self, tag='', attrs=None, parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs or []), parent
        self.children = []

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, _Node):
                yield from child.walk()

    def text(self, evidence=False):
        excluded = {'script', 'style', 'noscript', 'svg', 'nav', 'footer', 'form'}
        if self.tag in excluded or 'hidden' in self.attrs or self.attrs.get('aria-hidden') == 'true':
            return ''
        if evidence and (self.tag in {'aside', 'header'} or _is_byline(self)):
            return ''
        return _clean(' '.join(c.text(evidence) if isinstance(c, _Node) else c for c in self.children))

    def has_class(self, token):
        return token in self.attrs.get('class', '').split()


class _Document(HTMLParser):
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.root = _Node()
        self.stack = [self.root]
        self.node_count = 0
        try:
            self.feed(text)
            self.close()
        except (ValueError, RecursionError) as exc:
            raise SourceError('Malformed or excessively nested HTML') from exc
        self.nodes = list(self.root.walk())

    def handle_starttag(self, tag, attrs):
        self.node_count += 1
        if len(self.stack) > 100 or self.node_count > 30_000:
            raise SourceError('Source HTML exceeds parser structure limit')
        node = _Node(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                self.stack = self.stack[:index]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)

    def meta(self, name):
        return [node.attrs.get('content', '') for node in self.nodes if node.tag == 'meta'
                and (node.attrs.get('name') == name or node.attrs.get('property') == name)]

    def articles_json(self):
        result = []
        def visit(value):
            if isinstance(value, list):
                for item in value:
                    visit(item)
            elif isinstance(value, dict):
                types = value.get('@type', [])
                if isinstance(types, str):
                    types = [types]
                if any(t in {'Article', 'BlogPosting', 'TechArticle', 'NewsArticle'} for t in types):
                    result.append(value)
                if '@graph' in value:
                    visit(value['@graph'])
        for node in self.nodes:
            if node.tag == 'script' and node.attrs.get('type', '').lower() == 'application/ld+json':
                try:
                    visit(json.loads(''.join(c for c in node.children if isinstance(c, str))))
                except (ValueError, TypeError):
                    continue
        return result


def _source_key(source):
    value = source.lower()
    if value not in SOURCE_HOSTS:
        raise SourceError('Unsupported blog source')
    return value


def _blog_url(url, source):
    url = validate_url(url)
    parts = urlsplit(url)
    if parts.hostname not in SOURCE_HOSTS[source] or not parts.path.startswith('/blog/'):
        raise SourceError('Article URL is outside the selected official blog')
    path = parts.path
    if not path.removeprefix('/blog/').strip('/') or path.startswith(('/blog/tag/', '/blog/author/', '/blog/category/')):
        raise SourceError('Not an article URL')
    # Match the knowledge-base URL policy: preserve path, trailing slash,
    # non-tracking query parameters and their order. A publisher's explicit
    # canonical declaration may establish a stronger identity in the parser.
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
             if not key.lower().startswith('utm_') and key.lower() not in TRACKING_KEYS]
    return urlunsplit(('https', parts.hostname, path, urlencode(query), ''))


def parse_blog_list(text, base_url, source):
    source = _source_key(source)
    base_url = validate_url(base_url)
    if urlsplit(base_url).hostname not in SOURCE_HOSTS[source]:
        raise SourceError('Blog list is outside the selected official publisher')
    doc = _Document(text)
    urls = []
    for node in doc.nodes:
        if node.tag != 'a' or not node.attrs.get('href'):
            continue
        try:
            url = _blog_url(urljoin(base_url, node.attrs['href']), source)
        except SourceError:
            continue
        if url not in urls:
            urls.append(url)
    if not urls:
        raise SourceError('Blog listing has no recognized official article links; layout may have changed')
    return urls


def _is_byline(node):
    classes = node.attrs.get('class', '').split()
    return any(c in {'byline', 'byline__text', 'blog-author-name-item', 'author-name', 'post-author'} for c in classes)


def _visible_authors(doc):
    authors = []
    # LangChain repeats author widgets in related-article cards. Only the post
    # header is authoritative when that current layout is present.
    scopes = [n for n in doc.nodes if n.has_class('blog-author-wrapper') and n.has_class('is-blog-post')]
    if not scopes:
        scopes = [n for n in doc.nodes if n.tag == 'article']
    candidates = list(scopes[0].walk()) if len(scopes) == 1 else doc.nodes
    nodes = [n for n in candidates if n.tag == 'a' and 'author' in n.attrs.get('rel', '').split()]
    if not nodes:
        nodes = [n for n in candidates if n.has_class('byline__text') or n.has_class('blog-author-name-item')
                 or n.has_class('author-name') or n.has_class('post-author')]
    if not nodes:
        nodes = [n for n in candidates if n.has_class('byline')]
    for node in nodes:
        value = node.text()
        value = re.sub(r'^by\s+', '', value, flags=re.I)
        # Letta's visible byline includes a job title after the author's name.
        value = re.split(r',\s*(?:letta|co-founder|cto|ceo)', value, maxsplit=1, flags=re.I)[0].strip()
        if value and len(value) <= 120 and value not in authors:
            authors.append(value)
    return authors


def parse_blog_article(text, url, source):
    source = _source_key(source)
    requested = _blog_url(url, source)
    doc = _Document(text)
    canonical = requested
    for node in doc.nodes:
        if node.tag == 'link' and 'canonical' in node.attrs.get('rel', '').split():
            canonical = _blog_url(urljoin(url, node.attrs.get('href', '')), source)
            # An unrelated canonical article is a mismatch, not a second source.
            if urlsplit(canonical).path.rstrip('/') != urlsplit(requested).path.rstrip('/'):
                raise SourceError('Canonical article identity differs from the requested source')
            break
    headings = [n.text() for n in doc.nodes if n.tag == 'h1' and n.text()]
    if len(headings) != 1:
        raise SourceError('Expected one visible article heading')
    title = headings[0]
    if source == 'langchain':
        bodies = [n for n in doc.nodes if n.has_class('text-rich-text-v2-blog-post')]
    else:
        bodies = [n for n in doc.nodes if n.tag == 'article']
    if not bodies:
        bodies = [n for n in doc.nodes if n.tag == 'article']
    if len(bodies) != 1:
        raise SourceError('Missing or ambiguous article body; layout may have changed')
    body = bodies[0].text(evidence=True)
    articles = doc.articles_json()
    published = next((a.get('datePublished') for a in articles if a.get('datePublished')), None)
    if not published:
        published = next(iter(doc.meta('article:published_time')), None)
    if not published:
        published = next((n.attrs['datetime'] for n in bodies[0].walk()
                          if n.tag == 'time' and n.attrs.get('datetime')), None)
    updated = next((a.get('dateModified') for a in articles if a.get('dateModified')), None)
    if updated:
        _date(updated)
    metadata = {'title': title, 'source': SOURCE_NAMES[source], 'source_url': canonical,
                'authors': _visible_authors(doc), 'published_at': _date(published)}
    return _record('blog', metadata, body, 'fulltext', updated)


def parse_arxiv_abstract(text, url):
    """Explicit seed fallback, never represented as a successful API search."""
    url = validate_url(url)
    base, requested_version = _arxiv_identity(url)
    doc = _Document(text)
    get = lambda name: next(iter(doc.meta(name)), None)
    actual, meta_version = _arxiv_identity(get('citation_arxiv_id') or '')
    if actual != base:
        raise SourceError('arXiv abstract identity mismatch')
    version = requested_version or meta_version
    if not version:
        datelines = [n.text() for n in doc.nodes if n.has_class('dateline')]
        match = re.search(r'this version,\s*(v\d+)', ' '.join(datelines), re.I)
        if match:
            version = match.group(1)
        elif re.search(r'\[Submitted on', ' '.join(datelines)) and not re.search(r'revised', ' '.join(datelines), re.I):
            version = 'v1'
    abstract = get('citation_abstract')
    if not abstract:
        abstract = next((n.text() for n in doc.nodes if n.tag == 'blockquote' and n.has_class('abstract')), None)
        abstract = re.sub(r'^Abstract:\s*', '', abstract or '')
    metadata = {'title': _clean(get('citation_title')), 'source': 'arXiv',
                'source_url': 'https://arxiv.org/abs/' + base,
                'authors': [_clean(a) for a in doc.meta('citation_author') if _clean(a)],
                'published_at': _date(get('citation_date')), 'arxiv_id': base,
                'source_version': version}
    if get('citation_doi'):
        metadata['doi'] = _clean(get('citation_doi')).lower()
    updated = _date(get('citation_online_date'))
    record = _record('paper', metadata, abstract, 'abstract_only', updated)
    record['discovery_mode'] = 'explicit_seed_fallback'
    return record
