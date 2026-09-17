"""daemon 主循环(主方案 §6 + v0.2 并发/once_at/重试):
每 tick 对账 → 控制文件(manual)/cron 到期/once_at 到点/重试到点 → 派发执行 → after 链。
v0.2 并发模型: 每 workdir 一把 RLock(同线程链式重入安全);不同 workdir 由工作线程并行;
主循环只负责派发,不阻塞在任务上。状态全部落盘。"""
from __future__ import annotations

import os
import subprocess
import threading
import time
import traceback
from datetime import datetime, timedelta

from croniter import croniter

from . import runner
from .config import ConfigError, load_config
from .state import StateStore

DEFAULT_TICK = 30

# ---- v0.2: workdir 锁与在飞任务注册表(进程内) ----
_locks: dict[str, threading.RLock] = {}
_locks_mu = threading.Lock()
_inflight: set[str] = set()          # 正在执行的 job 名
_inflight_mu = threading.Lock()
_retry_q: list[dict] = []            # {job, not_before(datetime), attempt(int)}
_retry_mu = threading.Lock()


def _dlog(state: StateStore, msg: str) -> None:
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line, flush=True)
    with open(os.path.join(state.root, "daemon.log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def pid_alive(pid: int) -> bool:
    try:
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                           capture_output=True, text=True, timeout=15)
        return str(pid) in (r.stdout or "")
    except Exception:
        return False


def _wd_lock(workdir: str) -> threading.RLock:
    key = os.path.normcase(workdir)
    with _locks_mu:
        if key not in _locks:
            _locks[key] = threading.RLock()
        return _locks[key]


def run_chain(cfg: dict, state: StateStore, job: dict, trigger: str = "manual", prev_output: str = "",
              session_source: str | None = None) -> runner.RunResult:
    """执行 job(持本 workdir 锁),成功后(或 on:always)触发 after 依赖(链在同线程,RLock 可重入)。"""
    with _wd_lock(job["workdir"]):
        res = runner.run_job(cfg, state, job, trigger, prev_output, session_source=session_source)
    _dlog(state, f"run {job['name']} [{trigger}] -> {res.status} (exit={res.exit_code}, {res.duration_s:.0f}s)")
    if res.status in ("failed", "timeout", "error"):
        _maybe_retry(state, job)
    elif res.status == "success" and state.job(job["name"]).get("retry_attempt"):
        state.update_job(job["name"], retry_attempt=0)  # 成功后清零重试计数
    for dep in cfg["jobs"]:
        s = dep["schedule"]
        if s["kind"] == "after" and s["after"] == job["name"]:
            if (s["on"] == "success" and res.status == "success") or s["on"] == "always":
                run_chain(cfg, state, dep, "after", res.output, session_source=job["name"])
    return res


def _maybe_retry(state: StateStore, job: dict) -> None:
    """失败任务按 retry 配置排重试;达上限记 exhausted。重试不携带链(防连锁重试)。"""
    rmax = int(job.get("retry", {}).get("max", 0))
    if rmax <= 0:
        return
    st = state.job(job["name"])
    attempt = int(st.get("retry_attempt", 0)) + 1
    if attempt > rmax:
        _dlog(state, f"job {job['name']} 重试已达上限({rmax}),放弃")
        state.update_job(job["name"], retry_attempt=0)
        return
    bo = float(job["retry"].get("backoff_minutes", 5))
    nb = datetime.now() + timedelta(minutes=bo)
    state.update_job(job["name"], retry_attempt=attempt)
    with _retry_mu:
        _retry_q.append({"job": job, "not_before": nb, "attempt": attempt})
    _dlog(state, f"job {job['name']} 失败,第 {attempt}/{rmax} 次重试排期 {nb.isoformat(timespec='seconds')}")


def _dispatch(cfg: dict, state: StateStore, job: dict, trigger: str,
              prev_output: str = "", session_source: str | None = None) -> bool:
    """派发到工作线程;同名在飞则跳过(防并发重入同一 job)。返回是否已派发。"""
    with _inflight_mu:
        if job["name"] in _inflight:
            return False
        _inflight.add(job["name"])

    def _work():
        try:
            run_chain(cfg, state, job, trigger, prev_output, session_source)
        except Exception:
            _dlog(state, f"job {job['name']} 执行异常:\n{traceback.format_exc()}")
        finally:
            with _inflight_mu:
                _inflight.discard(job["name"])

    threading.Thread(target=_work, daemon=True, name=f"onduty-{job['name']}").start()
    return True


def _handle_markers(cfg: dict, state: StateStore) -> None:
    ctl = os.path.join(state.root, "ctl")
    by_name = {j["name"]: j for j in cfg["jobs"]}
    for fn in sorted(os.listdir(ctl)):
        if not (fn.startswith("run__") and fn.endswith(".marker")):
            continue
        job_name = fn[len("run__"):-len(".marker")]
        os.remove(os.path.join(ctl, fn))
        job = by_name.get(job_name)
        if job is None:
            _dlog(state, f"控制文件引用未知 job: {job_name}")
            continue
        _dlog(state, f"手动触发: {job_name}")
        _dispatch(cfg, state, job, "manual")


def _cron_tick(cfg: dict, state: StateStore) -> None:
    now = datetime.now()
    for job in cfg["jobs"]:
        s = job["schedule"]
        if s["kind"] != "cron":
            continue
        st = state.job(job["name"])
        expr = s["cron"]
        due_s = st.get("next_due")
        trigger = "cron"
        if not due_s:
            last_s = st.get("last_run_at")
            if job["catchup"] and last_s:
                due = datetime.fromisoformat(croniter(expr, datetime.fromisoformat(last_s)).get_next(datetime).isoformat())
                trigger = "catchup"
            else:
                due = datetime.fromisoformat(croniter(expr, now).get_next(datetime).isoformat())
                state.update_job(job["name"], next_due=due.isoformat(timespec="seconds"))
                continue
        else:
            due = datetime.fromisoformat(due_s)
        if due <= now:
            if _dispatch(cfg, state, job, trigger):
                nxt = datetime.fromisoformat(croniter(expr, datetime.now()).get_next(datetime).isoformat())
                state.update_job(job["name"], next_due=nxt.isoformat(timespec="seconds"))


def _once_tick(cfg: dict, state: StateStore) -> None:
    """v0.2: once_at 一次性定时,到点派发一次并归档(once_fired)。"""
    now = datetime.now()
    for job in cfg["jobs"]:
        s = job["schedule"]
        if s["kind"] != "once_at" or not s.get("once_at"):
            continue
        st = state.job(job["name"])
        if st.get("once_fired"):
            continue
        at = datetime.fromisoformat(s["once_at"])
        if at <= now:
            if _dispatch(cfg, state, job, "once_at"):
                state.update_job(job["name"], once_fired=datetime.now().isoformat(timespec="seconds"))
                _dlog(state, f"once_at 触发: {job['name']}")


def _retry_tick(cfg: dict, state: StateStore) -> None:
    """v0.2: 到点重试。重试成功会清 retry_attempt(见 run_chain 成功路径通过 _clear_retry)。"""
    now = datetime.now()
    due: list[dict] = []
    with _retry_mu:
        rest = []
        for item in _retry_q:
            if item["not_before"] <= now:
                due.append(item)
            else:
                rest.append(item)
        _retry_q[:] = rest
    for item in due:
        _dlog(state, f"重试触发: {item['job']['name']} 第 {item['attempt']} 次")
        _dispatch(cfg, state, item["job"], "retry")


def daemon(tasks_path: str, tick_seconds: int | None = None) -> int:
    root = os.path.dirname(os.path.abspath(tasks_path))
    # 先解析一次拿 state_dir(v0.2 可覆盖);失败则按默认目录,配置错误在循环内再报
    try:
        _pre = load_config(tasks_path)
        state_root = _pre.get("state_dir") or os.path.join(root, "state")
    except Exception:
        state_root = os.path.join(root, "state")
    state = StateStore(state_root)
    pid_file = os.path.join(state.root, "daemon.pid")
    if os.path.isfile(pid_file):
        try:
            old = int(open(pid_file, encoding="ascii").read().strip())
            if pid_alive(old):
                print(f"onduty daemon 已在运行 (pid={old}); 先停掉它或用 `onduty status`", flush=True)
                return 1
        except ValueError:
            pass
    with open(pid_file, "w", encoding="ascii") as f:
        f.write(str(os.getpid()))
    cfg = None
    _dlog(state, f"daemon 启动 pid={os.getpid()} tasks={tasks_path} state={state.root}")
    try:
        while True:
            try:
                cfg = load_config(tasks_path)
            except ConfigError as e:
                _dlog(state, f"配置校验失败: {e}" + (", 沿用上一份配置" if cfg else ""))
                if cfg is None:
                    return 2
            except Exception:
                _dlog(state, "配置加载异常:\n" + traceback.format_exc())
                if cfg is None:
                    return 2
            try:
                _handle_markers(cfg, state)
                _cron_tick(cfg, state)
                _once_tick(cfg, state)
                _retry_tick(cfg, state)
            except Exception:
                _dlog(state, "tick 异常(继续运行):\n" + traceback.format_exc())
            tick = tick_seconds or int((cfg.get("scheduler") or {}).get("tick_seconds", DEFAULT_TICK))
            time.sleep(max(2, tick))
    except KeyboardInterrupt:
        _dlog(state, "收到 Ctrl+C, 退出")
        return 0
    finally:
        try:
            os.remove(pid_file)
        except OSError:
            pass
