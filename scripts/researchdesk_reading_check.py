#!/usr/bin/env python3
"""Check one public paper's reading scope, without inference or repository writes."""

import argparse
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

import yaml

import researchdesk_batch_inputs as inputs
from researchdesk_sources import SafeFetcher, SourceError, validate_url


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True, help='Official version-pinned arXiv abstract URL')
    parser.add_argument('--max-chars', type=int, default=120000)
    parser.add_argument('--format', choices=('auto', 'html', 'pdf', 'abstract'), default='auto',
                        help='auto tries HTML then PDF; explicit formats verify only that extraction')
    args = parser.parse_args()
    try:
        url = validate_url(args.url)
        if (urlsplit(url).hostname != 'arxiv.org' or urlsplit(url).query or
                not re.fullmatch(r'/abs/(?:\d{4}\.\d{4,5}|[a-z][a-z0-9.-]*/\d{7})v[1-9]\d*', urlsplit(url).path)):
            raise SourceError('Reading check requires an official version-pinned abstract URL')
        inputs.positive(args.max_chars, 2000, 200000, 'max-chars')
        source = {'id': 'reading-check', 'adapter': 'arxiv', 'kind': 'paper',
                  'url': url, 'evidence_max_chars': args.max_chars,
                  'reading': {'mode': 'full_text_preferred'}}
        binding = None if args.format == 'auto' else {
            'evidence': {'reading_profile': 'arxiv-fulltext-v1', 'format': args.format}}
        # An empty temporary directory avoids reading the user's knowledge-base
        # identity/history. The checker never creates notes or model receipts.
        import tempfile
        with tempfile.TemporaryDirectory(prefix='researchdesk-reading-check-') as empty:
            candidate, material = inputs.fetch_candidate(Path(empty), {'topic': 'agent-memory'},
                source, SafeFetcher(retries=0), binding=binding)
        evidence = candidate['evidence']
        result = {'mode': 'public_source_reading_check', 'requested_format': args.format,
            'model_calls': 0, 'title': candidate['metadata']['title'],
            'source_url': candidate['metadata']['source_url'],
            'source_version': candidate['metadata']['source_version'],
            'attempts': candidate.get('acquisition_attempts', []),
            'evidence': {key: value for key, value in evidence.items() if key != 'locators'},
            'locator_count': len(evidence['locators']), 'material_chars': len(material),
            'production_accepted': False}
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False))
        return 0
    except Exception as exc:
        print('Reading check failed: %s: %s' % (type(exc).__name__, str(exc)), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
