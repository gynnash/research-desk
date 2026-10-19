#!/usr/bin/env python3
"""Trusted-main membership Writing worker and create-only TEST checkpoints."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import researchdesk_job as transfer
import researchdesk_offline as store
import researchdesk_batch as shared
import researchdesk_runner as runtime
import researchdesk_writing_member as member
import researchdesk_writing_member_inputs as inputs
import researchdesk_confirmation_inputs as confirmation_inputs


JobError = transfer.JobError
git, safe, tracked = transfer.git, transfer.safe, transfer.tracked
CONTEXT_FIELDS = {'schema_version', 'mode', 'topic', 'approval_id', 'batch_id',
                  'base_commit', 'baseline_blobs', 'input_fingerprint', 'config_path'}
VERIFICATION = re.compile(r'verifications/gha-([1-9][0-9]{0,19})-([1-9][0-9]{0,5})\.yaml\Z')


def context(root, bundle):
    return {'schema_version': 1, 'mode': 'writing_member_job', 'topic': bundle['topic'],
        'approval_id': bundle['approval_id'], 'batch_id': bundle['batch_id'],
        'base_commit': git(root, 'rev-parse', 'HEAD').decode().strip(),
        'baseline_blobs': tracked(root), 'input_fingerprint': bundle['input_fingerprint'],
        'config_path': bundle['config']['path']}


def _context(value, artifact=False):
    if (not isinstance(value, dict) or set(value) != CONTEXT_FIELDS | ({'files'} if artifact else set())
            or value.get('schema_version') != 1 or value.get('mode') != 'writing_member_job'
            or not isinstance(value.get('topic'), str)
            or not re.fullmatch(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*', value['topic'])
            or not isinstance(value.get('approval_id'), str)
            or not inputs.APPROVAL.fullmatch(value['approval_id'])
            or value.get('batch_id') != 'writing-' + value['approval_id']
            or not isinstance(value.get('base_commit'), str)
            or not inputs.COMMIT.fullmatch(value['base_commit'])
            or not isinstance(value.get('input_fingerprint'), str)
            or not confirmation_inputs.HASH.fullmatch(value['input_fingerprint'])
            or not isinstance(value.get('baseline_blobs'), dict)
            or not value['baseline_blobs']
            or not isinstance(value.get('config_path'), str)):
        raise JobError('writing_transfer_context_invalid')
    for path, blob in value['baseline_blobs'].items():
        if not isinstance(path, str) or not isinstance(blob, str) or not inputs.COMMIT.fullmatch(blob):
            raise JobError('writing_baseline_invalid')
    if artifact and (not isinstance(value['files'], dict) or len(value['files']) > 1000):
        raise JobError('writing_transfer_files_invalid')
    return value


def _clean_tracked(root):
    if git(root, 'diff', '--name-only') or git(root, 'diff', '--cached', '--name-only'):
        raise JobError('writing_tracked_files_changed_preserve_worker')


def allowed(relative, value):
    path = Path(relative)
    if (not isinstance(relative, str) or path.is_absolute() or path.as_posix() != relative
            or '..' in path.parts or '\\' in relative
            or any(part.startswith('.') for part in path.parts)):
        return False
    article = 'articles/test/%s/%s/' % (value['topic'], value['batch_id'])
    if relative.startswith(article):
        return relative[len(article):] in {'outline.md', 'draft.md', 'candidate.md'}
    base = 'reports/test/%s/writing-runs/%s/' % (value['topic'], value['batch_id'])
    if not relative.startswith(base):
        return False
    leaf = relative[len(base):].removesuffix('.sha256')
    return bool(leaf in {'manifest.yaml', 'receipt.yaml', 'artifact-plan.yaml'}
        or re.fullmatch(r'checkpoints/(?:outline|draft|candidate)-(?:writing|review)-[01]\.yaml', leaf)
        or re.fullmatch(r'stages/(?:outline|draft|candidate)\.yaml', leaf)
        or re.fullmatch(r'(?:events|partial)/[0-9]{6}\.yaml', leaf)
        or VERIFICATION.fullmatch(leaf))


def _untracked(root):
    return [path.decode() for path in git(root, 'ls-files', '--others', '--exclude-standard', '-z').split(b'\0') if path]


def inspect_files(root, files, value):
    for relative in files:
        if not allowed(relative, value):
            raise JobError('writing_transfer_outside_exact_test_paths')
        path = safe(root, relative)
        if not path.is_file():
            raise JobError('writing_transfer_file_missing')
        transfer.check_text(path.read_bytes(), relative)
        if relative.endswith('.yaml'):
            marker = safe(root, relative + '.sha256')
            if not marker.is_file() or marker.read_text().strip() != store.digest(path.read_bytes()):
                raise JobError('writing_incomplete_yaml_preserve_worker')
            store.load_yaml(path)
        elif relative.endswith('.sha256'):
            original = safe(root, relative[:-7])
            if not original.is_file() or path.read_text().strip() != store.digest(original.read_bytes()):
                raise JobError('writing_checkpoint_digest_invalid')


def check_baseline(root, value, publisher=False):
    _context({key: value[key] for key in CONTEXT_FIELDS})
    current = tracked(root)
    if any(current.get(path) != blob for path, blob in value['baseline_blobs'].items()):
        raise JobError('writing_main_inputs_changed_preserve_checkpoint')
    _clean_tracked(root)
    if not publisher and (current != value['baseline_blobs'] or
            git(root, 'rev-parse', 'HEAD').decode().strip() != value['base_commit']):
        raise JobError('writing_worker_baseline_changed_preserve_checkpoint')


def checkpoint_files(root, value):
    check_baseline(root, value)
    files = _untracked(root)
    inspect_files(root, files, value)
    return files


def execute(root, state, approval_id, config_path='config/confirmation.yaml', max_new_calls=6, fail_after=None):
    root, state = Path(root).resolve(), Path(state).absolute()
    if (os.environ.get('GITHUB_ACTIONS') == 'true' and
            (os.environ.get('GITHUB_REF') != 'refs/heads/main'
             or os.environ.get('GITHUB_EVENT_NAME') != 'workflow_dispatch')):
        raise JobError('writing_trusted_main_manual_dispatch_required')
    if type(max_new_calls) is not int or not 0 <= max_new_calls <= 6:
        raise JobError('writing_small_validation_limit_is_six')
    if state.resolve().is_relative_to(root) or any(path.is_symlink() for path in (state, *state.parents)):
        raise JobError('writing_state_must_be_external_regular_directory')
    _clean_tracked(root)
    member.refresh_origin(root)
    bundle = inputs.prepare_bundle(root, approval_id, config_path)
    value = context(root, bundle)
    inspect_files(root, _untracked(root), value)
    host = runtime.load_config(root)
    python = host['_venv'] / 'bin/python'
    if not python.is_file():
        raise JobError('writing_configured_external_python_missing')
    transfer.json_write(state / 'context.json', value)
    if max_new_calls == 0:
        # Recheck completed results without constructing a membership client,
        # refreshing its OAuth token, or contacting its model/status endpoints.
        try:
            result = _verify(root, value)
            if result['status'] != 'test_accepted':
                raise JobError('writing_zero_call_verification_requires_complete_accepted_batch')
            if os.environ.get('GITHUB_ACTIONS') == 'true':
                run_id, attempt = os.environ.get('GITHUB_RUN_ID', ''), os.environ.get('GITHUB_RUN_ATTEMPT', '')
                leaf = 'verifications/gha-%s-%s.yaml' % (run_id, attempt)
                if not VERIFICATION.fullmatch(leaf):
                    raise JobError('writing_github_verification_identity_invalid')
                base = 'reports/test/%s/writing-runs/%s/' % (value['topic'], value['batch_id'])
                store.save_yaml(root, base + leaf, _verification(root, value, result, run_id, attempt))
        finally:
            check_baseline(root, value)
        print(json.dumps(dict(result, approval_id=approval_id, batch_id=value['batch_id'],
            exit_code=0, new_model_calls=0, no_membership_contacts=True,
            output_mode='test_only', publish_authorized=False)))
        return 0
    command = [str(python), str(root / 'scripts/researchdesk_writing_member.py'), '--root', str(root),
               '--config', config_path, '--approval-id', approval_id,
               '--max-new-calls', str(max_new_calls), '--profile', str(host['_profile'])]
    if fail_after is not None:
        if fail_after not in {'after_outline', 'after_review', 'after_first_output'}:
            raise JobError('writing_acceptance_interruption_invalid')
        command += ['--fail-after', fail_after]
    try:
        result = subprocess.run(command, cwd=root, capture_output=True, check=False, timeout=1800)
    finally:
        check_baseline(root, value)
    # Never forward model output, private profile paths or provider errors.
    print(json.dumps({'approval_id': approval_id, 'batch_id': value['batch_id'],
                      'exit_code': result.returncode, 'output_mode': 'test_only', 'publish_authorized': False}))
    return result.returncode


def export(root, state, destination):
    root, state, destination = Path(root).resolve(), Path(state), Path(destination)
    value = _context(json.loads((state / 'context.json').read_text()))
    files = checkpoint_files(root, value)
    manifest = dict(value, files={})
    destination.mkdir(parents=True, exist_ok=False, mode=0o700)
    for relative in files:
        payload = safe(root, relative).read_bytes()
        path = safe(destination / 'payload', relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as handle:
            handle.write(payload)
        manifest['files'][relative] = store.digest(payload)
    transfer.json_write(destination / 'manifest.json', manifest)
    print(json.dumps({'exported_test_files': len(files), 'batch_id': value['batch_id']}))
    return manifest


def _verify_bindings(root, base, events, manifest, bundle):
    completed, accepted = {}, {}
    for event in events:
        if event['type'] == 'stage_accepted':
            accepted[event['stage']] = store.checked_yaml(root, base + '/stages/' + event['stage'] + '.yaml')['candidate']
        if event['type'] != 'call_completed':
            continue
        stage, role, revision = event['stage'], event['role'], event['revision']
        request = {'stage': stage, 'revision': revision, 'topic': bundle['topic'],
            'topic_card': bundle['topic_card'], 'evidence': bundle['material']['evidence'],
            'prior_accepted_stages': dict(accepted), 'confirmation': member._confirmation(bundle),
            'coverage_note': bundle['coverage_note'], 'insights': bundle['insights'], 'evidence_gaps': bundle['gaps']}
        if revision:
            request.update(previous_candidate=completed['%s-writing-%s' % (stage, revision - 1)],
                           previous_review=completed['%s-review-%s' % (stage, revision - 1)])
        if role == 'review':
            request['candidate'] = completed['%s-writing-%s' % (stage, revision)]
        instructions = member.WRITING_INSTRUCTIONS if role == 'writing' else member.REVIEW_INSTRUCTIONS
        serialized = json.dumps(request, ensure_ascii=False)
        expected = store.digest({'fingerprint': manifest['fingerprint'], 'stage': stage, 'role': role,
            'revision': revision, 'instructions': instructions, 'input': serialized})
        checkpoint = store.checked_yaml(root, event['response_path'])
        if checkpoint.get('binding') != expected or len(instructions) + len(serialized) > manifest['budget']['max_input_chars']:
            raise JobError('writing_model_input_binding_invalid')
        parsed = member._parse(checkpoint['result']['text'])
        if role == 'writing':
            member.validate_candidate(parsed, bundle, stage)
        else:
            member.validate_review(request['candidate'], parsed, bundle)
        completed[event['reservation_id']] = parsed
    return accepted


def _verify(root, value):
    bundle = inputs.prepare_bundle(root, value['approval_id'], value['config_path'])
    if (bundle['input_fingerprint'] != value['input_fingerprint'] or bundle['topic'] != value['topic']
            or bundle['batch_id'] != value['batch_id']):
        raise JobError('writing_original_confirmation_or_inputs_changed')
    base = 'reports/test/%s/writing-runs/%s' % (value['topic'], value['batch_id'])
    if not safe(root, base + '/manifest.yaml').exists():
        if value.get('files'):
            raise JobError('writing_transfer_missing_run_manifest')
        return {'status': 'no_checkpoints', 'completed_calls': 0}
    manifest = store.checked_yaml(root, base + '/manifest.yaml')
    authorization = manifest.get('authorization', {})
    if (set(authorization) != {'authenticated', 'plan_permission', 'authorization', 'account_fingerprint'}
            or authorization['authenticated'] is not True or authorization['plan_permission'] is not True
            or authorization['authorization'] != 'official_chatgpt_oauth'
            or not isinstance(authorization['account_fingerprint'], str) or not authorization['account_fingerprint']):
        raise JobError('writing_membership_authorization_proof_invalid')
    budget = dict(bundle['budget'], month_max_calls=bundle['month_max_calls'])
    fingerprint = store.digest({'input_fingerprint': bundle['input_fingerprint'], 'models': bundle['models'],
        'budget': budget, 'authorization': authorization,
        'writing_prompt': member.WRITING_INSTRUCTIONS, 'review_prompt': member.REVIEW_INSTRUCTIONS})
    expected = {'schema_version': 1, 'mode': 'writing_member_test', 'backend': 'chatgpt_plan',
        'topic': value['topic'], 'batch_id': value['batch_id'], 'approval_id': value['approval_id'],
        'fingerprint': fingerprint, 'input_fingerprint': bundle['input_fingerprint'], 'models': bundle['models'],
        'budget': budget, 'authorization': authorization, 'confirmation_path': bundle['confirmation_path'],
        'confirmation_sha256': bundle['confirmation_sha256'], 'publish_authorized': False}
    if set(manifest) != set(expected) | {'created_at', 'protected_notes'} or any(manifest.get(k) != v for k, v in expected.items()):
        raise JobError('writing_frozen_manifest_invalid')
    shared.verify_notes(root, manifest['protected_notes'])
    events = store.read_events(root, base)
    complete = member.verify_ledger(root, base, events, manifest, bundle)
    accepted = _verify_bindings(root, base, events, manifest, bundle)
    expected_outputs = dict(member.render(stage, accepted[stage], bundle, value['batch_id'])
                            for stage in member.STAGES if stage in accepted)
    outputs = {path: store.digest(content.encode()) for path, content in expected_outputs.items()}
    plan_path = base + '/artifact-plan.yaml'
    plan_exists = safe(root, plan_path).exists()
    if plan_exists and (not complete or len(accepted) != 3 or store.checked_yaml(root, plan_path) != {'files': outputs}):
        raise JobError('writing_artifact_plan_without_complete_independent_reviews')
    for stage in member.STAGES:
        path = 'articles/test/%s/%s/%s.md' % (value['topic'], value['batch_id'], stage)
        if safe(root, path).exists() and (not plan_exists or path not in expected_outputs
                or safe(root, path).read_bytes() != expected_outputs[path].encode()):
            raise JobError('writing_article_not_rendered_from_reviewed_candidate')
    receipt_path = base + '/receipt.yaml'
    reserved = [event for event in events if event['type'] == 'call_reserved']
    finished = [event for event in events if event['type'] == 'call_completed']
    if not safe(root, receipt_path).exists():
        return {'status': 'partial', 'completed_calls': len(finished), 'unknown_requests': not complete}
    receipt = store.checked_yaml(root, receipt_path)
    if (type(receipt.get('schema_version')) is not int or receipt['schema_version'] != 1
            or receipt.get('mode') != 'writing_member_test' or receipt.get('backend') != 'chatgpt_plan'
            or receipt.get('topic') != value['topic'] or receipt.get('batch_id') != value['batch_id']
            or receipt.get('approval_id') != value['approval_id']
            or receipt.get('confirmation_path') != bundle['confirmation_path']
            or receipt.get('confirmation_origin') != 'local_confirmation_page'
            or receipt.get('models') != bundle['models']
            or receipt.get('reserved_calls') != len(reserved) or receipt.get('completed_calls') != len(finished)
            or receipt.get('usage') != [event.get('usage') for event in finished]
            or receipt.get('actual_models') != sorted({event['model_id'] for event in finished})
            or receipt.get('all_existing_notes_unchanged') is not True or receipt.get('real_topic_approved') is not True
            or receipt.get('production_accepted') is not False or receipt.get('publish_authorized') is not False
            or receipt.get('writing_started') is not True or not complete):
        raise JobError('writing_receipt_does_not_match_verified_ledger')
    expected_stages = {}
    for stage in member.STAGES:
        if stage in accepted:
            checkpoint = '%s/stages/%s.yaml' % (base, stage)
            expected_stages[stage] = {'status': 'test_accepted',
                'revision_count': store.checked_yaml(root, checkpoint)['revision'], 'checkpoint': checkpoint}
        elif receipt.get('status') != 'test_accepted':
            reviews = [event for event in finished if event['stage'] == stage and event['role'] == 'review']
            if not reviews:
                raise JobError('writing_nonaccepted_receipt_missing_final_review')
            last = reviews[-1]
            review = member._parse(store.checked_yaml(root, last['response_path'])['result']['text'])
            decision = {'revise': 'revision_required', 'reject': 'rejected', 'blocked': 'blocked'}.get(review['decision'])
            if decision != receipt['status']:
                raise JobError('writing_nonaccepted_receipt_decision_changed')
            expected_stages[stage] = {'status': decision, 'revision_count': last['revision']}
            break
    if receipt.get('stages') != expected_stages:
        raise JobError('writing_receipt_stage_summary_changed')
    monthly = receipt.get('monthly_reserved_calls')
    if (type(monthly) is not int or not len(reserved) <= monthly <= bundle['month_max_calls']
            or receipt.get('effective_month_max_calls') != bundle['month_max_calls']
            or receipt.get('membership_remaining_quota') is not None or receipt.get('api_billed_cost') is not None):
        raise JobError('writing_receipt_budget_summary_changed')
    if receipt.get('status') == 'test_accepted':
        if (len(accepted) != 3 or not plan_exists or receipt.get('output_hashes') != outputs
                or any(not safe(root, path).is_file() for path in outputs)
                or set(receipt.get('stages', {})) != set(member.STAGES)
                or any(receipt['stages'][stage].get('status') != 'test_accepted' for stage in member.STAGES)):
            raise JobError('writing_acceptance_missing_three_reviewed_artifacts')
    elif receipt.get('status') not in {'rejected', 'blocked', 'revision_required'} or receipt.get('output_hashes') or plan_exists:
        raise JobError('writing_nonaccepted_receipt_has_artifacts')
    return {'status': receipt['status'], 'completed_calls': len(finished), 'unknown_requests': False}


def verify_result(root, bundle):
    """Read-only active-approval result check without a client or provider call."""
    return _verify(Path(root).resolve(), context(Path(root).resolve(), bundle))


def _verification(root, value, result, run_id, attempt):
    """Bind one zero-contact Actions check to the original verified results."""
    if result.get('status') != 'test_accepted' or result.get('unknown_requests') is not False:
        raise JobError('writing_verification_requires_complete_independent_reviews')
    base = 'reports/test/%s/writing-runs/%s' % (value['topic'], value['batch_id'])
    receipt_path = base + '/receipt.yaml'
    receipt = store.checked_yaml(root, receipt_path)
    monthly, ceiling = shared.monthly_budget(root, {'backend': 'chatgpt_plan',
        'budget': {'month_max_calls': shared.membership_monthly_limit(root)}})
    return {'schema_version': 1, 'mode': 'writing_zero_call_verification',
        'topic': value['topic'], 'approval_id': value['approval_id'], 'batch_id': value['batch_id'],
        'source_commit': value['base_commit'], 'input_fingerprint': value['input_fingerprint'],
        'github_run_id': run_id, 'github_run_attempt': attempt,
        'original_receipt_path': receipt_path,
        'original_receipt_sha256': store.digest(safe(root, receipt_path).read_bytes()),
        'output_hashes': receipt['output_hashes'], 'reserved_calls': receipt['reserved_calls'],
        'completed_calls': result['completed_calls'], 'monthly_reserved_calls': monthly,
        'effective_month_max_calls': ceiling, 'new_model_calls': 0, 'no_membership_contacts': True,
        'status': 'test_accepted', 'output_mode': 'test_only',
        'production_accepted': False, 'publish_authorized': False}


def _verify_verifications(root, value, result):
    base = 'reports/test/%s/writing-runs/%s/' % (value['topic'], value['batch_id'])
    for relative in value['files']:
        if not relative.startswith(base) or not relative.endswith('.yaml'):
            continue
        match = VERIFICATION.fullmatch(relative[len(base):])
        if match and store.checked_yaml(root, relative) != _verification(root, value, result, *match.groups()):
            raise JobError('writing_zero_call_verification_does_not_match_verified_results')


def apply(root, artifact):
    root, artifact = Path(root).resolve(), Path(artifact)
    value = _context(json.loads((artifact / 'manifest.json').read_text()), artifact=True)
    if git(root, 'branch', '--show-current').decode().strip() != 'main':
        raise JobError('writing_publisher_main_required')
    check_baseline(root, value, publisher=True)
    git(root, 'merge-base', '--is-ancestor', value['base_commit'], 'HEAD')
    files, payload = value['files'], artifact / 'payload'
    inspect_files(payload, files, value)
    current = tracked(root)
    if any(not allowed(path, value) for path in _untracked(root)):
        raise JobError('writing_publisher_unrelated_untracked_files')
    additions, writes = [], []
    for relative, expected in files.items():
        content = safe(payload, relative).read_bytes()
        if not isinstance(expected, str) or store.digest(content) != expected:
            raise JobError('writing_artifact_bytes_changed')
        target = safe(root, relative)
        if target.exists():
            if not target.is_file() or target.read_bytes() != content:
                raise JobError('writing_existing_note_conflict_preserve_both')
        else:
            writes.append((relative, content))
        if relative not in current:
            additions.append(relative)
    for relative, content in writes:
        target = safe(root, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(str(safe(root, relative)), os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o644)
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    result = _verify(root, value)
    _verify_verifications(root, value, result)
    validate = subprocess.run([sys.executable, str(root / 'workflows/validate.py'), '--include-test'],
                              cwd=root, capture_output=True, check=False)
    if validate.returncode:
        raise JobError('writing_schema_check_failed_preserve_artifact')
    if additions:
        git(root, 'config', 'user.name', 'github-actions[bot]')
        git(root, 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')
        git(root, 'add', '--', *sorted(additions))
        staged = [path.decode() for path in git(root, 'diff', '--cached', '--name-only', '-z').split(b'\0') if path]
        if sorted(staged) != sorted(additions):
            raise JobError('writing_unexpected_staged_changes')
        git(root, 'commit', '-m', 'Save confirmed ResearchDesk Writing test: ' + value['approval_id'])
        git(root, 'push', 'origin', 'HEAD:refs/heads/main')
    summary = dict(result, saved_files=len(additions), batch_id=value['batch_id'],
                   commit=git(root, 'rev-parse', 'HEAD').decode().strip(), production_accepted=False)
    print(json.dumps(summary))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    commands = parser.add_subparsers(dest='command', required=True)
    run = commands.add_parser('execute')
    run.add_argument('--state', type=Path, required=True)
    run.add_argument('--approval-id', required=True)
    run.add_argument('--config', default='config/confirmation.yaml')
    run.add_argument('--max-new-calls', type=int, default=6)
    run.add_argument('--fail-after', choices=('after_outline', 'after_review', 'after_first_output'))
    pack = commands.add_parser('export')
    pack.add_argument('--state', type=Path, required=True)
    pack.add_argument('--destination', type=Path, required=True)
    publish = commands.add_parser('apply')
    publish.add_argument('--artifact', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'execute':
            return execute(args.root, args.state, args.approval_id, args.config, args.max_new_calls, args.fail_after)
        if args.command == 'export':
            export(args.root, args.state, args.destination)
        else:
            apply(args.root, args.artifact)
        return 0
    except Exception as exc:
        error = exc.code if isinstance(exc, member.WritingRefreshError) else (
            str(exc) if isinstance(exc, JobError) else 'writing_job_stopped_preserve_checkpoint')
        print(json.dumps({'error': error,
                          'error_type': type(exc).__name__}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
