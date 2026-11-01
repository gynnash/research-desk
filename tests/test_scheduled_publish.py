"""New scheduler transfers use existing source/review proofs, never a model."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import researchdesk_harness as harness
import researchdesk_offline as store
import researchdesk_publish as publish
import test_codex_harness as codex_fixtures
import test_research_entry as research_fixtures


class ScheduledPublication(unittest.TestCase):
    def setUp(self):
        fixture = research_fixtures.ResearchEntry('test_collection_to_detailed_reviewed_summaries_and_idempotent_resume')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture, self.root = fixture, fixture.root
        self.temporary = tempfile.TemporaryDirectory(prefix='researchdesk-publish-test-')
        self.addCleanup(self.temporary.cleanup)
        outside = Path(self.temporary.name).resolve()
        self.artifact, self.publisher, self.state = outside / 'artifact', outside / 'publisher', outside / 'runtime'
        self.publisher.mkdir()
        fixture.collect()
        self.result = fixture.run_research()
        config = yaml.safe_load((ROOT / 'config/examples/codex-insight.yaml').read_text())
        config['models'] = {'generation': 'fixture-generator', 'review': 'fixture-independent-reviewer'}
        self.config = config
        path = self.root / 'config/codex-insight.yaml'
        path.write_text(yaml.safe_dump(config, allow_unicode=True, sort_keys=False))
        self.context = {
            'schema_version': 1, 'topic': 'agent_memory', 'cycle_id': 'first',
            'config_fingerprint': 'b' * 64,
            'topics_path': 'config/research_topics.yaml',
            'topics_yaml_text': (self.root / 'config/research_topics.yaml').read_text(),
            'research_config_path': 'config/cycles/default.yaml',
            'research_config_yaml_text': fixture.config_path.read_text(),
            'insight_config': {key: value for key, value in config.items() if key != 'runtime'},
        }
        for name in ('topics', 'research_config'):
            self.context[name + '_sha256'] = store.digest(self.context[name + '_yaml_text'].encode())
        self.save_context()
        result = harness.run(self.root, path, 'first', backend=codex_fixtures.RecordingBackend(),
                             state_root=self.state)
        self.assertEqual(result['status'], 'complete')
        self.calls = len(fixture.client.calls)
        self.base = 'a' * 40

    def save_context(self):
        relative = 'reports/test/agent_memory/automation/first/context.yaml'
        target = self.root / relative
        for path in (target, Path(str(target) + '.sha256')):
            if path.exists():
                path.unlink()
        store.save_yaml(self.root, relative, self.context)

    def export(self):
        return publish.export(self.root, self.artifact, 'agent_memory', 'first', self.base)

    def snapshot(self, root):
        return {path.relative_to(root).as_posix(): path.read_bytes()
                for path in root.rglob('*') if path.is_file()}

    def assert_no_new_calls(self):
        self.assertEqual(len(self.fixture.client.calls), self.calls)
        self.fixture.member.assert_not_called()

    def test_roundtrip_is_create_only_and_private_configuration_stays_out(self):
        private = self.root / 'reports/test/agent_memory/codex-requests/first/private.yaml'
        private.parent.mkdir(parents=True)
        private.write_text('Private request accounting must stay local.\n')
        result = self.export()
        self.assertGreater(result['exported_files'], 20)
        manifest = json.loads((self.artifact / 'manifest.json').read_text())
        self.assertTrue(any(path.startswith('collection/') for path in manifest['files']))
        self.assertTrue(any(path.startswith('summary/') for path in manifest['files']))
        self.assertFalse(any(path.startswith('config/') or 'codex-requests' in path for path in manifest['files']))
        saved = publish.apply(self.publisher, self.artifact)
        self.assertEqual(saved['saved_files'], result['exported_files'])
        self.assertFalse((self.publisher / 'config').exists())
        before = self.snapshot(self.publisher)
        self.assertEqual(publish.apply(self.publisher, self.artifact)['saved_files'], 0)
        self.assertEqual(self.snapshot(self.publisher), before)
        self.assert_no_new_calls()

    def test_human_note_conflict_stops_all_writes(self):
        self.export()
        path = self.publisher / self.result['summary_paths'][0]
        path.parent.mkdir(parents=True)
        path.write_text('# My annotation remains untouched.\n')
        before = self.snapshot(self.publisher)
        with self.assertRaisesRegex(publish.PublishError, 'conflict'):
            publish.apply(self.publisher, self.artifact)
        self.assertEqual(self.snapshot(self.publisher), before)
        self.assert_no_new_calls()

    def test_changed_original_or_unbound_article_cannot_be_resigned_into_a_pass(self):
        self.export()
        manifest_path = self.artifact / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        path = 'insights/test/agent_memory/first/report.md'
        target = self.artifact / 'payload' / path
        target.write_text(target.read_text() + '\nUnsupported additional claim.\n')
        manifest['files'][path] = hashlib.sha256(target.read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaises(store.OfflineError):
            publish.apply(self.publisher, self.artifact)
        self.assertEqual(self.snapshot(self.publisher), {})
        self.assert_no_new_calls()

    def test_forged_review_pass_and_changed_candidate_are_rejected(self):
        base = 'reports/test/agent_memory/codex-insight/first/'
        path = self.root / (base + 'review.yaml')
        value = yaml.safe_load(path.read_text())
        value['candidate_sha256'] = '0' * 64
        path.write_text(yaml.safe_dump(value))
        Path(str(path) + '.sha256').write_text(hashlib.sha256(path.read_bytes()).hexdigest())
        with self.assertRaises(store.OfflineError):
            self.export()
        self.assertFalse(self.artifact.exists())
        self.assert_no_new_calls()

    def test_private_path_or_cross_cycle_payload_never_reaches_the_repository(self):
        self.export()
        manifest_path = self.artifact / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        original = deepcopy(manifest)
        for path in ('config/local/workbench.yaml',
                     'reports/test/agent_memory/codex-requests/first/events/000001.yaml',
                     'summary/agent_memory/another-cycle/manual.md',
                     '../outside.md'):
            with self.subTest(path=path):
                manifest = deepcopy(original)
                manifest['files'][path] = '0' * 64
                manifest_path.write_text(json.dumps(manifest))
                with self.assertRaises(publish.PublishError):
                    publish.apply(self.publisher, self.artifact)
                self.assertEqual(self.snapshot(self.publisher), {})
        self.assert_no_new_calls()

    def test_base_change_and_existing_staged_changes_stop_before_writes(self):
        self.export()
        (self.publisher / '.git').mkdir()
        with mock.patch.object(publish, '_git', return_value='b' * 40), mock.patch.object(
                publish, '_ancestor', return_value=False):
            with self.assertRaisesRegex(publish.PublishError, 'main_history_changed'):
                publish.apply(self.publisher, self.artifact, push=True)
        with mock.patch.object(publish, '_git', side_effect=[self.base, 'README.md']):
            with self.assertRaisesRegex(publish.PublishError, 'staged_changes'):
                publish.apply(self.publisher, self.artifact, push=True)
        self.assertEqual(self.snapshot(self.publisher), {})
        self.assert_no_new_calls()

    def test_normal_main_advance_is_allowed_but_actual_human_changes_are_preserved(self):
        def git(*arguments):
            return subprocess.run(['git', *arguments], cwd=self.publisher, check=True,
                                  capture_output=True, text=True).stdout.strip()
        git('init', '-b', 'main')
        git('config', 'user.name', 'Offline fixture')
        git('config', 'user.email', 'fixture@example.org')
        readme = self.publisher / 'README.md'
        readme.write_text('# Original public framework\n')
        git('add', 'README.md')
        git('commit', '-m', 'Initial fictional framework')
        self.base = git('rev-parse', 'HEAD')
        self.export()
        readme.write_text('# Unrelated documentation update\n')
        git('add', 'README.md')
        git('commit', '-m', 'Update only README while research runs')
        head = git('rev-parse', 'HEAD')
        result = publish.apply(self.publisher, self.artifact)
        self.assertGreater(result['saved_files'], 0)
        self.assertEqual(git('rev-parse', 'HEAD'), head, 'verification does not rewrite Git history')
        self.assertEqual(readme.read_text(), '# Unrelated documentation update\n')
        note = self.publisher / self.result['summary_paths'][0]
        note.write_text(note.read_text() + '\nMy newer manual annotation.\n')
        before = self.snapshot(self.publisher)
        with self.assertRaisesRegex(publish.PublishError, 'conflict'):
            publish.apply(self.publisher, self.artifact)
        self.assertEqual(self.snapshot(self.publisher), before)
        self.assert_no_new_calls()


class AutomaticPublishIntegration(unittest.TestCase):
    def test_two_real_offline_rounds_restore_history_snapshots_on_the_publisher(self):
        import researchdesk_automatic as automatic
        import researchdesk_cycle as cycle
        import researchdesk_research as research
        import researchdesk_workbench as workbench
        fixture = research_fixtures.ResearchEntry('test_collection_to_detailed_reviewed_summaries_and_idempotent_resume')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        root = fixture.root
        system = workbench._read(workbench.REPOSITORY / workbench.SYSTEM_CONFIG)
        system['research'].pop('selection', None)
        (root / workbench.SYSTEM_CONFIG).write_bytes(workbench._yaml(system))
        workbench.initialize(root, adopt_existing=True)

        class NextRoundSources:
            def fetch(self, url):
                # Entirely fictional URLs/IDs keep real cross-cycle URL dedup
                # enabled while the next batch genuinely contains new records.
                substitutions = [('2610.01234', '2610.05678'),
                                 ('fixture-memory', 'fixture-memory-next')]
                original = url
                for old, new in substitutions:
                    original = original.replace(new, old)
                result = dict(fixture.fetcher.fetch(original))
                for field in ('text', 'url', 'requested_url'):
                    if isinstance(result.get(field), str):
                        for old, new in substitutions:
                            result[field] = result[field].replace(old, new)
                if 'text' in result:
                    result['sha256'] = store.digest(result['text'].encode())
                return result

            def fetch_pdf(self, url):
                raise AssertionError('The fictional HTML is complete')

        with tempfile.TemporaryDirectory(prefix='researchdesk-roundtrip-integration-') as temporary:
            outside = Path(temporary).resolve()
            publisher = outside / 'publisher'
            publisher.mkdir()
            backend = codex_fixtures.RecordingBackend()
            def dependencies(fetcher):
                return {
                    'collector': lambda root, path, identity: cycle.collect_originals(
                        root, path, identity, fetcher=fetcher),
                    'researcher': lambda root, path, identity, profile: research.run(
                        root, path, identity, client=fixture.client, profile=profile),
                    'insight_runner': lambda root, path, identity: harness.run(
                        root, path, identity, backend=backend, state_root=outside / 'runtime'),
                    'health_checker': lambda root, effective: {'ready': True},
                }
            first = automatic.run(root, event='manual', cycle_id='auto-first',
                                  publisher_context={'base_commit': 'a' * 40},
                                  **dependencies(fixture.fetcher))
            self.assertEqual(first['status'], 'complete', first)
            artifact_one = outside / 'artifact-one'
            publish.export(root, artifact_one, 'agent_memory', 'auto-first', 'a' * 40)
            publish.apply(publisher, artifact_one)
            self.assertFalse((publisher / 'config').exists())
            second = automatic.run(root, event='manual', cycle_id='auto-second',
                                   publisher_context={'base_commit': 'b' * 40},
                                   **dependencies(NextRoundSources()))
            self.assertEqual(second['status'], 'complete', second)
            accepted = store.checked_yaml(root,
                'reports/test/agent_memory/codex-insight/auto-second/accepted.yaml')
            self.assertTrue(any(path.startswith('summary/agent_memory/auto-first/')
                                for path in accepted['input_hashes']))
            # Exercise explicit old snapshot references too: only the public
            # first-round context in Git can restore this ignored host file.
            old_context = store.checked_yaml(root, first['context_path'])
            old_topics = old_context['topics_path']
            accepted['input_hashes'][old_topics] = old_context['topics_sha256']
            receipt = root / 'reports/test/agent_memory/codex-insight/auto-second/accepted.yaml'
            receipt.write_text(yaml.safe_dump(accepted, allow_unicode=True, sort_keys=True))
            Path(str(receipt) + '.sha256').write_text(store.digest(receipt.read_bytes()))
            calls = len(fixture.client.calls), len(backend.calls)
            artifact_two = outside / 'artifact-two'
            publish.export(root, artifact_two, 'agent_memory', 'auto-second', 'c' * 40)
            manifest = json.loads((artifact_two / 'manifest.json').read_text())
            self.assertEqual(manifest['base_commit'], 'c' * 40,
                             'a same-cycle save retry may use the latest main commit')
            self.assertEqual(store.checked_yaml(root, second['context_path'])['base_commit'], 'b' * 40)
            publish.apply(publisher, artifact_two)
            self.assertFalse((publisher / 'config').exists())
            self.assertEqual((len(fixture.client.calls), len(backend.calls)), calls)
            self.assertTrue((publisher / 'summary/agent_memory/auto-first').is_dir())
            self.assertTrue((publisher / 'summary/agent_memory/auto-second').is_dir())
            # A missing/corrupt historical public context cannot be replaced
            # with the maintainer's local ignored configuration.
            historical = publisher / first['context_path']
            original_context = historical.read_bytes()
            historical.write_bytes(original_context + b'\nchanged: true\n')
            with self.assertRaises(store.OfflineError):
                publish.apply(publisher, artifact_two)
            self.assertEqual(historical.read_bytes(), original_context + b'\nchanged: true\n')
            fixture.member.assert_not_called()
            fixture.writer.assert_not_called()


if __name__ == '__main__':
    unittest.main()
