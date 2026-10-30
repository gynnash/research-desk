"""In-memory, version-pinned official arXiv full-text acquisition.

Extraction is a reading aid, not a claim that figures, PDF layout, or mathematical
notation were recovered perfectly. No downloaded HTML, PDF, or full-text cache is
written by this module. The caller controls the model's eventual reading scope.
"""

import hashlib
from io import BytesIO
import re
from urllib.parse import urlsplit

from researchdesk_sources import ARXIV_ID, SourceError, _Document, _clean, validate_url


MAX_EXTRACT_CHARS = 500_000
MAX_PDF_PAGES = 500
MIN_FULLTEXT_CHARS = 160


class _IdentityError(SourceError):
    """A response explicitly identifies a different paper or version."""


def _identity(record):
    metadata = record.get('metadata', {})
    base, version = metadata.get('arxiv_id', ''), metadata.get('source_version', '')
    match = ARXIV_ID.fullmatch(str(base) + str(version or ''))
    if record.get('kind') != 'paper' or not match or not match.group('version'):
        raise SourceError('Full-text acquisition requires a paper with an exact arXiv version')
    return match.group('base').lower(), match.group('version')


def _check_declared(value, base, version):
    """Check explicit publisher identity declarations, allowing versionless IDs."""
    value = _clean(value)
    if not value:
        return
    if '://' in value:
        parsed = urlsplit(value)
        if parsed.hostname not in {'arxiv.org', 'export.arxiv.org'}:
            raise _IdentityError('Full-text identity declaration is outside official arXiv')
        match = re.fullmatch(r'/(?:abs|html|pdf)/(.+?)(?:\.pdf)?/?', parsed.path)
        if not match:
            raise _IdentityError('Full-text has an invalid arXiv identity declaration')
        value = match.group(1)
    value = re.sub(r'^arxiv:\s*', '', value, flags=re.I)
    match = ARXIV_ID.fullmatch(value)
    if (not match or match.group('base').lower() != base
            or (match.group('version') and match.group('version') != version)):
        raise _IdentityError('Full-text paper identity or version differs from the requested source')


def _check_response(response, url, base, version, fmt):
    expected_path = '/%s/%s%s' % (fmt, base, version)
    for key in ('url', 'requested_url'):
        actual = validate_url(response.get(key) or url)
        parts = urlsplit(actual)
        allowed_paths = {expected_path}
        if fmt == 'pdf':
            allowed_paths.add(expected_path + '.pdf')
        if parts.hostname != 'arxiv.org' or parts.path not in allowed_paths or parts.query:
            raise _IdentityError('Full-text response URL is not the requested official arXiv version')
    for redirect in response.get('redirects', []):
        for key in ('from', 'to'):
            parsed = urlsplit(validate_url(redirect[key]))
            allowed_paths = {expected_path, expected_path + '.pdf'} if fmt == 'pdf' else {expected_path}
            if parsed.hostname != 'arxiv.org' or parsed.path not in allowed_paths or parsed.query:
                raise _IdentityError('Full-text redirect changed paper identity or version')


def _digest(sections):
    # Include the section boundary and title so distinct segmentations cannot
    # accidentally bind to the same concatenated reading material.
    text = '\n\n'.join(section['title'] + '\n' + section['text'] for section in sections)
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _result(sections, fmt, coverage, url, attempts, limitations):
    if not sections:
        raise SourceError('Full-text extraction produced no readable sections')
    total = sum(len(section['text']) for section in sections)
    if total > MAX_EXTRACT_CHARS:
        raise SourceError('Extracted text exceeds the bounded extraction limit; no partial text accepted')
    return {'sections': sections, 'format': fmt, 'coverage': coverage,
            'source_url': url, 'attempts': attempts, 'text_sha256': _digest(sections),
            'total_chars': total, 'limitations': limitations,
            'extraction_scope': ('complete extracted document text including available references'
                                 if coverage == 'full_text' else
                                 'readable extracted pages only; one or more pages have no text'
                                 if fmt == 'pdf' else 'parsed source abstract only')}


