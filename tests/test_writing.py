"""Writing gates and recovery use fictional fixtures and a mock client only.

Every check runs in a temporary vault with sockets disabled. Creating a fixture
confirmation never approves a real Insight proposal or grants publication.
"""

import copy
import hashlib
import importlib
import json
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest import mock

import yaml


REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / 'scripts'))
import researchdesk_offline as store


class FakeWritingClient:
    backend = 'mock'

    def __init__(self, fixture):
        self.fixture = copy.deepcopy(fixture)
        self.calls = []
        self.actual_model = None
        self.fail_on_call = None
        self.generation_mutator = None
        self.review_mutator = None
        self.after_response = None

    def infer(self, model, instructions, input_text, **limits):
        payload = json.loads(input_text)
        self.calls.append({'model': model, 'payload': payload, 'instructions': instructions,
                           'limits': limits})
        if len(self.calls) == self.fail_on_call:
            raise OSError('Synthetic unknown writing result')
        stage, revision = payload['stage'], payload['revision']
        role = 'review' if 'candidate' in payload else 'writing'
        values = self.fixture['reviews' if role == 'review' else 'responses'][stage]
        result = copy.deepcopy(values[revision])
        mutator = self.review_mutator if role == 'review' else self.generation_mutator
        if mutator:
            mutator(stage, result)
        if self.after_response:
            self.after_response(stage, role, result)
        return {'model': self.actual_model or model,
                'text': json.dumps(result, ensure_ascii=False),
                'response_id': 'mock-writing-%s' % len(self.calls),
                'usage': {'input_tokens': 100, 'output_tokens': 60, 'total_tokens': 160}}


