"""tasks.yaml 加载与 fail-fast 校验(主方案 §7 安全模型、§8 配置约束;flag 依据 plans/001)。"""
from __future__ import annotations

import os

import yaml
from croniter import croniter

from .adapters import resolve as resolve_adapter


class ConfigError(Exception):
    """配置错误: 校验不通过直接拒绝,不静默降级。"""


VALID_MODES = {"new", "continue"}
VALID_TRIGGERS = {"cron", "once_at", "after", "manual"}
VALID_NOTIFY = {"log", "toast", "webhook"}
TEMPLATE_KEYS = {"prev.output"}
PREV_MAX = 4000  # {{prev.output}} 截断长度(主方案 §5)


def _norm(p: str, base: str) -> str:
    """绝对化 + 去冗余(保留原始大小写,用于存储/执行)。"""
    full = p if os.path.isabs(p) else os.path.join(base, p)
    return os.path.normpath(full)


def _key(p: str) -> str:
    """用于白名单包含比较(Windows 大小写不敏感)。"""
    return os.path.normcase(p)


def _under_roots(path: str, roots: list[str]) -> bool:
    npath, nroots = _key(path), [_key(r) for r in roots]
    return any(npath == r or npath.startswith(r + os.sep) for r in nroots)


def _check_templates(job_name: str, text: str) -> set:
    found = set()
    i = text.find("{{")
    while i >= 0:
        j = text.find("}}", i)
        if j < 0:
            raise ConfigError(f"job {job_name}: 模板 {{{{ 未闭合")
        found.add(text[i + 2:j].strip())
        i = text.find("{{", j)
    unknown = sorted({k for k in found if k not in TEMPLATE_KEYS})
    if unknown:
        raise ConfigError(f"job {job_name}: 不支持的模板位 {unknown}, v0.1 仅支持 {sorted(TEMPLATE_KEYS)}")
    return found


def _job_prompt_text(j: dict, base: str) -> str:
    if j.get("prompt"):
        return str(j["prompt"])
    p = _norm(str(j["prompt_file"]), base)
    with open(p, encoding="utf-8") as f:
        return f.read()


def _validate_job(j: dict, cfg: dict, base: str, adapters: dict, names: set) -> dict:
    if not isinstance(j, dict):
        raise ConfigError(f"job 必须是映射: {j!r}")
    name = j.get("name")
    if not name or not isinstance(name, str):
        raise ConfigError(f"job 缺少 name: {j!r}")
    agent = j.get("agent")
    if not agent or not isinstance(agent, str):
        raise ConfigError(f"job {name}: agent 必填")
    if agent not in adapters:
        adapters[agent] = resolve_adapter(agent, cfg["agents"])
    ad = adapters[agent]
    if not ad.capable:
        raise ConfigError(
            f"job {name}: agent '{agent}' 无法接入(未注册,或 v0.1 无头能力未证实,见 plans/001 §3);"
            f" 可在 tasks.yaml 配 agents.{agent}: {{type: custom, command: [..., \"{{prompt}}\", ...]}}")

    defaults = cfg["defaults"]
    out = {
        "name": name,
        "agent": agent,
        "model": j.get("model"),
        "mode": j.get("mode", "new"),
        "allow_danger": bool(j.get("allow_danger", defaults.get("allow_danger", False))),
        "timeout_minutes": float(j.get("timeout_minutes", defaults.get("timeout_minutes", 30))),
        "notify": list(j.get("notify", defaults.get("notify", ["log", "toast"]))),
        "catchup": bool(j.get("catchup", defaults.get("catchup", False))),
    }
    if out["mode"] not in VALID_MODES:
        raise ConfigError(f"job {name}: mode 必须是 {sorted(VALID_MODES)}")
    if out["mode"] == "continue" and not ad.supports_resume:
        raise ConfigError(f"job {name}: agent '{agent}' 不支持会话续接(plans/001),mode 不能为 continue")
    if out["model"] and not ad.model_flagged:
        raise ConfigError(f"job {name}: agent '{agent}' 未配置 model_flag,无法命令行指定模型(主方案 §5 模型参数经适配层) ")
    bad = [c for c in out["notify"] if c not in VALID_NOTIFY]
    if bad:
        raise ConfigError(f"job {name}: 未知通知渠道 {bad}, 可用 {sorted(VALID_NOTIFY)}")

    wd = j.get("workdir")
    if not wd:
        raise ConfigError(f"job {name}: workdir 必填(强制隔离,主方案 §7)")
    wd_norm = _norm(str(wd), base)
    if not _under_roots(wd_norm, cfg["allow_roots"]):
        raise ConfigError(f"job {name}: workdir '{wd}' 不在 safety.allow_roots 白名单内(强制隔离,主方案 §7)")
    out["workdir"] = wd_norm

    prompt, prompt_file = j.get("prompt"), j.get("prompt_file")
    if bool(prompt) == bool(prompt_file):
        raise ConfigError(f"job {name}: prompt 与 prompt_file 二选一(必填其一)")
    if prompt_file and not os.path.isfile(_norm(str(prompt_file), base)):
        raise ConfigError(f"job {name}: prompt_file 不存在: {prompt_file}")
    out["prompt"] = prompt
    out["prompt_file"] = prompt_file

    sched = j.get("schedule") or {}
    if isinstance(sched, dict) and True in sched:
        # YAML 1.1 把裸 on: 键解析为 True,兼容归一化为 "on"
        sched = dict(sched)
        sched.setdefault("on", str(sched.pop(True)))
    if not isinstance(sched, dict):
        raise ConfigError(f"job {name}: schedule 必须是映射")
    kinds = [k for k in sched if k in VALID_TRIGGERS]
    if len(kinds) > 1:
        raise ConfigError(f"job {name}: schedule 四选一,不能同时有 {kinds}")
    unknown = [k for k in sched if k not in VALID_TRIGGERS and k != "on"]
    if unknown:
        raise ConfigError(f"job {name}: schedule 未知字段 {unknown}")
    kind = kinds[0] if kinds else "manual"
    cron_expr = after = None
    if kind == "cron":
        cron_expr = str(sched["cron"])
        if not croniter.is_valid(cron_expr):
            raise ConfigError(f"job {name}: cron 表达式非法: {cron_expr}")
    elif kind == "once_at":
        raise ConfigError(f"job {name}: once_at 是 v0.2 功能(主方案 §11),v0.1 不可用")
    elif kind == "after":
        after = str(sched["after"])
        if after == name:
            raise ConfigError(f"job {name}: after 不能指向自身")
        if str(sched.get("on", "success")) not in {"success", "always"}:
            raise ConfigError(f"job {name}: schedule.on 只能是 success/always")
    out["schedule"] = {"kind": kind, "cron": cron_expr, "after": after, "on": str(sched.get("on", "success"))}

    used = _check_templates(name, _job_prompt_text(j, base))
    if "prev.output" in used and kind != "after":
        raise ConfigError(f"job {name}: 用了 {{{{prev.output}}}} 但 schedule 不是 after(v0.1 模板仅链式可用)")
    return out


