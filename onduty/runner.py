"""任务执行: 渲染 prompt → 适配层建命令 → 子进程(超时杀进程树) → 回写状态 → 通知(主方案 §8)。"""
from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime

from .adapters import resolve as resolve_adapter
from .config import PREV_MAX
from .notify import notify

CREATE_NO_WINDOW = 0x08000000

# state.json 里保留上一次最终输出的长度上限(供 {{prev.output}} 与排障)
STATE_OUTPUT_MAX = 8000


@dataclass
class RunResult:
    job: str
    agent: str
    status: str  # success | failed | timeout | error
    trigger: str
    exit_code: int | None
    duration_s: float
    output: str = ""
    session_id: str | None = None
    log_path: str = ""


def render_prompt(job: dict, prev_output: str, base: str) -> str:
    """拼最终提示词: prompt_file 相对 tasks.yaml 所在目录; {{prev.output}} 截断注入。"""
    if job.get("prompt"):
        text = str(job["prompt"])
    else:
        p = str(job["prompt_file"])
        p = p if os.path.isabs(p) else os.path.join(base, p)
        with open(p, encoding="utf-8") as f:
            text = f.read()
    if "{{prev.output}}" in text:
        text = text.replace("{{prev.output}}", (prev_output or "")[:PREV_MAX])
    return text


def _kill_tree(proc) -> None:
    """Windows 上杀整棵进程树(agent CLI 多为 node 父+子)。"""
    if os.name == "nt":
        try:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True, timeout=20, creationflags=CREATE_NO_WINDOW)
            return
        except Exception:
            pass
    proc.kill()


def _resolve_run_workdir(cfg: dict, state, job: dict, started: datetime, log_path: str) -> str:
    """v0.2: auto_git_worktree 开启且 workdir 在 git 仓库内 → 建独立 worktree 跑(主目录零污染)。
    失败(非 git 仓库/git 不可用)回退原 workdir 并记日志。"""
    if not cfg.get("auto_git_worktree"):
        return job["workdir"]
    wd = job["workdir"]
    try:
        chk = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=wd,
                             capture_output=True, text=True, timeout=20, creationflags=CREATE_NO_WINDOW)
        if chk.returncode != 0 or "true" not in (chk.stdout or ""):
            _write_log(log_path, "", f"[worktree] {wd} 非 git 仓库,回退原目录运行", None, 0.0)
            return wd
        ts = started.strftime("%Y%m%d-%H%M%S")
        wt = os.path.join(state.root, "worktrees", f"{job['name']}-{ts}")
        os.makedirs(os.path.dirname(wt), exist_ok=True)
        mk = subprocess.run(["git", "worktree", "add", "--detach", wt, "HEAD"], cwd=wd,
                            capture_output=True, text=True, timeout=60, creationflags=CREATE_NO_WINDOW)
        if mk.returncode != 0:
            _write_log(log_path, "", f"[worktree] 建 worktree 失败,回退原目录: {mk.stderr}", None, 0.0)
            return wd
        _write_log(log_path, "", f"[worktree] 隔离执行于 {wt}(run 后由用户 git worktree remove 清理)", None, 0.0)
        return wt
    except Exception as e:
        _write_log(log_path, "", f"[worktree] 异常回退原目录: {e!r}", None, 0.0)
        return wd


