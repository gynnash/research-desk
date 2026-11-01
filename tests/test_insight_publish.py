"""Formal Insight and page-ready topics survive offline Actions result transfer."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import researchdesk_insight_admission as admission
import researchdesk_offline as store
import researchdesk_publish as publish
from test_insight_admission import prepare_cycle
from workflows import validate


class InsightPublication(unittest.TestCase):
    def prepare(self, formal=True):
        self.fixture, self.backend = prepare_cycle(self, admit=formal)
        self.root = self.fixture.root
        external = tempfile.TemporaryDirectory(prefix='researchdesk-formal-publish-')
        self.addCleanup(external.cleanup)
        self.artifact = Path(external.name) / 'artifact'
        self.publisher = Path(external.name) / 'publisher'
        self.publisher.mkdir()
        config = yaml.safe_load((self.root / 'config/codex-insight.yaml').read_text())
        context = {
            'schema_version': 1, 'topic': 'agent_memory', 'cycle_id': 'first',
            'config_fingerprint': 'b' * 64,
            'topics_path': 'config/research_topics.yaml',
            'topics_yaml_text': (self.root / 'config/research_topics.yaml').read_text(),
            'research_config_path': 'config/cycles/default.yaml',
            'research_config_yaml_text': self.fixture.config_path.read_text(),
            'insight_config': {key: value for key, value in config.items() if key != 'runtime'},
        }
        for name in ('topics', 'research_config'):
            context[name + '_sha256'] = store.digest(context[name + '_yaml_text'].encode())
        store.save_yaml(self.root, 'reports/test/agent_memory/automation/first/context.yaml', context)
        self.calls = (len(self.fixture.client.calls), list(self.backend.calls))

    def export(self):
        return publish.export(self.root, self.artifact, 'agent_memory', 'first', 'a' * 40)

    def snapshot(self, root):
        return {path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob('*') if path.is_file()}

    def assert_no_new_calls(self):
        self.assertEqual((len(self.fixture.client.calls), self.backend.calls), self.calls)
        self.fixture.member.assert_not_called()

    def test_formal_roundtrip_verifies_without_private_config_and_preserves_test(self):
        self.prepare()
        exported = self.export()
        self.assertTrue(exported['production_accepted'])
        manifest = json.loads((self.artifact / 'manifest.json').read_text())
        required = {'insights/agent_memory/first/report.md',
                    'articles/agent_memory/first-topic-1.md',
                    'reports/agent_memory/admissions/first/plan.yaml',
                    'reports/agent_memory/admissions/first/plan.yaml.sha256',
                    'reports/agent_memory/admissions/first/accepted.yaml',
                    'reports/agent_memory/admissions/first/accepted.yaml.sha256',
                    'insights/test/agent_memory/first/report.md'}
        self.assertTrue(required.issubset(manifest['files']))
        self.assertFalse(any(relative.startswith('config/') for relative in manifest['files']))
        publish.apply(self.publisher, self.artifact)
        self.assertFalse((self.publisher / 'config').exists())
        self.assertEqual(admission.load(self.publisher, 'agent_memory', 'first')['mode'], admission.MODE)
        problems = []
        count = validate.check_insight_admissions(self.publisher, {'agent_memory': {}},
            lambda path, message: problems.append((path, message)),
            lambda text, relative: yaml.safe_load(text.split('---', 2)[1]))
        self.assertEqual(count, 1)
        self.assertEqual(problems, [])
        before = self.snapshot(self.publisher)
        self.assertEqual(publish.apply(self.publisher, self.artifact)['saved_files'], 0)
        self.assertEqual(self.snapshot(self.publisher), before)
        self.assert_no_new_calls()

    def test_existing_formal_annotation_blocks_transfer_without_overwriting(self):
        self.prepare()
        self.export()
        target = self.publisher / 'insights/agent_memory/first/report.md'
        target.parent.mkdir(parents=True)
        target.write_text('# 我的人工研究笔记\n')
        before = self.snapshot(self.publisher)
        with self.assertRaisesRegex(publish.PublishError, 'conflict'):
            publish.apply(self.publisher, self.artifact)
        self.assertEqual(self.snapshot(self.publisher), before)
        self.assert_no_new_calls()

    def test_unadmitted_test_export_remains_usable_without_creating_formal_outputs(self):
        self.prepare(formal=False)
        self.assertFalse(self.export()['production_accepted'])
        publish.apply(self.publisher, self.artifact)
        self.assertTrue((self.publisher / 'insights/test/agent_memory/first/report.md').is_file())
        self.assertFalse((self.publisher / 'insights/agent_memory').exists())
        self.assertFalse((self.publisher / 'articles/agent_memory').exists())
        self.assertFalse((self.publisher / 'reports/agent_memory').exists())
        self.assert_no_new_calls()


if __name__ == '__main__':
    unittest.main()
