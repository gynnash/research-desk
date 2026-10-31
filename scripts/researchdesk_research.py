#!/usr/bin/env python3
"""Read a completed collection and produce independently reviewed per-source summaries.

No discovery, source fetching, Insight, Writing, scheduling, or Git operations
live here. Existing batch checkpoints retain budget reservations and resume.
"""

import argparse
from pathlib import Path
import posixpath
import sys

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import researchdesk_archive as archive
import researchdesk_batch as batch
import researchdesk_cycle as cycle
import researchdesk_offline as store


class _NoSourceFetching:
    def fetch(self, url):
        raise store.OfflineError('逐篇研究只读取 collection 原文，不重新采集')

    fetch_pdf = fetch
    fetch_json = fetch


def _verify_hashes(root, hashes):
    if not isinstance(hashes, dict):
        raise store.OfflineError('采集回执缺少固定文件散列')
    for relative, expected in hashes.items():
        path = store.safe_path(root, relative)
        if not path.is_file() or store.digest(path.read_bytes()) != expected:
            raise store.OfflineError('采集文件已变化，保留原文并停止: ' + relative)


def _collection(root, config_path, config, cycle_id):
    """Validate every fixed original before authorization or any model call."""
    base = cycle.base_path(config, cycle_id)
    receipt_path = base + '/collection.yaml'
    if not store.safe_path(root, receipt_path).is_file():
        raise store.OfflineError(
            '尚无该批次的采集结果。请先执行 python3 -B scripts/researchdesk_cycle.py collect'
            ' --config %s --cycle-id %s' % (config['_config_path'], cycle_id))
    receipt = store.checked_yaml(root, receipt_path)
    if (receipt.get('mode') != 'collection_only' or receipt.get('topic') != config['topic']
            or receipt.get('cycle_id') != cycle_id or receipt.get('status') not in {'collected', 'empty'}
            or not isinstance(receipt.get('records'), list)):
        raise store.OfflineError('采集回执身份或完成状态无效')
    _verify_hashes(root, receipt.get('input_hashes'))
    _verify_hashes(root, receipt.get('output_hashes'))
    manifest = store.checked_yaml(root, base + '/manifest.yaml')
    if (manifest.get('topic') != config['topic'] or manifest.get('cycle_id') != cycle_id
            or manifest.get('mode') != 'research_cycle_test'
            or manifest.get('production_accepted') is not False):
        raise store.OfflineError('采集批次配置不属于当前主题或轮次')
    config = cycle.load_config(root, config_path, snapshot=manifest['config'])
    if manifest['config'] != config:
        raise store.OfflineError('采集批次已绑定配置，不可替换研究上下文')
    batch.verify_notes(root, manifest['protected_notes'])
    index_path = 'collection/%s/%s/manifest.yaml' % (config['topic'], cycle_id)
    if receipt.get('collection_manifest_path') != index_path:
        raise store.OfflineError('该批次尚未使用 collection 布局，请先完成新批次采集')
    if not store.safe_path(root, index_path).is_file():
        raise store.OfflineError('collection 索引未完成，请用相同 cycle-id 补跑 collect')
    index = store.checked_yaml(root, index_path)
    if (index.get('mode') != 'collection_index' or index.get('topic') != config['topic']
            or index.get('cycle_id') != cycle_id or index.get('receipt_path') != receipt_path
            or index.get('receipt_sha256') != store.digest(store.safe_path(root, receipt_path).read_bytes())
            or index.get('records') != receipt['records']):
        raise store.OfflineError('collection 索引与已完成采集回执不一致')
    records = receipt['records']
    if (len(records) > min(5, config['discovery']['max_documents'])
            or (receipt['status'] == 'empty') != (not records)):
        raise store.OfflineError('采集条数或空批次状态无效')
    selection = store.checked_yaml(root, base + '/selection.yaml')
    selected = {item['source']['id']: item['source'] for item in selection['candidates']}
    keys = [record.get('key') for record in records if isinstance(record, dict)]
    if len(keys) != len(records) or len(keys) != len(set(keys)) or set(keys) != set(selected):
        raise store.OfflineError('采集索引与固定选材不一致')
    sources = []
    for record in records:
        key, source = record['key'], selected[record['key']]
        expected_plan = 'reports/test/%s/research-batches/%s/items/%s/candidate.yaml' % (
            config['topic'], cycle_id, key)
        original = 'collection/%s/%s/items/%s/original' % (config['topic'], cycle_id, key)
        if (record.get('candidate_path') != expected_plan
                or record.get('original_path') != original + '.yaml'
                or record.get('original_markdown_path') != original + '.md'):
            raise store.OfflineError('候选必须绑定同主题同批次 collection 原文')
        plan = store.checked_yaml(root, expected_plan)
        candidate, material, _ = archive.load(root, plan['candidate'], source=source, config=config)
        if (plan.get('action') not in {'research', 'update'}
                or plan.get('material_sha256') != store.digest(material.encode())
                or candidate.get('topic') != config['topic'] or candidate.get('key') != key
                or candidate['evidence']['coverage'] != 'full_text'
                or candidate['archive']['path'] != record['original_path']
                or candidate['archive']['markdown_path'] != record['original_markdown_path']
                or candidate['content_hash'] != record.get('content_hash')):
            raise store.OfflineError('候选未绑定完整原文，停止模型调用')
        sources.append(source)
    return config, receipt, sources