class OfflineWritingLoop(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='researchdesk-writing-tests-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        for directory in ('config/test/custom-topic', 'workflows/test/custom-topic/fixtures',
                          'sources/papers', 'sources/blogs', 'reports', 'insights', 'articles'):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        (self.root / 'config/research_topics.yaml').write_text(yaml.safe_dump({
            'schema_version': 1, 'topics': {'custom-topic': {
                'name': '虚构测试方向', 'enabled': True, 'description': '仅虚构资料的离线写作验收。',
                'scope': ['可追溯写作'], 'keywords': ['fixture']}}}, allow_unicode=True))
        source = REPOSITORY / 'workflows/test/agent-memory/fixtures/writing.yaml'
        self.fixture = yaml.safe_load(source.read_text())
        self.fixture['topic'] = 'custom-topic'
        self.fixture_path = self.root / 'workflows/test/custom-topic/fixtures/writing.yaml'
        self.config = {
            'schema_version': 1, 'mode': 'writing_offline_test', 'backend': 'mock',
            'topic': 'custom-topic', 'topics_file': 'config/research_topics.yaml',
            'models': {'writing': 'mock-writer', 'review': 'mock-reviewer'},
            'budget': {'max_calls': 12, 'max_calls_per_stage': 4, 'max_revisions': 1,
                       'max_input_chars': 30000, 'max_output_chars': 12000},
            'fixture': {'path': self.fixture_path.relative_to(self.root).as_posix(), 'sha256': ''},
            'confirmation': None}
        self.config_path = self.root / 'config/test/custom-topic/writing.yaml'
        self.write_fixture()
        self.client = FakeWritingClient(self.fixture)
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(socket, 'create_connection',
                          side_effect=AssertionError('Network prohibited')).start()
        mock.patch.object(socket.socket, 'connect',
                          side_effect=AssertionError('Network prohibited')).start()

    def writing(self):
        return importlib.import_module('researchdesk_writing')

    def write_config(self):
        self.config_path.write_text(yaml.safe_dump(self.config, allow_unicode=True, sort_keys=False))

    def write_fixture(self):
        self.fixture_path.write_text(yaml.safe_dump(self.fixture, allow_unicode=True, sort_keys=False))
        self.config['fixture']['sha256'] = hashlib.sha256(self.fixture_path.read_bytes()).hexdigest()
        self.write_config()

    def confirm(self, identity='fixture-confirmation', decision='confirmed'):
        self.write_config()
        path = self.writing().create_fixture_confirmation(
            self.root, self.config_path, identity, decision=decision)
        self.config['confirmation'] = path
        self.write_config()
        return self.root / path

    def run_writing(self, batch_id='first', **kwargs):
        self.write_config()
        return self.writing().run(self.root, self.config_path, batch_id,
                                  client=self.client, **kwargs)

    def directory(self, batch_id='first'):
        return self.root / 'reports/test/custom-topic/writing-runs' / batch_id

    def articles(self, batch_id='first'):
        return self.root / 'articles/test/custom-topic' / batch_id

    def assert_blocked(self, batch_id='first'):
        try:
            result = self.run_writing(batch_id)
        except (store.OfflineError, ValueError, yaml.YAMLError):
            return
        self.assertNotEqual(result['status'], 'test_accepted')

    def assert_unique_calls(self):
        identities = [(call['payload']['stage'], 'review' if 'candidate' in call['payload'] else 'writing',
                       call['payload']['revision']) for call in self.client.calls]
        self.assertEqual(len(identities), len(set(identities)))

    def interrupted_ledger(self):
        self.confirm()
        with self.assertRaises(store.SimulatedInterruption):
            self.run_writing(fail_after='after_review')
        base = self.directory().relative_to(self.root).as_posix()
        return base, store.read_events(self.root, base)

    def replace_test_ledger(self, base, events):
        for path in (self.root / base / 'events').iterdir():
            path.unlink()
        for index, event in enumerate(events, 1):
            store.save_yaml(self.root, '%s/events/%06d.yaml' % (base, index), event)

    def assert_ledger_attack_stopped(self):
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 8)
        self.assertFalse(any(self.articles().glob('*.md')))

    def test_manifest_cannot_change_bound_fields_while_retaining_fingerprint(self):
        base, _ = self.interrupted_ledger()
        path = self.root / base / 'manifest.yaml'
        sidecar = path.with_name(path.name + '.sha256')
        original_bytes, original_sidecar = path.read_bytes(), sidecar.read_bytes()
        original = yaml.safe_load(original_bytes)
        changes = [('budget', dict(original['budget'], max_calls=10)),
                   ('models', dict(original['models'], writing='mock-another-writer')),
                   ('confirmation_path', 'reports/test/custom-topic/writing-approvals/another.yaml'),
                   ('confirmation_sha256', '0' * 64), ('identity', '0' * 64),
                   ('topic', 'another-topic'), ('batch_id', 'another-batch'),
                   ('mode', 'production'), ('backend', 'chatgpt_plan'),
                   ('publish_authorized', True), ('schema_version', 2)]
        try:
            for key, value in changes:
                changed = dict(copy.deepcopy(original), **{key: value})
                self.assertEqual(changed['fingerprint'], original['fingerprint'])
                path.write_text(yaml.safe_dump(changed, allow_unicode=True, sort_keys=False))
                sidecar.write_text(store.digest(path.read_bytes()) + '\n')
                with self.subTest(field=key):
                    self.assert_ledger_attack_stopped()
        finally:
            path.write_bytes(original_bytes)
            sidecar.write_bytes(original_sidecar)

    def test_duplicate_completion_cannot_generate_articles(self):
        base, events = self.interrupted_ledger()
        events.append(copy.deepcopy(next(event for event in events if event['type'] == 'call_completed')))
        self.replace_test_ledger(base, events)
        self.assert_ledger_attack_stopped()

    def test_completion_without_reservation_cannot_generate_articles(self):
        base, events = self.interrupted_ledger()
        events = [event for event in events if not (event['type'] == 'call_reserved'
                  and event['reservation_id'] == 'outline-writing-0')]
        self.replace_test_ledger(base, events)
        self.assert_ledger_attack_stopped()

    def test_checkpoint_cannot_be_replaced_by_another_role(self):
        base, events = self.interrupted_ledger()
        generation = next(event for event in events if event.get('reservation_id') == 'outline-writing-0'
                          and event['type'] == 'call_completed')
        review = next(event for event in events if event.get('reservation_id') == 'outline-review-0'
                      and event['type'] == 'call_completed')
        generation['response_path'] = review['response_path']
        generation['response_sha256'] = review['response_sha256']
        self.replace_test_ledger(base, events)
        self.assert_ledger_attack_stopped()

    def test_skipping_prior_accepted_stages_is_rejected(self):
        base, events = self.interrupted_ledger()
        events = [event for event in events if event.get('reservation_id') == 'candidate-writing-0']
        self.replace_test_ledger(base, events)
        self.assert_ledger_attack_stopped()

    def test_extra_completed_revision_after_pass_cannot_generate_articles(self):
        base, events = self.interrupted_ledger()
        reserved = copy.deepcopy(next(event for event in events if event.get('reservation_id') == 'candidate-writing-0'
                                      and event['type'] == 'call_reserved'))
        completed = copy.deepcopy(next(event for event in events if event.get('reservation_id') == 'candidate-writing-0'
                                       and event['type'] == 'call_completed'))
        checkpoint = store.checked_yaml(self.root, completed['response_path'])
        path = base + '/checkpoints/candidate-writing-1.yaml'
        sha = store.save_yaml(self.root, path, checkpoint)
        reserved.update(reservation_id='candidate-writing-1', revision=1)
        completed.update(reservation_id='candidate-writing-1', revision=1,
                         response_path=path, response_sha256=sha)
        events.extend([reserved, completed])
        self.replace_test_ledger(base, events)
        self.assert_ledger_attack_stopped()

    def test_unknown_ledger_event_cannot_approve_or_publish_articles(self):
        base, events = self.interrupted_ledger()
        events.append({'type': 'publication_approved', 'publish_authorized': True})
        self.replace_test_ledger(base, events)
        self.assert_ledger_attack_stopped()

    def test_changed_receipt_output_hashes_are_preserved_and_rejected(self):
        self.confirm()
        self.run_writing()
        receipt = self.directory() / 'receipt.yaml'
        result = yaml.safe_load(receipt.read_text())
        result['output_hashes'][next(iter(result['output_hashes']))] = '0' * 64
        receipt.write_text(yaml.safe_dump(result, allow_unicode=True, sort_keys=False))
        receipt.with_name(receipt.name + '.sha256').write_text(store.digest(receipt.read_bytes()) + '\n')
        before = receipt.read_bytes()
        articles = {path: path.read_bytes() for path in self.articles().glob('*.md')}
        self.assert_blocked()
        self.assertEqual(receipt.read_bytes(), before)
        self.assertEqual(len(self.client.calls), 8)
        for path, payload in articles.items():
            self.assertEqual(path.read_bytes(), payload)

    def test_revocation_during_generation_stops_before_next_call_and_keeps_response(self):
        self.confirm()
        def revoke_after_response(stage, role, result):
            self.writing().revoke_fixture_confirmation(
                self.root, self.config_path, '模拟运行中的用户撤回确认。')
        self.client.after_response = revoke_after_response
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 1)
        checkpoint = self.directory() / 'checkpoints/outline-writing-0.yaml'
        self.assertTrue(checkpoint.is_file())
        self.assertFalse(any(self.articles().glob('*.md')))

    def test_mock_confirmation_runs_outline_draft_candidate_with_independent_reviews(self):
        self.confirm()
        result = self.run_writing()
        self.assertEqual(result['status'], 'test_accepted')
        self.assertEqual(result['backend'], 'mock')
        self.assertEqual(result['real_inference_calls'], 0)
        self.assertIsNone(result['membership_usage'])
        self.assertEqual(result['real_api_cost'], 0)
        self.assertIs(result['real_topic_approved'], False)
        self.assertIs(result['production_accepted'], False)
        self.assertIs(result['publish_authorized'], False)
        self.assertEqual(len(self.client.calls), 8)
        self.assertEqual([call['model'] for call in self.client.calls],
                         ['mock-writer', 'mock-reviewer'] * 4)
        self.assert_unique_calls()
        for name in ('outline', 'draft', 'candidate'):
            path = self.articles() / (name + '.md')
            self.assertTrue(path.is_file())
            self.assertIn('TEST', path.read_text())
        self.assertEqual(self.fixture['topic_card']['status'], 'proposed')
        self.assertFalse(self.fixture['topic_card']['writing_started'])
        self.assertFalse(self.fixture['topic_card']['publish_authorized'])

    def test_unconfirmed_proposal_cannot_start_writing(self):
        self.assert_blocked()
        self.assertEqual(self.client.calls, [])
        self.assertFalse(self.articles().exists())

    def test_pending_confirmation_cannot_start_writing(self):
        try:
            self.confirm(decision='pending')
        except (store.OfflineError, ValueError):
            self.assertEqual(self.client.calls, [])
            return
        self.assert_blocked()
        self.assertEqual(self.client.calls, [])

    def test_confirmation_api_defaults_to_pending_without_implicit_approval(self):
        self.write_config()
        relative = self.writing().create_fixture_confirmation(
            self.root, self.config_path, 'default-pending')
        record = store.checked_yaml(self.root, relative)
        self.assertEqual(record['decision'], 'pending')
        self.assertIs(record['writing_authorized'], False)
        self.config['confirmation'] = relative
        self.assert_blocked()
        self.assertEqual(self.client.calls, [])

    def test_revoked_fixture_confirmation_cannot_start_or_resume_writing(self):
        self.confirm()
        self.writing().revoke_fixture_confirmation(self.root, self.config_path, '模拟用户撤回确认。')
        self.assert_blocked()
        self.assertEqual(self.client.calls, [])

    def test_revocation_after_completed_run_preserves_outputs_and_blocks_resume(self):
        self.confirm()
        self.run_writing()
        before = {path: path.read_bytes() for path in self.articles().glob('*.md')}
        self.writing().revoke_fixture_confirmation(self.root, self.config_path, '模拟撤回，保留已有测试稿。')
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 8)
        for path, payload in before.items():
            self.assertEqual(path.read_bytes(), payload)

    def test_existing_real_topic_card_is_never_approved_by_fixture_helper(self):
        path = self.root / 'articles/test/custom-topic/real-proposal.md'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('---\nstatus: proposed\napproval_required: true\nwriting_started: false\n'
                        'publish_authorized: false\n---\n# 现有选题，尚未人工确认\n')
        before = path.read_bytes()
        self.config['fixture'] = {'path': path.relative_to(self.root).as_posix(),
                                  'sha256': store.digest(before)}
        with self.assertRaises((store.OfflineError, ValueError)):
            self.confirm()
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(self.client.calls, [])

    def test_confirmation_is_bound_to_angle_audience_and_evidence(self):
        self.confirm()
        original = copy.deepcopy(self.fixture)
        for field in ('angle', 'audience'):
            self.fixture = copy.deepcopy(original)
            self.fixture['topic_card'][field] += '（已修改）'
            self.write_fixture()
            with self.subTest(field=field):
                self.assert_blocked()
                self.assertEqual(self.client.calls, [])
        self.fixture = copy.deepcopy(original)
        self.fixture['evidence'][0]['text'] += ' 已修改的证据。'
        self.write_fixture()
        self.assert_blocked()
        self.assertEqual(self.client.calls, [])

    def test_running_batch_is_bound_to_models_and_budget(self):
        self.confirm()
        self.run_writing()
        original = copy.deepcopy(self.config)
        self.config['models']['writing'] = 'mock-another-writer'
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 8)
        self.config = copy.deepcopy(original)
        self.config['budget']['max_calls'] = 10
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 8)

    def test_same_writer_and_reviewer_models_cannot_start(self):
        self.config['models']['review'] = self.config['models']['writing']
        try:
            self.confirm()
        except (store.OfflineError, ValueError):
            return
        self.assert_blocked()
        self.assertEqual(self.client.calls, [])

    def test_real_backend_or_client_is_rejected_before_inference(self):
        self.confirm()
        self.config['backend'] = 'chatgpt_plan'
        self.assert_blocked()
        self.assertEqual(self.client.calls, [])
        self.config['backend'] = 'mock'
        self.client.backend = 'chatgpt_plan'
        self.assert_blocked()
        self.assertEqual(self.client.calls, [])

    def test_actual_model_mismatch_stops_without_retry(self):
        self.confirm()
        self.client.actual_model = 'mock-unexpected-model'
        self.assert_blocked()
        before = len(self.client.calls)
        self.assertEqual(before, 1)
        self.client.actual_model = None
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), before)

    def test_review_receives_same_evidence_and_confirmed_angle_as_writer(self):
        self.confirm()
        self.run_writing()
        for index in range(0, len(self.client.calls), 2):
            generation, review = [call['payload'] for call in self.client.calls[index:index + 2]]
            for key in ('stage', 'revision', 'topic_card', 'evidence', 'confirmation'):
                self.assertEqual(generation[key], review[key])
            self.assertIn('candidate', review)

    def test_completed_resume_is_cached_without_new_mock_requests(self):
        self.confirm()
        first = self.run_writing()
        second = self.run_writing()
        self.assertEqual(first['status'], second['status'])
        self.assertEqual(len(self.client.calls), 8)
        self.assert_unique_calls()

    def test_default_fixture_backend_needs_no_membership_client(self):
        self.confirm()
        with mock.patch.dict(sys.modules, {'researchdesk_membership': None}):
            result = self.writing().run(self.root, self.config_path, 'default-mock', client=None)
        self.assertEqual(result['backend'], 'mock')
        self.assertEqual(result['status'], 'test_accepted')
        self.assertEqual(result['completed_calls'], 8)
        self.assertEqual(self.client.calls, [])

    def test_each_controlled_interruption_resumes_without_duplicate_requests(self):
        self.confirm()
        with self.assertRaises(store.SimulatedInterruption):
            self.run_writing(fail_after='after_outline')
        self.assertFalse((self.articles() / 'outline.md').exists())
        events = store.read_events(self.root, self.directory().relative_to(self.root).as_posix())
        self.assertTrue(any(event['type'] == 'stage_accepted' and event['stage'] == 'outline'
                            for event in events))
        self.run_writing()
        self.assertEqual(len(self.client.calls), 8)
        self.assert_unique_calls()

    def test_interruption_after_review_resumes_without_new_review_requests(self):
        self.confirm()
        with self.assertRaises(store.SimulatedInterruption):
            self.run_writing(fail_after='after_review')
        self.run_writing()
        self.assertEqual(len(self.client.calls), 8)
        self.assert_unique_calls()

    def test_interruption_after_first_output_preserves_written_output(self):
        self.confirm()
        with self.assertRaises(store.SimulatedInterruption):
            self.run_writing(fail_after='after_first_output')
        existing = {path: path.read_bytes() for path in self.articles().glob('*.md')}
        self.assertTrue(existing)
        self.run_writing()
        for path, payload in existing.items():
            self.assertEqual(path.read_bytes(), payload)
        self.assertEqual(len(self.client.calls), 8)
        self.assert_unique_calls()

    def test_unknown_mock_request_outcome_is_reserved_and_never_reissued(self):
        self.confirm()
        self.client.fail_on_call = 1
        try:
            self.assert_blocked()
        except OSError:
            pass
        self.assertEqual(len(self.client.calls), 1)
        self.client.fail_on_call = None
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 1)

    def test_unknown_paragraph_evidence_cannot_be_reviewed_or_published(self):
        self.confirm()
        self.client.generation_mutator = lambda stage, candidate: candidate['sections'][0]['paragraphs'][0].update(
            evidence_ids=['E999'])
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 1)
        self.assertFalse((self.articles() / 'candidate.md').exists())

    def test_writer_cannot_return_approval_or_publication_authorization(self):
        self.confirm()
        self.client.generation_mutator = lambda stage, candidate: candidate.update(publish_authorized=True)
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 1)

    def test_inference_evidence_cannot_be_relabelled_as_original_fact(self):
        self.confirm()
        self.client.generation_mutator = lambda stage, candidate: candidate['sections'][0]['paragraphs'][0].update(
            kind='fact', evidence_ids=['E3'])
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 1)

    def test_actual_response_must_respect_output_character_budget(self):
        self.config['budget']['max_output_chars'] = 1000
        self.confirm()
        self.client.generation_mutator = lambda stage, candidate: candidate.update(summary='x' * 2000)
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 1)

    def test_review_must_check_every_paragraph(self):
        self.confirm()
        self.client.review_mutator = lambda stage, review: review['checks'].pop()
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 2)

    def test_blocking_issue_prevents_pass(self):
        self.confirm()
        self.client.review_mutator = lambda stage, review: review['issues'].append({
            'severity': 'blocking', 'location': 'sections.0', 'reason': '证据不支持这一段。',
            'suggestion': '删除或缩小主张。'})
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 2)

    def test_reject_does_not_start_later_stages(self):
        self.confirm()
        self.client.review_mutator = lambda stage, review: review.update(decision='reject')
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 2)
        self.assertFalse((self.articles() / 'draft.md').exists())
        self.assertFalse((self.articles() / 'candidate.md').exists())

    def test_repeated_revision_request_stops_at_one_revision(self):
        self.confirm()
        self.client.review_mutator = lambda stage, review: review.update(decision='revise')
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 4)
        self.assertTrue(all(call['payload']['stage'] == 'outline' for call in self.client.calls))
        self.run_writing()
        self.assertEqual(len(self.client.calls), 4)

    def test_total_call_budget_stops_without_creating_partial_articles(self):
        self.config['budget']['max_calls'] = 6
        self.confirm()
        self.assert_blocked()
        self.assertLessEqual(len(self.client.calls), 6)
        self.assertFalse(any(self.articles().glob('*.md')))
        before = len(self.client.calls)
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), before)

    def test_per_stage_budget_stops_before_unauthorized_revision(self):
        self.config['budget']['max_calls_per_stage'] = 2
        self.config['budget']['max_calls'] = 6
        self.confirm()
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 4)
        self.assertFalse(any(call['payload']['stage'] == 'candidate' for call in self.client.calls))

    def test_zero_revision_policy_does_not_revise_rejected_draft(self):
        self.config['budget']['max_revisions'] = 0
        self.confirm()
        self.assert_blocked()
        self.assertEqual(len(self.client.calls), 4)

    def test_config_escape_cross_topic_and_duplicate_yaml_are_rejected(self):
        original = copy.deepcopy(self.config)
        for change in ({'topic': 'another-topic'}, {'topics_file': '../outside.yaml'},
                       {'fixture': {'path': '../outside.yaml', 'sha256': '0' * 64}}):
            self.config = dict(copy.deepcopy(original), **change)
            with self.subTest(change=change):
                try:
                    self.confirm()
                except (store.OfflineError, ValueError):
                    continue
                self.assert_blocked()
                self.assertEqual(self.client.calls, [])
        self.config = copy.deepcopy(original)
        self.write_config()
        self.config_path.write_text(self.config_path.read_text() + '\nbackend: chatgpt_plan\n')
        with self.assertRaises((store.OfflineError, ValueError, yaml.YAMLError)):
            self.writing().run(self.root, self.config_path, 'duplicate-yaml', client=self.client)
        self.assertEqual(self.client.calls, [])

    def test_invalid_config_fields_and_budget_are_rejected_before_confirmation(self):
        original = copy.deepcopy(self.config)
        changes = [dict(original, mode='production'), dict(original, surprise='unsupported')]
        for key, value in (('max_calls', True), ('max_calls', 13),
                           ('max_calls_per_stage', 5), ('max_revisions', 2)):
            changed = copy.deepcopy(original)
            changed['budget'][key] = value
            changes.append(changed)
        for index, changed in enumerate(changes):
            self.config = changed
            with self.subTest(change=index), self.assertRaises((store.OfflineError, ValueError, yaml.YAMLError)):
                self.confirm()
        self.assertEqual(self.client.calls, [])

    def test_fixture_real_url_is_rejected_without_creating_confirmation(self):
        self.fixture['evidence'][0]['text'] += ' https://arxiv.org/abs/2310.08560'
        self.write_fixture()
        with self.assertRaises((store.OfflineError, ValueError)):
            self.confirm()
        self.assertEqual(self.client.calls, [])

    def test_article_symlink_cannot_overwrite_formal_notes(self):
        self.confirm()
        target = self.root / 'articles/human'
        target.mkdir()
        note = target / 'outline.md'
        note.write_text('正式人工文章，请保留。\n')
        link = self.articles()
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target, target_is_directory=True)
        before = note.read_bytes()
        self.assert_blocked()
        self.assertEqual(note.read_bytes(), before)
        self.assertEqual(list(target.iterdir()), [note])

    def test_mutated_confirmation_is_never_trusted_or_overwritten(self):
        path = self.confirm()
        value = yaml.safe_load(path.read_text())
        value['audience'] += '（被改动）'
        path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False))
        path.with_name(path.name + '.sha256').write_text(store.digest(path.read_bytes()) + '\n')
        before = path.read_bytes()
        self.assert_blocked()
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(self.client.calls, [])

    def test_human_edit_to_generated_article_is_never_overwritten(self):
        self.confirm()
        self.run_writing()
        path = self.articles() / 'draft.md'
        path.write_text(path.read_text() + '\n人工修改，请保留。\n')
        before = path.read_bytes()
        self.assert_blocked()
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(len(self.client.calls), 8)

    def test_preexisting_formal_and_test_notes_are_unchanged(self):
        self.confirm()
        notes = [self.root / 'articles/formal.md', self.root / 'reports/test/custom-topic/human.md']
        for path in notes:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('人工笔记，不可覆盖。\n')
        before = {path: path.read_bytes() for path in notes}
        self.run_writing()
        for path, payload in before.items():
            self.assertEqual(path.read_bytes(), payload)

    def test_only_test_output_is_created_and_no_scheduler_is_installed(self):
        self.confirm()
        before = {path: path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
        self.run_writing()
        for path, payload in before.items():
            self.assertEqual(path.read_bytes(), payload, str(path))
        for path in self.root.rglob('*'):
            if not path.is_file() or path in before:
                continue
            relative = path.relative_to(self.root).as_posix()
            if relative == 'reports/test/custom-topic/.offline.lock':
                continue
            self.assertTrue(relative.startswith(('reports/test/custom-topic/writing-runs/first/',
                                                  'articles/test/custom-topic/first/')), relative)
        self.assertFalse((self.root / '.github').exists())


if __name__ == '__main__':
    unittest.main()
