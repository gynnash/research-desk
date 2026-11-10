#!/usr/bin/env python3
"""One explicitly requested, append-only recovery of a terminal Insight failure.

Original cycle, Research and failed Insight bytes remain immutable. Source
revalidation and an independent new review are mandatory; discovery/Research,
credentials, budgets, writing and publishing are never reset here.
"""

import argparse
import copy
from pathlib import Path
import re
import sys

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import offline as store
import batch as research
import cycle
import insight
import insight_inputs as inputs
import admission


def recovery_id(original_cycle_id):
    if (not isinstance(original_cycle_id, str) or not store.SAFE_ID.fullmatch(original_cycle_id)
            or re.search(r'-recovery-[0-9]+$', original_cycle_id)
            or not store.SAFE_ID.fullmatch(original_cycle_id + '-recovery-1')):
        raise store.OfflineError('恢复只允许原始轮次的一次关联尝试')
    return original_cycle_id + '-recovery-1'


def _base(topic, identifier):
    admission._base(topic, identifier)  # Validate both identities before constructing paths.
    return 'reports/test/%s/cycles/%s' % (topic, identifier)


def _prompt_version(config):
    """Preserve full-text inputs; old recoveries retain their exact v2 upgrade."""
    version = config.get('prompts', {}).get('version')
    if version in {'insight-v1', 'insight-v2'}:
        return 'insight-v2'
    if version in {'insight-v3', 'insight-v4', 'insight-v5', 'insight-v6'}:
        return version
    raise store.OfflineError('恢复原始 Insight 提示词版本无效')


def _original_files(root, topic, original):
    paths = set()
    folders = ['reports/test/%s/%s/%s' % (topic, stage, original)
               for stage in ('cycles', 'research-batches', 'insight-runs')]
    folders += ['%s/test/%s/%s' % (folder, topic, original) for folder in ('insights', 'articles')]
    for folder in folders:
        directory = admission._location(root, folder)
        for path in directory.rglob('*'):
            relative = path.relative_to(root).as_posix()
            admission._location(root, relative)
            if path.is_file():
                if path.suffix not in {'.yaml', '.sha256', '.md'}:
                    raise store.OfflineError('原轮次包含未支持的检查点文件')
                if path.suffix == '.yaml':
                    store.checked_yaml(root, relative)
                if path.suffix == '.sha256':
                    original_file = admission._location(root, relative[:-7])
                    if not original_file.is_file() or path.read_text().strip() != store.digest(original_file.read_bytes()):
                        raise store.OfflineError('原轮次散列侧文件不一致')
                paths.add(relative)
    return admission._hashes(root, paths)


def _original_documents(root, config_path, original):
    current = cycle.load_config(root, config_path)
    recovery_id(original)
    base = _base(current['topic'], original)
    manifest = store.checked_yaml(root, base + '/manifest.yaml')
    config = cycle.load_config(root, config_path, snapshot=manifest.get('config'))
    receipt = store.checked_yaml(root, base + '/receipt.yaml')
    if (config['topic'] != current['topic'] or manifest.get('config') != config or manifest.get('cycle_id') != original
            or manifest.get('topic') != config['topic'] or manifest.get('production_accepted') is not False
            or receipt.get('mode') != 'research_cycle_test' or receipt.get('backend') != 'chatgpt_plan'
            or receipt.get('topic') != config['topic'] or receipt.get('cycle_id') != original
            or receipt.get('status') != 'insight_blocked' or receipt.get('production_accepted') is not False
            or receipt.get('writing_started') is not False or receipt.get('publish_authorized') is not False
            or receipt.get('output_hashes')):
        raise store.OfflineError('仅可恢复配置未变且已终止的 Insight 失败轮次')
    cycle._cached(root, receipt)
    research.verify_notes(root, manifest['protected_notes'])
    old_config = inputs.load_config(root, base + '/configs/insight.yaml')
    old_insight = store.checked_yaml(root, 'reports/test/%s/insight-runs/%s/receipt.yaml' % (config['topic'], original))
    if store.checked_yaml(root, base + '/insight-result.yaml') != old_insight:
        raise store.OfflineError('原 Insight 回执不一致')
    if len(old_config['research_inputs']) != 1:
        raise store.OfflineError('轮次恢复只复用原有唯一 Research 批次')
    entry = old_config['research_inputs'][0]
    research_base, research_manifest, _, old_research, _ = inputs._checked_research(root, old_config, entry)
    if (Path(research_base).name != original or entry['config'] != base + '/configs/research.yaml'
            or store.checked_yaml(root, base + '/research-result.yaml') != old_research
            or old_research.get('status') != 'test_accepted'
            or old_research['reserved_calls'] != old_research['completed_calls']
            or old_insight['reserved_calls'] != old_insight['completed_calls']
            or receipt.get('stages') != {
                'research': {'status': old_research['status'], 'reserved_calls': old_research['reserved_calls']},
                'insight': {'status': old_insight['status'], 'reserved_calls': old_insight['reserved_calls']}}
            or receipt.get('reserved_calls') != old_research['reserved_calls'] + old_insight['reserved_calls']):
        raise store.OfflineError('原请求账本存在未知结果或阶段用量不一致')
    research.verify_notes(root, research_manifest['protected_notes'])
    return config, manifest, receipt, old_config, old_insight


