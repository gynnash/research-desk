#!/usr/bin/env python3
"""Trusted-main worker, checkpoint transfer and reviewed create-only admission."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys


class JobError(RuntimeError):
    pass


def git(root, *arguments):
    value = subprocess.run(['git', *arguments], cwd=root, capture_output=True, check=False)
    if value.returncode:
        raise JobError('git_operation_failed')
    return value.stdout


def sha(value):
    return hashlib.sha256(value).hexdigest()


def json_write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, ensure_ascii=False, sort_keys=True)


def tracked(root):
    result = {}
    for entry in git(root, 'ls-files', '--stage', '-z').split(b'\0'):
        if not entry:
            continue
        header, path = entry.split(b'\t', 1)
        mode, blob, stage = header.decode().split()
        if stage != '0' or mode not in ('100644', '100755'):
            raise JobError('repository_index_not_regular')
        result[path.decode()] = blob
    return result


def safe(root, relative):
    value = Path(relative)
    if value.is_absolute() or not value.parts or '..' in value.parts or '\\' in relative:
        raise JobError('transfer_path_invalid')
    path = root / value
    for part in (path,) + tuple(path.parents):
        if part == root.parent:
            break
        if part.is_symlink():
            raise JobError('transfer_symlink_forbidden')
    return path


def allowed(path, topic, cycle, formal_files=None):
    parts = Path(path).parts
    prefixes = [('reports', 'test', topic, stage, cycle)
                for stage in ('cycles', 'research-batches', 'insight-runs')]
    prefixes += [(folder, 'test', topic, cycle) for folder in ('insights', 'articles')]
    return ((path in (formal_files or set()) or
             any(parts[:len(prefix)] == prefix and len(parts) > len(prefix) for prefix in prefixes))
            and Path(path).suffix in ('.yaml', '.md', '.sha256')
            and not any(part.startswith('.') for part in parts))


def check_text(payload, path, formal=False):
    if len(payload) > 2_000_000:
        raise JobError('transfer_file_too_large')
    try:
        text = payload.decode('utf-8')
    except UnicodeError as exc:
        raise JobError('transfer_must_be_utf8') from exc
    if (re.search(r'(?i)\b(?:access_token|refresh_token|id_token|client_secret|code_verifier|api_key)\s*["\']?\s*:', text)
            or re.search(r'\bBearer\s+[A-Za-z0-9._-]{20,}|\beyJ[A-Za-z0-9_-]{30,}\.[A-Za-z0-9_-]{20,}\.', text)
            or re.search(r'\bsk-[A-Za-z0-9_-]{20,}', text)
            or re.search(r'(?<![\w:])/(?:Users|home|private|tmp|var|root)/', text)):
        raise JobError('possible_secret_in_transfer')
    if path.endswith('.md') and not formal and '> TEST' not in text:
        raise JobError('test_notice_missing')
    return text


def formal_plan(root, topic, cycle):
    from researchdesk_offline import load_yaml
    base = 'reports/%s/admissions/%s/' % (topic, cycle)
    path = safe(root, base+'plan.yaml')
    if not path.is_file():
        return None, set()
    value = load_yaml(path)
    if not isinstance(value.get('files'), dict):
        raise JobError('formal_plan_invalid')
    result = set(value['files']) | {base+name for name in
                                   ('plan.yaml','plan.yaml.sha256','accepted.yaml','accepted.yaml.sha256')}
    # A plan cannot widen the transfer boundary to configuration or old notes.
    for relative in value['files']:
        parts = Path(relative).parts
        source = len(parts)==4 and parts[:2] in {('sources','papers'),('sources','blogs')} and parts[2]==topic
        derived = len(parts)>=3 and parts[0] in {'reports','insights','articles'} and parts[1]==topic
        if not (source or derived) or Path(relative).suffix != '.md' or any(part.startswith('.') for part in parts):
            raise JobError('formal_plan_path_invalid')
        safe(root, relative)
    return value, result


def admission_enabled(root, topic):
    import researchdesk_offline as store
    import researchdesk_batch_inputs as common
    path = common.config_path(root, 'config/admission.yaml')
    policy = store.load_yaml(path)
    common.fields(policy, {'schema_version','enabled','topics','require_independent_review','preserve_existing_files'}, '正式准入策略')
    if (type(policy['schema_version']) is not int or policy['schema_version'] != 1
            or type(policy['enabled']) is not bool
            or policy['require_independent_review'] is not True or policy['preserve_existing_files'] is not True
            or not isinstance(policy['topics'], list) or any(not isinstance(x,str) for x in policy['topics'])):
        raise JobError('admission_policy_invalid')
    return policy['enabled'] and topic in policy['topics']


def inspect_files(root, files, topic, cycle):
    _, formal_files = formal_plan(root, topic, cycle)
    for relative in files:
        if not allowed(relative, topic, cycle, formal_files):
            raise JobError('transfer_outside_cycle_paths')
        path = safe(root, relative)
        if not path.is_file() or not stat.S_ISREG(path.lstat().st_mode):
            raise JobError('transfer_not_regular_file')
        check_text(path.read_bytes(), relative, relative in formal_files)
        if relative.endswith('.yaml'):
            marker = safe(root, relative + '.sha256')
            if not marker.is_file() or marker.read_text().strip() != sha(path.read_bytes()):
                raise JobError('incomplete_yaml_checkpoint_preserve_worker')
        if relative.endswith('.sha256'):
            original = safe(root, relative[:-7])
            if not original.is_file() or path.read_text().strip() != sha(original.read_bytes()):
                raise JobError('checkpoint_digest_invalid')


def execute(root, state, config_path, cycle_id, operation, fail_after=None):
    import researchdesk_cycle as cycle
    import researchdesk_runner as runtime
    root = root.resolve()
    if os.environ.get('GITHUB_ACTIONS') == 'true' and os.environ.get('GITHUB_REF') != 'refs/heads/main':
        raise JobError('trusted_main_required')
    config = cycle.load_config(root, config_path)
    cycle.base_path(config, cycle_id)
    host = runtime.load_config(root)
    python = host['_venv'] / 'bin/python'
    if not python.is_file():
        raise JobError('configured_runtime_python_missing')
    baseline = tracked(root)
    if git(root, 'diff', '--name-only') or git(root, 'diff', '--cached', '--name-only'):
        raise JobError('worker_has_modified_tracked_files')
    untracked = [p.decode() for p in git(root, 'ls-files', '--others', '--exclude-standard', '-z').split(b'\0') if p]
    if operation != 'health':
        _, formal_files = formal_plan(root, config['topic'], cycle_id)
        if any(not allowed(path, config['topic'], cycle_id, formal_files) for path in untracked):
            raise JobError('unpublished_other_cycle_files_require_recovery')
        inspect_files(root, untracked, config['topic'], cycle_id)
    context = {'schema_version': 1, 'topic': config['topic'], 'cycle_id': cycle_id,
               'operation': operation, 'base_commit': git(root, 'rev-parse', 'HEAD').decode().strip(),
               'baseline_blobs': baseline}
    json_write(state / 'context.json', context)
    if operation == 'health':
        command = [str(python), str(root / 'scripts/researchdesk_job.py'), '--root', str(root),
                   'health', '--config', config_path]
    elif operation == 'admit':
        command = [str(python), str(root/'scripts/researchdesk_job.py'), '--root', str(root),
                   'admit', '--config', config_path, '--cycle-id', cycle_id]
    else:
        command = [str(python), str(root / 'scripts/researchdesk_cycle.py'), '--root', str(root),
                   operation, '--config', config_path, '--cycle-id', cycle_id, '--profile', str(host['_profile'])]
        if fail_after:
            command += ['--fail-after', fail_after]
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
    admission_status = 'not_requested'
    if result.returncode == 0 and operation == 'run' and admission_enabled(root, config['topic']):
        import researchdesk_offline as store
        receipt = store.checked_yaml(root, cycle.base_path(config,cycle_id)+'/receipt.yaml')
        if all(receipt.get('stages',{}).get(stage,{}).get('status')=='test_accepted' for stage in ('research','insight')):
            result = subprocess.run([str(python),str(root/'scripts/researchdesk_job.py'),'--root',str(root),
                                     'admit','--config',config_path,'--cycle-id',cycle_id],
                                    cwd=root,capture_output=True,text=True,check=False)
            admission_status = 'accepted' if result.returncode==0 else 'failed'
        else:
            admission_status = 'no_accepted_bundle'
    # No provider/model stdout, private paths or credential-bearing errors in Actions logs.
    summary = {'operation': operation, 'cycle_id': cycle_id, 'exit_code': result.returncode,
               'admission': admission_status if operation!='admit' else ('accepted' if result.returncode==0 else 'failed')}
    if operation == 'health' and result.returncode == 0:
        summary['health'] = json.loads(result.stdout)
    print(json.dumps(summary))
    return result.returncode


def health(root, config_path):
    import researchdesk_cycle as cycle
    import researchdesk_runner as runtime
    from researchdesk_membership import MembershipClient
    host = runtime.load_config(root)
    config = cycle.load_config(root, config_path)
    diagnostic = runtime.doctor(root, host)
    client = MembershipClient(host['_profile'], root)
    authorization = client.status()
    models = client.models()
    if (authorization.get('authenticated') is not True or authorization.get('plan_permission') is not True
            or not set(config['models'].values()).issubset({item['slug'] for item in models})):
        raise JobError('membership_permission_or_selected_models_unavailable')
    print(json.dumps({'runtime_dependencies_ready': diagnostic['python']['dependencies_ready'],
                      'membership_authorized': True, 'configured_models_available': True,
                      'available_model_count': len(models), 'inference_calls': 0}))


def export(root, state, destination):
    context = json.loads((state / 'context.json').read_text())
    if tracked(root) != context['baseline_blobs'] or git(root, 'diff', '--name-only') or git(root, 'diff', '--cached', '--name-only'):
        raise JobError('tracked_inputs_changed_preserve_worker')
    files = [p.decode() for p in git(root, 'ls-files', '--others', '--exclude-standard', '-z').split(b'\0') if p]
    inspect_files(root, files, context['topic'], context['cycle_id'])
    manifest = dict(context, files={})
    destination.mkdir(parents=True, exist_ok=False, mode=0o700)
    for relative in files:
        payload = safe(root, relative).read_bytes()
        output = safe(destination / 'payload', relative)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('xb') as handle:
            handle.write(payload)
        manifest['files'][relative] = sha(payload)
    json_write(destination / 'manifest.json', manifest)
    print(json.dumps({'exported_test_files': len(files), 'cycle_id': context['cycle_id']}))


def apply(root, artifact):
    manifest = json.loads((artifact / 'manifest.json').read_text())
    if set(manifest) != {'schema_version', 'topic', 'cycle_id', 'operation', 'base_commit', 'baseline_blobs', 'files'}:
        raise JobError('transfer_manifest_invalid')
    for identity in ('topic', 'cycle_id'):
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,100}', manifest[identity]):
            raise JobError('transfer_identity_invalid')
    if len(manifest['files']) > 1000 or manifest['schema_version'] != 1:
        raise JobError('transfer_manifest_invalid')
    current = tracked(root)
    if any(current.get(path) != blob for path, blob in manifest['baseline_blobs'].items()):
        raise JobError('main_inputs_changed_preserve_artifact')
    files = manifest['files']
    payload = artifact / 'payload'
    inspect_files(payload, files, manifest['topic'], manifest['cycle_id'])
    additions = []
    for relative, expected in files.items():
        content = safe(payload, relative).read_bytes()
        if sha(content) != expected:
            raise JobError('transfer_content_changed')
        target = safe(root, relative)
        if target.exists():
            if target.read_bytes() != content:
                raise JobError('existing_content_conflict_preserve_both')
        else:
            additions.append((relative, content))
    for relative, content in additions:
        path = safe(root, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o644)
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(content)
    plan, _ = formal_plan(root, manifest['topic'], manifest['cycle_id'])
    production_accepted = False
    if plan is not None:
        if not admission_enabled(root, manifest['topic']):
            raise JobError('formal_admission_disabled')
        import researchdesk_admission as admission
        # Verify the hash-bound plan again on the publisher, and finish an
        # interrupted create-only install before committing formal acceptance.
        admission.run(root, manifest['topic'], manifest['cycle_id'])
        production_accepted = True
        known = {relative for relative,_ in additions}
        _, formal_files = formal_plan(root,manifest['topic'],manifest['cycle_id'])
        for relative in sorted(formal_files):
            if relative not in current and relative not in known and safe(root,relative).is_file():
                additions.append((relative,safe(root,relative).read_bytes()))
                known.add(relative)
        inspect_files(root,[relative for relative,_ in additions],manifest['topic'],manifest['cycle_id'])
    validate = subprocess.run([sys.executable, 'workflows/validate.py', '--include-test'], cwd=root,
                              capture_output=True, check=False)
    if validate.returncode:
        raise JobError('published_test_schema_invalid_preserve_artifact')
    if additions:
        git(root, 'config', 'user.name', 'github-actions[bot]')
        git(root, 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')
        git(root, 'add', '--', *[relative for relative, _ in additions])
        staged = [p.decode() for p in git(root, 'diff', '--cached', '--name-only', '-z').split(b'\0') if p]
        if sorted(staged) != sorted(relative for relative, _ in additions):
            raise JobError('unexpected_staged_changes')
        git(root, 'commit', '-m', ('Accept reviewed ResearchDesk cycle: ' if production_accepted else
                                 'Save ResearchDesk test checkpoints: ') + manifest['cycle_id'])
        git(root, 'push', 'origin', 'HEAD:refs/heads/main')
    print(json.dumps({'saved_files': len(additions), 'cycle_id': manifest['cycle_id'],
                      'commit': git(root, 'rev-parse', 'HEAD').decode().strip(), 'production_accepted': production_accepted}))


def admit(root, config_path, cycle_id):
    import researchdesk_cycle as cycle
    import researchdesk_admission as admission
    config=cycle.load_config(root,config_path)
    if not admission_enabled(root,config['topic']):
        raise JobError('formal_admission_disabled')
    result=admission.run(root,config['topic'],cycle_id)
    print(json.dumps({'cycle_id':cycle_id,'production_accepted':True,'inference_calls':0}))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    commands = parser.add_subparsers(dest='command', required=True)
    start = commands.add_parser('execute')
    start.add_argument('--state', type=Path, required=True)
    start.add_argument('--config', required=True)
    start.add_argument('--cycle-id', required=True)
    start.add_argument('--operation', choices=('health', 'discover', 'run', 'admit'), required=True)
    start.add_argument('--fail-after', choices=('after_research',))
    pack = commands.add_parser('export')
    pack.add_argument('--state', type=Path, required=True)
    pack.add_argument('--destination', type=Path, required=True)
    publish = commands.add_parser('apply')
    publish.add_argument('--artifact', type=Path, required=True)
    check = commands.add_parser('health')
    check.add_argument('--config', required=True)
    promote = commands.add_parser('admit')
    promote.add_argument('--config',required=True)
    promote.add_argument('--cycle-id',required=True)
    args = parser.parse_args()
    try:
        if args.command == 'execute':
            return execute(args.root, args.state, args.config, args.cycle_id, args.operation, args.fail_after)
        if args.command == 'export':
            export(args.root, args.state, args.destination)
        elif args.command == 'health':
            health(args.root, args.config)
        elif args.command == 'admit':
            admit(args.root,args.config,args.cycle_id)
        else:
            apply(args.root, args.artifact)
        return 0
    except Exception as exc:
        print(json.dumps({'error': str(exc) if isinstance(exc, JobError) else 'job_operation_failed'}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