def _summary_path(topic, cycle_id, key):
    return 'summary/%s/%s/%s.md' % (topic, cycle_id, key)


def _verify_summaries(root, batch_base, records, topic, cycle_id):
    """Protect prior published summaries before even constructing the client."""
    for record in records:
        binding_path = '%s/items/%s/summary.yaml' % (batch_base, record['key'])
        expected_path = _summary_path(topic, cycle_id, record['key'])
        if store.safe_path(root, binding_path).exists():
            binding = store.checked_yaml(root, binding_path)
            if binding.get('path') != expected_path:
                raise store.OfflineError('总结输出绑定不属于当前资料')
            _verify_hashes(root, {expected_path: binding.get('sha256')})
        elif store.safe_path(root, expected_path).exists():
            # A process may stop between writing Markdown and its binding.
            # Reconstruct the exact completed result before allowing another
            # item to spend model budget; existence of result.yaml is not proof
            # that this unbound Markdown remains unmodified.
            prefix = '%s/items/%s/' % (batch_base, record['key'])
            result_path = prefix + 'result.yaml'
            if not store.safe_path(root, result_path).is_file():
                raise store.OfflineError('总结位置已有人工文件，保留内容并停止: ' + expected_path)
            manifest = store.checked_yaml(root, batch_base + '/manifest.yaml')
            events = store.read_events(root, batch_base)
            batch.verify_events(root, batch_base, events, manifest)
            finished = [event for event in events
                        if event.get('type') == 'item_finished' and event.get('key') == record['key']]
            result = store.checked_yaml(root, result_path)
            if (len(finished) != 1 or finished[0].get('result_path') != result_path
                    or result.get('status') != 'test_accepted'):
                raise store.OfflineError('未绑定总结缺少审阅通过的完成记录，保留内容并停止')
            revision = result['revision_count']
            candidate = store.checked_yaml(root, prefix + 'candidate.yaml')['candidate']
            research = batch.parse_result(store.checked_yaml(root,
                prefix + 'checkpoints/research-%s.yaml' % revision)['result']['text'])
            review = batch.parse_result(store.checked_yaml(root,
                prefix + 'checkpoints/review-%s.yaml' % revision)['result']['text'])
            expected = _render_summary(manifest, candidate, research, review, result,
                                       record['original_markdown_path'], cycle_id)
            if store.safe_path(root, expected_path).read_bytes() != expected.encode('utf-8'):
                raise store.OfflineError('未绑定总结已被人工修改，保留内容并停止: ' + expected_path)


def _render_summary(manifest, candidate, research, review, result, original_path, cycle_id):
    if review.get('decision') != 'pass' or candidate['evidence']['coverage'] != 'full_text':
        raise store.OfflineError('只有独立审阅通过的完整原文研究可写入 summary')
    metadata = candidate['metadata']
    source_url = metadata['source_url']
    if candidate['kind'] == 'paper' and metadata.get('arxiv_id') and metadata.get('source_version'):
        source_url = 'https://arxiv.org/abs/' + metadata['arxiv_id'] + metadata['source_version']
    header = {
        'schema_version': 1, 'kind': 'research_summary', 'topic': candidate['topic'], 'cycle_id': cycle_id,
        'title': metadata['title'], 'source_url': source_url, 'source_id': candidate['source_id'],
        'collection_original': original_path, 'coverage': 'full_text', 'review_status': 'passed',
        'research_model': manifest['models']['research'], 'review_model': manifest['models']['review'],
        'generated_at': result['finished_at'],
    }
    article = batch.render_article(manifest, candidate, research, review,
                                   result['revision_count'], test_notice=False)
    summary_dir = posixpath.dirname(_summary_path(candidate['topic'], cycle_id, candidate['key']))
    local_link = posixpath.relpath(original_path, summary_dir)
    return ('---\n' + yaml.safe_dump(header, allow_unicode=True, sort_keys=False).rstrip()
            + '\n---\n\n' + article
            + '\n- [阅读已采集的完整原文](%s)。\n' % local_link)


