"""Trusted main Writing deployment using the registered persistent workbench.

The worker reads local settings; only confirmed task material and verifiable
Writing checkpoints are exported. The hosted saver never needs OAuth or YAML.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile

import researchdesk_admission as admission
import researchdesk_confirmation_inputs as previews
import researchdesk_deployment as deployment
import researchdesk_offline as store
import researchdesk_runner as runtime
import researchdesk_workbench as workbench
import researchdesk_writing_job as job
import researchdesk_writing_member as writing
import researchdesk_writing_member_inputs as inputs

MODE = 'writing_deployment_transfer'


def _public(relative):
    parts = Path(relative).parts
    return (parts and parts[0] in {'collection', 'summary', 'insights', 'articles', 'reports'}
            and not any(part.startswith('.') or part == '..' for part in parts)
            and Path(relative).as_posix() == relative and not Path(relative).is_absolute()
            and '\\' not in relative and not any(part in {'codex-requests', 'codex-sdk-smoke'} for part in parts))


def _import_approval(root, source, effective, approval_id):
    if not inputs.APPROVAL.fullmatch(approval_id):
        raise job.JobError('writing_page_approval_required')
    matches = []
    for topic in effective['confirmation']['topics']:
        base = 'reports/%s/writing-approvals/%s' % (topic, approval_id)
        if admission._location(source, base + '/confirmed.yaml').is_file():
            matches.append(base)
    if len(matches) != 1:
        raise job.JobError('writing_synced_confirmation_not_found')
    base = matches[0]
    record = admission._checked(source, base + '/confirmed.yaml')
    preview = admission._checked(source, base + '/preview.yaml')
    if record.get('preview_sha256') != store.digest(preview):
        raise job.JobError('writing_confirmation_changed')
    payload = preview.get('payload', {})
    if payload.get('admission_mode') != 'codex_insight_admission':
        raise job.JobError('writing_new_deployment_requires_current_insight_admission')
    paths = {path: sha for path, sha in payload.get('snapshot', {}).get('hashes', {}).items()
             if Path(path).parts[:1] != ('config',)}
    for relative in (base + '/confirmed.yaml', base + '/preview.yaml'):
        paths[relative] = store.digest(admission._location(source, relative).read_bytes())
        paths[relative + '.sha256'] = store.digest(admission._location(source, relative + '.sha256').read_bytes())
    # Observe a cancellation from the trusted checkout before copying or calls.
    if any(admission._location(source, base + '/revocations').glob('*')):
        raise job.JobError('writing_confirmation_revoked')
    writes = []
    for relative, expected in paths.items():
        if not _public(relative):
            raise job.JobError('writing_public_input_path_invalid')
        original = admission._location(source, relative)
        data = original.read_bytes()
        if store.digest(data) != expected:
            raise job.JobError('writing_synced_input_changed')
        target = admission._location(root, relative)
        if target.exists():
            if not target.is_file() or target.read_bytes() != data:
                raise job.JobError('writing_existing_input_conflict_preserve_notes')
        else:
            writes.append((relative, data))
    for relative, data in writes:
        target = admission._location(root, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as handle:
            handle.write(data)
    return payload


def _input_path(topic, batch):
    return 'reports/test/%s/writing-runs/%s/input.yaml' % (topic, batch)


def _files(root, bundle):
    value = {'topic': bundle['topic'], 'batch_id': bundle['batch_id']}
    base = admission._location(root, 'reports/test/%s/writing-runs/%s' % (bundle['topic'], bundle['batch_id']))
    paths = [path.relative_to(root).as_posix() for path in base.rglob('*') if path.is_file()]
    for stage in writing.STAGES:
        relative = 'articles/test/%s/%s/%s.md' % (bundle['topic'], bundle['batch_id'], stage)
        if admission._location(root, relative).is_file():
            paths.append(relative)
    for path in paths:
        if path not in {_input_path(bundle['topic'], bundle['batch_id']),
                        _input_path(bundle['topic'], bundle['batch_id']) + '.sha256'} and not job.allowed(path, value):
            raise job.JobError('writing_export_unexpected_file')
    return sorted(paths)


def dispatch(source, base_commit, approval_id, artifact, max_new_calls=6,
             environment=None, github_output=None, writer=None):
    environment = os.environ if environment is None else environment
    if environment.get('GITHUB_EVENT_NAME') != 'workflow_dispatch':
        raise job.JobError('writing_manual_confirmation_dispatch_required')
    if type(max_new_calls) is not int or not 0 <= max_new_calls <= 6:
        raise job.JobError('writing_small_validation_limit_is_six')
    source = Path(source).resolve()
    root = deployment._binding(source, base_commit, environment)
    deployment.sync_system(root, source, base_commit)
    workbench.apply(root)
    effective = workbench.load_effective(root)
    _import_approval(root, source, effective, approval_id)
    writing.refresh_origin(root)
    bundle = inputs.prepare_bundle(root, approval_id)
    relative = _input_path(bundle['topic'], bundle['batch_id'])
    store.save_yaml(root, relative, bundle)
    host = runtime.load_config(root)
    if Path(os.sys.prefix).resolve() != host['_venv'].resolve():
        raise job.JobError('writing_runtime_changed_run_workbench_start')
    result = None
    try:
        if max_new_calls == 0:
            result = job._verify(root, {'topic': bundle['topic'], 'batch_id': bundle['batch_id'],
                'approval_id': approval_id, 'input_fingerprint': bundle['input_fingerprint'],
                'config_path': bundle['config']['path']})
        elif writer is not None:
            result = writer(root, approval_id, max_new_calls=max_new_calls)
        else:
            from researchdesk_membership import MembershipClient
            result = writing.run(root, approval_id, client=MembershipClient(host['_profile'], root),
                                 max_new_calls=max_new_calls, refresh=lambda: writing.refresh_origin(root))
    finally:
        files = _files(root, bundle)
        artifact = Path(artifact).resolve()
        artifact.mkdir(parents=True, exist_ok=False, mode=0o700)
        hashes = {}
        for path in files:
            data = admission._location(root, path).read_bytes()
            target = admission._location(artifact / 'payload', path)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as handle:
                handle.write(data)
            hashes[path] = store.digest(data)
        value = {'schema_version': 2, 'mode': MODE, 'topic': bundle['topic'], 'approval_id': approval_id,
            'batch_id': bundle['batch_id'], 'base_commit': base_commit,
            'input_fingerprint': bundle['input_fingerprint'],
            'input_hashes': {path: sha for path, sha in bundle['snapshot']['hashes'].items()
                             if Path(path).parts[:1] != ('config',)}, 'files': hashes}
        (artifact / 'manifest.json').write_text(json.dumps(value, sort_keys=True), encoding='utf-8')
        if github_output:
            with Path(github_output).open('a', encoding='utf-8') as handle:
                handle.write('artifact_path=' + str(artifact) + '\n')
    return {'status': (result or {}).get('status', 'interrupted'), 'approval_id': approval_id,
            'artifact_path': str(artifact), 'publish_authorized': False}


def _manifest(value):
    expected = {'schema_version', 'mode', 'topic', 'approval_id', 'batch_id', 'base_commit',
                'input_fingerprint', 'input_hashes', 'files'}
    if (set(value) != expected or value.get('schema_version') != 2 or value.get('mode') != MODE
            or not previews.TOPIC.fullmatch(value.get('topic', ''))
            or not inputs.APPROVAL.fullmatch(value.get('approval_id', ''))
            or value.get('batch_id') != 'writing-' + value['approval_id']
            or not inputs.COMMIT.fullmatch(value.get('base_commit', ''))
            or not previews.HASH.fullmatch(value.get('input_fingerprint', ''))
            or not isinstance(value.get('files'), dict) or not 1 <= len(value['files']) <= 1000
            or not isinstance(value.get('input_hashes'), dict)):
        raise job.JobError('writing_deployment_manifest_invalid')
    for path, sha in value['input_hashes'].items():
        if not _public(path) or not previews.HASH.fullmatch(sha):
            raise job.JobError('writing_deployment_input_invalid')
    allowed_input = _input_path(value['topic'], value['batch_id'])
    for path, sha in value['files'].items():
        if (path not in {allowed_input, allowed_input + '.sha256'} and not job.allowed(path, value)) or not previews.HASH.fullmatch(sha):
            raise job.JobError('writing_deployment_output_invalid')
    return value


def apply(root, artifact, push=True):
    root, artifact = Path(root).resolve(), Path(artifact).resolve()
    value = _manifest(json.loads((artifact / 'manifest.json').read_text()))
    if job.git(root, 'branch', '--show-current').decode().strip() != 'main':
        raise job.JobError('writing_publisher_main_required')
    job._clean_tracked(root)
    job.git(root, 'merge-base', '--is-ancestor', value['base_commit'], 'HEAD')
    for path, expected in value['input_hashes'].items():
        if store.digest(admission._location(root, path).read_bytes()) != expected:
            raise job.JobError('writing_main_input_changed')
    payloads = {}
    for path, expected in value['files'].items():
        data = admission._location(artifact / 'payload', path).read_bytes()
        if store.digest(data) != expected:
            raise job.JobError('writing_artifact_bytes_changed')
        target = admission._location(root, path)
        if target.exists() and (not target.is_file() or target.read_bytes() != data):
            raise job.JobError('writing_existing_note_conflict_preserve_both')
        payloads[path] = data
    with tempfile.TemporaryDirectory(prefix='researchdesk-writing-verify-') as directory:
        overlay = (Path(directory) / 'workbench').resolve()
        subprocess.run(['git', 'clone', '--quiet', '--no-hardlinks', '--', str(root), str(overlay)],
                       check=True, capture_output=True, timeout=60)
        for path, data in payloads.items():
            target = admission._location(overlay, path)
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.write_bytes(data)
        bundle = store.checked_yaml(overlay, _input_path(value['topic'], value['batch_id']))
        inputs.verify_frozen_bundle(overlay, bundle)
        context = {'topic': value['topic'], 'batch_id': value['batch_id'], 'approval_id': value['approval_id'],
                   'input_fingerprint': value['input_fingerprint'], 'config_path': bundle['config']['path'], 'files': value['files']}
        result = job._verify(overlay, context, bundle=bundle, public=True)
        if result['status'] == 'test_accepted':
            import researchdesk_writing_admission as formal
            accepted = formal.admit_frozen(overlay, bundle)
            for path in accepted['files']:
                payloads[path] = admission._location(overlay, path).read_bytes()
        # Inspect all targets and ancestor types before any persistent write.
        from researchdesk_writing_admission import _preflight
        _preflight(root, payloads)
        additions = []
        for path, data in payloads.items():
            target = admission._location(root, path)
            if target.exists():
                if not target.is_file() or target.read_bytes() != data:
                    raise job.JobError('writing_existing_note_conflict_preserve_both')
            else:
                additions.append(path)
        for path in additions:
            target = admission._location(root, path)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as handle:
                handle.write(payloads[path])
    if additions:
        job.git(root, 'add', '--', *sorted(additions))
        staged = job.git(root, 'diff', '--cached', '--name-only').decode().splitlines()
        if sorted(staged) != sorted(additions):
            raise job.JobError('writing_unexpected_staged_changes')
        job.git(root, '-c', 'user.name=github-actions[bot]', '-c',
                'user.email=41898282+github-actions[bot]@users.noreply.github.com', 'commit', '-m',
                'Save confirmed ResearchDesk Writing: ' + value['approval_id'])
        if push:
            job.git(root, 'push', 'origin', 'HEAD:refs/heads/main')
    return dict(result, saved_files=len(additions), production_accepted=result['status'] == 'test_accepted',
                publish_authorized=False, approval_id=value['approval_id'])
