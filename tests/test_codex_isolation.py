"""Small model-free checks for the Mac runtime and its real command sandbox."""

from importlib import metadata
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import researchdesk_codex_isolation as isolation


@unittest.skipUnless(platform.system() == 'Darwin', 'Mac profile only')
class CodexIsolation(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.input_dir = self.base / 'input'
        self.input_dir.mkdir()
        self.task = SimpleNamespace(input_dir=self.input_dir)

    def test_wrapper_drops_ambient_credentials_and_does_not_persist_capability(self):
        binary = self.base / 'fake-codex'
        binary.write_text('#!/usr/bin/python3\n'
                          'import json, os\nprint(json.dumps(dict(os.environ)))\n')
        binary.chmod(0o700)
        runtime = isolation.build_runtime(self.task, binary, 'FAKE_EPHEMERAL_CAP',
                                          'http://127.0.0.1:12345/v1', self.base)
        env = dict(OPENAI_API_KEY='SYNTHETIC_HOST_SECRET',
                   AWS_SECRET_ACCESS_KEY='SYNTHETIC_HOST_SECRET',
                   PYTHONPATH='/synthetic/untrusted/path', **runtime['env'])
        response = subprocess.run([runtime['codex_bin']], env=env, text=True,
                                  capture_output=True, check=True)
        actual = json.loads(response.stdout)
        self.assertNotIn('OPENAI_API_KEY', actual)
        self.assertNotIn('AWS_SECRET_ACCESS_KEY', actual)
        self.assertNotIn('PYTHONPATH', actual)
        self.assertEqual(actual['HOME'], runtime['home'])
        self.assertEqual(actual['CODEX_HOME'], runtime['codex_home'])
        self.assertEqual(actual[isolation.GATEWAY_ENV], 'FAKE_EPHEMERAL_CAP')
        self.assertNotIn('FAKE_EPHEMERAL_CAP', Path(runtime['codex_bin']).read_text())
        overrides = runtime['config_overrides']
        self.assertIn('default_permissions="researchdesk_read"', overrides)
        self.assertIn('shell_environment_policy.inherit="none"', overrides)
        self.assertIn('permissions.researchdesk_read.network.enabled=false', overrides)
        self.assertFalse(any(item.startswith('sandbox_') for item in overrides))

    def test_gateway_must_be_loopback_and_state_outside_input(self):
        binary = Path('/usr/bin/true')
        with self.assertRaises(ValueError):
            isolation.build_runtime(self.task, binary, 'FAKE', 'https://example.org/v1', self.base)
        with self.assertRaises(ValueError):
            isolation.build_runtime(self.task, binary, 'FAKE', 'http://127.0.0.1:12345/v1', self.input_dir)

    def test_sdk_interpreter_path_with_spaces_does_not_change_trusted_launcher(self):
        with patch.object(sys, 'executable', str(self.base / 'Application Support/codex-venv/bin/python')):
            runtime = isolation.build_runtime(self.task, '/usr/bin/true', 'FAKE',
                                              'http://127.0.0.1:12345/v1', self.base)
        self.assertEqual(Path(runtime['codex_bin']).read_text().splitlines()[0],
                         '#!/usr/bin/python3 -I')
        self.assertEqual(subprocess.run([runtime['codex_bin']], env=runtime['env']).returncode, 0)

    def test_official_runtime_native_tools_cannot_read_private_state_or_use_network(self):
        try:
            binary = metadata.distribution('openai-codex-cli-bin').locate_file('codex_cli_bin/bin/codex')
            metadata.distribution('openai-codex')
        except metadata.PackageNotFoundError:
            self.skipTest('install the pinned optional SDK/runtime to run the native canary')
        runtime = isolation.build_runtime(self.task, binary, 'FAKE_NATIVE_CAP',
                                          'http://127.0.0.1:12345/v1', self.base)
        result = isolation.verify_isolation(runtime)
        self.assertTrue(result['passed'], result)
        self.assertEqual(result['model_requests'], 0)
        self.assertEqual(list(self.input_dir.iterdir()), [])


if __name__ == '__main__':
    unittest.main()
