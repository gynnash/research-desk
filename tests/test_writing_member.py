"""Real Writing gates in disposable, locally synchronized workbenches.

Existing admission proofs are copied unchanged. A real ConfirmationStore and
GitPublisher confirm an isolated copy of the topic against a local bare origin.
Only membership responses are simulated; provenance, review validation, budget
accounting and create-only output protection execute their real code paths.
These checks never confirm a topic in the user's vault or access the network.
"""

import importlib
import json
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import yaml


REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / 'scripts'))
import researchdesk_batch as shared
import researchdesk_retired as retired
import researchdesk_confirmation as confirmation
import researchdesk_membership as membership
import researchdesk_offline as store
import researchdesk_sources as sources

TOPIC = 'agent-memory'
CYCLE = 'cycle-agent-memory-gh-20261019'
CARD = 'formal-topic-agent-memory-%s-1' % CYCLE
ADMISSION = 'reports/%s/admissions/%s' % (TOPIC, CYCLE)


class BoundedMemberClient:
    """Transport double; actual candidate/review/proof validators stay enabled."""

    backend = 'chatgpt_plan'

    def __init__(self, models):
        self.selected = models
        self.calls = []
        self.decisions = {}
        self.fail_on_call = None
        self.actual_model = None

    def models(self):
        return [{'slug': model} for model in self.selected.values()]

    def status(self):
        return {'authenticated': True, 'plan_permission': True,
                'authorization': 'official_chatgpt_oauth',
                'account_fingerprint': 'isolated-test-account-no-real-authorization'}

    def infer(self, model, instructions, input_text, **limits):
        request = json.loads(input_text)
        stage, revision = request['stage'], request['revision']
        role = 'review' if 'candidate' in request else 'writing'
        self.calls.append({'model': model, 'stage': stage, 'revision': revision,
                           'role': role, 'request': request, 'limits': limits})
        if len(self.calls) == self.fail_on_call:
            raise OSError('Isolated unknown response; no transport retry allowed')
        if role == 'writing':
            # The bounded body is long enough for an 800-character confirmation.
            paragraph = ('本文只基于提供的摘要与博客节选讨论记忆设计。这里的相关表述属于作者主张，'
                         '尚不能据此验证完整实验、具体实现或长期效果；实际取舍仍需进一步核实。') * 3
            result = {'title': request['confirmation']['title'],
                'summary': '这是隔离验收中的模拟写作响应，保留摘要与节选的证据限制。',
                'sections': [{'heading': '材料边界与研究问题', 'paragraphs': [
                    {'kind': 'author_claim', 'text': paragraph, 'evidence_ids': ['R1']}
                    for _ in range(3)]}],
                'limitations': ['仅覆盖已提供的摘要和博客节选，不代表完整论文、实验或产品验证。']}
        else:
            decision = self.decisions.get((stage, revision), 'pass')
            result = {'decision': decision, 'coverage_acknowledged': True,
                'issues': [] if decision == 'pass' else [{
                    'severity': 'warning', 'location': '材料边界',
                    'reason': '隔离验收要求核对表达边界。', 'suggestion': '继续明确资料覆盖范围。'}],
                'checks': [{'section_index': si, 'paragraph_index': pi,
                            'verdict': 'supported', 'evidence_ids': paragraph['evidence_ids']}
                           for si, section in enumerate(request['candidate']['sections'])
                           for pi, paragraph in enumerate(section['paragraphs'])]}
        return {'model': self.actual_model or model,
                'text': json.dumps(result, ensure_ascii=False),
                'response_id': 'isolated-writing-%s' % len(self.calls),
                'usage': {'input_tokens': 100, 'output_tokens': 120, 'total_tokens': 220}}