def _html_sections(response, url, base, version):
    _check_response(response, url, base, version, 'html')
    if response.get('content_type', 'text/html') not in {'text/html', 'application/xhtml+xml'}:
        raise SourceError('Official HTML response has an unexpected Content-Type')
    if not isinstance(response.get('text'), str):
        raise SourceError('Official HTML response has no decoded text')
    doc = _Document(response['text'])
    for name in ('citation_arxiv_id', 'citation_pdf_url', 'og:url'):
        for value in doc.meta(name):
            _check_declared(value, base, version)
    for node in doc.nodes:
        if node.tag == 'link' and 'canonical' in node.attrs.get('rel', '').split():
            _check_declared(node.attrs.get('href', ''), base, version)
    roots = [node for node in doc.nodes if node.has_class('ltx_document')]
    if len(roots) != 1:
        raise SourceError('Official HTML lacks one unambiguous LaTeXML document')
    sections, current, chunks = [], {'title': 'Front matter', 'location': url}, []
    excluded = {'script', 'style', 'noscript', 'nav', 'footer', 'form', 'svg'}
    blocks = {'p', 'div', 'section', 'article', 'li', 'dt', 'dd', 'tr', 'figure', 'figcaption', 'pre'}
    skipped_classes = {'ltx_page_navbar', 'ltx_page_footer', 'ltx_page_header', 'ltx_TOC'}

    def visible(node):
        return not (node.tag in excluded or 'hidden' in node.attrs
                    or node.attrs.get('aria-hidden') == 'true'
                    or skipped_classes.intersection(node.attrs.get('class', '').split()))

    def inline(node):
        if isinstance(node, str):
            return node
        if not visible(node):
            return ''
        # Prefer a single accessible representation of mathematics instead of
        # concatenating MathML, TeX annotations, and visual fallbacks.
        if node.tag == 'math':
            if node.attrs.get('alttext'):
                return node.attrs['alttext']
            annotations = [n for n in node.walk() if n.tag == 'annotation'
                           and n.attrs.get('encoding', '').lower() in {'application/x-tex', 'application/x-latex'}]
            if annotations:
                return annotations[0].text()
        if node.tag in {'annotation', 'annotation-xml'}:
            return ''
        return ' '.join(inline(child) for child in node.children)

    def flush():
        text = '\n\n'.join(_clean(part) for part in ''.join(chunks).split('\n') if _clean(part))
        if text:
            sections.append({'id': 'S%d' % (len(sections) + 1), 'title': current['title'],
                             'text': text, 'location': current['location']})
            if sum(len(item['text']) for item in sections) > MAX_EXTRACT_CHARS:
                raise SourceError('Extracted HTML exceeds the bounded extraction limit')
        chunks.clear()

    def visit(node):
        nonlocal current
        if isinstance(node, str):
            chunks.append(node)
            return
        if not visible(node):
            return
        if re.fullmatch(r'h[1-6]', node.tag) or node.has_class('ltx_title'):
            title = _clean(inline(node))
            if title:
                flush()
                ancestor = node
                while ancestor is not None and not ancestor.attrs.get('id'):
                    ancestor = ancestor.parent
                anchor = ancestor.attrs.get('id') if ancestor is not None else None
                current = {'title': title, 'location': url + ('#' + anchor if anchor else '')}
            return
        if node.tag == 'math':
            chunks.append(' ' + inline(node) + ' ')
            return
        if node.tag in blocks:
            chunks.append('\n')
        if node.tag == 'br':
            chunks.append('\n')
        for child in node.children:
            visit(child)
        if node.tag in blocks:
            chunks.append('\n')

    visit(roots[0])
    flush()
    body_sections = [node for node in roots[0].walk()
                     if node.has_class('ltx_section') or node.has_class('ltx_appendix')]
    # Error/abstract-only pages sometimes copy a paper title. Require an actual
    # document section and meaningful body, rather than treating that as HTML.
    if (not body_sections or not any(len(node.text()) >= MIN_FULLTEXT_CHARS for node in body_sections)
            or sum(len(s['text']) for s in sections) < MIN_FULLTEXT_CHARS):
        raise SourceError('Official HTML has no sufficient readable paper body')
    return sections, 'full_text', ['Text extraction does not verify figures, layout, or faithful mathematical rendering.']


