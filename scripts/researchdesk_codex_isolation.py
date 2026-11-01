"""Mac Codex 0.163 runtime isolation, with a model-free native-tool canary.

Permission profiles: https://learn.chatgpt.com/docs/permissions
Tool environment: https://learn.chatgpt.com/docs/config-file/config-reference
The wrapper does not sandbox the service process. Codex applies the named
profile to tools; verify_isolation checks that boundary through the official
SDK's command/exec endpoint, without starting a model turn.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import re
import shlex
import socket
import subprocess
import tempfile
import threading
import uuid
from urllib.parse import urlsplit


PROFILE = 'researchdesk_read'
GATEWAY_ENV = 'RESEARCHDESK_CODEX_GATEWAY_TOKEN'
SAFE_PATH = '/usr/bin:/bin:/usr/sbin:/sbin'


def _literal(value):
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, dict):
        return '{' + ', '.join(_literal(key) + '=' + _literal(item)
                               for key, item in value.items()) + '}'
    if isinstance(value, list):
        return '[' + ', '.join(_literal(item) for item in value) + ']'
    return json.dumps(value, ensure_ascii=False)


def _directory(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError('runtime directory must not be a symlink')
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    return path.resolve()


def build_runtime(task, runtime_binary, gateway_token, gateway_url, run_directory=None):
    """Return SDK launch settings; never read ambient config or credentials.

    The only bearer value entering the runtime is a short-lived local gateway
    capability. It is passed in the SDK environment, not written into a file.
    The real OAuth token stays in the gateway's parent process.
    """
    if platform.system() != 'Darwin':
        raise ValueError('this accepted isolation profile is currently Mac-only')
    binary = Path(runtime_binary).resolve()
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise ValueError('an executable bundled Codex runtime is required')
    if not isinstance(gateway_token, str) or not gateway_token:
        raise ValueError('a nonempty temporary gateway capability is required')
    endpoint = urlsplit(gateway_url)
    if (endpoint.scheme != 'http' or endpoint.hostname not in {'127.0.0.1', 'localhost', '::1'}
            or endpoint.username or endpoint.password or not endpoint.port):
        raise ValueError('the inference gateway must be an explicit loopback HTTP endpoint')
    input_dir = Path(task.input_dir).resolve(strict=True)
    if not input_dir.is_dir():
        raise ValueError('the task input must be a directory')
    base = _directory(run_directory or input_dir.parent)
    if base == input_dir or base.is_relative_to(input_dir):
        raise ValueError('runtime state must remain outside the readable input')
    home = _directory(base / 'runtime-home')
    codex_home = _directory(base / 'codex-state')
    temporary = _directory(base / 'runtime-tmp')
    launch = _directory(base / 'runtime-launch')
    # This stdlib-only launcher deliberately uses the SIP-protected system
    # interpreter, independent of the SDK venv (whose path may contain spaces).
    # -I disables PYTHONPATH and user-site startup before clearing inherited env.
    interpreter = Path('/usr/bin/python3')
    if not interpreter.is_file() or not os.access(interpreter, os.X_OK):
        raise ValueError('the trusted Mac system Python launcher is unavailable')
    process_env = {'PATH': SAFE_PATH, 'HOME': str(home), 'CODEX_HOME': str(codex_home),
                   'TMPDIR': str(temporary), 'SHELL': '/bin/sh', 'LANG': 'en_US.UTF-8'}
    wrapper = launch / 'codex'
    text = ('#!' + str(interpreter) + ' -I\n'
            'import os, sys\n'
            'clean = ' + repr(process_env) + '\n'
            'capability = os.environ.get(' + repr(GATEWAY_ENV) + ')\n'
            'if not capability:\n    raise SystemExit("missing local gateway capability")\n'
            'clean[' + repr(GATEWAY_ENV) + '] = capability\n'
            'os.execve(' + repr(str(binary)) + ', [' + repr(str(binary)) + '] + sys.argv[1:], clean)\n')
    if wrapper.is_symlink():
        raise ValueError('runtime wrapper must not be a symlink')
    descriptor, staged = tempfile.mkstemp(prefix='.codex-', dir=launch)
    try:
        with os.fdopen(descriptor, 'w') as handle:
            handle.write(text)
        os.chmod(staged, 0o700)
        os.replace(staged, wrapper)
    finally:
        if os.path.exists(staged):
            os.unlink(staged)

    settings = {
        'default_permissions': PROFILE,
        'approval_policy': 'never',
        'web_search': 'disabled',
        'permissions.' + PROFILE + '.filesystem': {
            ':root': 'deny', ':minimal': 'read', ':tmpdir': 'deny',
            ':slash_tmp': 'deny', str(input_dir): 'read',
        },
        'permissions.' + PROFILE + '.network.enabled': False,
        'shell_environment_policy.inherit': 'none',
        'shell_environment_policy.ignore_default_excludes': False,
        'shell_environment_policy.experimental_use_profile': False,
        'features.apps': False, 'features.plugins': False,
        'features.remote_plugin': False, 'features.multi_agent': False,
        'features.hooks': False, 'features.memories': False,
        'features.browser_use': False, 'features.computer_use': False,
        'features.skill_search': False, 'features.skip_host_skill_discovery': True,
        'features.shell_snapshot': False,
        'mcp_servers': {},
        # These five bundled skills are shipped by the pinned 0.163.0 runtime.
        # An added/renamed enabled skill fails the model-free catalog canary.
        'skills.config': [{'path': str(codex_home / 'skills/.system' / name / 'SKILL.md'), 'enabled': False}
                          for name in ('imagegen', 'openai-docs', 'review-agent',
                                       'skill-creator', 'skill-installer')],
    }
    for key in ('PATH', 'HOME', 'SHELL', 'LANG'):
        settings['shell_environment_policy.set.' + key] = process_env[key]
    overrides = tuple(key + '=' + _literal(value)
                      for key, value in settings.items())
    return {'codex_bin': str(wrapper), 'env': {GATEWAY_ENV: gateway_token},
            'config_overrides': overrides, 'runtime_root': str(base),
            'codex_home': str(codex_home), 'home': str(home),
            'input_dir': str(input_dir), 'permission_profile': PROFILE,
            'gateway_token_env_var': GATEWAY_ENV}


def verify_isolation(runtime):
    """Probe native command execution; returns booleans, never command output.

    Uses synthetic outside-input files instead of touching user credentials.
    The listener is local and carries no data; a successful connection would
    fail the canary. No model, login, remote service, or OAuth file is involved.
    """
    checks = {}
    if platform.system() != 'Darwin':
        return {'passed': False, 'failure': 'mac_only', 'checks': checks}
    try:
        from openai_codex import CodexConfig
        from openai_codex.client import CodexClient
        from openai_codex.generated.v2_all import CommandExecResponse, SkillsListResponse
    except ImportError:
        return {'passed': False, 'failure': 'official_sdk_unavailable', 'checks': checks}
    base, input_dir = Path(runtime['runtime_root']), Path(runtime['input_dir'])
    marker = input_dir / ('.isolation-canary-' + uuid.uuid4().hex)
    outside = base / ('isolation-canary-' + uuid.uuid4().hex)
    state_marker = Path(runtime['codex_home']) / ('isolation-canary-' + uuid.uuid4().hex)
    listener = None
    operation = 'prepare_synthetic_canaries'
    try:
        marker.write_text('PUBLIC_CANARY')
        outside.write_text('SYNTHETIC_PRIVATE_CANARY')
        state_marker.write_text('SYNTHETIC_RUNTIME_CANARY')
        operation = 'loopback_listener'
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        listener.settimeout(3)
        port = listener.getsockname()[1]
        connected = threading.Event()

        def serve_canary():
            try:
                for _ in range(2):
                    connection, _ = listener.accept()
                    connected.set()
                    with connection:
                        connection.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
            except OSError:
                pass

        threading.Thread(target=serve_canary, daemon=True).start()
        operation = 'unsandboxed_network_baseline'
        baseline = subprocess.run([
            '/usr/bin/curl', '--noproxy', '*', '--connect-timeout', '1', '--max-time', '1',
            '-s', '-o', '/dev/null', 'http://127.0.0.1:%s/' % port,
        ], env={'PATH': SAFE_PATH, 'HOME': runtime['home']}, capture_output=True, timeout=3)
        checks['network_canary_reachable'] = baseline.returncode == 0 and connected.is_set()
        if not checks['network_canary_reachable']:
            return {'passed': False, 'checks': checks, 'failure': 'network_canary_not_reachable',
                    'model_requests': 0}
        connected.clear()
        # Only fixed shell fragments plus correctly quoted local canary paths.
        # Do not print env, file contents, the gateway URL, or stderr diagnostics.
        fragments = [
            'test "$(/bin/cat %s 2>/dev/null)" = PUBLIC_CANARY; printf "input_read=%%s\\n" "$?"' % shlex.quote(str(marker)),
            'if /bin/cat %s >/dev/null 2>&1; then echo host_denied=1; else echo host_denied=0; fi' % shlex.quote(str(outside)),
            'if /bin/cat %s >/dev/null 2>&1; then echo state_denied=1; else echo state_denied=0; fi' % shlex.quote(str(state_marker)),
            'if printf MODIFIED >>%s 2>/dev/null; then echo input_readonly=1; else echo input_readonly=0; fi' % shlex.quote(str(marker)),
            'test -z "${%s+x}"; printf "capability_absent=%%s\\n" "$?"' % GATEWAY_ENV,
            'test -z "${OPENAI_API_KEY+x}${AWS_SECRET_ACCESS_KEY+x}"; printf "ambient_secrets_absent=%s\\n" "$?"',
            'if /usr/bin/curl --noproxy "*" --connect-timeout 1 --max-time 1 -s -o /dev/null http://127.0.0.1:%s/; then echo network_denied=1; else echo network_denied=0; fi' % port,
        ]
        config = CodexConfig(codex_bin=runtime['codex_bin'], env=runtime['env'],
            config_overrides=runtime['config_overrides'], cwd=str(input_dir),
            client_name='ResearchDesk', client_title='ResearchDesk', client_version='0.1',
            experimental_api=False)
        operation = 'official_sdk_command_exec'
        with CodexClient(config) as client:
            client.initialize()
            response = client.request('command/exec', {
                'command': ['/bin/sh', '-c', '\n'.join(fragments)],
                'cwd': str(input_dir), 'timeoutMs': 8000,
            }, response_model=CommandExecResponse)
            skills = client.request('skills/list', {'cwds': [str(input_dir)]},
                                    response_model=SkillsListResponse)
            checks['skills_disabled'] = not any(skill.enabled for entry in skills.data
                                                for skill in entry.skills)
        parsed = dict(re.findall(r'^([a-z_]+)=([01])$', response.stdout, re.MULTILINE))
        required = ('input_read', 'host_denied', 'state_denied', 'input_readonly',
                    'capability_absent', 'ambient_secrets_absent', 'network_denied')
        checks.update({name: parsed.get(name) == '0' for name in required})
        checks['network_denied'] = checks['network_denied'] and not connected.is_set()
        checks['input_unchanged'] = marker.read_text() == 'PUBLIC_CANARY'
        return {'passed': all(checks.values()), 'checks': checks,
                'probe': 'official_sdk_command_exec', 'model_requests': 0}
    except Exception as exc:
        return {'passed': False, 'checks': checks, 'failure': type(exc).__name__,
                'failure_stage': operation, 'model_requests': 0}
    finally:
        if listener is not None:
            listener.close()
        for path in (marker, outside, state_marker):
            path.unlink(missing_ok=True)
