"""Official full-text extraction with fixed bytes; no network or model calls."""

from email.message import Message
import hashlib
import importlib.util
import io
from pathlib import Path
import socket
import sys
from types import SimpleNamespace
import unittest
from unittest import mock
from urllib.error import HTTPError


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import researchdesk_fulltext as fulltext
from researchdesk_sources import SafeFetcher, SourceError


PAPER = {'kind': 'paper', 'metadata': {'arxiv_id': '2610.01234', 'source_version': 'v2',
                                      'title': 'A Fixture Paper'},
         'body_text': 'This parsed abstract describes a fictional method and supplies no measured results.'}
HTML_URL = 'https://arxiv.org/html/2610.01234v2'
PDF_URL = 'https://arxiv.org/pdf/2610.01234v2'
BODY = ('The fictional method preserves source provenance and checks sufficient evidence before producing an answer. '
        'An evaluation section describes a controlled comparison without making an unsupported performance claim. ')
HTML = '''<html><head><meta name="citation_arxiv_id" content="2610.01234v2"></head>
<body><nav>Outside navigation</nav><article class="ltx_document">
<h1 class="ltx_title ltx_title_document">A Fixture Paper</h1>
<div class="ltx_abstract"><h6 class="ltx_title">Abstract</h6><p>Parsed abstract.</p></div>
<section class="ltx_section" id="S1"><h2 class="ltx_title">1 Introduction</h2>
<p>''' + BODY + '''</p><section class="ltx_section" id="S1.S1"><h3>1.1 Evidence</h3>
<p>Unique nested paragraph. <math alttext="x+y"><mi>x</mi><mo>+</mo><mi>y</mi>
<annotation encoding="application/x-tex">duplicate formula</annotation></math></p></section></section>
<section class="ltx_bibliography" id="bib"><h2>References</h2><p>One cited source.</p></section>
</article><footer>Outside footer</footer></body></html>'''


class FixedFetcher:
    def __init__(self, html=None, pdf=None):
        self.html = html if html is not None else SourceError('Public source HTTP 404')
        self.pdf = pdf if pdf is not None else SourceError('Public source HTTP 404')
        self.calls = []

    def _fetch(self, url, value, fmt):
        self.calls.append((fmt, url))
        if isinstance(value, Exception):
            raise value
        if isinstance(value, dict):
            return value
        return {'url': url, 'requested_url': url, 'content_type': 'text/html' if fmt == 'html' else 'application/pdf',
                'text' if fmt == 'html' else 'body': value}

    def fetch(self, url):
        return self._fetch(url, self.html, 'html')

    def fetch_pdf(self, url):
        return self._fetch(url, self.pdf, 'pdf')


