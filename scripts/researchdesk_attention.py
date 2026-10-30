"""Small, read-only community attention observations; no model or credentials.

Hugging Face paper_info: https://huggingface.co/docs/huggingface_hub/package_reference/hf_api#huggingface_hub.HfApi.paper_info
HTTP fields: https://github.com/huggingface/huggingface_hub/blob/main/src/huggingface_hub/hf_api.py
HN fields/search: https://hn.algolia.com/api and https://github.com/algolia/hn-search

Scores cover only observed Hugging Face votes and HN stories. They are neither
research quality nor whole-web popularity. Missing metrics remain unknown.
"""

from datetime import datetime, timezone
import math
import re
from urllib.parse import quote, urlencode

import researchdesk_offline as store


SCOPE = 'Observed Hugging Face paper votes/comments and matching Hacker News stories only; not research quality or whole-web popularity.'
FORMULA = 'log1p(hf_upvotes) + log1p(hn_points) + 0.5*log1p(hf_comments) + 0.5*log1p(hn_comments); missing metrics omitted'


def _instant(value):
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        raise ValueError('Attention dates require an explicit date or timestamp')
    if parsed.tzinfo is None:
        raise ValueError('Attention timestamp requires timezone')
    return parsed.astimezone(timezone.utc)


def _count(value):
    # Treat impossible/unbounded counters as schema failures, not a huge score.
    return value if type(value) is int and 0 <= value <= 1_000_000_000_000 else None


def _observation(provider, url, observed_at):
    return {'provider': provider, 'request_url': url, 'source_url': url,
            'observed_at': observed_at, 'status': 'unknown', 'metrics': {},
            'response_sha256': None}


def _response(observation, response):
    if not isinstance(response, dict) or not isinstance(response.get('json'), dict):
        raise ValueError('Expected JSON object')
    observation['observed_at'] = response.get('fetched_at') or observation['observed_at']
    digest = response.get('sha256')
    if isinstance(digest, str) and re.fullmatch(r'[0-9a-f]{64}', digest):
        observation['response_sha256'] = digest
        observation['digest_scope'] = 'response_body'
    else:
        observation['response_sha256'] = store.digest(response['json'])
        observation['digest_scope'] = 'parsed_json'
    return response['json']


def _huggingface(observation, payload, identifier):
    paper = payload.get('paper') if isinstance(payload.get('paper'), dict) else {}
    if (payload.get('id') or paper.get('id')) != identifier:
        raise ValueError('HF paper identity mismatch')
    upvotes = _count(paper.get('upvotes', payload.get('upvotes')))
    comments = _count(payload.get('numComments'))
    observation.update(source_url='https://huggingface.co/papers/' + identifier,
                       metrics={'upvotes': upvotes, 'comments': comments},
                       status='observed' if upvotes is not None and comments is not None else
                              'partial' if upvotes is not None or comments is not None else 'unknown')
    if observation['status'] != 'observed':
        observation['reason'] = 'missing_or_invalid_metrics'
    return [(upvotes, 1.0), (comments, 0.5)]


def _hackernews(observation, payload, keys, start, end):
    hits = payload.get('hits')
    if not isinstance(hits, list):
        raise ValueError('HN response lacks hits')
    stories, seen, unknown = [], set(), 0
    for hit in hits[:10]:
        if not isinstance(hit, dict):
            continue
        try:
            matching = keys.intersection(store.identities({'source_url': hit.get('url')}))
        except (store.OfflineError, ValueError, TypeError):
            continue
        if not matching:
            continue
        timestamp, identifier = hit.get('created_at_i'), hit.get('objectID')
        if type(timestamp) is not int or not isinstance(identifier, str) or not identifier.isdigit():
            unknown += 1
            continue
        if not start.timestamp() <= timestamp < end.timestamp() or identifier in seen:
            continue
        seen.add(identifier)
        stories.append({'source_url': 'https://news.ycombinator.com/item?id=' + identifier,
                        'original_url': hit['url'], 'created_at_i': timestamp,
                        'points': _count(hit.get('points')), 'comments': _count(hit.get('num_comments'))})
    points = [story['points'] for story in stories if story['points'] is not None]
    comments = [story['comments'] for story in stories if story['comments'] is not None]
    # An empty valid exact-match search is an observation about this bounded
    # query, never proof that nobody discussed or read the original elsewhere.
    no_matches = not stories and not unknown
    metrics = {'points': sum(points) if points else 0 if no_matches else None,
               'comments': sum(comments) if comments else 0 if no_matches else None,
               'matching_stories': len(stories)}
    complete = not unknown and all(story['points'] is not None and story['comments'] is not None
                                   for story in stories)
    observation.update(metrics=metrics, stories=stories,
                       status='no_matching_story' if no_matches else 'observed' if complete else
                              'partial' if points or comments else 'unknown',
                       search_complete=False, inspected_hits=min(len(hits), 10),
                       reported_hits=payload.get('nbHits'),
                       limitation='At most 10 search hits; only exact original identities and in-window stories count. No matching story is not zero global attention.')
    if observation['status'] == 'unknown':
        observation['reason'] = 'missing_or_invalid_matching_story_metrics'
    return [(metrics['points'], 1.0), (metrics['comments'], 0.5)]