def make_request(root, config_path, original_cycle_id):
    """Build a reviewable request; caller must explicitly authorize and save it."""
    root = Path(root).resolve()
    config, _, receipt, old_config, old_insight = _original_documents(root, config_path, original_cycle_id)
    original_base = _base(config['topic'], original_cycle_id)
    cap = old_insight.get('effective_month_max_calls')
    if type(cap) is not int or cap < 2:
        raise store.OfflineError('原月度预算记录无效')
    return {'schema_version': 1, 'mode': 'linked_insight_recovery_request',
        'topic': config['topic'], 'original_cycle_id': original_cycle_id,
        'recovery_id': recovery_id(original_cycle_id), 'config_path': config['_config_path'],
        'config_sha256': config['_config_sha256'],
        'original_receipt_sha256': store.digest((root / original_base / 'receipt.yaml').read_bytes()),
        'original_files': _original_files(root, config['topic'], original_cycle_id),
        'original_reserved_calls': receipt['reserved_calls'],
        'max_calls_per_cycle': config['budget']['max_calls_per_cycle'],
        'max_new_calls': 4, 'max_revisions': 1, 'month_max_calls': cap,
        'prompt_version': _prompt_version(old_config), 'writing_started': False, 'publish_authorized': False}


def requested(root, config_path, original_cycle_id):
    """No request is ordinary replay; a mismatching explicit request fails closed."""
    root = Path(root).resolve()
    recovery_id(original_cycle_id)
    path = admission._location(root, 'config/recoveries/%s.yaml' % original_cycle_id)
    if not path.exists():
        return None
    expected = make_request(root, config_path, original_cycle_id)
    if store.load_yaml(path) != expected:
        raise store.OfflineError('显式恢复请求与原配置、失败回执或原始检查点不一致')
    return expected['recovery_id']


def _new_config(root, topic, original):
    value = copy.deepcopy(store.checked_yaml(root, _base(topic, original) + '/configs/insight.yaml'))
    value['prompts']['version'] = _prompt_version(value)
    value['budget']['max_calls'] = 4
    value['budget']['max_revisions'] = 1
    return value


def _compact(bundle):
    result = {key: bundle[key] for key in ('topic', 'research_context', 'provenance', 'input_fingerprint')}
    result['evidence'] = [{key: value for key, value in record.items() if key not in {'text', 'original_material'}}
                          for record in bundle['evidence']]
    return result



