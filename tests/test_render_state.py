"""tests.test_render_state — prompt 渲染/截断 与状态落盘回读。"""
import json
import os
import tempfile
import unittest
from datetime import datetime

from onduty.config import PREV_MAX
from onduty.runner import render_prompt
from onduty.state import StateStore


class TestRender(unittest.TestCase):
    def test_plain_prompt(self):
        self.assertEqual(render_prompt({"prompt": "你好"}, "", "."), "你好")

    def test_prev_output_injection(self):
        out = render_prompt({"prompt": "上段: {{prev.output}} 继续"}, "结论X", ".")
        self.assertEqual(out, "上段: 结论X 继续")

    def test_prev_output_truncated(self):
        big = "啊" * (PREV_MAX + 100)
        out = render_prompt({"prompt": "{{prev.output}}"}, big, ".")
        self.assertLessEqual(len(out), PREV_MAX)

    def test_prev_output_missing_replaced_empty(self):
        self.assertEqual(render_prompt({"prompt": "[{{prev.output}}]"}, "", "."), "[]")

    def test_prompt_file_relative_to_base(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "p.md")
            with open(p, "w", encoding="utf-8") as f:
                f.write("来自文件 {{prev.output}}")
            out = render_prompt({"prompt_file": "p.md"}, "V", td)
            self.assertEqual(out, "来自文件 V")


class TestState(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.st = StateStore(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_update_and_read(self):
        self.st.update_job("j1", last_status="success", session_id="s1")
        got = self.st.job("j1")
        self.assertEqual(got["last_status"], "success")
        self.assertEqual(got["session_id"], "s1")
        self.st.update_job("j1", last_status="failed")
        self.assertEqual(self.st.job("j1")["session_id"], "s1")  # 合并不丢失

    def test_missing_job_empty(self):
        self.assertEqual(self.st.job("nope"), {})

    def test_runs_jsonl_append(self):
        self.st.append_run({"job": "j1", "status": "success"})
        self.st.append_run({"job": "j1", "status": "failed"})
        with open(os.path.join(self._td.name, "runs.jsonl"), encoding="utf-8") as f:
            recs = [json.loads(line) for line in f]
        self.assertEqual(len(recs), 2)
        self.assertEqual(recs[1]["status"], "failed")

    def test_log_path_per_job(self):
        p = self.st.new_log_path("j1", datetime(2026, 9, 16, 8, 0, 0))
        self.assertTrue(p.endswith(os.path.join("logs", "j1", "20260916-080000.log")))
        self.assertTrue(os.path.isdir(os.path.dirname(p)))


if __name__ == "__main__":
    unittest.main()
