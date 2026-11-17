"""Collection -> detailed per-source summary; all sources/models are fictional."""

import json
from pathlib import Path
import sys
import unittest
from unittest import mock

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import batch
import cycle
import membership
import note_paths as notes
import offline as store
import research
import writing
import test_research_batch as fixtures
from test_collection_only import CollectionFetcher, FixedClock
from test_research_depth import detailed_response


class ResearchEntry(unittest.TestCase):
    def setUp(self):
        fixtures.ConfigDrivenResearchBatch.setUp(self)
        self.config = yaml.safe_load((fixtures.REPOSITORY / 'config/cycles/default.yaml').read_text())
        self.config['topic'] = 'agent_memory'
        self.config['models'] = {
            'research': 'fixture-research', 'insight': 'fixture-research', 'review': 'fixture-review'}
        self.config['discovery'].update(max_documents=2, max_per_source=1, max_candidates=20)
        self.config['discovery']['sources'] = [
            {'id': 'arxiv', 'adapter': 'arxiv', 'entry_url': 'https://export.arxiv.org/api/query'},
            {'id': 'letta', 'adapter': 'letta', 'entry_url': 'https://www.letta.com/blog/'}]
        self.config.pop('selection', None)
        (self.root / 'config/research_topics.yaml').write_text(yaml.safe_dump({
            'schema_version': 1, 'topics': {'agent_memory': {
                'name': 'Agent Memory', 'enabled': True, 'description': '虚构离线研究方向。',
                'scope': ['记忆与证据边界'], 'keywords': ['memory']}}}, allow_unicode=True))
        (self.root / 'config/membership_budget.yaml').write_text(yaml.safe_dump({
            'schema_version': 1, 'backend': 'chatgpt_plan', 'month_max_calls': 100}))
        (self.root / 'config/cycles').mkdir(exist_ok=True)
        self.config_path = self.root / 'config/cycles/default.yaml'
        self.config_path.write_text(yaml.safe_dump(self.config, allow_unicode=True, sort_keys=False))
        self.fetcher = CollectionFetcher()
        self.client.research_mutator = lambda result: (result.clear(), result.update(detailed_response()))
        mock.patch.object(cycle, 'datetime', FixedClock).start()
        self.member = mock.patch.object(membership, 'MembershipClient',
            side_effect=AssertionError('No implicit credential access')).start()
        self.insight = mock.patch.object(cycle.insight, 'run',
            side_effect=AssertionError('Research must not start Insight')).start()
        self.writer = mock.patch.object(writing, 'run',
            side_effect=AssertionError('Research must not start Writing')).start()

    def collect(self):
        receipt = cycle.collect_originals(self.root, self.config_path, 'first', fetcher=self.fetcher)
        self.assertEqual(len(receipt['records']), 2)
        self.fetcher.calls.clear()
        return receipt

    def run_research(self, **kwargs):
        return research.run(self.root, self.config_path, 'first', client=self.client, **kwargs)

    def assert_research_only(self):
        self.assertEqual(self.fetcher.calls, [])
        self.member.assert_not_called()
        self.insight.assert_not_called()
        self.writer.assert_not_called()

    def test_collection_to_detailed_reviewed_summaries_and_idempotent_resume(self):
        collection = self.collect()
        self.client.review_decisions = ['revise', 'pass', 'pass']
        result = self.run_research()
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['completed_calls'], 4)
        self.assertEqual(len(result['summary_paths']), 2)
        self.assertFalse(result['insight_started'])
        self.assertFalse(result['writing_started'])
        self.assert_research_only()
        first_generation, first_review = (entry['payload'] for entry in self.client.calls[:2])
        self.assertEqual(first_generation, {key: value for key, value in first_review.items() if key != 'candidate'})
        self.assertEqual(first_generation['coverage'], 'full_text')
        self.assertTrue(any(self.fetcher.blog_tail in entry['payload']['original_material']
                            for entry in self.client.calls))
        originals = {record['key']: record['original_markdown_path'] for record in collection['records']}
        for item in result['items']:
            path = self.root / item['summary_path']
            self.assertEqual(notes.summary_ids(item['summary_path']), ('agent_memory', 'first', item['key']))
            self.assertEqual(path.parent.name, '保存引用为何有助于核对~first')
            self.assertEqual(path.stem, '保存引用为何有助于核对~' + item['key'])
            text = path.read_text()
            metadata = yaml.safe_load(text.split('---', 2)[1])
            self.assertEqual(metadata['topic'], 'agent_memory')
            self.assertEqual(metadata['cycle_id'], 'first')
            self.assertEqual(metadata['coverage'], 'full_text')
            self.assertEqual(metadata['review_status'], 'advisory')
            self.assertEqual(metadata['collection_original'], originals[item['key']])
            self.assertNotIn('TEST', text)
            self.assertIn('## 保存引用为何有助于核对', text)
            self.assertIn('## 证据边界如何贯穿处理流程', text)
            article = text.split('## 资料来源与阅读范围')[0]
            self.assertNotIn('A1', article)
            self.assertIn('[阅读已采集的完整原文](../../../collection/agent_memory/', text)
        before = {path.relative_to(self.root): path.read_bytes()
                  for path in self.root.rglob('*') if path.is_file()}
        cached = self.run_research()
        self.assertTrue(cached['cached'])
        self.assertEqual(len(self.client.calls), 4)
        self.assertEqual(before, {path.relative_to(self.root): path.read_bytes()
                                  for path in self.root.rglob('*') if path.is_file()})

    def test_research_budget_can_allow_100_per_paper_and_batch(self):
        self.config['budget'].update(max_calls_per_cycle=100, research_max_calls=100,
                                     insight_max_calls=100, max_calls_per_item=100)
        self.config_path.write_text(yaml.safe_dump(self.config, allow_unicode=True, sort_keys=False))
        self.collect()
        result = self.run_research()
        self.assertEqual(result['status'], 'complete')
        batch_config = store.checked_yaml(
            self.root, 'reports/test/agent_memory/cycles/first/configs/research.yaml')
        self.assertEqual(batch_config['budget']['max_calls_per_item'], 100)
        self.assertEqual(batch_config['budget']['max_calls_per_batch'], 100)
        self.assertEqual(len(self.client.calls), 4)

    def test_new_batches_use_advisory_review_prompts(self):
        self.collect()
        concise = detailed_response()
        concise['claims'] = concise['claims'][:3]
        self.client.research_mutator = lambda result: (result.clear(), result.update(concise))

        result = self.run_research()

        self.assertEqual(result['status'], 'complete')
        generation, review = batch.instructions_for(batch.ADVISORY_PROMPT)
        self.assertEqual([call['instructions'] for call in self.client.calls], [generation, review] * 2)
        self.assertEqual(len(self.client.calls[1]['payload']['candidate']['claims']), 3)

    def test_resuming_v4_batch_preserves_bound_prompt_and_notes(self):
        self.collect()
        with mock.patch.object(research, 'SUMMARY_PROMPT_VERSION', 'research-batch-v4'):
            first = self.run_research()
        self.assertEqual(first['status'], 'complete')
        config_path = self.root / 'reports/test/agent_memory/cycles/first/configs/research.yaml'
        paths = [config_path, *(self.root / path for path in first['summary_paths'])]
        before = {path: path.read_bytes() for path in paths}

        resumed = self.run_research()

        self.assertTrue(resumed['cached'])
        self.assertEqual(resumed['summary_paths'], first['summary_paths'])
        self.assertEqual(len(self.client.calls), 4)
        self.assertEqual({path: path.read_bytes() for path in paths}, before)

    def test_review_rejection_is_recorded_without_blocking_summaries(self):
        self.collect()
        self.client.review_decisions = ['reject', 'reject']
        infer = self.client.infer

        def reply(model, instructions, input_text, **kwargs):
            response = infer(model, instructions, input_text, **kwargs)
            if 'candidate' in json.loads(input_text) and len(self.client.calls) == 4:
                response['text'] = '审阅只返回了自然语言说明。'
            return response

        self.client.infer = reply
        result = self.run_research()
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(len(result['summary_paths']), 2)
        self.assertEqual([item['status'] for item in result['items']], ['summarized', 'summarized'])
        self.assertIn('审阅结论：reject', (self.root / result['summary_paths'][0]).read_text())
        self.assertIn('审阅只返回了自然语言说明。', (self.root / result['summary_paths'][1]).read_text())
        self.assertEqual(len(self.client.calls), 4)
        self.assert_research_only()

    def test_partial_fields_and_review_add_per_claim_evidence_notes(self):
        self.collect()
        generated = {'summary': 98, 'body': '可阅读的概述', 'limitations': False,
                     'claims': [None, {'text': '待验证的第一条结论', 'kind': 'unknown'},
                                {'text': '引文未支持的第二条结论', 'evidence_ids': ['A1']},
                                {'text': '有依据的第三条结论', 'kind': 'fact', 'evidence_ids': 'A1'}]}
        checked = {'decision': {}, 'coverage_acknowledged': False,
                   'checks': [False, {'claim_index': '2', 'verdict': 'unsupported'},
                              {'claim_index': 3, 'verdict': 'supported', 'evidence_ids': ['A1']}],
                   'issues': [{'reason': '单独保留审阅意见。'}]}

        def infer(model, instructions, input_text, **kwargs):
            payload = json.loads(input_text)
            self.client.calls.append({'payload': payload})
            text = json.dumps(checked if 'candidate' in payload else generated, ensure_ascii=False)
            return {'model': model, 'text': '```json\n' + text + '\n```'}

        self.client.infer = infer
        result = self.run_research()
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['completed_calls'], 4)
        for path in result['summary_paths']:
            summary = (self.root / path).read_text()
            self.assertIn('可阅读的概述', summary)
            self.assertIn('待验证的第一条结论\n\n> 证据提示：没有可定位的证据。', summary)
            self.assertIn('引文未支持的第二条结论\n\n> 证据提示：审阅指出所引证据未支持该结论。', summary)
            self.assertIn('有依据的第三条结论\n\n## 独立审阅意见', summary)
            self.assertIn('单独保留审阅意见。', summary)
        self.assertEqual(self.run_research()['summary_paths'], result['summary_paths'])
        self.assertEqual(len(self.client.calls), 4)

    def test_wrong_overall_generation_shape_fails_before_review(self):
        self.collect()
        self.client.infer = mock.Mock(return_value={'model': 'fixture-research', 'text': '[]'})
        result = self.run_research()
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['summary_paths'], [])
        self.assertEqual(result['completed_calls'], 2)
        self.assertEqual(self.client.infer.call_count, 2)

    def test_missing_collection_and_empty_collection_do_not_construct_membership_client(self):
        with self.assertRaisesRegex(store.OfflineError, '请先执行'):
            research.run(self.root, self.config_path, 'first')
        self.member.assert_not_called()
        snapshot = {'schema_version': 1, 'mode': 'cycle_discovery_test', 'topic': 'agent_memory',
                    'cycle_id': 'first', 'status': 'complete', 'candidates': [], 'deferred': []}
        with mock.patch.object(cycle.discovery, 'discover', return_value=snapshot):
            collection = cycle.collect_originals(self.root, self.config_path, 'first', fetcher=self.fetcher)
        self.assertEqual(collection['status'], 'empty')
        result = research.run(self.root, self.config_path, 'first')
        self.assertEqual(result['status'], 'empty')
        self.assertEqual(result['model_calls'], 0)
        self.assertFalse((self.root / 'summary').exists())
        self.member.assert_not_called()
        self.assertEqual(self.client.calls, [])

    def test_interrupted_research_resumes_completed_item_without_new_fetch_or_duplicate_calls(self):
        self.collect()
        with self.assertRaises(store.SimulatedInterruption):
            self.run_research(fail_after='after_first_item')
        self.assertEqual(len(self.client.calls), 2)
        result = self.run_research()
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(len(self.client.calls), 4)
        self.assertEqual(len(result['summary_paths']), 2)
        self.assert_research_only()

    def test_human_summary_edit_is_preserved_and_stops_before_new_model_calls(self):
        self.collect()
        result = self.run_research()
        path = self.root / result['summary_paths'][0]
        path.write_text(path.read_text() + '\n人工笔记：保留这个判断。\n')
        annotated = path.read_bytes()
        with self.assertRaises(store.OfflineError):
            research.run(self.root, self.config_path, 'first')
        self.member.assert_not_called()
        self.assertEqual(path.read_bytes(), annotated)
        self.assertEqual(len(self.client.calls), 4)

    def test_changed_original_is_rejected_before_model_or_account_access(self):
        collection = self.collect()
        path = self.root / collection['records'][0]['original_markdown_path']
        path.write_text(path.read_text() + '\n人工原文批注。\n')
        changed = path.read_bytes()
        with self.assertRaises(store.OfflineError):
            research.run(self.root, self.config_path, 'first')
        self.member.assert_not_called()
        self.assertEqual(self.client.calls, [])
        self.assertEqual(path.read_bytes(), changed)

    def test_preexisting_unbound_summary_stops_before_calls_and_is_preserved(self):
        collection = self.collect()
        path = self.root / ('summary/agent_memory/first/' + collection['records'][0]['key'] + '.md')
        path.parent.mkdir(parents=True)
        path.write_text('# 我的人工研究笔记\n')
        with self.assertRaisesRegex(store.OfflineError, '人工文件'):
            self.run_research()
        self.assertEqual(path.read_text(), '# 我的人工研究笔记\n')
        self.assertEqual(self.client.calls, [])
        self.member.assert_not_called()

    def test_interrupted_export_checks_unbound_markdown_before_processing_pending_source(self):
        collection = self.collect()
        with self.assertRaises(store.SimulatedInterruption):
            self.run_research(fail_after='after_first_item')
        self.assertEqual(len(self.client.calls), 2)
        base = 'reports/test/agent_memory/research-batches/first'
        record = collection['records'][0]
        prefix = '%s/items/%s/' % (base, record['key'])
        manifest = store.checked_yaml(self.root, base + '/manifest.yaml')
        result = store.checked_yaml(self.root, prefix + 'result.yaml')
        candidate = store.checked_yaml(self.root, prefix + 'candidate.yaml')['candidate']
        _, research_result, review = research._approved_material(self.root, base, result)
        original = research._render_summary(manifest, candidate, research_result, review, result,
                                            record['original_markdown_path'], 'first')
        path = self.root / ('summary/agent_memory/first/' + record['key'] + '.md')
        path.parent.mkdir(parents=True)
        path.write_text(original + '\n人工补充：保留这个判断。\n')
        modified = path.read_bytes()
        self.assertFalse((self.root / (prefix + 'summary.yaml')).exists())
        with self.assertRaisesRegex(store.OfflineError, '未绑定总结已被人工修改'):
            research.run(self.root, self.config_path, 'first')
        self.member.assert_not_called()
        with self.assertRaisesRegex(store.OfflineError, '未绑定总结已被人工修改'):
            self.run_research()
        self.assertEqual(len(self.client.calls), 2)
        self.assertEqual(path.read_bytes(), modified)
        # An intact interrupted export can resume, bind the existing Markdown,
        # and process only the other source.
        path.write_text(original)
        resumed = self.run_research()
        self.assertEqual(resumed['status'], 'complete')
        self.assertEqual(len(self.client.calls), 4)
        self.assertTrue((self.root / (prefix + 'summary.yaml')).is_file())

    def test_interrupted_named_export_reuses_the_same_markdown(self):
        self.collect()
        save_yaml = store.save_yaml

        def interrupt_binding(root, relative, value):
            if relative.endswith('/summary.yaml'):
                raise store.SimulatedInterruption('fixture interrupted before summary binding')
            return save_yaml(root, relative, value)

        with mock.patch.object(store, 'save_yaml', side_effect=interrupt_binding):
            with self.assertRaises(store.SimulatedInterruption):
                self.run_research()
        (path,) = list((self.root / 'summary' / 'agent_memory').glob('*/*.md'))
        payload = path.read_bytes()
        self.assertTrue(path.stem.startswith('保存引用为何有助于核对~'))
        self.assertEqual(len(self.client.calls), 4)

        path.write_bytes(payload + b'\nmanual edit\n')
        with self.assertRaisesRegex(store.OfflineError, '未绑定总结已被人工修改'):
            self.run_research()
        path.write_bytes(payload)
        result = self.run_research()
        self.assertIn(path.relative_to(self.root).as_posix(), result['summary_paths'])
        self.assertEqual(path.read_bytes(), payload)
        self.assertEqual(len(self.client.calls), 4)


if __name__ == '__main__':
    unittest.main()