class RealMemberWriting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        plan = REPOSITORY / ADMISSION / 'plan.yaml'
        if not plan.is_file():
            raise unittest.SkipTest('需要已有真实独立审阅及正式准入证明；不联网或伪造 pass 补建')
        cls.plan = yaml.safe_load(plan.read_text(encoding='utf-8'))
        cls.inputs = importlib.import_module('researchdesk_writing_member_inputs')
        cls.writing = importlib.import_module('researchdesk_writing_member')

    def git(self, *arguments):
        return subprocess.run(['git', '-C', str(self.root), *arguments], check=True,
                              capture_output=True, text=True).stdout.strip()

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='researchdesk-member-writing-tests-')
        self.addCleanup(temporary.cleanup)
        parent = Path(temporary.name).resolve()
        self.root, self.origin = parent / 'workbench', parent / 'origin.git'
        self.root.mkdir()
        shutil.copytree(REPOSITORY / 'config', self.root / 'config')
        paths = set(self.plan['input_hashes']) | set(self.plan['protected_notes']) | set(self.plan['output_hashes'])
        paths |= {'README.md', '.gitignore', 'sources/README.md', 'reports/README.md',
                  'insights/README.md', 'articles/README.md', 'workflows/README.md',
                  'workflows/source-schema.md', 'workflows/maintenance.md',
                  'workflows/requirements.txt', 'workflows/validate.py',
                  'workflows/templates/paper.md', 'workflows/templates/blog.md'}
        paths |= {p.relative_to(REPOSITORY).as_posix()
                  for p in (REPOSITORY / ADMISSION).iterdir() if p.is_file()}
        for relative in list(paths):
            if (REPOSITORY / (relative + '.sha256')).is_file():
                paths.add(relative + '.sha256')
        for relative in sorted(paths):
            expected = self.plan['input_hashes'].get(relative, self.plan['protected_notes'].get(relative))
            if not (REPOSITORY / relative).exists() and retired.missing_hash(REPOSITORY, relative, expected):
                continue
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(REPOSITORY / relative, destination)
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'ResearchDesk isolated Writing test')
        self.git('config', 'user.email', 'writing-test@example.invalid')
        self.git('add', '.')
        self.git('commit', '-m', 'Copy genuine admission proof into isolated workbench')
        subprocess.run(['git', 'init', '--bare', '--initial-branch=main', str(self.origin)],
                       check=True, capture_output=True)
        self.git('remote', 'add', 'origin', str(self.origin))
        self.git('push', '-u', 'origin', 'main')
        self.config = confirmation.load_config(self.root)
        self.app = confirmation.ConfirmationStore(self.root, self.config)
        self.client = BoundedMemberClient(self.config['writing']['models'])
        self.original = self.hashes()
        for patcher in (
            mock.patch.object(membership.MembershipClient, 'infer',
                              side_effect=AssertionError('Actual membership calls prohibited')),
            mock.patch.object(sources.SafeFetcher, 'fetch',
                              side_effect=AssertionError('Source collection prohibited')),
            mock.patch.object(socket, 'create_connection', side_effect=AssertionError('Network prohibited')),
            mock.patch.object(socket.socket, 'connect', side_effect=AssertionError('Network prohibited')),
        ):
            self.addCleanup(patcher.stop)
            patcher.start()

    def hashes(self):
        return {p.relative_to(self.root).as_posix(): store.digest(p.read_bytes())
                for p in self.root.rglob('*') if p.is_file() and '.git' not in p.relative_to(self.root).parts}

    def confirm(self, app=None):
        app = app or self.app
        preview = app.preview(CARD, {'target_words': 800})
        return app.confirm(preview['preview_id'], acknowledged=True)

    def run_writing(self, record, **options):
        return self.writing.run(self.root, approval_id=record['id'], client=self.client, **options)

    def assert_original_unchanged(self):
        for relative, expected in self.original.items():
            self.assertEqual(store.digest((self.root / relative).read_bytes()), expected, relative)

    def assert_test_only(self, before):
        for relative in set(self.hashes()) - set(before):
            self.assertIn('test', Path(relative).parts, relative)
        self.assert_original_unchanged()

    def assert_no_articles(self):
        self.assertFalse(self.new_articles())

    def new_articles(self):
        return [p for p in (self.root / 'articles/test' / TOPIC).rglob('*.md')
                if p.relative_to(self.root).as_posix() not in self.original]

    def record_budget(self, entry, count, name):
        base = 'reports/test/%s/%s/%s' % (TOPIC, entry, name)
        store.save_yaml(self.root, base + '/manifest.yaml', {
            'schema_version': 1, 'backend': 'chatgpt_plan', 'created_at': shared.now(),
            'budget': {'month_max_calls': 100}})
        events = []
        for index in range(count):
            store.append_event(self.root, base, events, {
                'type': 'call_reserved', 'reservation_id': '%s-%s' % (name, index),
                'role': 'research' if entry == 'research-batches' else 'insight',
                'revision': 0, 'model_id': 'isolated-audit-fixture',
                'month': shared.now()[:7], 'at': shared.now(), 'usage_status': 'unknown'})

    def test_real_page_confirmation_is_required_and_mock_record_is_rejected(self):
        self.assertEqual(self.inputs.eligible(self.root), [])
        with self.assertRaises(store.OfflineError):
            self.inputs.prepare_bundle(self.root, 'approval-20260101-000000-000000000000')
        record = self.confirm()
        bundle = self.inputs.prepare_bundle(self.root, record['id'])
        self.assertEqual(bundle['approval_id'], record['id'])
        self.assertEqual(bundle['confirmation']['origin'], 'local_confirmation_page')
        self.assertEqual({item['id'] for item in bundle['evidence']}, {'R1', 'R2', 'H1'})
        self.assertTrue(any(item['source_urls'] for item in bundle['evidence']))
        self.assertEqual(bundle['topic_card']['target_words'], 800)
        path = self.root / record['record_path']
        value = yaml.safe_load(path.read_text(encoding='utf-8'))
        value.update(origin='offline_fixture', mode='writing_fixture_confirmation')
        path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding='utf-8')
        path.with_name(path.name + '.sha256').write_text(store.digest(path.read_bytes()) + '\n')
        self.git('add', '.')
        self.git('commit', '-m', 'Isolated forged fixture approval must not authorize real Writing')
        self.git('push', 'origin', 'main')
        with self.assertRaises(store.OfflineError):
            self.inputs.prepare_bundle(self.root, record['id'])
        self.assertFalse(self.client.calls)

    def test_unsynced_or_revoked_confirmation_never_authorizes_writing(self):
        unsynced = confirmation.ConfirmationStore(
            self.root, self.config, publisher=lambda root, files, message: False)
        record = self.confirm(unsynced)
        self.assertEqual(record['status'], 'pending_sync')
        with self.assertRaises(store.OfflineError):
            self.run_writing(record)
        synced = self.app.retry_sync(record['id'])
        self.assertTrue(synced['synced'])
        self.inputs.prepare_bundle(self.root, record['id'])
        self.app.revoke(record['id'], '隔离验收中模拟用户撤回')
        with self.assertRaises(store.OfflineError):
            self.run_writing(record)
        self.assertFalse(self.client.calls)
        self.assert_no_articles()

    def test_changed_evidence_stops_without_overwriting_human_change(self):
        record = self.confirm()
        bundle = self.inputs.prepare_bundle(self.root, record['id'])
        historical = next(item['path'] for item in bundle['evidence'] if item['origin'] == 'human_baseline')
        path = self.root / historical
        changed = path.read_bytes() + '\n人工补充：必须保留。\n'.encode('utf-8')
        path.write_bytes(changed)
        with self.assertRaises(store.OfflineError):
            self.run_writing(record)
        self.assertEqual(path.read_bytes(), changed)
        self.assertFalse(self.client.calls)
        self.assert_no_articles()

    def test_three_stages_have_independent_reviews_and_cached_replay_uses_zero_calls(self):
        record = self.confirm()
        before = self.hashes()
        result = self.run_writing(record)
        self.assertEqual(result['status'], 'test_accepted')
        self.assertEqual(result['new_model_calls'], 6)
        self.assertEqual(len(self.client.calls), 6)
        self.assertEqual([(call['stage'], call['role']) for call in self.client.calls],
                         [(stage, role) for stage in ('outline', 'draft', 'candidate')
                          for role in ('writing', 'review')])
        for call in self.client.calls:
            self.assertEqual(call['model'], self.config['writing']['models'][call['role']])
        self.assertEqual(len(set(result['actual_models'])), 2)
        self.assertEqual(len(result['output_hashes']), 3)
        self.assertFalse(result['publish_authorized'])
        for relative, expected in result['output_hashes'].items():
            path = self.root / relative
            self.assertEqual(store.digest(path.read_bytes()), expected)
            self.assertIn('> TEST', path.read_text(encoding='utf-8'))
            self.assertIn('https://', path.read_text(encoding='utf-8'))
            for target in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
                if '://' not in target:
                    self.assertTrue((path.parent / target.split('#', 1)[0]).resolve().is_file(), target)
        after = self.hashes()
        replay = self.run_writing(record)
        self.assertTrue(replay['cached'])
        self.assertEqual(replay['new_model_calls'], 0)
        self.assertEqual(len(self.client.calls), 6)
        self.assertEqual(self.hashes(), after)
        self.assert_test_only(before)

    def test_rejected_review_produces_no_markdown_artifacts(self):
        record = self.confirm()
        self.client.decisions[('outline', 0)] = 'reject'
        result = self.run_writing(record)
        self.assertEqual(result['status'], 'rejected')
        self.assertEqual(len(self.client.calls), 2)
        self.assertFalse(result['output_hashes'])
        self.assert_no_articles()
        self.assert_original_unchanged()

    def test_v2_author_opening_is_frozen_reviewed_and_replayed(self):
        notes = '我用一组业务输入检查过排序，发现实现与预期的优先级不同。'
        preview = self.app.preview(CARD, {'target_words': 800, 'author_notes': notes})
        record = self.app.confirm(preview['preview_id'], acknowledged=True)
        bundle = self.inputs.prepare_bundle(self.root, record['id'])
        self.assertEqual(bundle['style_profile']['version'], 'writing-v2')
        self.assertEqual(bundle['topic_card']['author_notes'], notes)
        self.assertTrue(any(item.get('original_excerpts') for item in bundle['evidence']))
        original_infer = self.client.infer

        def infer(model, instructions, input_text, **limits):
            request = json.loads(input_text)
            self.assertEqual(request['author_notes'], notes)
            self.assertIn(bundle['style_profile']['text'], instructions)
            result = original_infer(model, instructions, input_text, **limits)
            if 'candidate' not in request:
                candidate = json.loads(result['text'])
                candidate['sections'].insert(0, {'heading': '', 'paragraphs': [
                    {'kind': 'author_experience', 'text': notes, 'evidence_ids': []},
                    {'kind': 'commentary', 'text': '哪些要求需要在实现前明确？', 'evidence_ids': []}]})
                result['text'] = json.dumps(candidate, ensure_ascii=False)
            return result

        self.client.infer = infer
        result = self.run_writing(record)
        self.assertEqual(result['status'], 'test_accepted')
        self.assertEqual(len(self.client.calls), 6)
        for relative in result['output_hashes']:
            text = (self.root / relative).read_text()
            self.assertIn(notes, text)
            self.assertNotIn('**原作者声称', text)
            self.assertNotIn('## 导读', text)
        job = importlib.import_module('researchdesk_writing_job')
        self.assertEqual(job.verify_result(self.root, bundle)['status'], 'test_accepted')
        progress = self.app.list_confirmations()[0]['writing']
        self.assertEqual(progress['status'], 'test_accepted')
        self.assertEqual(len(progress['documents']), 3)
        self.assertEqual(self.run_writing(record)['new_model_calls'], 0)
        self.assertEqual(len(self.client.calls), 6)
        self.assert_original_unchanged()

    def test_one_revision_is_bounded_and_reuses_explicit_review_feedback(self):
        record = self.confirm()
        self.client.decisions[('outline', 0)] = 'revise'
        result = self.run_writing(record, max_new_calls=8)
        self.assertEqual(result['status'], 'test_accepted')
        self.assertEqual(len(self.client.calls), 8)
        outline = [call for call in self.client.calls if call['stage'] == 'outline']
        self.assertEqual([call['revision'] for call in outline], [0, 0, 1, 1])
        self.assertIn('previous_review', outline[2]['request'])
        self.assertEqual(result['stages']['outline']['revision_count'], 1)
        self.assert_original_unchanged()

    def test_shared_100_call_budget_includes_research_insight_and_unknown_reservations(self):
        record = self.confirm()
        budget_config = {'backend': 'chatgpt_plan', 'budget': {'month_max_calls': 100}}
        existing, ceiling = shared.monthly_budget(self.root, budget_config)
        self.assertEqual(ceiling, 100)
        self.assertLess(existing, 60)
        self.record_budget('research-batches', 40, 'isolated-budget-research')
        self.record_budget('insight-runs', 60 - existing, 'isolated-budget-insight')
        self.assertEqual(shared.monthly_budget(self.root, budget_config), (100, 100))
        with self.assertRaises(store.OfflineError):
            self.run_writing(record)
        self.assertFalse(self.client.calls)
        self.assert_no_articles()
        self.assertEqual(shared.monthly_budget(self.root, budget_config), (100, 100))

    def test_unknown_model_outcome_is_reserved_and_never_resent(self):
        record = self.confirm()
        self.client.fail_on_call = 1
        budget_config = {'backend': 'chatgpt_plan', 'budget': {'month_max_calls': 100}}
        previous, _ = shared.monthly_budget(self.root, budget_config)
        with self.assertRaises((OSError, store.OfflineError)):
            self.run_writing(record)
        self.assertEqual(len(self.client.calls), 1)
        self.client.fail_on_call = None
        with self.assertRaises(store.OfflineError):
            self.run_writing(record)
        self.assertEqual(len(self.client.calls), 1)
        self.assertEqual(shared.monthly_budget(self.root, budget_config), (previous + 1, 100))
        self.assert_no_articles()
        self.assert_original_unchanged()

    def test_existing_human_test_article_is_preserved(self):
        record = self.confirm()
        with self.assertRaises(store.SimulatedInterruption):
            self.run_writing(record, fail_after='after_first_output')
        articles = self.new_articles()
        self.assertEqual(len(articles), 1)
        target = articles[0]
        changed = target.read_bytes() + '\n人工写作笔记：请保留。\n'.encode('utf-8')
        target.write_bytes(changed)
        with self.assertRaises(store.OfflineError):
            self.run_writing(record)
        self.assertEqual(target.read_bytes(), changed)
        self.assertEqual(len(self.client.calls), 6)
        self.assert_original_unchanged()

    def test_job_transfer_rejects_changed_inputs_and_conflicts_then_saves_test_only(self):
        job = importlib.import_module('researchdesk_writing_job')
        record = self.confirm()
        bundle = self.inputs.prepare_bundle(self.root, record['id'])
        state, artifact = self.root.parent / 'state', self.root.parent / 'artifact'
        job.transfer.json_write(state / 'context.json', job.context(self.root, bundle))
        result = self.run_writing(record)
        exported = job.export(self.root, state, artifact)
        self.assertTrue(exported['files'])
        self.assertTrue(all('test' in Path(relative).parts for relative in exported['files']))
        self.assertTrue(set(result['output_hashes']).issubset(exported['files']))

        def clone(name):
            target = self.root.parent / name
            subprocess.run(['git', 'clone', '--quiet', str(self.origin), str(target)],
                           check=True, capture_output=True)
            return target

        conflicted = clone('conflicted-publisher')
        config_path = conflicted / 'config/research_topics.yaml'
        original_config = config_path.read_bytes()
        changed = original_config + b'\n# Isolated human configuration change\n'
        config_path.write_bytes(changed)
        with self.assertRaises(job.JobError):
            job.apply(conflicted, artifact)
        self.assertEqual(config_path.read_bytes(), changed)
        self.assertTrue(all(not (conflicted / relative).exists() for relative in result['output_hashes']))
        config_path.write_bytes(original_config)
        manual = conflicted / next(iter(result['output_hashes']))
        manual.parent.mkdir(parents=True, exist_ok=True)
        content = '# 人工测试写作笔记：自动回存不可覆盖。\n'.encode('utf-8')
        manual.write_bytes(content)
        with self.assertRaises(job.JobError):
            job.apply(conflicted, artifact)
        self.assertEqual(manual.read_bytes(), content)

        publisher = clone('clean-publisher')
        original_notes = {relative: (publisher / relative).read_bytes()
                          for relative in self.original if Path(relative).suffix == '.md'}
        saved = job.apply(publisher, artifact)
        self.assertEqual(saved['status'], 'test_accepted')
        self.assertEqual(saved['completed_calls'], 6)
        self.assertGreater(saved['saved_files'], 3)
        self.assertFalse(saved['production_accepted'])
        self.assertEqual(len(self.client.calls), 6)
        for relative, content in original_notes.items():
            self.assertEqual((publisher / relative).read_bytes(), content, relative)
        changes = subprocess.run(
            ['git', '-C', str(publisher), 'diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD'],
            check=True, capture_output=True, text=True).stdout.splitlines()
        self.assertTrue(changes)
        self.assertTrue(all('test' in Path(relative).parts for relative in changes))
        replay = job.apply(publisher, artifact)
        self.assertEqual(replay['saved_files'], 0)
        self.assertEqual(replay['commit'], saved['commit'])
        self.assertEqual(len(self.client.calls), 6)

    def complete_synced_batch(self):
        record = self.confirm()
        result = self.run_writing(record)
        self.git('add', '.')
        self.git('commit', '-m', 'Save isolated reviewed Writing checkpoints')
        self.git('push', 'origin', 'main')
        return record, result

    def test_zero_call_job_verifies_locally_without_any_membership_contact(self):
        job = importlib.import_module('researchdesk_writing_job')
        record, result = self.complete_synced_batch()
        before = self.hashes()
        host = self.root.parent / 'external-runtime'
        (host / 'bin').mkdir(parents=True)
        (host / 'bin/python').touch()
        state = self.root.parent / 'zero-local-state'
        prohibited = AssertionError('Zero-call verification must not contact membership')
        with mock.patch.dict('os.environ', {'GITHUB_ACTIONS': 'false'}), \
                mock.patch.object(job.runtime, 'load_config', return_value={
                    '_venv': host, '_profile': self.root.parent / 'unused-profile'}), \
                mock.patch.object(job.member, 'run', side_effect=prohibited), \
                mock.patch.object(shared, 'authorization', side_effect=prohibited), \
                mock.patch.object(membership.MembershipClient, '__init__', side_effect=prohibited), \
                mock.patch.object(membership.MembershipClient, 'status', side_effect=prohibited), \
                mock.patch.object(membership.MembershipClient, 'models', side_effect=prohibited):
            self.assertEqual(job.execute(self.root, state, record['id'], max_new_calls=0), 0)
        self.assertEqual(self.hashes(), before)
        self.assertEqual(len(self.client.calls), result['completed_calls'])

    def test_zero_call_actions_receipt_is_exported_verified_and_saved_create_only(self):
        job = importlib.import_module('researchdesk_writing_job')
        record, result = self.complete_synced_batch()
        before = self.hashes()
        host = self.root.parent / 'external-runtime'
        (host / 'bin').mkdir(parents=True)
        (host / 'bin/python').touch()
        state, artifact = self.root.parent / 'zero-actions-state', self.root.parent / 'zero-actions-artifact'
        env = {'GITHUB_ACTIONS': 'true', 'GITHUB_REF': 'refs/heads/main',
               'GITHUB_EVENT_NAME': 'workflow_dispatch', 'GITHUB_RUN_ID': '1234567', 'GITHUB_RUN_ATTEMPT': '2',
               'GH_TOKEN': 'isolated-placeholder-for-local-bare-origin-no-network'}
        prohibited = AssertionError('Zero-call verification must not contact membership')
        with mock.patch.dict('os.environ', env), \
                mock.patch.object(job.runtime, 'load_config', return_value={
                    '_venv': host, '_profile': self.root.parent / 'unused-profile'}), \
                mock.patch.object(job.member, 'run', side_effect=prohibited), \
                mock.patch.object(shared, 'authorization', side_effect=prohibited), \
                mock.patch.object(membership.MembershipClient, '__init__', side_effect=prohibited), \
                mock.patch.object(membership.MembershipClient, 'status', side_effect=prohibited), \
                mock.patch.object(membership.MembershipClient, 'models', side_effect=prohibited):
            self.assertEqual(job.execute(self.root, state, record['id'], max_new_calls=0), 0)
        relative = 'reports/test/%s/writing-runs/writing-%s/verifications/gha-1234567-2.yaml' % (TOPIC, record['id'])
        proof = store.checked_yaml(self.root, relative)
        self.assertEqual(proof['output_hashes'], result['output_hashes'])
        self.assertEqual(proof['completed_calls'], 6)
        self.assertEqual(proof['new_model_calls'], 0)
        self.assertTrue(proof['no_membership_contacts'])
        self.assertEqual(proof['effective_month_max_calls'], 100)
        for path, sha in before.items():
            self.assertEqual(store.digest((self.root / path).read_bytes()), sha, path)
        exported = job.export(self.root, state, artifact)
        self.assertEqual(set(exported['files']), {relative, relative + '.sha256'})
        publisher = self.root.parent / 'zero-actions-publisher'
        subprocess.run(['git', 'clone', '--quiet', str(self.origin), str(publisher)],
                       check=True, capture_output=True)
        saved = job.apply(publisher, artifact)
        self.assertEqual(saved['status'], 'test_accepted')
        self.assertEqual(saved['saved_files'], 2)
        self.assertEqual(store.checked_yaml(publisher, relative), proof)
        self.assertEqual(job.apply(publisher, artifact)['saved_files'], 0)
        # A matching checksum cannot turn a false contact/call claim into proof.
        tampered = dict(proof, new_model_calls=1)
        payload = yaml.safe_dump(tampered, allow_unicode=True, sort_keys=False).encode()
        (artifact / 'payload' / relative).write_bytes(payload)
        marker = (store.digest(payload) + '\n').encode()
        (artifact / 'payload' / (relative + '.sha256')).write_bytes(marker)
        exported['files'].update({relative: store.digest(payload), relative + '.sha256': store.digest(marker)})
        (artifact / 'manifest.json').write_text(json.dumps(exported), encoding='utf-8')
        with self.assertRaises(job.JobError):
            job.apply(publisher, artifact)
        self.assertEqual(store.checked_yaml(publisher, relative), proof)
        self.assertEqual(len(self.client.calls), 6)


if __name__ == '__main__':
    unittest.main()
