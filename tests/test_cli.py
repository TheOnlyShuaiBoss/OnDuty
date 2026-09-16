"""tests.test_cli — CLI 层错误体验回归(缺配置不吐 traceback,给指引)。"""
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout

from onduty import cli

VALID = """
safety:
  allow_roots: [sandbox]
jobs:
  - name: j1
    agent: dsh
    workdir: sandbox/a
    prompt: hi
"""


class TestCliMissingConfig(unittest.TestCase):
    def test_check_missing_config_returns_2_with_hint(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            with self.assertRaises(SystemExit) as cm:
                cli.main(["check", "--config", os.path.join(tempfile.gettempdir(), "no-such-tasks-xyz.yaml")])
        self.assertEqual(cm.exception.code, 2)
        out = buf.getvalue()
        self.assertIn("未找到配置文件", out)
        self.assertIn("tasks.example.yaml", out)

    def test_daemon_missing_config_no_traceback(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cli.main(["daemon", "--config", os.path.join(tempfile.gettempdir(), "no-such-tasks-xyz.yaml")])
        self.assertEqual(rc, 2)
        self.assertIn("未找到配置文件", buf.getvalue())

    def test_check_valid_config_exit_0(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "tasks.yaml")
            with open(p, "w", encoding="utf-8") as f:
                f.write(VALID)
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = cli.main(["check", "--config", p])
            self.assertEqual(rc, 0)
            self.assertIn("配置 OK", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