def run_job(cfg: dict, state, job: dict, trigger: str = "manual", prev_output: str = "",
            session_source: str | None = None) -> RunResult:
    """跑一个任务(阻塞)。失败不抛出: 以 status 表达,并照常通知与落盘。
    session_source: after 接力传入的上游 job 名——mode:continue 优先续接其会话。"""
    started = datetime.now()
    t0 = time.monotonic()
    adapter = cfg["adapters"].get(job["agent"]) or resolve_adapter(job["agent"], cfg["agents"])
    agent_cfg = cfg["agents"].get(job["agent"], {})

    session_id = None
    if job["mode"] == "continue":
        # 续接优先级: after 上游 job 的会话(接力语义) > 自己的历史会话(独立续聊)
        if session_source:
            session_id = state.job(session_source).get("session_id")
        if not session_id:
            session_id = state.job(job["name"]).get("session_id")
    log_path = state.new_log_path(job["name"], started)
    try:
        prompt = render_prompt(job, prev_output, cfg["base"])
        argv = adapter.build(job, agent_cfg, prompt, session_id or None)
    except Exception as e:
        _write_log(log_path, f"构建命令失败: {e!r}", "", None, 0.0, str(e))
        return _finish(cfg, state, job, trigger, "error", None, "", t0, log_path, started)

    env = dict(os.environ)
    env.update(adapter.env(job, agent_cfg))
    # 任意 agent 可在 tasks.yaml agents.<name>.env 追加环境变量(认证材料等由用户自带)
    env.update({str(k): str(v) for k, v in (agent_cfg.get("env") or {}).items()})
    run_wd = _resolve_run_workdir(cfg, state, job, started, log_path)
    os.makedirs(run_wd, exist_ok=True)

    timed_out = False
    rc: int | None
    out = err = ""
    with open(log_path, "w", encoding="utf-8") as log:
        log.write(f"# job={job['name']} agent={job['agent']} mode={job['mode']} trigger={trigger}\n")
        log.write(f"# start={started.isoformat(timespec='seconds')} cwd={run_wd}\n")
        log.write(f"# argv={argv!r}\n# ---------- prompt(渲染后) ----------\n{prompt}\n# ====================================\n")
        try:
            proc = subprocess.Popen(argv, cwd=run_wd,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, encoding="utf-8", errors="replace",
                                    env=env, creationflags=CREATE_NO_WINDOW)
            try:
                out, err = proc.communicate(timeout=job["timeout_minutes"] * 60)
                rc = proc.returncode
            except subprocess.TimeoutExpired:
                timed_out = True
                _kill_tree(proc)
                out, err = proc.communicate()
                rc = None
        except FileNotFoundError as e:
            out = ""
            err = f"启动失败, 找不到命令: {e}"
            rc = None
        except Exception as e:  # 兜底: 子进程异常不外抛
            out = ""
            err = f"执行异常: {e!r}"
            rc = None

    try:
        sid, output = adapter.parse(out or "")
    except Exception:
        sid, output = None, (out or "").strip()

    _write_log(log_path, out or "", err or "", rc, time.monotonic() - t0,
               "" if sid is None else f"session_id={sid}",
               final=output, header=f"# ---------- stdout/stderr 见上文件头部 ----------")
    status = "success" if rc == 0 and not timed_out else ("timeout" if timed_out else "failed")
    if rc is None and not timed_out:
        status = "error"
    if status == "success" and not output.strip():
        # 部分 CLI 认证失败仍退出 0(codebuddy 实测) → 空产出判 failed,防接力链误判
        status = "failed"
        err = (err + "\n[onduty] 退出码 0 但无任何输出,判定 failed(常见原因:未登录/认证过期)").strip()
    if sid:
        state.update_job(job["name"], session_id=sid)
    return _finish(cfg, state, job, trigger, status, rc, output, t0, log_path, started)


def _write_log(path, out, err, rc, duration, extra="", final="", header=""):
    with open(path, "a", encoding="utf-8") as log:
        if header:
            log.write(header + "\n")
        log.write(f"# exit={rc} duration={duration:.1f}s\n{extra}\n")
        log.write(f"--- stdout ---\n{out}\n--- stderr ---\n{err}\n")
        if final:
            log.write(f"--- final(解析后) ---\n{final}\n")


def _finish(cfg, state, job, trigger, status, rc, output, t0, log_path, started) -> RunResult:
    duration = time.monotonic() - t0
    old = state.job(job["name"])
    state.update_job(job["name"],
                     last_run_at=started.isoformat(timespec="seconds"),
                     last_status=status, last_exit=rc, last_log=log_path,
                     last_output=output[:STATE_OUTPUT_MAX],
                     run_count=int(old.get("run_count", 0)) + 1)
    state.append_run({"ts": started.isoformat(timespec="seconds"), "job": job["name"],
                      "agent": job["agent"], "mode": job["mode"], "trigger": trigger,
                      "status": status, "exit_code": rc, "duration_s": round(duration, 1),
                      "log": log_path, "session_id": state.job(job["name"]).get("session_id")})
    try:
        notify(cfg, job, status, output)
    except Exception as e:  # 通知异常绝不影响任务结果与 daemon 存活
        print(f"[notify] 异常(忽略): {e!r}", flush=True)
    return RunResult(job["name"], job["agent"], status, trigger, rc, duration,
                     output, state.job(job["name"]).get("session_id"), log_path)
