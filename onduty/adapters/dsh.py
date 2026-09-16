"""DSH(@deepseek-ai/dsh)适配: `dsh --profile headless "<任务>"`。
实测见 plans/001 §1: 一次性任务,stdout=最终答复,退出码 0/1,无 session 输出。
本机若 dsh 不在 PATH,用 tasks.yaml 配置 agents.dsh.command 指向 bin/dsh.cmd。"""
from __future__ import annotations

from .base import Adapter, _cmd_list


class DshAdapter(Adapter):
    name = "dsh"
    capable = True
    supports_resume = False  # headless 无 resume(官方 Known Limitations)

    def build(self, job, agent_cfg, prompt, session_id):
        argv = _cmd_list(agent_cfg, ["dsh"])
        argv += ["--profile", agent_cfg.get("profile", "headless")]
        argv += list(agent_cfg.get("extra_args") or [])
        argv.append(prompt)  # 单个 positional 任务参数
        return argv

    def parse(self, stdout):
        return None, stdout.strip()
