"""Verified local inputs for the Codex path; no network or member clients."""

from copy import deepcopy
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import researchdesk_insight_inputs as inputs
from researchdesk_note_paths import summary_ids
import researchdesk_offline as store
import test_research_entry as entry_fixtures


class CodexInputs(unittest.TestCase):
    setUp = entry_fixtures.ResearchEntry.setUp
    collect = entry_fixtures.ResearchEntry.collect
    run_research = entry_fixtures.ResearchEntry.run_research

    def prepared(self):
        self.collect()
        return self.run_research()

    def bundle(self, cycle_id='first', **kwargs):
        return inputs.prepare_codex_bundle(
            self.root, 'agent_memory', cycle_id, as_of='2026-11-02', **kwargs)

    def rewrite_yaml(self, relative, value):
        path = self.root / relative
        path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False))
        Path(str(path) + '.sha256').write_text(store.digest(path.read_bytes()) + '\n')

    def test_complete_originals_review_proofs_and_links_are_preserved_without_calls_or_writes(self):
        self.prepared()
        before = {path.relative_to(self.root): path.read_bytes()
                  for path in self.root.rglob('*') if path.is_file()}
        calls = len(self.client.calls)
        with mock.patch.object(inputs.batch, 'validate_research', side_effect=AssertionError('No style regrading')):
            result = self.bundle()
        self.assertEqual([item['id'] for item in result['sources']], ['R1', 'R2'])
        self.assertTrue(all(item['role'] == 'current' for item in result['sources']))
        for item in result['sources']:
            self.assertEqual(item['coverage'], 'full_text')
            self.assertIn('[阅读已采集的完整原文]', item['summary_text'])
            self.assertIn('## 抽取正文', item['original_text'])
            self.assertEqual(result['input_hashes'][item['summary_path']],
                             store.digest((self.root / item['summary_path']).read_bytes()))
            self.assertEqual(result['input_hashes'][item['original_path']],
                             store.digest((self.root / item['original_path']).read_bytes()))
        self.assertEqual(len(self.client.calls), calls)
        self.member.assert_not_called()
        self.assertEqual(before, {path.relative_to(self.root): path.read_bytes()
                                  for path in self.root.rglob('*') if path.is_file()})

    def test_single_source_no_history_and_later_topic_preferences_are_allowed(self):
        prepared = self.prepared()
        (self.root / prepared['summary_paths'][1]).unlink()
        topics_path = self.root / 'config/research_topics.yaml'
        topics = yaml.safe_load(topics_path.read_text())
        topics['topics']['agent_memory'].update(name='新的名称', keywords=['新的偏好'])
        topics_path.write_text(yaml.safe_dump(topics, allow_unicode=True))
        result = self.bundle()
        self.assertEqual(len(result['sources']), 1)
        self.assertEqual(result['sources'][0]['role'], 'current')
        self.assertIn('没有可核实的相关历史', result['history_note'])

    def test_explicit_topics_snapshot_is_used_instead_of_live_private_topics(self):
        self.prepared()
        relative = 'config/local/automation/first/topics.yaml'
        snapshot = self.root / relative
        snapshot.parent.mkdir(parents=True)
        snapshot.write_bytes((self.root / 'config/research_topics.yaml').read_bytes())
        (self.root / 'config/research_topics.yaml').write_text('schema_version: 1\ntopics: {}\n')
        bundle = inputs.prepare_codex_bundle(self.root, 'agent_memory', 'first', topics_file=relative)
        self.assertTrue(bundle['sources'])
        self.assertIn(relative, bundle['input_hashes'])
        self.assertNotIn('config/research_topics.yaml', bundle['input_hashes'])

    def test_historical_research_date_window_uses_saved_receipt_instead_of_file_mtime(self):
        self.prepared()
        current = self.bundle()['sources']
        for item in current:
            os.utime(self.root / item['summary_path'], (946684800, 946684800))
        research_date = max(item['research_date'] for item in current)
        result = inputs.prepare_codex_bundle(self.root, 'agent_memory', 'next', as_of=research_date)
        self.assertEqual([item['id'] for item in result['sources']], ['H1', 'H2'])
        self.assertTrue(all(item['research_date'] for item in result['sources']))
        old = inputs.prepare_codex_bundle(self.root, 'agent_memory', 'next', as_of='2027-06-01')
        self.assertEqual(old['sources'], [])

    def test_current_summary_and_original_changes_are_not_accepted(self):
        prepared = self.prepared()
        path = self.root / prepared['summary_paths'][0]
        saved = path.read_bytes()
        path.write_text(path.read_text() + '\n人工补充。\n')
        with self.assertRaisesRegex(store.OfflineError, '当前批次输入未通过验证'):
            self.bundle()
        path.write_bytes(saved)
        topic, cycle, key = summary_ids(prepared['summary_paths'][0])
        binding = store.checked_yaml(self.root, 'reports/test/%s/research-batches/%s/items/%s/candidate.yaml' %
                                     (topic, cycle, key))
        original = self.root / binding['candidate']['archive']['markdown_path']
        original.write_text(original.read_text() + '\nchanged original\n')
        with self.assertRaisesRegex(store.OfflineError, '当前批次输入未通过验证'):
            self.bundle()

    def test_frontmatter_passed_without_receipt_cannot_be_used_as_review(self):
        path = self.root / 'summary/agent_memory/first/unbound.md'
        path.parent.mkdir(parents=True)
        path.write_text('---\nreview_status: passed\n---\n# Fake reviewed summary\n')
        with self.assertRaisesRegex(store.OfflineError, '当前批次输入未通过验证'):
            self.bundle()
        historical = self.bundle('next')
        self.assertEqual(historical['sources'], [])
        self.assertIn('跳过未能验证的历史', historical['history_note'])

    def test_rejected_review_is_detected_even_if_its_yaml_hash_is_repaired(self):
        self.prepared()
        base = 'reports/test/agent_memory/research-batches/first'
        event_path = next(path for path in (self.root / base / 'events').glob('*.yaml')
                          if (value := yaml.safe_load(path.read_text())).get('type') == 'call_completed'
                          and value.get('role') == 'review')
        event = yaml.safe_load(event_path.read_text())
        checkpoint = store.checked_yaml(self.root, event['response_path'])
        review = inputs.batch.parse_result(checkpoint['result']['text'])
        review['decision'] = 'reject'
        import json
        checkpoint['result']['text'] = json.dumps(review, ensure_ascii=False)
        self.rewrite_yaml(event['response_path'], checkpoint)
        event['response_sha256'] = store.digest((self.root / event['response_path']).read_bytes())
        self.rewrite_yaml(event_path.relative_to(self.root).as_posix(), event)
        with self.assertRaisesRegex(store.OfflineError, '独立审阅未通过'):
            self.bundle()

    def test_history_has_no_document_count_cap_and_identity_aliases_are_deduplicated(self):
        self.prepared()
        actual = inputs._codex_summary
        baseline = self.bundle()['sources'][0]
        for index in range(15):
            path = self.root / ('summary/agent_memory/history-%s/item.md' % index)
            path.parent.mkdir(parents=True)
            path.write_text('Reader fixture; verified proof supplied by the selection test.')

        def verified(root, relative, topic, hashes):
            if '/history-' not in relative:
                return actual(root, relative, topic, hashes)
            number = int(Path(relative).parts[2].split('-')[1])
            item = deepcopy(baseline)
            item.pop('id')
            item.pop('role')
            item.update(summary_path=relative, research_date='2026-10-10',
                        source_id='fixture-%s' % number, url='https://example.org/%s' % number,
                        _identities={'url:https://example.org/%s' % number})
            if number == 14:
                # An arXiv HTML/version alias of the current paper is not
                # another independent historical source.
                item['_identities'] = {'arxiv:2610.01234'}
            return item

        with mock.patch.object(inputs, '_codex_summary', side_effect=verified):
            result = self.bundle()
        self.assertEqual(sum(item['role'] == 'history' for item in result['sources']), 14)
        self.assertEqual(len(result['sources']), 16)


if __name__ == '__main__':
    unittest.main()