def rank_candidates(items, fetcher, policy, start, end):
    """Return scored items and a transparent summary/deferred list.

    max_requests bounds provider lookups; the supplied transport's retry and
    redirect bounds remain independent. No network or model action is hidden.
    The caller persists these observations with its own discovery snapshot.
    """
    if (not isinstance(policy, dict) or policy.get('mode') != 'community_attention'
            or type(policy.get('max_requests')) is not int or not 0 <= policy['max_requests'] <= 1000
            or type(policy.get('min_score')) not in (int, float)
            or not math.isfinite(policy['min_score']) or policy['min_score'] < 0):
        raise store.OfflineError('Community attention policy is invalid')
    start, end = _instant(start), _instant(end)
    if start >= end:
        raise store.OfflineError('Community attention window must increase')
    observed_at = datetime.now(timezone.utc).isoformat()
    ranked, deferred, requests, provider_status = [], [], 0, {}
    for original in items:
        item = dict(original)
        observations, values = [], []
        attention = {'status': 'unknown', 'community_attention_score': None,
                     'observed_at': observed_at, 'scope': SCOPE, 'formula': FORMULA,
                     'providers': observations, 'score_is_observed_lower_bound': True}
        item['attention'] = attention
        metadata = item.get('metadata', {})
        try:
            keys = set(store.identities(metadata))
            published = _instant(metadata.get('published_at') or item.get('published_at'))
        except (store.OfflineError, ValueError, TypeError):
            deferred.append(dict(item, reason='attention_invalid_identity_or_publication_date'))
            continue
        if not start <= published < end:
            deferred.append(dict(item, reason='outside_attention_window'))
            continue
        identifier = next((key[6:] for key in sorted(keys) if key.startswith('arxiv:')), None)
        source_url = ('https://arxiv.org/abs/' + identifier if identifier else
                      store.canonical_url(metadata['source_url']))
        lookups = []
        if item.get('kind') == 'paper' and identifier:
            lookups.append(('huggingface', 'https://huggingface.co/api/papers/' + quote(identifier, safe='')))
        # The arXiv identifier finds abs/pdf/html URL spellings; the exact
        # identity check below still rejects unrelated keyword matches.
        query = urlencode({'query': identifier or source_url, 'restrictSearchableAttributes': 'url',
                           'tags': 'story', 'hitsPerPage': 10,
                           'numericFilters': 'created_at_i>=%d,created_at_i<%d' % (
                               math.ceil(start.timestamp()), math.ceil(end.timestamp()))})
        lookups.append(('hackernews', 'https://hn.algolia.com/api/v1/search?' + query))
        for provider, url in lookups:
            observation = _observation(provider, url, observed_at)
            observations.append(observation)
            if requests >= policy['max_requests']:
                observation['reason'] = 'request_budget_exhausted'
            else:
                requests += 1
                try:
                    payload = _response(observation, fetcher.fetch_json(url))
                    values += (_huggingface(observation, payload, identifier) if provider == 'huggingface'
                               else _hackernews(observation, payload, keys, start, end))
                except Exception as exc:
                    observation.update(status='unknown', reason='provider_fetch_or_schema_failed',
                                       error_type=type(exc).__name__)
            counts = provider_status.setdefault(provider, {})
            counts[observation['status']] = counts.get(observation['status'], 0) + 1
        known = [weight * math.log1p(value) for value, weight in values if value is not None]
        if known:
            attention['community_attention_score'] = round(sum(known), 6)
            attention['status'] = 'observed' if all(observation['status'] in {
                'observed', 'no_matching_story'} for observation in observations) else 'partial'
        if not known:
            deferred.append(dict(item, reason='attention_unknown'))
        elif attention['community_attention_score'] < policy['min_score']:
            deferred.append(dict(item, reason='attention_below_minimum'))
        else:
            ranked.append(item)
    ranked.sort(key=lambda item: (-item['attention']['community_attention_score'],
                                 item['metadata']['source_url']))
    summary = {'mode': 'community_attention', 'status': 'complete' if not any(
        counts.get('unknown', 0) or counts.get('partial', 0) for counts in provider_status.values()) else 'partial',
        'observed_at': observed_at, 'scope': SCOPE, 'formula': FORMULA,
        'requests_used': requests, 'request_limit': policy['max_requests'],
        'request_budget_unit': 'provider_lookup; transport retries/redirects are separately bounded',
        'provider_status': provider_status, 'ranked_count': len(ranked), 'deferred': deferred}
    return ranked, summary
