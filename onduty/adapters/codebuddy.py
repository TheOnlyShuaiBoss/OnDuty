"""CodeBuddy/WorkBuddy CLI 适配(npm @tencent-ai/codebuddy-code,命令 codebuddy/cbc)。
flag 依据官方无头文档(plans/001 §2): -p/--print, --output-format json, --resume/-r。
未实测(本机未装);所有 flag 可用 agents.codebuddy.* 配置覆盖,装好后冒烟转正。"""
from __future__ import annotations

import json

from .base import Adapter, _cmd_list


class CodebuddyAdapter(Adapter):
    name = "codebuddy"
    capable = True
    supports_resume = True       # --resume <session_id>(官方文档)
    model_flagged = False        # --model 未在文档证实,默认不传

    def build(self, job, agent_cfg, prompt, session_id):
        argv = _cmd_list(agent_cfg, ["codebuddy"])
        argv += [agent_cfg.get("print_flag", "-p"), prompt]
        fmt = agent_cfg.get("output_format", "json")
        if fmt and fmt != "text":
            argv += [agent_cfg.get("format_flag", "--output-format"), fmt]
        if session_id:
            argv += [agent_cfg.get("resume_flag", "--resume"), session_id]
        if job.get("model") and agent_cfg.get("model_flag"):
            argv += [agent_cfg["model_flag"], job["model"]]
        if job.get("allow_danger"):
            argv.append(agent_cfg.get("allow_flag", "-y"))  # 无头放权必需;workdir 已被强制在白名单内
        argv += list(agent_cfg.get("extra_args") or [])
        return argv

    def env(self, job, agent_cfg):
        # 官方: 隔离沙箱内 CODEBUDDY_IS_SANDBOX=1 + -y 才真正全程免询问(高危,仅当 allow_danger)
        if job.get("allow_danger") and agent_cfg.get("sandbox_env", True):
            return {"CODEBUDDY_IS_SANDBOX": "1"}
        return {}

    def parse(self, stdout):
        raw = stdout.strip()
        try:
            obj = json.loads(raw)
        except (ValueError, TypeError):
            return None, raw
        if isinstance(obj, dict):
            sid = obj.get("session_id") or obj.get("sessionId")
            out = obj.get("result") or obj.get("text") or raw
            return sid, str(out)
        return None, raw
