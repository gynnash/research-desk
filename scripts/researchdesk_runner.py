#!/usr/bin/env python3
"""Install/inspect a ResearchDesk self-hosted runner on the current machine.

Registration secrets are captured in memory and passed through the official
ACTIONS_RUNNER_INPUT_TOKEN environment interface, never command arguments.
Remote configuration describes a host where the user runs this CLI; no SSH or
credential copying is performed. Doctor never reads OAuth credential contents.
"""

import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from urllib.parse import urlsplit

import researchdesk_offline as store
from researchdesk_membership import DEFAULT_PROFILE


class RunnerError(RuntimeError):
    """Only fixed, sanitized diagnostic codes may leave this module."""


def _run(command, cwd, code, env=None, timeout=180, check=True):
    try:
        result = subprocess.run(command, cwd=cwd, env=env, capture_output=True,
                                text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RunnerError(code) from exc
    if check and result.returncode:
        # Provider/runner output can contain credentials or private filesystem
        # details. Never interpolate stderr, stdout or command into errors.
        raise RunnerError(code)
    return result


def _outside(root, value):
    if not isinstance(value, str) or not value or '\x00' in value:
        raise RunnerError('runtime_path_invalid')
    path = Path(value).expanduser().absolute()
    if not Path(value).expanduser().is_absolute():
        raise RunnerError('runtime_path_must_be_absolute_or_home_relative')
    for entry in (path,) + tuple(path.parents):
        if entry.is_symlink():
            raise RunnerError('runtime_path_symlink')
    if path.resolve().is_relative_to(root):
        raise RunnerError('runtime_must_live_outside_repository')
    return path


def load_config(root, config_path='config/runtime.yaml'):
    root = Path(root).resolve()
    path = Path(config_path)
    if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0] != 'config':
        raise RunnerError('runtime_config_path_invalid')
    config = store.load_yaml(root / path)
    if (set(config) != {'schema_version', 'environment', 'runner', 'membership', 'python'}
            or type(config['schema_version']) is not int or config['schema_version'] != 1
            or config['environment'] not in {'local', 'remote'}):
        raise RunnerError('runtime_config_invalid')
    runner, membership, python = config['runner'], config['membership'], config['python']
    if (not isinstance(runner, dict) or set(runner) != {'directory', 'labels', 'name'}
            or not isinstance(membership, dict) or set(membership) != {'profile'}
            or not isinstance(python, dict) or set(python) != {'venv'}):
        raise RunnerError('runtime_config_fields_invalid')
    if not isinstance(runner['name'], str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', runner['name']):
        raise RunnerError('runner_name_invalid')
    labels = runner['labels']
    if (not isinstance(labels, list) or not 1 <= len(labels) <= 10
            or any(not isinstance(label, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,64}', label) for label in labels)
            or len(set(labels)) != len(labels)):
        raise RunnerError('runner_labels_invalid')
    directory = _outside(root, runner['directory'])
    venv = _outside(root, python['venv'])
    profile = _outside(root, str(DEFAULT_PROFILE) if membership['profile'] is None else membership['profile'])
    if (directory == venv or directory.is_relative_to(venv) or venv.is_relative_to(directory)
            or profile == directory or profile.is_relative_to(directory)
            or directory.is_relative_to(profile) or profile == venv or profile.is_relative_to(venv)
            or venv.is_relative_to(profile)):
        raise RunnerError('runtime_directories_must_be_separate')
    return dict(config, _directory=directory, _venv=venv, _profile=profile)


def _repository(root):
    origin = _run(['git', 'remote', 'get-url', 'origin'], root, 'github_origin_unavailable').stdout.strip()
    if origin.startswith('git@github.com:'):
        name = origin[len('git@github.com:'):]
    else:
        parsed = urlsplit(origin)
        if parsed.scheme != 'https' or parsed.hostname != 'github.com' or parsed.username or parsed.password:
            raise RunnerError('only_github_repository_origins_supported')
        name = parsed.path.lstrip('/')
    name = name.removesuffix('.git').rstrip('/')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', name):
        raise RunnerError('github_repository_name_invalid')
    return name


def _api(root, route, method='GET'):
    result = _run(['gh', 'api', '--method', method, route], root, 'github_api_failed')
    try:
        value = json.loads(result.stdout)
    except (ValueError, TypeError) as exc:
        raise RunnerError('github_api_response_invalid') from exc
    if not isinstance(value, dict):
        raise RunnerError('github_api_response_invalid')
    return value


def _platform():
    system = {'Darwin': 'osx', 'Linux': 'linux'}.get(platform.system())
    architecture = {'arm64': 'arm64', 'aarch64': 'arm64', 'x86_64': 'x64', 'amd64': 'x64'}.get(platform.machine().lower())
    if not system or not architecture:
        raise RunnerError('runner_platform_not_supported')
    return system, architecture


def _asset(release, system, architecture):
    tag = release.get('tag_name', '')
    if not re.fullmatch(r'v\d+\.\d+\.\d+', tag):
        raise RunnerError('runner_release_version_invalid')
    name = 'actions-runner-%s-%s-%s.tar.gz' % (system, architecture, tag[1:])
    assets = [asset for asset in release.get('assets', []) if asset.get('name') == name]
    if len(assets) != 1:
        raise RunnerError('runner_release_asset_unavailable')
    asset = assets[0]
    expected_url = 'https://github.com/actions/runner/releases/download/%s/%s' % (tag, name)
    if asset.get('browser_download_url') != expected_url:
        raise RunnerError('runner_release_asset_url_invalid')
    digest = asset.get('digest')
    if isinstance(digest, str) and re.fullmatch(r'sha256:[0-9a-f]{64}', digest):
        checksum = digest[7:]
    else:
        # Official release bodies publish checksums beside each package name.
        expression = re.escape(name) + r'\s+<!-- BEGIN SHA ' + re.escape(system + '-' + architecture) + r' -->([0-9a-f]{64})<!-- END SHA'
        match = re.search(expression, release.get('body', ''))
        if not match:
            raise RunnerError('runner_official_checksum_unavailable')
        checksum = match.group(1)
    return name, expected_url, checksum, tag


def _install_package(root, config, system, architecture):
    directory = config['_directory']
    if (directory / 'config.sh').is_file():
        if not (directory / '.researchdesk-package.json').is_file() and not (directory / '.runner').is_file():
            raise RunnerError('existing_runner_package_requires_inspection')
        return
    if directory.exists() and any(directory.iterdir()):
        raise RunnerError('runner_directory_is_not_empty')
    release = _api(root, 'repos/actions/runner/releases/latest')
    name, url, checksum, tag = _asset(release, system, architecture)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(prefix='researchdesk-runner-') as temporary:
        archive = Path(temporary) / name
        _run(['curl', '--fail', '--location', '--silent', '--show-error', '--proto', '=https',
              '--tlsv1.2', '--output', str(archive), url], root, 'runner_download_failed', timeout=600)
        hasher = hashlib.sha256()
        with archive.open('rb') as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                hasher.update(chunk)
        if hasher.hexdigest() != checksum:
            raise RunnerError('runner_package_checksum_mismatch')
        with tarfile.open(archive, 'r:gz') as package:
            for member in package.getmembers():
                path = Path(member.name)
                if path.is_absolute() or '..' in path.parts or member.isdev():
                    raise RunnerError('runner_package_path_invalid')
                if member.issym() or member.islnk():
                    target = (path.parent / member.linkname if member.issym() else Path(member.linkname))
                    if Path(member.linkname).is_absolute() or not (directory / target).resolve().is_relative_to(directory):
                        raise RunnerError('runner_package_link_invalid')
        _run(['tar', '-xzf', str(archive), '-C', str(directory)], root, 'runner_package_extract_failed')
    marker = {'release': tag, 'asset': name, 'sha256': checksum}
    (directory / '.researchdesk-package.json').write_text(json.dumps(marker) + '\n', encoding='utf-8')


def _service_state(directory):
    if not (directory / 'svc.sh').is_file():
        return 'unavailable'
    if platform.system() == 'Darwin':
        marker = directory / '.service'
        if not marker.is_file():
            return 'not_installed'
        plist = Path(marker.read_text(encoding='utf-8').strip())
        if not plist.is_file():
            return 'not_installed'
        label = plist.stem
        if not re.fullmatch(r'actions\.runner\.[A-Za-z0-9_.@-]+', label):
            return 'unknown'
        result = _run(['launchctl', 'list', label], directory,
                      'runner_service_status_failed', check=False)
        # svc.sh says Started when a label is loaded, even if its process has
        # exited. Check the real PID instead of treating a loaded job as live.
        if result.returncode:
            return 'stopped'
        return 'running' if re.search(r'"PID"\s*=\s*[1-9]\d*\s*;', result.stdout) else 'stopped'
    if platform.system() == 'Linux' and (directory / '.service').is_file():
        # The Linux svc wrapper requires root even for status. systemctl's
        # read-only is-active query does not need service mutation privileges.
        name = (directory / '.service').read_text(encoding='utf-8').strip()
        if not re.fullmatch(r'actions\.runner\.[A-Za-z0-9_.@-]+\.service', name):
            return 'unknown'
        result = _run(['systemctl', 'is-active', '--', name], directory,
                      'runner_service_status_failed', check=False)
        return 'running' if result.stdout.strip() == 'active' else 'stopped'
    result = _run(['./svc.sh', 'status'], directory, 'runner_service_status_failed', check=False)
    output = result.stdout.lower()
    if 'not installed' in output or not (directory / '.service').is_file():
        return 'not_installed'
    if result.returncode:
        return 'unknown'
    if 'started:' in output or 'active (running)' in output:
        return 'running'
    if 'stopped' in output or 'inactive' in output:
        return 'stopped'
    return 'unknown'


def _permissions(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return {'exists': False, 'mode': None, 'owned_by_current_user': None, 'symlink': False}
    return {'exists': True, 'mode': format(stat.S_IMODE(info.st_mode), '04o'),
            'owned_by_current_user': info.st_uid == os.getuid(), 'symlink': stat.S_ISLNK(info.st_mode)}


def doctor(root, config):
    """Inspect only; no OAuth reads, login, model calls, SSH or network API."""
    directory, profile, venv = config['_directory'], config['_profile'], config['_venv']
    python = venv / 'bin/python'
    dependencies = False
    if python.is_file():
        dependencies = _run([str(python), '-c',
                             'import sys; assert sys.version_info >= (3, 9); import yaml, jwt, cryptography'], root,
                            'runtime_python_check_failed', check=False).returncode == 0
    profile_info = _permissions(profile)
    credential_info = _permissions(profile / 'credentials.json')
    return {'schema_version': 1, 'environment': config['environment'],
            'execution': 'current_machine_no_ssh', 'platform': platform.system(),
            'runner': {'name': config['runner']['name'], 'labels': config['runner']['labels'],
                       'package_installed': (directory / 'config.sh').is_file(),
                       'registered': (directory / '.runner').is_file(), 'service': _service_state(directory)},
            'python': {'venv_exists': (venv / 'pyvenv.cfg').is_file(), 'dependencies_ready': dependencies},
            'membership': {'profile': profile_info, 'credential_file': credential_info,
                           'contents_read': False, 'authorization_verified': False},
            'tools': {'git': shutil.which('git') is not None, 'gh': shutil.which('gh') is not None,
                      'curl': shutil.which('curl') is not None}, 'model_calls': 0}


def setup(root, config):
    """Install/register/start on this host; caller authorizes host mutations."""
    root = Path(root).resolve()
    if sys.version_info < (3, 9):
        raise RunnerError('python_3_9_or_newer_required')
    if os.getuid() == 0:
        raise RunnerError('run_setup_as_normal_user_not_root')
    if any(shutil.which(tool) is None for tool in ('git', 'gh', 'curl', 'tar')):
        raise RunnerError('required_runner_tools_missing')
    system, architecture = _platform()
    directory, venv = config['_directory'], config['_venv']
    repository = _repository(root)
    if venv.exists() and any(venv.iterdir()) and not (venv / 'pyvenv.cfg').is_file():
        raise RunnerError('runtime_venv_directory_is_not_empty')
    if not (venv / 'pyvenv.cfg').is_file():
        _run([sys.executable, '-m', 'venv', str(venv)], root, 'runtime_venv_creation_failed')
    _run([str(venv / 'bin/python'), '-m', 'pip', 'install', '--disable-pip-version-check',
          '-r', str(root / 'workflows/requirements-membership.txt')], root,
         'runtime_dependencies_install_failed', timeout=600)
    _install_package(root, config, system, architecture)
    registration = directory / '.runner'
    if registration.is_file():
        try:
            existing = json.loads(registration.read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise RunnerError('existing_runner_registration_invalid') from exc
        if (existing.get('agentName') != config['runner']['name']
                or existing.get('gitHubUrl', '').rstrip('/').lower() != ('https://github.com/' + repository).lower()):
            raise RunnerError('existing_runner_registration_mismatch')
    else:
        result = _api(root, 'repos/%s/actions/runners/registration-token' % repository, method='POST')
        token = result.get('token')
        if not isinstance(token, str) or not token or any(char.isspace() for char in token):
            raise RunnerError('runner_registration_token_invalid')
        environment = dict(os.environ, ACTIONS_RUNNER_INPUT_TOKEN=token)
        try:
            _run(['./config.sh', '--unattended', '--url', 'https://github.com/' + repository,
                  '--name', config['runner']['name'], '--labels', ','.join(config['runner']['labels']),
                  '--work', '_work'], directory, 'runner_registration_failed', env=environment)
        finally:
            environment.pop('ACTIONS_RUNNER_INPUT_TOKEN', None)
            result.clear()
            token = None
    state = _service_state(directory)
    service_prefix = [] if system == 'osx' else ['sudo', '-n']
    if state == 'not_installed':
        arguments = ['./svc.sh', 'install'] + ([getpass.getuser()] if system == 'linux' else [])
        _run(service_prefix + arguments, directory, 'runner_service_install_failed')
    if _service_state(directory) != 'running':
        _run(service_prefix + ['./svc.sh', 'start'], directory, 'runner_service_start_failed')
    return doctor(root, config)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument('--config', default='config/runtime.yaml')
    parser.add_argument('command', choices=('doctor', 'setup'))
    args = parser.parse_args()
    try:
        if sys.version_info < (3, 9):
            raise RunnerError('python_3_9_or_newer_required')
        root = Path(args.root).resolve()
        config = load_config(root, args.config)
        result = doctor(root, config) if args.command == 'doctor' else setup(root, config)
    except (RunnerError, store.OfflineError) as exc:
        code = str(exc) if isinstance(exc, RunnerError) else 'runtime_yaml_invalid'
        print(json.dumps({'error': code, 'model_calls': 0}))
        return 1
    except Exception:
        # No traceback: subprocess/provider data may contain private details.
        print(json.dumps({'error': 'runner_operation_failed', 'model_calls': 0}))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
