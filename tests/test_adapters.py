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

    def test_parse_message_array_with_result_tail(self):
        # 本机实测形态(plans/003): 顶层是消息数组,尾部带 result 对象
        ad = CodebuddyAdapter()
        payload = '[{"type":"message","role":"user","content":[]},{"type":"message","role":"assistant","content":[]},{"type":"result","subtype":"success","result":"WB-STEP1","session_id":"819d8853"}]'
        sid, out = ad.parse(payload)
        self.assertEqual((sid, out), ("819d8853", "WB-STEP1"))

    def test_parse_message_array_without_result(self):
        ad = CodebuddyAdapter()
        sid, out = ad.parse('[{"type":"message","role":"assistant","content":[{"type":"text","text":"hi"}]}]')
        self.assertIsNone(sid)
        self.assertIn("hi", out)  # 回退: 原文透传,不静默丢弃

    def test_parse_plain_text_fallback(self):
        ad = CodebuddyAdapter()
        sid, out = ad.parse("纯文本输出")
        self.assertEqual((sid, out), (None, "纯文本输出"))

    def test_model_default_flag(self):
        # 本机 help 实测: --model 存在,默认即传(可 model_flag 覆盖)
        ad = CodebuddyAdapter()
        argv = ad.build({"name": "j", "model": "glm-5.1"}, {}, "P", None)
        self.assertEqual(argv[argv.index("--model") + 1], "glm-5.1")
        argv2 = ad.build({"name": "j", "model": "m1"}, {"model_flag": "-m"}, "P", None)
        self.assertIn("-m", argv2)
        self.assertNotIn("--model", argv2)


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


class TestZcode(unittest.TestCase):
    """flag 依据本机 zcode.cjs --help 实测(plans/003)。"""

    def test_argv_safe_default(self):
        ad = resolve("zcode", {})
        argv = ad.build({"name": "j"}, {}, "P", None)
        self.assertEqual(argv, ["zcode", "--prompt", "P", "--json", "--mode", "plan"])

    def test_allow_danger_maps_yolo(self):
        ad = resolve("zcode", {})
        argv = ad.build({"name": "j", "allow_danger": True}, {}, "P", None)
        self.assertEqual(argv[argv.index("--mode") + 1], "yolo")

    def test_resume(self):
        ad = resolve("zcode", {})
        argv = ad.build({"name": "j"}, {}, "P", "sess-abc")
        self.assertEqual(argv[argv.index("--resume") + 1], "sess-abc")

    def test_parse_json(self):
        ad = resolve("zcode", {})
        sid, out = ad.parse('{"result":"好","session_id":"sess-9"}')
        self.assertEqual((sid, out), ("sess-9", "好"))

    def test_parse_last_json_line(self):
        ad = resolve("zcode", {})
        sid, out = ad.parse('noise\n{"text":"T","session":"s2"}\n')
        self.assertEqual((sid, out), ("s2", "T"))

    def test_parse_plain_fallback(self):
        ad = resolve("zcode", {})
        self.assertEqual(ad.parse("纯文本"), (None, "纯文本"))

    def test_node_bundle_command_override(self):
        acfg = {"command": ["node", "C:\\ZCode\\resources\\glm\\zcode.cjs"]}
        ad = resolve("zcode", {"zcode": acfg})
        argv = ad.build({"name": "j"}, acfg, "P", None)
        self.assertEqual(argv[:3], ["node", "C:\\ZCode\\resources\\glm\\zcode.cjs", "--prompt"])


class TestUnknown(unittest.TestCase):
    def test_missing_adapter_not_capable(self):
        self.assertFalse(resolve("nosuch", {}).capable)


if __name__ == "__main__":
    unittest.main()