def _original_compact(root, config, manifest):
    """Reconstruct offline evidence from pinned originals, never trust a cache.

    Original material is refetched and request-bound before execution. The
    publisher cannot refetch it, but can independently derive every retained
    identity, coverage, claim and history field from the immutable originals.
    """
    records = []
    for entry in config['research_inputs']:
        base, _, _, receipt, _ = inputs._checked_research(root, config, entry)
        for item in receipt['items']:
            if 'item_keys' in entry and item['key'] not in entry['item_keys']:
                continue
            plan = store.checked_yaml(root, '%s/items/%s/candidate.yaml' % (base, item['key']))
            candidate = plan['candidate']
            checkpoint = store.checked_yaml(root, '%s/items/%s/checkpoints/research-%s.yaml' % (
                base, item['key'], item['revision_count']))
            result = research.parse_result(checkpoint['result']['text'])
            source_id = candidate['source_id']
            url = candidate['metadata']['source_url']
            if candidate['kind'] == 'paper' and candidate['metadata'].get('arxiv_id'):
                url = 'https://arxiv.org/abs/' + candidate['metadata']['arxiv_id'] + candidate['metadata']['source_version']
            records.append({'id': 'R%s' % (len(records) + 1), 'origin': 'reviewed_research',
                'path': item['report_path'], 'sha256': item['report_sha256'],
                'source_ids': [source_id], 'source_id': source_id, 'source_url': url, 'source_urls': [url],
                'coverage': candidate['evidence']['coverage'], 'identity_keys': candidate['identity_keys'],
                'source_identities': [{'source_id': source_id, 'identity_keys': candidate['identity_keys']}],
                'independently_reviewed': True, 'can_support_original_facts': True,
                'metadata': candidate['metadata'], 'research_summary': result['summary'],
                'research_claims': result['claims'], 'research_limitations': result['limitations'],
                'locators': candidate['evidence']['locators']})
            if candidate['evidence'].get('reading_profile'):
                records[-1].update(reading_scope=research.reading_scope(candidate),
                                   acquisition_attempts=candidate.get('acquisition_attempts', []))
    historical, historical_provenance = inputs._historical_evidence(root, config)
    if historical_provenance != manifest['provenance']['historical_inputs']:
        raise store.OfflineError('历史证明与原失败轮次不一致')
    return _compact({'topic': config['topic'], 'research_context': {'name': config['topic_name'],
        'description': config['topic_description'], 'scope': config['topic_scope'], 'keywords': config['topic_keywords']},
        'evidence': records + historical, 'provenance': manifest['provenance'],
        'input_fingerprint': manifest['input_fingerprint']})


def binding(root, topic, identifier):
    relative = _base(topic, identifier) + '/recovery.yaml'
    return {'path': relative, 'sha256': store.digest(admission._location(root, relative).read_bytes())}


def verify_if_present(root, topic, identifier, bundle=None, config=None, auth=None):
    relative = _base(topic, identifier) + '/recovery.yaml'
    root = Path(root).resolve()
    if admission._location(root, relative).exists():
        return verify_lineage(root, topic, identifier, bundle=bundle, config=config, auth=auth)
    manifest_path = 'reports/test/%s/insight-runs/%s/manifest.yaml' % (topic, identifier)
    if admission._location(root, manifest_path).exists():
        if store.checked_yaml(root, manifest_path).get('recovery') is not None:
            raise store.OfflineError('关联 Insight 缺失恢复记录，不能降级为普通轮次')
    if identifier.endswith('-recovery-1'):
        original = identifier[:-len('-recovery-1')]
        request_path = admission._location(root, 'config/recoveries/%s.yaml' % original)
        if request_path.is_file() and store.load_yaml(request_path).get('recovery_id') == identifier:
            raise store.OfflineError('显式恢复请求缺失对应关联记录')
    return None