def _pdf_sections(response, url, base, version):
    _check_response(response, url, base, version, 'pdf')
    raw = response.get('body')
    if (response.get('content_type', 'application/pdf') != 'application/pdf'
            or not isinstance(raw, bytes) or not raw.startswith(b'%PDF-')):
        raise SourceError('Official PDF response is not a PDF document')
    if len(raw) > 20_000_000:
        raise SourceError('Official PDF exceeds the bounded download limit')
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise SourceError('PDF text extraction requires the optional pypdf dependency') from exc
    try:
        reader = PdfReader(BytesIO(raw), strict=False)
        if reader.is_encrypted:
            raise SourceError('Encrypted PDF is not supported')
        if not 0 < len(reader.pages) <= MAX_PDF_PAGES:
            raise SourceError('PDF exceeds the bounded page limit or has no pages')
        sections, empty_pages, total, previous_heading = [], [], 0, None

        def heading(line):
            # PDF has no reliable semantic DOM. Split only standalone, short
            # conventional titles; otherwise retain explicit page locations.
            if len(line) > 160 or len(line.split()) > 18 or line.endswith(('.', ';', '?')):
                return False
            return bool(re.fullmatch(r'\d+(?:\.\d+)*[.)]?\s+[A-Z][^\n]*', line)
                        or re.fullmatch(r'[A-Z]\.\s+[A-Z][^\n]*', line)
                        or re.fullmatch(r'(?:Abstract|References|Bibliography|Appendix(?:\s+[A-Z](?:[.:]\s*.*|\s+.*)?)?)',
                                        line, re.I))

        for number, page in enumerate(reader.pages, 1):
            text = page.extract_text() or ''
            if number == 1:
                # The publisher stamp often lives at the end of the first page.
                for label in re.findall(r'(?im)^\s*arxiv:\s*((?:\d{4}\.\d{4,5}|[a-z][a-z.\-]+/\d{7})(?:v\d+)?)', text):
                    _check_declared(label, base, version)
            lines = [_clean(line) for line in text.splitlines() if _clean(line)]
            text = '\n'.join(lines)
            readable = '\n'.join(line for line in lines if not re.match(r'^arxiv:', line, re.I))
            if len(re.findall(r'[A-Za-z\u3400-\u9fff]', readable)) < 30:
                empty_pages.append(number)
                continue
            total += len(text)
            if total > MAX_EXTRACT_CHARS:
                raise SourceError('Extracted PDF exceeds the bounded extraction limit')
            title = previous_heading + ' (continued)' if previous_heading else 'Page %d' % number
            segment = []

            def flush_segment():
                if segment:
                    sections.append({'id': 'S%d' % (len(sections) + 1), 'title': title,
                                     'text': '\n'.join(segment), 'location': url + '#page=%d' % number})
                    segment.clear()

            for line in lines:
                if heading(line):
                    flush_segment()
                    title = previous_heading = line
                # Preserve heading lines in the evidence text as well as its
                # title. Every extracted line belongs to exactly one segment.
                segment.append(line)
            flush_segment()
        if total < MIN_FULLTEXT_CHARS:
            raise SourceError('PDF has insufficient extractable text; scanned PDFs require unsupported OCR')
    except SourceError:
        raise
    except Exception as exc:
        # Libraries may include snippets of document input in exception text;
        # receipts need only a stable category and never untrusted raw content.
        raise SourceError('PDF parsing or text extraction failed (%s)' % type(exc).__name__) from exc
    limitations = ['PDF sections use recognized standalone headings with page locations; '
                   'unrecognized headings retain page or continued-section labels. '
                   'Column order, equations, figures, and layout may be imperfect.']
    if empty_pages:
        limitations.append('No text extracted from PDF pages: ' + ', '.join(map(str, empty_pages)))
    return sections, 'excerpt' if empty_pages else 'full_text', limitations


def acquire_paper(record, fetcher, expected_format=None):
    """Get official HTML, then PDF, otherwise the already parsed abstract.

    ``expected_format`` replays a previously bound input. A failed full-text
    replay raises instead of silently replacing reviewed evidence. Explicit
    identity/version mismatches always raise, including during discovery.
    """
    if expected_format not in {None, 'html', 'pdf', 'abstract'}:
        raise SourceError('Unknown pinned paper extraction format')
    base, version = _identity(record)
    abstract_url = 'https://arxiv.org/abs/' + base + version
    attempts = []
    formats = [expected_format] if expected_format else ['html', 'pdf']
    for fmt in formats:
        if fmt == 'abstract':
            break
        url = 'https://arxiv.org/%s/%s%s' % (fmt, base, version)
        try:
            if fmt == 'pdf' and not callable(getattr(fetcher, 'fetch_pdf', None)):
                raise SourceError('Transport does not support bounded PDF fetching')
            response = fetcher.fetch(url) if fmt == 'html' else fetcher.fetch_pdf(url)
            sections, coverage, limitations = (_html_sections(response, url, base, version) if fmt == 'html'
                                                else _pdf_sections(response, url, base, version))
            attempts.append({'format': fmt, 'url': url, 'status': 'success', 'reason': 'extracted'})
            return _result(sections, fmt, coverage, url, attempts, limitations)
        except _IdentityError:
            raise
        except SourceError as exc:
            attempts.append({'format': fmt, 'url': url, 'status': 'failed', 'reason': str(exc)[:240]})
            if expected_format:
                raise SourceError('Pinned %s extraction failed: %s' % (fmt, str(exc))) from exc
    abstract = _clean(record.get('body_text', ''))
    if len(abstract) < 30:
        raise SourceError('No usable parsed abstract remains after full-text acquisition failed')
    attempts.append({'format': 'abstract', 'url': abstract_url, 'status': 'success',
                     'reason': 'pinned_abstract' if expected_format == 'abstract' else 'full_text_unavailable'})
    sections = [{'id': 'S1', 'title': 'Abstract', 'text': abstract, 'location': abstract_url}]
    return _result(sections, 'abstract', 'abstract_only', abstract_url, attempts,
                   ['Only the parsed source abstract was read; methods and experiments in the body were not verified.'])
