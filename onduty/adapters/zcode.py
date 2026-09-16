"""ZCode 官方运行时适配(客户端内嵌 resources/glm/zcode.cjs,或 npm 全局 zcode)。
flag 全部来自本机 --help 实测(plans/003): --prompt / --json / --resume sess_xxx / -c
/ --mode build|edit|plan|yolo(--prompt 默认 yolo!)。
CLI 模型配置在 %USERPROFILE%/.zcode/cli/config.json(桌面 provider 复用可用
 scripts/sync-zcode-cli-config.ps1 生成,零密钥入库)。"""
from __future__ import annotations

import json

from .base import Adapter, _cmd_list


class ZcodeAdapter(Adapter):
    name = "zcode"
    capable = True
    supports_resume = True      # --resume <sessionId>(sess_... 格式)
    model_flagged = False       # CLI 无 --model flag,TUI 内 /model 或 config.model.main 切换

    def build(self, job, agent_cfg, prompt, session_id):
        argv = _cmd_list(agent_cfg, ["zcode"])
        argv += [agent_cfg.get("prompt_flag", "--prompt"), prompt]
        if agent_cfg.get("json", True):
            argv.append("--json")
        if session_id:
            argv += [agent_cfg.get("resume_flag", "--resume"), session_id]
        # 无人值守权限映射: allow_danger=false → 只读 plan;true → yolo(显式覆盖其默认 yolo)
        mode = "yolo" if job.get("allow_danger") else agent_cfg.get("safe_mode", "plan")
        argv += ["--mode", str(agent_cfg.get("mode") or mode)]
        argv += list(agent_cfg.get("extra_args") or [])
        return argv

    def parse(self, stdout):
        """--json 输出成功形态尚未实测(网关 captcha 拦截,见 plans/003);
        做宽容解析:整体 JSON → 逐行取最后 JSON → 原文。登录打通后按实际字段校核。"""
        raw = stdout.strip()
        if not raw:
            return None, raw
        candidates = [raw]
        lines = [ln for ln in raw.splitlines() if ln.strip()]
        if lines:
            candidates.append(lines[-1])
        for text in candidates:
            try:
                obj = json.loads(text)
            except (ValueError, TypeError):
                continue
            if isinstance(obj, dict):
                sid = None
                for k in ("session_id", "sessionId", "session", "conversation_id"):
                    if obj.get(k):
                        sid = str(obj[k])
                        break
                out = None
                for k in ("result", "text", "output", "response", "message"):
                    if isinstance(obj.get(k), str):
                        out = obj[k]
                        break
                return sid, out if out is not None else raw
        return None, raw