def verify_lineage(root, topic, identifier, bundle=None, config=None, auth=None):
    """Offline verifiable lineage, including interrupted/blocked new attempts."""
    root = Path(root).resolve()
    base = _base(topic, identifier)
    value = store.checked_yaml(root, base + '/recovery.yaml')
    original = value.get('original_cycle_id')
    if identifier != recovery_id(original) or value.get('topic') != topic:
        raise store.OfflineError('恢复身份与原始轮次不一致')
    request_path = 'config/recoveries/%s.yaml' % original
    request = make_request(root, value['config_path'], original)
    if requested(root, value['config_path'], original) != identifier:
        raise store.OfflineError('恢复请求不存在')
    loaded, _, old_cycle, old_config, _ = _original_documents(root, value['config_path'], original)
    old_base = 'reports/test/%s/insight-runs/%s' % (topic, original)
    old_manifest = store.checked_yaml(root, old_base + '/manifest.yaml')
    expected_compact = _original_compact(root, old_config, old_manifest)
    if value['verification_bundle'] != expected_compact:
        raise store.OfflineError('恢复离线证据投影与受保护原始资料不一致')
    source_bundle = bundle if bundle is not None else expected_compact
    if (source_bundle['input_fingerprint'] != old_manifest.get('input_fingerprint')
            or source_bundle['provenance'] != old_manifest.get('provenance')
            or _compact(source_bundle) != value['verification_bundle']):
        raise store.OfflineError('恢复必须使用与失败轮次完全相同的原文和历史证据')
    full = all(('original_material' in item if item['origin'] == 'reviewed_research' else 'text' in item)
               for item in source_bundle['evidence'])
    _, old_receipt, _, _ = admission._insight_proof(root, old_config, source_bundle, original, full, allow_failure=True)
    research.verify_notes(root, old_manifest['protected_notes'])
    final_revision = old_receipt['revision_count']
    expected = {'schema_version': 1, 'mode': 'linked_insight_recovery', 'topic': topic,
        'original_cycle_id': original, 'recovery_id': identifier,
        'config_path': loaded['_config_path'], 'request_path': request_path,
        'request_sha256': store.digest((root / request_path).read_bytes()),
        'original_files': request['original_files'], 'original_reserved_calls': old_cycle['reserved_calls'],
        'max_calls_per_cycle': request['max_calls_per_cycle'], 'max_new_calls': 4,
        'month_max_calls': request['month_max_calls'], 'prompt_version': _prompt_version(old_config),
        'original_failure_sha256': store.digest((root / old_base / 'receipt.yaml').read_bytes()),
        'original_candidate_sha256': store.digest((root / old_base / ('checkpoints/generation-%s.yaml' % final_revision)).read_bytes()),
        'original_reviewer_sha256': store.digest((root / old_base / ('checkpoints/review-%s.yaml' % final_revision)).read_bytes()),
        'verification_bundle': _compact(source_bundle), 'authorization': old_manifest['authorization'],
        'writing_started': False, 'publish_authorized': False}
    if value != expected:
        raise store.OfflineError('恢复关联记录与原始证明不一致')
    new_path = base + '/configs/insight.yaml'
    if store.checked_yaml(root, new_path) != _new_config(root, topic, original):
        raise store.OfflineError('恢复配置不得更换资料、模型或放宽原有边界')
    current_config = inputs.load_config(root, new_path)
    if config is not None and config != current_config:
        raise store.OfflineError('Insight 未绑定恢复配置')
    if auth is not None and auth != old_manifest['authorization']:
        raise store.OfflineError('恢复不可更换原会员账户')
    new_base = 'reports/test/%s/insight-runs/%s' % (topic, identifier)
    if admission._location(root, new_base + '/manifest.yaml').exists():
        new_manifest = store.checked_yaml(root, new_base + '/manifest.yaml')
        if new_manifest.get('recovery') != binding(root, topic, identifier):
            raise store.OfflineError('Insight 检查点缺少恢复关联散列')
        events = store.read_events(root, new_base)
        # Incomplete reservations remain exportable but can never be resent.
        insight.verify_ledger(root, new_base, events, new_manifest, source_bundle,
                              prompt_version=current_config['prompts']['version'])
        if (any(event.get('role') == 'format_review' for event in events)
                or old_cycle['reserved_calls'] + sum(e['type'] == 'call_reserved' for e in events) > request['max_calls_per_cycle']):
            raise store.OfflineError('恢复请求超过原轮次累计预算或允许角色')
    return value


def check_room(root, config, events, count, recovery_binding):
    parts = Path(recovery_binding.get('path', '')).parts
    if len(parts) != 6 or parts[:2] != ('reports', 'test') or parts[3] != 'cycles' or parts[5] != 'recovery.yaml':
        raise store.OfflineError('恢复预算关联路径无效')
    value = verify_lineage(root, config['topic'], parts[4], config=config)
    if recovery_binding != binding(root, config['topic'], parts[4]):
        raise store.OfflineError('恢复关联散列已变化')
    new_calls = sum(e['type'] == 'call_reserved' for e in events)
    monthly, cap = research.monthly_budget(root, config)
    if (new_calls + count > value['max_new_calls']
            or value['original_reserved_calls'] + new_calls + count > value['max_calls_per_cycle']
            or monthly + count > min(cap, value['month_max_calls'])):
        raise store.OfflineError('恢复超过新调用、原轮次累计或共享月度预算')