def run(root, config_path, cycle_id, client=None, profile=None, fail_after=None):
    root = Path(root).resolve()
    initial = cycle.load_config(root, config_path)
    cycle.base_path(initial, cycle_id)
    with cycle.cycle_lock(root, initial['topic']):
        config, collection, sources = _collection(root, config_path, initial, cycle_id)
        topic = config['topic']
        if not sources:
            return {'schema_version': 1, 'mode': 'research_only', 'topic': topic,
                    'cycle_id': cycle_id, 'status': 'empty', 'items': [], 'model_calls': 0,
                    'discovery_status': collection.get('discovery_status'),
                    'insight_started': False, 'writing_started': False, 'summary_paths': []}
        batch_base = 'reports/test/%s/research-batches/%s' % (topic, cycle_id)
        _verify_summaries(root, batch_base, collection['records'], topic, cycle_id)
        budget = config['budget']
        monthly = batch.membership_monthly_limit(root) or 10
        per_item = 2 * (budget['max_revisions'] + 1)
        research_config = {
            'schema_version': 1, 'mode': 'research_batch_test', 'backend': config['backend'],
            'topic': topic, 'topics_file': config['topics_file'],
            'models': {role: config['models'][role] for role in ('research', 'review')},
            'budget': {'max_documents': len(sources), 'max_calls_per_item': per_item,
                       'max_calls_per_batch': min(budget['research_max_calls'], len(sources) * per_item, monthly),
                       'month_max_calls': monthly,
                       **{key: budget[key] for key in (
                           'max_input_chars', 'max_output_chars', 'timeout_seconds', 'max_revisions')}},
            'prompts': {'version': 'research-batch-v4'}, 'sources': sources,
        }
        research_path = cycle.base_path(config, cycle_id) + '/configs/research.yaml'
        store.save_yaml(root, research_path, research_config)
        if client is None:
            from researchdesk_membership import MembershipClient, DEFAULT_PROFILE
            client = MembershipClient(profile or DEFAULT_PROFILE, root)
        receipt = batch.run(root, research_path, cycle_id, client,
                            fetcher=_NoSourceFetching(), fail_after=fail_after)
        # Verify bound collection again before exposing any generated prose.
        _collection(root, config_path, initial, cycle_id)
        manifest = store.checked_yaml(root, batch_base + '/manifest.yaml')
        records = {record['key']: record for record in collection['records']}
        items, paths = [], []
        for result in receipt['items']:
            item = dict(result)
            if result['status'] == 'test_accepted':
                key, revision = result['key'], result['revision_count']
                prefix = '%s/items/%s/' % (batch_base, key)
                candidate = store.checked_yaml(root, prefix + 'candidate.yaml')['candidate']
                research = batch.parse_result(store.checked_yaml(root,
                    prefix + 'checkpoints/research-%s.yaml' % revision)['result']['text'])
                review = batch.parse_result(store.checked_yaml(root,
                    prefix + 'checkpoints/review-%s.yaml' % revision)['result']['text'])
                path = _summary_path(topic, cycle_id, key)
                text = _render_summary(manifest, candidate, research, review, result,
                                       records[key]['original_markdown_path'], cycle_id)
                sha = store.create(root, path, text)
                store.save_yaml(root, prefix + 'summary.yaml', {
                    'path': path, 'sha256': sha, 'source_id': candidate['source_id'],
                    'research_result_path': prefix + 'result.yaml',
                    'research_result_sha256': store.digest(store.safe_path(root, prefix + 'result.yaml').read_bytes()),
                })
                item.update(status='summarized', summary_path=path, summary_sha256=sha)
                paths.append(path)
            items.append(item)
        status = ('complete' if len(paths) == len(sources) else 'partial' if paths else 'failed')
        return {'schema_version': 1, 'mode': 'research_only', 'topic': topic, 'cycle_id': cycle_id,
                'status': status, 'items': items, 'summary_paths': paths,
                'research_receipt_path': receipt['receipt_path'],
                'reserved_calls': receipt['reserved_calls'], 'completed_calls': receipt['completed_calls'],
                'cached': receipt.get('cached', False), 'discovery_status': collection.get('discovery_status'),
                'insight_started': False, 'writing_started': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--config', type=Path, default=Path('config/cycles/default.yaml'))
    parser.add_argument('--cycle-id', required=True)
    parser.add_argument('--profile', type=Path)
    args = parser.parse_args(argv)
    try:
        result = run(args.root, args.config, args.cycle_id, profile=args.profile)
    except store.SimulatedInterruption as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except store.OfflineError as exc:
        print('逐篇研究停止：' + str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print('逐篇研究停止：%s' % type(exc).__name__, file=sys.stderr)
        return 2
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False))
    return 0 if result['status'] in {'complete', 'empty'} else 1


if __name__ == '__main__':
    raise SystemExit(main())
