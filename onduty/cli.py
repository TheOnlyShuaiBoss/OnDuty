"""onduty 单命令入口: daemon / once / check / list / status / run / logs。"""
from __future__ import annotations

import argparse
import os
import sys

from . import scheduler
from .config import ConfigError, load_config
from .state import StateStore


def _load(config_path: str):
    if not os.path.isfile(config_path):
        hint = (f"未找到配置文件: {os.path.abspath(config_path)}\n"
                f"  首次使用: copy tasks.example.yaml tasks.yaml(或 cp),然后编辑 allow_roots 与 jobs\n"
                "  字段说明: docs/MANUAL.md §4;校验通过后先 `onduty check` 预览,再 `onduty once <job>` 试跑")
        raise SystemExit(_print_and_code(hint, 2))
    try:
        cfg = load_config(config_path)
    except ConfigError as e:
        raise SystemExit(_print_and_code(f"配置不合法: {e}", 2))
    state = StateStore(os.path.join(cfg["base"], "state"))
    return cfg, state


def _print_and_code(msg: str, code: int) -> int:
    print(msg)
    return code


def _daemon_pid(state: StateStore) -> int | None:
    pid_file = os.path.join(state.root, "daemon.pid")
    if not os.path.isfile(pid_file):
        return None
    try:
        pid = int(open(pid_file, encoding="ascii").read().strip())
    except ValueError:
        return None
    return pid if scheduler.pid_alive(pid) else None


# ---------- 子命令 ----------

def cmd_daemon(args) -> int:
    if not os.path.isfile(args.config):
        print(f"未找到配置文件: {os.path.abspath(args.config)}\n"
              "  首次使用: copy tasks.example.yaml tasks.yaml(或 cp),再编辑 allow_roots 与 jobs")
        return 2
    return scheduler.daemon(args.config, tick_seconds=args.tick)


def cmd_once(args) -> int:
    cfg, state = _load(args.config)
    job = next((j for j in cfg["jobs"] if j["name"] == args.job), None)
    if job is None:
        print(f"job 不存在: {args.job}")
        return 2
    res = scheduler.run_chain(cfg, state, job, "manual")
    print(f"[once] {res.job} -> {res.status} (exit={res.exit_code}, log={res.log_path})")
    return 0 if res.status == "success" else 1


def cmd_check(args) -> int:
    cfg, state = _load(args.config)
    print(f"配置 OK: {len(cfg['jobs'])} 个 job, allow_roots={cfg['allow_roots']}")
    for j in cfg["jobs"]:
        ad = cfg["adapters"][j["agent"]]
        agent_cfg = cfg["agents"].get(j["agent"], {})
        s = j["schedule"]
        desc = s["cron"] if s["kind"] == "cron" else (s["after"] if s["kind"] == "after" else s["kind"])
        try:
            demo_session = "SESSION-DEMO" if (ad.supports_resume and j["mode"] == "continue") else None
            argv = ad.build(j, agent_cfg, "<PROMPT>", demo_session)
        except Exception as e:
            print(f"  {j['name']:<22} [{j['agent']}/{j['mode']}/{desc}] 建令失败: {e}")
            continue
        shown = [a if len(str(a)) < 40 else str(a)[:37] + "..." for a in argv]
        print(f"  {j['name']:<22} [{j['agent']}/{j['mode']}/{desc}] {shown}")
    return 0


def cmd_list(args) -> int:
    cfg, state = _load(args.config)
    print(f"{'JOB':<22} {'AGENT':<12} {'MODE':<9} {'SCHEDULE':<26} {'LAST':<8} NEXT_DUE")
    for j in cfg["jobs"]:
        s = j["schedule"]
        desc = s["cron"] if s["kind"] == "cron" else (f"after:{s['after']}({s['on']})" if s["kind"] == "after" else s["kind"])
        st = state.job(j["name"])
        print(f"{j['name']:<22} {j['agent']:<12} {j['mode']:<9} {desc:<26} {st.get('last_status', '-'):<8} {st.get('next_due', '-')}")
    return 0


def cmd_status(args) -> int:
    cfg, state = _load(args.config)
    pid = _daemon_pid(state)
    print(f"daemon: {'运行中 pid=' + str(pid) if pid else '未运行'}")
    print(f"jobs: {len(cfg['jobs'])}, state 目录: {state.root}")
    for j in cfg["jobs"]:
        st = state.job(j["name"])
        print(f"  {j['name']}: runs={st.get('run_count', 0)} last={st.get('last_run_at', '-')} "
              f"status={st.get('last_status', '-')} session={st.get('session_id', '-')} "
              f"log={st.get('last_log', '-')}")
    return 0


def cmd_run(args) -> int:
    cfg, state = _load(args.config)
    job = next((j for j in cfg["jobs"] if j["name"] == args.job), None)
    if job is None:
        print(f"job 不存在: {args.job}")
        return 2
    if args.inline:
        res = scheduler.run_chain(cfg, state, job, "manual")
        print(f"[run --inline] {res.job} -> {res.status}")
        return 0 if res.status == "success" else 1
    pid = _daemon_pid(state)
    if pid is None:
        print("daemon 未运行: 先 `onduty daemon`,或加 --inline 直接跑")
        return 2
    marker = os.path.join(state.root, "ctl", f"run__{args.job}.marker")
    with open(marker, "w", encoding="utf-8") as f:
        f.write("queued\n")
    print(f"已排队 {args.job},daemon(pid={pid})将在下个 tick 拾取")
    return 0


def cmd_logs(args) -> int:
    cfg, state = _load(args.config)
    st = state.job(args.job)
    log = st.get("last_log")
    if not log or not os.path.isfile(log):
        print(f"job {args.job} 尚无日志")
        return 2
    with open(log, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    sys.stdout.write("".join(lines[-args.tail:]))
    return 0


def main(argv: list[str] | None = None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", default="tasks.yaml", help="tasks.yaml 路径(默认:当前目录)")
    p = argparse.ArgumentParser(prog="onduty",
                                description="让 agent 替你值班 —— 多 agent 定时/接力任务守护进程")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("daemon", parents=[common], help="前台启动守护进程(Ctrl+C 退出)")
    d.add_argument("--tick", type=int, default=None, help="对账秒数,默认 30")
    o = sub.add_parser("once", parents=[common], help="不等 daemon,直接跑一个 job(含 after 链)")
    o.add_argument("job")
    sub.add_parser("check", parents=[common], help="校验配置并预览各 job 最终命令行")
    sub.add_parser("list", parents=[common], help="列出全部 job 与调度")
    sub.add_parser("status", parents=[common], help="daemon 存活与各 job 状态")
    r = sub.add_parser("run", parents=[common], help="排队让 daemon 执行一个 job")
    r.add_argument("job")
    r.add_argument("--inline", action="store_true", help="不等 daemon,当前进程直接跑")
    l = sub.add_parser("logs", parents=[common], help="打印某 job 最近一次运行日志尾部")
    l.add_argument("job")
    l.add_argument("-n", "--tail", type=int, default=50)
    args = p.parse_args(argv)
    handlers = {"daemon": cmd_daemon, "once": cmd_once, "check": cmd_check, "list": cmd_list,
                "status": cmd_status, "run": cmd_run, "logs": cmd_logs}
    try:
        return handlers[args.cmd](args)
    except ConfigError as e:
        print(f"配置不合法: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