def run(root, config_path, original_cycle_id, client=None, fetcher=None, fail_after=None):
    root = Path(root).resolve()
    initial = cycle.load_config(root, config_path)
    identifier = recovery_id(original_cycle_id)
    if fail_after not in (None, 'after_review'):
        raise store.OfflineError('恢复断点只允许新独立审阅之后')
    fetcher = cycle.CycleFetcher(fetcher)
    with cycle.cycle_lock(root, initial['topic']):
        if requested(root, config_path, original_cycle_id) != identifier:
            raise store.OfflineError('终态恢复需要明确登记的单次请求')
        config, _, original_receipt, old_config, _ = _original_documents(root, config_path, original_cycle_id)
        topic, base = config['topic'], _base(config['topic'], identifier)
        # Always revalidate sources, even on a retry; never reuse changed material.
        bundle = inputs.prepare_bundle(root, old_config, fetcher=fetcher)
        _, old_receipt, old_manifest, old_base = admission._insight_proof(
            root, old_config, bundle, original_cycle_id, True, allow_failure=True)
        request_path = 'config/recoveries/%s.yaml' % original_cycle_id
        request = store.load_yaml(root / request_path)
        revision = old_receipt['revision_count']
        value = {'schema_version': 1, 'mode': 'linked_insight_recovery', 'topic': topic,
            'original_cycle_id': original_cycle_id, 'recovery_id': identifier,
            'config_path': config['_config_path'], 'request_path': request_path,
            'request_sha256': store.digest((root / request_path).read_bytes()),
            'original_files': request['original_files'], 'original_reserved_calls': original_receipt['reserved_calls'],
            'max_calls_per_cycle': request['max_calls_per_cycle'], 'max_new_calls': 4,
            'month_max_calls': request['month_max_calls'], 'prompt_version': _prompt_version(old_config),
            'original_failure_sha256': store.digest((root / old_base / 'receipt.yaml').read_bytes()),
            'original_candidate_sha256': store.digest((root / old_base / ('checkpoints/generation-%s.yaml' % revision)).read_bytes()),
            'original_reviewer_sha256': store.digest((root / old_base / ('checkpoints/review-%s.yaml' % revision)).read_bytes()),
            'verification_bundle': _compact(bundle), 'authorization': old_manifest['authorization'],
            'writing_started': False, 'publish_authorized': False}
        store.save_yaml(root, base + '/recovery.yaml', value)
        new_path = base + '/configs/insight.yaml'
        store.save_yaml(root, new_path, _new_config(root, topic, original_cycle_id))
        verify_lineage(root, topic, identifier, bundle=bundle)
        receipt_path = base + '/receipt.yaml'
        if admission._location(root, receipt_path).exists():
            return cycle._cached(root, store.checked_yaml(root, receipt_path))
        if client is None:
            from membership import MembershipClient
            client = MembershipClient(root=root)
        result = insight.run(root, new_path, identifier, client, fetcher=fetcher, fail_after=fail_after)
        result = {key: item for key, item in result.items() if key != 'cached'}
        store.save_yaml(root, base + '/insight-result.yaml', result)
        lineage = verify_lineage(root, topic, identifier, bundle=bundle)
        paths = set(lineage['original_files']) | {request_path, base + '/recovery.yaml', new_path,
            base + '/insight-result.yaml', 'reports/test/%s/insight-runs/%s/receipt.yaml' % (topic, identifier)}
        status = 'completed' if original_receipt['discovery_complete'] else 'partial'
        receipt = {'schema_version': 1, 'mode': 'research_cycle_test', 'backend': 'chatgpt_plan',
            'topic': topic, 'cycle_id': identifier, 'original_cycle_id': original_cycle_id,
            'status': status if result['status'] == 'test_accepted' else 'insight_blocked',
            'window_start': original_receipt['window_start'], 'window_end': original_receipt['window_end'],
            'discovery_complete': original_receipt['discovery_complete'], 'source_status': original_receipt['source_status'],
            'stages': {'research': original_receipt['stages']['research'],
                       'insight': {'status': result['status'], 'reserved_calls': result['reserved_calls']}},
            'reserved_calls': original_receipt['reserved_calls'] + result['reserved_calls'],
            'new_reserved_calls': result['reserved_calls'], 'pending_count': original_receipt['pending_count'],
            'input_hashes': admission._hashes(root, paths), 'output_hashes': result['output_hashes'],
            'production_accepted': False, 'writing_started': False, 'publish_authorized': False}
        store.save_yaml(root, receipt_path, receipt)
        return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--cycle-id', required=True, help='Original failed cycle ID')
    parser.add_argument('--profile', type=Path)
    parser.add_argument('--fail-after', choices=['after_review'])
    args = parser.parse_args()
    try:
        client = None
        if args.profile:
            from membership import MembershipClient
            client = MembershipClient(args.profile, args.root)
        result = run(args.root, args.config, args.cycle_id, client=client, fail_after=args.fail_after)
    except store.SimulatedInterruption:
        return 3
    except Exception as exc:
        print('关联恢复停止：' + type(exc).__name__, file=sys.stderr)
        return 2
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False))
    return 0 if result['status'] in {'completed', 'partial'} else 1


if __name__ == '__main__':
    sys.exit(main())
