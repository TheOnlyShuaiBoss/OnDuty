"""tests.test_session_chain — after 链 continue 续接上游会话(runner 级真实子进程)。
用 python -c 当"假 agent CLI",输出 JSON 形态模拟 codebuddy。"""
import os
import sys
import tempfile
import unittest

from onduty.adapters import resolve
from onduty.runner import run_job
from onduty.state import StateStore


def _fake_agent(tmp: str):
    """custom agent: 打印固定 JSON 会话输出;argv 进日志可查。"""
    code = "import json; print(json.dumps({'result':'OK','session_id':'sess-9'}))"
    return {
        "type": "custom",
        "command": [sys.executable, "-c", code, "{prompt}", "--resume", "{session}"],
    }


def _job(tmp, name, mode):
    return {"name": name, "agent": "fakecli", "mode": mode, "model": None,
            "workdir": tmp, "prompt": "ping", "prompt_file": None,
            "timeout_minutes": 5, "allow_danger": False, "notify": ["log"],
            "catchup": False, "schedule": {"kind": "manual", "cron": None, "after": None, "on": "success"}}


class TestSessionChain(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = self._td.name
        self.agent_cfg = _fake_agent(self.tmp)
        self.cfg = {"base": self.tmp, "agents": {"fakecli": self.agent_cfg},
                    "adapters": {"fakecli": resolve("fakecli", {"fakecli": self.agent_cfg})}}
        self.state = StateStore(os.path.join(self.tmp, "state"))

    def tearDown(self):
        self._td.cleanup()

    def _read_argv_line(self, job_name):
        log = self.state.job(job_name)["last_log"]
        with open(log, encoding="utf-8") as f:
            return next(l for l in f if l.startswith("# argv="))

    def test_chain_continue_resumes_upstream_session(self):
        up = _job(self.tmp, "up", "new")
        r1 = run_job(self.cfg, self.state, up, "manual")
        self.assertEqual(r1.status, "success")
        self.assertEqual(self.state.job("up")["session_id"], "sess-9")

        down = _job(self.tmp, "down", "continue")
        r2 = run_job(self.cfg, self.state, down, "after", prev_output="OK", session_source="up")
        self.assertEqual(r2.status, "success")
        argv_line = self._read_argv_line("down")
        self.assertIn("--resume", argv_line)
        self.assertIn("sess-9", argv_line)

    def test_continue_without_source_uses_own_session_then(self):
        a = _job(self.tmp, "selfj", "continue")
        r1 = run_job(self.cfg, self.state, a, "manual")  # 首轮无 session → 不传
        self.assertNotIn("--resume", self._read_argv_line("selfj"))
        r2 = run_job(self.cfg, self.state, a, "manual")  # 二轮续接自己的
        self.assertIn("sess-9", self._read_argv_line("selfj"))

    def test_upstream_priority_over_self(self):
        # 自己有旧会话,但 after 上游对话优先
        run_job(self.cfg, self.state, _job(self.tmp, "me", "continue"), "manual")
        self.state.update_job("me", session_id="sess-9-self")
        run_job(self.cfg, self.state, _job(self.tmp, "up2", "new"), "manual")  # up2 得 sess-9
        run_job(self.cfg, self.state, _job(self.tmp, "me", "continue"), "after", session_source="up2")
        self.assertIn("'sess-9'", self._read_argv_line("me"))  # 精确匹配元素,排除 sess-9-self


if __name__ == "__main__":
    unittest.main()
