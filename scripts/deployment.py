#!/usr/bin/env python3
"""Dispatch trusted Actions code against the registered persistent workbench."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import yaml

import automatic
import publish as publisher
import runner
import workbench


SYSTEM_SYNC = 'config/local/system-source.json'


class DeploymentError(ValueError):
    pass


def _git(root, *arguments, optional=False):
    result = subprocess.run(['git', '-C', str(root), *arguments], capture_output=True, check=False)
    if result.returncode:
        if optional:
            return None
        raise DeploymentError('deployment_repository_check_failed')
    return result.stdout


def sync_system(root, source, base_commit):
    """Import upstream defaults only when the operator has not edited them.

    Never pull/reset a Vault or touch its private user configuration. A locally
    edited system file is itself the user's chosen system configuration.
    """
    root, source = Path(root).resolve(), Path(source).resolve()
    local = workbench._path(root, workbench.SYSTEM_CONFIG)
    upstream = workbench._path(source, workbench.SYSTEM_CONFIG)
    if not upstream.is_file():
        raise DeploymentError('upstream_system_configuration_missing')
    payload = upstream.read_bytes()
    # Parse before a possible replacement; the merged runtime is checked again
    # by automatic.run under its workbench lock, before any inference.
    workbench._read(upstream)
    current = local.read_bytes() if local.exists() else None
    state_path = workbench._path(root, SYSTEM_SYNC)
    previous = {}
    if state_path.exists():
        try:
            previous = json.loads(state_path.read_text())
        except (ValueError, OSError) as exc:
            raise DeploymentError('system_sync_state_invalid') from exc
        if not isinstance(previous, dict):
            raise DeploymentError('system_sync_state_invalid')
    baseline = _git(root, 'show', 'HEAD:' + workbench.SYSTEM_CONFIG, optional=True)
    managed = current is not None and workbench._hash(current) == previous.get('imported_sha256')
    unchanged = managed if previous else current == baseline
    if current is not None and current != payload and not unchanged:
        return 'local_system_preserved'
    if current != payload:
        workbench._write(local, payload)
    workbench._write(state_path, json.dumps({
        'source_commit': base_commit, 'imported_sha256': workbench._hash(payload)},
        sort_keys=True).encode())
    return 'upstream_system_loaded'


def _binding(source, base_commit, environment):
    if (environment.get('GITHUB_ACTIONS') != 'true'
            or environment.get('GITHUB_REF') != 'refs/heads/main'
            or environment.get('GITHUB_EVENT_NAME') not in {'schedule', 'workflow_dispatch'}):
        raise DeploymentError('trusted_main_actions_required')
    value = environment.get('RESEARCHDESK_WORKBENCH_ROOT', '')
    if not value or not Path(value).is_absolute():
        raise DeploymentError('deployment_binding_missing_run_workbench_start')
    root = Path(value)
    for path in (root,) + tuple(root.parents):
        if path.is_symlink():
            raise DeploymentError('deployment_workbench_symlink')
    root = root.resolve()
    if not (root / workbench.LOCAL_CONFIG).is_file():
        raise DeploymentError('deployment_user_configuration_missing')
    repository = environment.get('GITHUB_REPOSITORY', '')
    if not repository or runner._repository(root).lower() != repository.lower():
        raise DeploymentError('deployment_repository_binding_mismatch')
    source = Path(source).resolve()
    if not re.fullmatch(r'[0-9a-f]{40,64}', base_commit or ''):
        raise DeploymentError('deployment_source_commit_invalid')
    if _git(source, 'rev-parse', 'HEAD').decode().strip() != base_commit:
        raise DeploymentError('deployment_source_commit_mismatch')
    if runner._repository(source).lower() != repository.lower():
        raise DeploymentError('deployment_source_repository_mismatch')
    if _git(source, 'diff', '--name-only') or _git(source, 'diff', '--cached', '--name-only'):
        raise DeploymentError('deployment_source_code_changed')
    return root


def _workflow_trigger_zone(source, cron):
    """Read the verified main checkout's zone for the GitHub event expression."""
    path = Path(source) / '.github/workflows/researchdesk-manual.yml'
    try:
        workflow = yaml.load(path.read_text(encoding='utf-8'), Loader=yaml.BaseLoader)
    except (OSError, ValueError, yaml.YAMLError):
        return ''
    events = workflow.get('on') if isinstance(workflow, dict) else None
    entries = events.get('schedule') if isinstance(events, dict) else None
    if not isinstance(entries, list):
        return ''
    expected = ' '.join(cron.split())
    zones = [entry.get('timezone', 'UTC') for entry in entries if isinstance(entry, dict)
             and isinstance(entry.get('cron'), str) and ' '.join(entry['cron'].split()) == expected]
    return zones[0] if len(zones) == 1 and isinstance(zones[0], str) else ''


