"""custom 适配器: 任何"命令行非交互"agent 免代码接入(zcode 兜底/未来扩展)。
tasks.yaml 示例:
  agents:
    myagent:
      type: custom
      command: ["myagent", "--print", "{prompt}", "--resume", "{session}"]
      session_keys: [session_id]   # 可选: stdout 为 JSON 时,session id 候选键
      output_key: result           # 可选: JSON 里最终文本的键(默认 result→text→原文)
      resume: true                 # 可选覆盖;缺省按模板含 {session} 判定
      model_flag: "--model"        # 可选: 配置后方可对 job.model 生效
      allow_args: ["--yes"]        # 可选: job.allow_danger 时追加的参数
      env: {K: V}                  # 可选: 附加环境变量
"""
from __future__ import annotations

import json

from .base import Adapter, _render_argv


class CustomAdapter(Adapter):
    capable = True

    def __init__(self, name: str, agent_cfg: dict):
        self.name = name
        self._cfg = dict(agent_cfg or {})
        cmd_join = " ".join(str(t) for t in (self._cfg.get("command") or []))
        self.supports_resume = bool(self._cfg.get("resume", "{session}" in cmd_join))
        self.model_flagged = bool(self._cfg.get("model_flag"))

    def build(self, job, agent_cfg, prompt, session_id):
        template = self._cfg.get("command")
        if not template:
            raise RuntimeError(f"custom agent '{self.name}': agents.{self.name}.command 必填")
        argv = _render_argv([str(t) for t in template], prompt, session_id if self.supports_resume else None)
        if job.get("model") and self._cfg.get("model_flag"):
            argv += [self._cfg["model_flag"], job["model"]]
        if job.get("allow_danger") and self._cfg.get("allow_args"):
            argv += [str(a) for a in self._cfg["allow_args"]]
        return argv

    def env(self, job, agent_cfg):
        return {str(k): str(v) for k, v in (self._cfg.get("env") or {}).items()}

    def parse(self, stdout):
        raw = stdout.strip()
        if not raw:
            return None, raw
        try:
            obj = json.loads(raw)
        except (ValueError, TypeError):
            return None, raw
        if isinstance(obj, dict):
            sid = None
            for k in (self._cfg.get("session_keys") or ["session_id", "sessionId"]):
                if k in obj and obj[k] is not None:
                    sid = str(obj[k])
                    break
            key = self._cfg.get("output_key")
            out = obj.get(key) if key else (obj.get("result") or obj.get("text"))
            return sid, str(out if out is not None else raw)
        return None, raw
