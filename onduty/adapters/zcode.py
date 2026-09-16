"""zcode(zcode-app-cli)占位适配: v0.1 无头能力证据不足,见 plans/001 §3。
实测到非交互命令后,请改用 agents.zcode.type: custom 接入,或据实更新本文件。"""
from __future__ import annotations

from .base import Adapter


class ZcodeAdapter(Adapter):
    name = "zcode"
    capable = False  # 仅 TUI 证据(README/HOST_INTEGRATION),无 -p/--print 文档
    supports_resume = False

    def build(self, job, agent_cfg, prompt, session_id):
        raise RuntimeError(
            "zcode v0.1 未接入: 无公开非交互调用证据(plans/001 §3)。"
            "请在 tasks.yaml 配置 agents.zcode: {type: custom, command: [...含 {prompt} ...]}")