def dispatch(source, base_commit, artifact, event='schedule', operation='run', cycle_id=None,
             environment=None, github_output=None, pipeline=None, exporter=None):
    environment = os.environ if environment is None else environment
    root = _binding(source, base_commit, environment)
    if event != environment['GITHUB_EVENT_NAME']:
        raise DeploymentError('deployment_event_mismatch')
    if operation not in {'health', 'collect', 'run', 'catchup'}:
        raise DeploymentError('deployment_operation_invalid')
    selection = {}

    def prepare():
        selection['system_configuration'] = sync_system(root, source, base_commit)
        # A relocated interpreter/runner is deployment infrastructure. Fail
        # before collection/model calls, rather than using an old environment.
        effective = workbench.load_effective(root)
        expected = Path(effective['runtime']['python']['venv']).expanduser().absolute()
        if Path(sys.prefix).absolute() != expected:
            raise DeploymentError('runtime_environment_changed_run_workbench_start')

    trigger = environment.get('RESEARCHDESK_TRIGGER_CRON') if event == 'schedule' else None
    result = (pipeline or automatic.run)(root,
        event='schedule' if event == 'schedule' else 'manual', operation=operation,
        cycle_id=cycle_id or None, publisher_context={'base_commit': base_commit}, prepare=prepare,
        **({'trigger_cron': trigger, 'trigger_timezone': _workflow_trigger_zone(source, trigger)} if trigger else {}))
    exported = None
    identity = result.get('cycle_id')
    status = result['status']
    details = {}
    if result.get('reason') == 'schedule_trigger_mismatch':
        details['reason'] = result['reason']

    def exportable(run):
        topic, cycle = run.get('topic'), run.get('cycle_id')
        return bool(cycle) and (root / automatic._base(topic, cycle) / 'context.yaml').is_file()

    if 'runs' in result:
        runs = result['runs']
        details['runs'] = [{key: run[key] for key in ('topic', 'cycle_id', 'status')} for run in runs]
        cycles = [(run['topic'], run['cycle_id']) for run in runs if exportable(run)]
        if cycles:
            transfer = publisher.export_many(root, Path(artifact), cycles, base_commit, exporter=exporter)
            if transfer['exported_cycles']:
                exported = transfer
            if transfer['failures']:
                details['export_failures'] = transfer['failures']
                status = 'partial' if exported and status != 'failed' else 'failed'
    elif operation != 'health' and exportable(result):
        exported = (exporter or publisher.export)(root, Path(artifact), result['topic'], identity, base_commit)
    if github_output:
        values = {'artifact_path': str(Path(artifact).absolute()) if exported else '',
                  'cycle_id': identity or '', 'research_status': status}
        with Path(github_output).open('a', encoding='utf-8') as handle:
            for key, value in values.items():
                if any(character in value for character in '\r\n\x00'):
                    raise DeploymentError('deployment_output_invalid')
                handle.write(key + '=' + value + '\n')
    return {'status': status, 'topic': result.get('topic'), 'cycle_id': identity,
            'cached': result.get('cached', False), 'exported': exported is not None,
            'writing_started': False, **selection, **details}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    command = commands.add_parser('dispatch')
    command.add_argument('--source', required=True, type=Path)
    command.add_argument('--base-commit', required=True)
    command.add_argument('--artifact', required=True, type=Path)
    command.add_argument('--event', choices=('schedule', 'workflow_dispatch'), required=True)
    command.add_argument('--operation', choices=('health', 'collect', 'run', 'catchup'), default='run')
    command.add_argument('--cycle-id')
    command.add_argument('--github-output', type=Path)
    args = parser.parse_args(argv)
    try:
        result = dispatch(args.source, args.base_commit, args.artifact, args.event, args.operation,
                          args.cycle_id, github_output=args.github_output)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result['status'] in automatic.SUCCESS_STATUSES else 1
    except Exception as exc:
        code = str(exc) if isinstance(exc, DeploymentError) else 'scheduled_workbench_failed_preserve_checkpoints'
        print(json.dumps({'error': code, 'writing_started': False}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