def load_config(path: str) -> dict:
    """加载并校验 tasks.yaml,返回规范化 cfg(含 adapters)。失败抛 ConfigError。"""
    path = os.path.abspath(path)
    base = os.path.dirname(path)
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    if not isinstance(raw, dict):
        raise ConfigError("tasks.yaml 顶层必须是映射")

    cfg = {
        "base": base,
        "path": path,
        "defaults": raw.get("defaults") or {},
        "notify": raw.get("notify") or {},
        "scheduler": raw.get("scheduler") or {},
        "agents": {k: (v or {}) for k, v in (raw.get("agents") or {}).items()},
    }
    safety = raw.get("safety") or {}
    roots = safety.get("allow_roots")
    if not roots or not isinstance(roots, list):
        raise ConfigError("safety.allow_roots 必填(强制隔离目录,主方案 §7)")
    cfg["allow_roots"] = [_norm(str(r), base) for r in roots]
    if bool(safety.get("auto_git_worktree", False)):
        raise ConfigError("auto_git_worktree 是 v0.2 功能(主方案 §11),v0.1 不可用")

    raw_jobs = raw.get("jobs")
    if not raw_jobs or not isinstance(raw_jobs, list):
        raise ConfigError("jobs 必填且非空")
    names = [j.get("name") if isinstance(j, dict) else None for j in raw_jobs]
    if any(not n for n in names):
        raise ConfigError("每个 job 必须有 name")
    if len(set(names)) != len(names):
        raise ConfigError("job name 不能重复")

    adapters: dict = {}
    jobs = [_validate_job(j, cfg, base, adapters, set(names)) for j in raw_jobs]
    by_after = {j["name"]: j["schedule"]["after"] for j in jobs}
    for start in by_after:
        cur, seen = start, set()
        while cur:
            if cur in seen:
                raise ConfigError(f"after 链存在环: {start}")
            seen.add(cur)
            cur = by_after.get(cur)
    for j in jobs:
        a = j["schedule"]["after"]
        if a and a not in by_after:
            raise ConfigError(f"job {j['name']}: after 指向不存在的 job '{a}'")
    cfg["adapters"] = adapters
    cfg["jobs"] = jobs
    return cfg
