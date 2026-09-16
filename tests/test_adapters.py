"""tests.test_adapters — 三家内置适配器 + custom 的建令/解析行为(flag 依据 plans/001)。"""
import unittest

from onduty.adapters import resolve
from onduty.adapters.codebuddy import CodebuddyAdapter


class TestDsh(unittest.TestCase):
    def test_argv(self):
        ad = resolve("dsh", {})
        argv = ad.build({"name": "j", "allow_danger": False}, {}, "任务文本", None)
        self.assertEqual(argv, ["dsh", "--profile", "headless", "任务文本"])

    def test_command_override(self):
        acfg = {"dsh": {"command": ["C:\\bin\\dsh.cmd"]}}
        ad = resolve("dsh", acfg)
        argv = ad.build({"name": "j"}, acfg["dsh"], "P", None)
        self.assertEqual(argv, ["C:\\bin\\dsh.cmd", "--profile", "headless", "P"])

    def test_no_session_ever(self):
        self.assertIsNone(resolve("dsh", {}).parse("好")[0])

    def test_extra_args(self):
        acfg = {"command": "dsh", "extra_args": ["--patch", "x.yml"]}
        ad = resolve("dsh", {"dsh": acfg})
        argv = ad.build({"name": "j"}, acfg, "P", None)
        self.assertEqual(argv, ["dsh", "--profile", "headless", "--patch", "x.yml", "P"])


class TestCodebuddy(unittest.TestCase):
    def test_basic(self):
        ad = resolve("codebuddy", {})
        argv = ad.build({"name": "j"}, {}, "P", None)
        self.assertEqual(argv, ["codebuddy", "-p", "P", "--output-format", "json"])

    def test_resume(self):
        ad = CodebuddyAdapter()
        argv = ad.build({"name": "j"}, {}, "P", "sess-1")
        self.assertIn("--resume", argv)
        self.assertEqual(argv[argv.index("--resume") + 1], "sess-1")

    def test_allow_danger(self):
        ad = CodebuddyAdapter()
        argv = ad.build({"name": "j", "allow_danger": True}, {}, "P", None)
        self.assertIn("-y", argv)
        self.assertEqual(ad.env({"allow_danger": True}, {}), {"CODEBUDDY_IS_SANDBOX": "1"})
        self.assertEqual(ad.env({"allow_danger": False}, {}), {})

    def test_parse_json(self):
        ad = CodebuddyAdapter()
        sid, out = ad.parse('{"type":"result","result":"结论ABC","session_id":"s-9"}')
        self.assertEqual((sid, out), ("s-9", "结论ABC"))

    def test_parse_plain_text_fallback(self):
        ad = CodebuddyAdapter()
        sid, out = ad.parse("纯文本输出")
        self.assertEqual((sid, out), (None, "纯文本输出"))

    def test_model_only_with_flag(self):
        ad = CodebuddyAdapter()
        argv = ad.build({"name": "j", "model": "m1"}, {}, "P", None)
        self.assertNotIn("--model", argv)
        argv2 = ad.build({"name": "j", "model": "m1"}, {"model_flag": "--model"}, "P", None)
        self.assertIn("--model", argv2)


class TestCustom(unittest.TestCase):
    CFG = {"zcode": {"type": "custom",
                     "command": ["zcode-cli", "-p", "{prompt}", "--session", "{session}"],
                     "session_keys": ["conversation_id"], "allow_args": ["--yes"]}}

    def test_session_placeholder_dropped_without_session(self):
        ad = resolve("zcode", self.CFG)
        argv = ad.build({"name": "j"}, self.CFG["zcode"], "P", None)
        self.assertNotIn("--session", argv)
        self.assertEqual(argv, ["zcode-cli", "-p", "P"])

    def test_session_placeholder_filled(self):
        ad = resolve("zcode", self.CFG)
        argv = ad.build({"name": "j"}, self.CFG["zcode"], "P", "abc")
        self.assertEqual(argv, ["zcode-cli", "-p", "P", "--session", "abc"])

    def test_resume_detected_from_template(self):
        self.assertTrue(resolve("zcode", self.CFG).supports_resume)

    def test_parse_json_custom_keys(self):
        ad = resolve("zcode", self.CFG)
        sid, out = ad.parse('{"conversation_id":"c1","result":"R"}')
        self.assertEqual((sid, out), ("c1", "R"))

    def test_allow_args(self):
        ad = resolve("zcode", self.CFG)
        argv = ad.build({"name": "j", "allow_danger": True}, self.CFG["zcode"], "P", None)
        self.assertIn("--yes", argv)


class TestZcodeBuiltin(unittest.TestCase):
    def test_not_capable(self):
        ad = resolve("zcode", {})
        self.assertFalse(ad.capable)
        with self.assertRaises(RuntimeError):
            ad.build({"name": "j"}, {}, "P", None)


class TestUnknown(unittest.TestCase):
    def test_missing_adapter_not_capable(self):
        self.assertFalse(resolve("nosuch", {}).capable)


if __name__ == "__main__":
    unittest.main()
