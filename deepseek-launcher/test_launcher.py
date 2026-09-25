"""Behavioral checks using synthetic credentials and command stubs."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest


LAUNCHER = Path(__file__).with_name("deepcode-run.sh")


class LauncherTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / "home"
        self.bin = self.root / "bin"
        self.home.mkdir()
        self.bin.mkdir()
        self.write("doppler", "#!/bin/sh\necho sk-0123456789abcdef0123456789abcdef\n")
        self.write("deepcode", "#!/usr/bin/env python3\nimport sys\nsys.exit(0 if sys.stdin.isatty() and sys.stdout.isatty() else 17)\n")
        self.write("trash", "#!/bin/sh\ncat \"$1\" >> \"$TEST_TRASH_CONTENT\"\n: > \"$1\"\nmv \"$1\" \"$TEST_TRASH_FILE\"\n")
        self.env = dict(os.environ, HOME=str(self.home), PATH=f"{self.bin}:{os.environ['PATH']}",
                        DEEPCODE_CREATE_WAIT_STEPS="2",
                        TEST_TRASH_CONTENT=str(self.root / "trash-content"),
                        TEST_TRASH_FILE=str(self.root / "trashed"))

    def write(self, name, content):
        path = self.bin / name
        path.write_text(content)
        path.chmod(0o755)

    @property
    def settings(self):
        return self.home / ".deepcode" / "settings.json"

    def run_launcher(self, *args):
        return subprocess.run([str(LAUNCHER), *args], cwd=self.root, env=self.env,
                              capture_output=True, text=True, timeout=15)

    def assert_secret_cleared(self):
        self.assertFalse(self.settings.exists())
        trashed = self.root / "trashed"
        if trashed.exists():
            self.assertEqual(trashed.read_bytes(), b"")
        content = self.root / "trash-content"
        if content.exists():
            self.assertEqual(content.read_bytes(), b"")

    def test_non_tty_exit_and_cwd(self):
        result = self.run_launcher("-x", "-p", "synthetic")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_secret_cleared()

    def test_doppler_failure(self):
        self.write("doppler", "#!/bin/sh\nexit 9\n")
        result = self.run_launcher("--version")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("failed to read", result.stderr)
        self.assert_secret_cleared()

    def test_doppler_timeout(self):
        self.write("doppler", "#!/bin/sh\nexec sleep 30\n")
        self.env["DEEPCODE_DOPPLER_TIMEOUT"] = "1"
        result = self.run_launcher("--version")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("failed to read", result.stderr)
        self.assert_secret_cleared()

    def test_trash_failure_is_reported_after_secret_is_cleared(self):
        self.write("trash", "#!/bin/sh\nexit 7\n")
        result = self.run_launcher("--version")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("settings operation failed", result.stderr)
        self.assertTrue(self.settings.exists())
        self.assertEqual(self.settings.read_bytes(), b"")

    def test_stale_and_empty_file(self):
        self.settings.parent.mkdir()
        self.settings.write_text(json.dumps({"_deepcode_run_owner_pid": "999999",
                                             "env": {"API_KEY": "STALE_SECRET"}}))
        self.assertEqual(self.run_launcher("-x").returncode, 0)
        self.assert_secret_cleared()
        self.settings.touch()
        self.assertEqual(self.run_launcher("-x").returncode, 0)
        self.assert_secret_cleared()

    def test_handwritten_file_untouched(self):
        self.settings.parent.mkdir()
        original = '{"env":{"API_KEY":"HANDWRITTEN"}}'
        self.settings.write_text(original)
        self.assertNotEqual(self.run_launcher("--version").returncode, 0)
        self.assertEqual(self.settings.read_text(), original)

    def test_concurrent_sessions(self):
        self.write("deepcode", "#!/bin/sh\nsleep 1\n")
        processes = [subprocess.Popen([str(LAUNCHER), "--version"], cwd=self.root,
                                      env=self.env, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE) for _ in range(3)]
        for process in processes:
            _, err = process.communicate(timeout=15)
            self.assertEqual(process.returncode, 0, err.decode())
        self.assert_secret_cleared()

    def test_mode_while_running(self):
        self.write("deepcode", "#!/bin/sh\nsleep 2\n")
        process = subprocess.Popen([str(LAUNCHER), "--version"], cwd=self.root,
                                   env=self.env, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE)
        for _ in range(40):
            if self.settings.exists() and self.settings.stat().st_size:
                break
            time.sleep(0.05)
        self.assertTrue(self.settings.exists())
        self.assertEqual(self.settings.stat().st_mode & 0o777, 0o600)
        _, err = process.communicate(timeout=15)
        self.assertEqual(process.returncode, 0, err.decode())
        self.assert_secret_cleared()

    def test_non_tty_timeout_cleans_credential(self):
        self.write("deepcode", "#!/bin/sh\nsleep 30\n")
        self.env["DEEPCODE_TIMEOUT"] = "1"
        result = self.run_launcher("-x", "-p", "synthetic")
        self.assertEqual(result.returncode, 124, result.stderr)
        self.assert_secret_cleared()


if __name__ == "__main__":
    unittest.main()
