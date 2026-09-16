"""daemon 主循环(主方案 §6): 每 tick 对账 → 控制文件(manual)/cron 到期 → 执行 → after 链。
v0.1 全局串行(一次只跑一个任务),状态全部落盘。"""
from __future__ import annotations

import os
import subprocess
import time
import traceback
from datetime import datetime, timedelta

from croniter import croniter

from . import runner
from .config import ConfigError, load_config
from .state import StateStore

DEFAULT_TICK = 30


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


def run_chain(cfg: dict, state: StateStore, job: dict, trigger: str = "manual", prev_output: str = "") -> runner.RunResult:
    """执行 job,成功后(或 on:always)触发 after 依赖。v0.1 串行,链深度天然有界(配置校验防环)。"""
    res = runner.run_job(cfg, state, job, trigger, prev_output)
    _dlog(state, f"run {job['name']} [{trigger}] -> {res.status} (exit={res.exit_code}, {res.duration_s:.0f}s)")
    for dep in cfg["jobs"]:
        s = dep["schedule"]
        if s["kind"] == "after" and s["after"] == job["name"]:
            if (s["on"] == "success" and res.status == "success") or s["on"] == "always":
                run_chain(cfg, state, dep, "after", res.output)
    return res


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
        run_chain(cfg, state, job, "manual")


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
                # 补跑: 从上次运行时刻起算,错过的第一个到点立即执行(主方案 §6)
                due = datetime.fromisoformat(croniter(expr, datetime.fromisoformat(last_s)).get_next(datetime).isoformat())
                trigger = "catchup"
            else:
                due = datetime.fromisoformat(croniter(expr, now).get_next(datetime).isoformat())
                state.update_job(job["name"], next_due=due.isoformat(timespec="seconds"))
                continue
        else:
            due = datetime.fromisoformat(due_s)
        if due <= now:
            run_chain(cfg, state, job, trigger)
            nxt = datetime.fromisoformat(croniter(expr, datetime.now()).get_next(datetime).isoformat())
            state.update_job(job["name"], next_due=nxt.isoformat(timespec="seconds"))


def daemon(tasks_path: str, tick_seconds: int | None = None) -> int:
    root = os.path.dirname(os.path.abspath(tasks_path))
    state = StateStore(os.path.join(root, "state"))
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
    _dlog(state, f"daemon 启动 pid={os.getpid()} tasks={tasks_path}")
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