class FulltextAcceptance(unittest.TestCase):
    def test_html_preserves_section_order_without_nested_duplicate_or_navigation(self):
        fetcher = FixedFetcher(html=HTML)
        result = fulltext.acquire_paper(PAPER, fetcher)
        self.assertEqual(result['format'], 'html')
        self.assertEqual(result['coverage'], 'full_text')
        self.assertEqual(fetcher.calls, [('html', HTML_URL)])
        self.assertEqual([s['title'] for s in result['sections']], ['Abstract', '1 Introduction', '1.1 Evidence', 'References'])
        text = '\n'.join(s['text'] for s in result['sections'])
        self.assertEqual(text.count('Unique nested paragraph.'), 1)
        self.assertIn('x+y', text)
        self.assertNotIn('duplicate formula', text)
        self.assertNotIn('Outside', text)
        self.assertEqual(result['sections'][1]['location'], HTML_URL + '#S1')
        self.assertEqual(result['sections'][2]['location'], HTML_URL + '#S1.S1')
        self.assertEqual(result['total_chars'], sum(len(s['text']) for s in result['sections']))
        self.assertEqual(len(result['text_sha256']), 64)

    def test_pdf_fallback_uses_page_locations_and_detected_section_titles(self):
        reader = SimpleNamespace(is_encrypted=False, pages=[
            SimpleNamespace(extract_text=lambda: 'arXiv:2610.01234v2\n1 Introduction\n' + BODY),
            SimpleNamespace(extract_text=lambda: '2 Results\n' + BODY)])
        with mock.patch.dict(sys.modules, {'pypdf': SimpleNamespace(PdfReader=lambda *a, **kw: reader)}):
            result = fulltext.acquire_paper(PAPER, FixedFetcher(pdf=b'%PDF-fixture'))
        self.assertEqual(result['format'], 'pdf')
        self.assertEqual(result['coverage'], 'full_text')
        results_section = next(s for s in result['sections'] if s['title'] == '2 Results')
        self.assertEqual(results_section['location'], PDF_URL + '#page=2')
        self.assertEqual([a['status'] for a in result['attempts']], ['failed', 'success'])

    def test_pdf_two_sections_on_one_page_keep_all_lines_once(self):
        page_text = '1 Introduction\n' + BODY + '\n2.1 Method\nDistinct method paragraph describes its evidence rules.'
        reader = SimpleNamespace(is_encrypted=False, pages=[SimpleNamespace(extract_text=lambda: page_text)])
        with mock.patch.dict(sys.modules, {'pypdf': SimpleNamespace(PdfReader=lambda *a, **kw: reader)}):
            result = fulltext.acquire_paper(PAPER, FixedFetcher(pdf=b'%PDF-fixture'))
        self.assertEqual([s['id'] for s in result['sections']], ['S1', 'S2'])
        self.assertEqual([s['title'] for s in result['sections']], ['1 Introduction', '2.1 Method'])
        self.assertEqual({s['location'] for s in result['sections']}, {PDF_URL + '#page=1'})
        self.assertEqual('\n'.join(s['text'] for s in result['sections']),
                         '\n'.join(line.strip() for line in page_text.splitlines()))

    def test_pdf_cross_page_continuation_and_appendix_preserve_text(self):
        page_one = '1 Introduction\n' + BODY
        page_two = 'Continued discussion preserves its distinct evidence and does not repeat the first page.\nAppendix A\nSupplementary rules have their own distinct context.'
        reader = SimpleNamespace(is_encrypted=False, pages=[SimpleNamespace(extract_text=lambda: page_one),
                                                           SimpleNamespace(extract_text=lambda: page_two)])
        with mock.patch.dict(sys.modules, {'pypdf': SimpleNamespace(PdfReader=lambda *a, **kw: reader)}):
            result = fulltext.acquire_paper(PAPER, FixedFetcher(pdf=b'%PDF-fixture'))
        self.assertEqual([s['title'] for s in result['sections']],
                         ['1 Introduction', '1 Introduction (continued)', 'Appendix A'])
        self.assertEqual([s['location'] for s in result['sections']],
                         [PDF_URL + '#page=1', PDF_URL + '#page=2', PDF_URL + '#page=2'])
        self.assertEqual('\n'.join(s['text'] for s in result['sections']),
                         '\n'.join(line.strip() for line in (page_one + '\n' + page_two).splitlines()))

    def test_pdf_without_recognized_headings_uses_explicit_page_label(self):
        reader = SimpleNamespace(is_encrypted=False, pages=[SimpleNamespace(extract_text=lambda: BODY)])
        with mock.patch.dict(sys.modules, {'pypdf': SimpleNamespace(PdfReader=lambda *a, **kw: reader)}):
            result = fulltext.acquire_paper(PAPER, FixedFetcher(pdf=b'%PDF-fixture'))
        self.assertEqual(result['sections'][0]['title'], 'Page 1')

    def test_both_failures_return_only_explicit_parsed_abstract(self):
        result = fulltext.acquire_paper(PAPER, FixedFetcher())
        self.assertEqual(result['coverage'], 'abstract_only')
        self.assertEqual(result['format'], 'abstract')
        self.assertEqual(result['sections'][0]['text'], PAPER['body_text'])
        self.assertEqual([a['format'] for a in result['attempts']], ['html', 'pdf', 'abstract'])
        self.assertEqual(result['attempts'][-1]['reason'], 'full_text_unavailable')

    def test_pinned_abstract_does_not_fetch_fulltext(self):
        fetcher = FixedFetcher(html=HTML)
        result = fulltext.acquire_paper(PAPER, fetcher, expected_format='abstract')
        self.assertEqual(fetcher.calls, [])
        self.assertEqual(result['attempts'][0]['reason'], 'pinned_abstract')

    def test_pinned_html_failure_cannot_silently_fall_back(self):
        fetcher = FixedFetcher()
        with self.assertRaisesRegex(SourceError, 'Pinned html extraction failed'):
            fulltext.acquire_paper(PAPER, fetcher, expected_format='html')
        self.assertEqual(fetcher.calls, [('html', HTML_URL)])

    def test_declared_identity_or_version_mismatch_fails_closed(self):
        for declaration in ('2610.99999v2', '2610.01234v3'):
            fetcher = FixedFetcher(html=HTML.replace('content="2610.01234v2"', 'content="' + declaration + '"'))
            with self.subTest(declaration=declaration), self.assertRaisesRegex(SourceError, 'identity or version'):
                fulltext.acquire_paper(PAPER, fetcher)
            self.assertEqual(len(fetcher.calls), 1)

    def test_wrong_response_url_fails_closed(self):
        fetcher = FixedFetcher(html={'url': 'https://arxiv.org/html/2610.99999v2', 'text': HTML})
        with self.assertRaisesRegex(SourceError, 'response URL'):
            fulltext.acquire_paper(PAPER, fetcher)

    def test_html_error_page_is_not_fulltext(self):
        result = fulltext.acquire_paper(PAPER, FixedFetcher(html='<html><h1>HTML not available</h1></html>'))
        self.assertEqual(result['format'], 'abstract')
        self.assertIn('LaTeXML', result['attempts'][0]['reason'])

    def test_extraction_limit_falls_back_without_truncating_or_claiming_fulltext(self):
        with mock.patch.object(fulltext, 'MAX_EXTRACT_CHARS', 120):
            result = fulltext.acquire_paper(PAPER, FixedFetcher(html=HTML))
        self.assertEqual(result['format'], 'abstract')
        self.assertIn('extraction limit', result['attempts'][0]['reason'])
        self.assertEqual(result['sections'][0]['text'], PAPER['body_text'])

    def test_unversioned_paper_cannot_use_latest_fulltext(self):
        paper = dict(PAPER, metadata=dict(PAPER['metadata'], source_version=None))
        with self.assertRaisesRegex(SourceError, 'exact arXiv version'):
            fulltext.acquire_paper(paper, FixedFetcher(html=HTML))

    def test_no_text_pdf_explicitly_degrades_without_ocr(self):
        reader = SimpleNamespace(is_encrypted=False, pages=[SimpleNamespace(extract_text=lambda: '')])
        with mock.patch.dict(sys.modules, {'pypdf': SimpleNamespace(PdfReader=lambda *a, **kw: reader)}):
            result = fulltext.acquire_paper(PAPER, FixedFetcher(pdf=b'%PDF-fixture'))
        self.assertEqual(result['format'], 'abstract')
        self.assertIn('OCR', result['attempts'][1]['reason'])

    def test_mixed_scanned_pdf_does_not_claim_complete_text(self):
        reader = SimpleNamespace(is_encrypted=False, pages=[SimpleNamespace(extract_text=lambda: BODY),
                                                           SimpleNamespace(extract_text=lambda: '')])
        with mock.patch.dict(sys.modules, {'pypdf': SimpleNamespace(PdfReader=lambda *a, **kw: reader)}):
            result = fulltext.acquire_paper(PAPER, FixedFetcher(pdf=b'%PDF-fixture'))
        self.assertEqual(result['coverage'], 'excerpt')
        self.assertIn('2', result['limitations'][1])

    def test_pdf_publisher_stamp_mismatch_cannot_be_hidden_by_fallback(self):
        reader = SimpleNamespace(is_encrypted=False, pages=[SimpleNamespace(
            extract_text=lambda: 'arXiv:2610.01234v3\n' + BODY)])
        with mock.patch.dict(sys.modules, {'pypdf': SimpleNamespace(PdfReader=lambda *a, **kw: reader)}):
            with self.assertRaisesRegex(SourceError, 'identity or version'):
                fulltext.acquire_paper(PAPER, FixedFetcher(pdf=b'%PDF-fixture'))

    @unittest.skipUnless(importlib.util.find_spec('pypdf'), 'pypdf optional dependency not installed')
    def test_real_pdf_parser_extracts_fixed_handwritten_pdf(self):
        # This minimal PDF is generated in memory from an ASCII text stream;
        # exercising the actual reader catches interface/encoding regressions.
        lines = ['1 Introduction', 'arXiv:2610.01234v2'] + [BODY[i:i + 80] for i in range(0, len(BODY), 80)]
        stream = 'BT /F1 10 Tf 20 750 Td ' + ' '.join('(' + line + ') Tj 0 -14 Td' for line in lines) + ' ET'
        objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
                   b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
                   b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
                   ('<< /Length %d >>\nstream\n%s\nendstream' % (len(stream), stream)).encode()]
        raw, offsets = bytearray(b'%PDF-1.4\n'), [0]
        for number, value in enumerate(objects, 1):
            offsets.append(len(raw))
            raw.extend(('%d 0 obj\n' % number).encode() + value + b'\nendobj\n')
        start = len(raw)
        raw.extend(('xref\n0 %d\n0000000000 65535 f \n' % (len(objects) + 1)).encode())
        raw.extend(''.join('%010d 00000 n \n' % offset for offset in offsets[1:]).encode())
        raw.extend(('trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF' % (len(objects) + 1, start)).encode())
        result = fulltext.acquire_paper(PAPER, FixedFetcher(pdf=bytes(raw)))
        self.assertEqual(result['format'], 'pdf')
        self.assertIn('preserves source provenance', result['sections'][0]['text'])


