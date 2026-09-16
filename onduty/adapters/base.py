"""适配器协议: 命令构建 / 环境变量 / 输出解析。能力用数据声明,配置校验 fail fast(见 plans/001)。"""
from __future__ import annotations


class Adapter:
    name = "?"
    capable = False        # 是否有非交互调用能力证据
    supports_resume = False  # 是否能把 session_id 续接进命令行
    model_flagged = False    # 用户是否配置了 model_flag(能命令行指定模型)

    def build(self, job: dict, agent_cfg: dict, prompt: str, session_id: str | None) -> list[str]:
        raise NotImplementedError

    def env(self, job: dict, agent_cfg: dict) -> dict[str, str]:
        return {}

    def parse(self, stdout: str) -> tuple[str | None, str]:
        """返回 (session_id 或 None, 最终文本输出)。"""
        return None, stdout.strip()


def _cmd_list(agent_cfg: dict, default: list[str]) -> list[str]:
    c = agent_cfg.get("command")
    if c is None:
        return default
    return [c] if isinstance(c, str) else list(c)


def _render_argv(template: list, prompt: str, session_id: str | None) -> list[str]:
    """custom 模板渲染: {prompt}/{session} 占位。
    无 session 时丢弃 {session} 参数本身;若其前一个参数是旗标(以 - 开头)则一并丢弃。"""
    out = []
    for part in template:
        part = str(part)
        if "{session}" in part:
            if session_id is None:
                if out and out[-1].startswith("-"):
                    out.pop()
                continue
            part = part.replace("{session}", session_id)
        out.append(part.replace("{prompt}", prompt))
    return out
