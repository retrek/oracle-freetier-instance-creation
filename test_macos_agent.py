import plistlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import macos_agent as agent


class MacOSAgentTests(unittest.TestCase):
    def test_launchd_policy_and_paths(self):
        root = Path('/example/bot with spaces')
        config = plistlib.loads(plistlib.dumps(agent.agent_config(root)))
        self.assertEqual(config['ProgramArguments'], [str(root / '.venv/bin/python'), '-B', str(root / 'macos_agent.py')])
        self.assertEqual(config['KeepAlive'], {'SuccessfulExit': False})
        self.assertTrue(config['RunAtLoad'])
        self.assertEqual(config['ThrottleInterval'], 300)
        self.assertEqual(config['EnvironmentVariables']['TMPDIR'], str(agent.SCRATCH))

    @patch.object(agent.os.path, 'ismount', return_value=False)
    def test_missing_volume_refuses_start(self, _):
        with self.assertRaisesRegex(RuntimeError, 'scratch is unavailable'):
            agent.run(Path('/unused'))

    @patch.object(agent.os, 'chdir')
    @patch.object(agent.os, 'access', return_value=True)
    @patch.object(agent.Path, 'is_dir', return_value=True)
    @patch.object(agent.os.path, 'ismount', return_value=True)
    @patch.object(agent.subprocess, 'Popen')
    def test_success_receipt_prevents_launch(self, popen, *_):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'INSTANCE_CREATED').write_text('acquired\n')
            self.assertEqual(agent.run(root), 0)
        popen.assert_not_called()


    @patch.object(agent.os, 'chdir')
    @patch.object(agent.os, 'access', return_value=True)
    @patch.object(agent.Path, 'is_dir', return_value=True)
    @patch.object(agent.os.path, 'ismount', return_value=True)
    @patch.object(agent.subprocess, 'Popen')
    def test_exit_without_receipt_restarts_and_releases_caffeinate(self, popen, *_):
        child, awake = unittest.mock.Mock(), unittest.mock.Mock()
        child.pid = 123
        child.wait.return_value = 0
        popen.side_effect = [child, awake]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(agent.run(root), 1)
            self.assertEqual((root / 'main.pid').read_text(), '123\n')
        awake.terminate.assert_called_once()
        awake.wait.assert_called_once()

    @patch.object(agent.os, 'chdir')
    @patch.object(agent.os, 'access', return_value=True)
    @patch.object(agent.Path, 'is_dir', return_value=True)
    @patch.object(agent.os.path, 'ismount', return_value=True)
    @patch.object(agent.subprocess, 'Popen')
    def test_duplicate_service_refuses_launch(self, popen, *_):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (root / '.macos-agent.lock').open('a') as lock:
                agent.fcntl.flock(lock, agent.fcntl.LOCK_EX | agent.fcntl.LOCK_NB)
                with self.assertRaisesRegex(RuntimeError, 'already running'):
                    agent.run(root)
        popen.assert_not_called()


if __name__ == '__main__':
    unittest.main()
