"""tests.test_config — 校验规则逐条(主方案 §7/§8,全部应 fail fast)。"""
import os
import tempfile
import unittest

from onduty import config


def write_tasks(tmp: str, doc: str) -> str:
    p = os.path.join(tmp, "tasks.yaml")
    with open(p, "w", encoding="utf-8") as f:
        f.write(doc)
    return p


HEAD = """
safety:
  allow_roots: [sandbox]
jobs:
"""

BASE_JOB = """  - name: j1
    agent: dsh
    workdir: sandbox/a
    prompt: hi
"""


class TestConfig(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = self._td.name

    def tearDown(self):
        self._td.cleanup()

    def load(self, body: str):
        return config.load_config(write_tasks(self.tmp, HEAD + body))

    def test_valid_minimal(self):
        cfg = self.load(BASE_JOB)
        self.assertEqual(len(cfg["jobs"]), 1)
        self.assertEqual(cfg["jobs"][0]["schedule"]["kind"], "manual")
        self.assertFalse(cfg["adapters"]["dsh"].supports_resume)

    def test_workdir_escape_rejected(self):
        with self.assertRaises(config.ConfigError):
            self.load(BASE_JOB.replace("workdir: sandbox/a", "workdir: ../outside"))

    def test_continue_on_dsh_rejected(self):
        with self.assertRaises(config.ConfigError):
            self.load(BASE_JOB + "    mode: continue\n")

    def test_model_needs_flag_rejected(self):
        with self.assertRaises(config.ConfigError):
            self.load(BASE_JOB + "    model: glm-5\n")

    def test_prompt_either(self):
        with self.assertRaises(config.ConfigError):
            self.load(BASE_JOB + "    prompt_file: p.md\n")

    def test_bad_cron_rejected(self):
        with self.assertRaises(config.ConfigError):
            self.load(BASE_JOB + "    schedule:\n      cron: \"99 99 * * *\"\n")

    def test_once_at_rejected_in_v01(self):
        with self.assertRaises(config.ConfigError):
            self.load(BASE_JOB + "    schedule:\n      once_at: \"2026-09-20 08:00\"\n")

    def test_after_unknown_rejected(self):
        with self.assertRaises(config.ConfigError):
            self.load(BASE_JOB + "    schedule:\n      after: nope\n")

    def test_after_cycle_rejected(self):
        body = (BASE_JOB + "    schedule:\n      after: j2\n"
                "  - name: j2\n    agent: dsh\n    workdir: sandbox/b\n    prompt: x\n"
                "    schedule:\n      after: j1\n")
        with self.assertRaises(config.ConfigError):
            self.load(body)

    def test_prev_template_requires_after(self):
        with self.assertRaises(config.ConfigError):
            self.load(BASE_JOB.replace("prompt: hi", "prompt: \"{{prev.output}}\""))

    def test_unknown_template_rejected(self):
        body = (BASE_JOB + "  - name: j2\n    agent: dsh\n    workdir: sandbox/b\n"
                "    prompt: \"值={{whatever}}\"\n    schedule:\n      after: j1\n")
        with self.assertRaises(config.ConfigError):
            self.load(body)

    def test_notify_channel_rejected(self):
        with self.assertRaises(config.ConfigError):
            self.load(BASE_JOB + "    notify: [carrier-pigeon]\n")

    def test_unknown_agent_rejected(self):
        with self.assertRaises(config.ConfigError):
            self.load(BASE_JOB.replace("agent: dsh", "agent: totally-not-real"))

    def test_zcode_continue_now_valid(self):
        cfg = self.load(BASE_JOB.replace("agent: dsh", "agent: zcode") + "    mode: continue\n")
        self.assertEqual(cfg["jobs"][0]["mode"], "continue")

    def test_custom_agent_ok(self):
        cfg = config.load_config(write_tasks(self.tmp, """
safety:
  allow_roots: [sandbox]
agents:
  mya:
    type: custom
    command: ["mya", "-p", "{prompt}"]
jobs:
  - name: c1
    agent: mya
    workdir: sandbox/c
    prompt: hi
"""))
        self.assertTrue(cfg["adapters"]["mya"].capable)
        self.assertEqual(cfg["jobs"][0]["name"], "c1")

    def test_after_chain_valid(self):
        body = (BASE_JOB + "  - name: j2\n    agent: dsh\n    workdir: sandbox/b\n"
                "    prompt: ok {{prev.output}}\n    schedule:\n      after: j1\n")
        cfg = self.load(body)
        self.assertEqual(cfg["jobs"][1]["schedule"]["after"], "j1")

    def test_yaml_bare_on_key_normalized(self):
        # YAML 1.1 会把裸 on: 解析为 True,必须兼容
        body = (BASE_JOB + "  - name: j2\n    agent: dsh\n    workdir: sandbox/b\n"
                "    prompt: ok {{prev.output}}\n    schedule:\n      after: j1\n      on: always\n")
        cfg = self.load(body)
        self.assertEqual(cfg["jobs"][1]["schedule"]["on"], "always")

    def test_duplicate_names_rejected(self):
        with self.assertRaises(config.ConfigError):
            self.load(BASE_JOB + BASE_JOB)


if __name__ == "__main__":
    unittest.main()