class FakeResponse(io.BytesIO):
    def __init__(self, raw, content_type='application/pdf', status=200, **headers):
        super().__init__(raw)
        self.status = status
        self.headers = Message()
        self.headers['Content-Type'] = content_type
        for key, value in headers.items():
            self.headers[key.replace('_', '-')] = str(value)


class PdfTransportAcceptance(unittest.TestCase):
    def fetcher(self, opener, **kwargs):
        resolver = lambda *a, **kw: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('93.184.216.34', 443))]
        return SafeFetcher(opener=opener, resolver=resolver, sleep=lambda _: None, **kwargs)

    def test_pdf_bytes_have_dedicated_limit_digest_and_accept_header(self):
        requests = []
        def open_pdf(request, timeout):
            requests.append(request)
            return FakeResponse(b'%PDF-fixture' + b'x' * 128)
        result = self.fetcher(open_pdf, max_bytes=64).fetch_pdf(PDF_URL)
        self.assertEqual(requests[0].get_header('Accept'), 'application/pdf')
        self.assertTrue(result['body'].startswith(b'%PDF-'))
        self.assertNotIn('text', result)
        self.assertEqual(result['sha256'], hashlib.sha256(result['body']).hexdigest())

    def test_wrong_mime_signature_length_or_compression_is_rejected(self):
        values = [FakeResponse(b'%PDF-x', content_type='text/html'), FakeResponse(b'not a PDF'),
                  FakeResponse(b'%PDF-x', Content_Length=20_000_001),
                  FakeResponse(b'%PDF-x', Content_Encoding='gzip')]
        for response in values:
            with self.subTest(headers=str(response.headers)), self.assertRaises(SourceError):
                self.fetcher(lambda *a, **kw: response).fetch_pdf(PDF_URL)

    def test_pdf_redirect_cannot_leave_official_pdf_origin(self):
        def redirect(request, timeout):
            headers = Message()
            headers['Location'] = 'https://www.letta.com/blog/paper'
            raise HTTPError(request.full_url, 302, 'Found', headers, io.BytesIO())
        with self.assertRaisesRegex(SourceError, 'PDF origin'):
            self.fetcher(redirect).fetch_pdf(PDF_URL)

    def test_pdf_private_dns_rejected_before_transport(self):
        opener = mock.Mock(side_effect=AssertionError('network prohibited'))
        fetcher = self.fetcher(opener)
        fetcher.resolver = lambda *a, **kw: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('127.0.0.1', 443))]
        with self.assertRaisesRegex(SourceError, 'public source hostname'):
            fetcher.fetch_pdf(PDF_URL)
        opener.assert_not_called()


if __name__ == '__main__':
    unittest.main()
