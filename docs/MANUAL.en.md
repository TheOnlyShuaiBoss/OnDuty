# onduty Manual (English)

> Send your coding agents on shift — a local daemon that runs multi-agent CLI tasks on schedule or as a relay chain.
> v0.1, Windows-first (cross-platform code runs, macOS/Linux notification paths untested). 中文版见 [MANUAL.md](MANUAL.md)。

## 1. Core concepts

A **job** is a declarative task: which agent, which working directory, which prompt, when to trigger. A **daemon** ticks (default 30 s) and checks for due cron jobs and queued manual runs. Triggers are four-in-one: `cron` (schedule) / `once_at` (v0.2) / `after` (relay on previous job completion) / manual. Chains form a DAG checked at config load. Each agent is a tiny **adapter** (argv building + session-id extraction); anything else plugs in via the **custom** template adapter. All state is persisted (`state.json`, `runs.jsonl`, per-run logs).

Workflow: write `tasks.yaml` → `onduty check` → `onduty daemon` → results arrive as toasts / webhook pings.

## 2. Install

Python ≥ 3.10; only two deps (PyYAML, croniter).

```bash
git clone git@github.com:<you>/onduty.git && cd onduty
pip install -e .
onduty --help
```

## 3. Quick start

```yaml
safety:
  allow_roots: [sandbox]          # mandatory isolation whitelist
jobs:
  - name: fix_tests
    agent: codebuddy              # dsh / codebuddy / workbuddy / custom
    workdir: sandbox/proj
    prompt: Run the tests, write failures to report.md
    allow_danger: true            # needed for headless file writes (see §8)

  - name: followup
    agent: codebuddy
    mode: continue                # resume the same session via --resume
    workdir: sandbox/proj
    prompt: |
      Previous result:
      {{prev.output}}
      Fix the first failure.
    schedule: { after: fix_tests, on: success }

  - name: daily_review
    agent: dsh
    workdir: sandbox/daily
    prompt: Summarize yesterday's changes into changelog_draft.md
    schedule: { cron: "0 8 * * *" }
```

```bash
onduty check            # validate + preview final argv per job
onduty once fix_tests   # run now (foreground), including the after-chain
onduty daemon           # go on shift: cron + queued runs
onduty status / list / run <job> / logs <job> -n 30
```

## 4. Triggers

- **cron** — standard 5-field expression, local timezone. `catchup: true` runs one missed occurrence after a daemon restart.
- **after** — dependent job fires immediately when the target succeeds (`on: success`, default) or regardless (`on: always`); the target's final text is available as `{{prev.output}}`. Cycles are rejected at load.
- **manual** — no `schedule`, or `onduty run <job>` (marker file picked up on next tick; `--inline` bypasses the daemon).
- **once_at** — planned for v0.2; rejected by config now.

## 5. Context passing

| Mechanism | How | Works with |
|---|---|---|
| `{{prev.output}}` | previous chained job's final text, truncated to 4000 chars | any agent |
| `mode: continue` | stored `session_id` passed through the adapter's resume flag | codebuddy / custom templates containing `{session}` |

DSH has **no** headless resume (upstream limitation) — use `new` + text injection.

## 6. Adapters

| agent | headless | resume | notes |
|---|---|---|---|
| `dsh` | `dsh --profile headless "<task>"` | ✗ | stdout = final answer; no session id printed |
| `codebuddy` / `workbuddy` | `-p "…" --output-format json` | `-r/--resume <id>` | Tencent CodeBuddy CLI — npm `@tencent-ai/codebuddy-code` **or the CLI bundled inside the WorkBuddy desktop client** (`resources\app.asar.unpacked\cli\bin\codebuddy`). `--model` / `--session-id` / `-w worktree` live-verified. One-time: run it once interactively and `/login` (browser OAuth). Beware: unauthenticated runs print an error but **exit 0** — onduty fails empty output by design |
| `zcode` | `--prompt "…" --json` | `--resume sess_…` | Official ZCode runtime (`resources\glm\zcode.cjs`) bundled in the desktop client, or npm. Needs `~\.zcode\cli\config.json` once — generate it from your desktop provider with `scripts/sync-zcode-cli-config.ps1` (**UTF-8 without BOM** required) and finish `zcode login` once. Permission mapping: `allow_danger: false` → `--mode plan` (read-only; the runtime's own default is `yolo`), `true` → `--mode yolo` |
| `custom` | your argv template | via `{session}` | see below |

Per-agent overrides under `agents.<name>:` — `command` (string or argv list), `extra_args`, `env`, codebuddy: `print_flag/format_flag/resume_flag/allow_flag/output_format/model_flag(default --model)/sandbox_env`; zcode: `prompt_flag/json/mode/safe_mode`; dsh: `profile`.

Custom example:

```yaml
agents:
  mytool:
    type: custom
    command: ["mytool", "-p", "{prompt}", "--resume", "{session}"]
    session_keys: [conversation_id]
```

When there is no session yet, `{session}` **and the preceding `-flag` argument** are dropped automatically; non-JSON stdout falls back to raw text.

## 7. Safety model

1. Every `workdir` must sit inside `safety.allow_roots` or the config is refused — the hard wall against an unattended agent editing the wrong project.
2. No permission-bypass flags by default. Real unattended writes require per-job `allow_danger: true` **and** the isolation whitelist (codebuddy then gets `-y` + `CODEBUDDY_IS_SANDBOX=1`).
3. The daemon itself only writes `state/`.
4. Auto git-worktrees land in v0.2.

## 8. Notifications

- `log` — console + daemon.log + runs.jsonl + per-run full log. Always on if listed.
- `toast` — native Windows toast via WinRT, zero dependencies.
- `webhook` — POST JSON; template `{{job}} {{status}} {{summary}}`. Works with ServerChan (`{"text":…, "desp":…}`), Telegram bot (`{"chat_id":…, "text":…}`), WeCom group bots (`{"msgtype":"markdown",…}`). Notification failures never affect job results.

## 9. Files & troubleshooting

`state/`: `daemon.pid` (single instance) · `daemon.log` · `state.json` (per job: last run/status/session/next_due) · `runs.jsonl` · `logs/<job>/<ts>.log` · `ctl/run__<job>.marker`.

- 0.1 s instant failure with mojibake stderr on Windows → you wrapped the agent in a `.cmd`; cmd's GBK codepage corrupts Chinese/quoted prompts. Call the executable directly via an argv list.
- Chinese mojibake in console only → `chcp 65001` / `PYTHONIOENCODING=utf-8`; log files are UTF-8.
- "workdir not in allow_roots" / "mode cannot be continue" / "once_at is v0.2" — fail-fast by design.
- Schedule skipped during sleep → `catchup: true` + power settings / "wake computer to run task".

Exit codes: 0 ok · 1 job failed / daemon already running · 2 bad config.

## 10. Roadmap

v0.2: `once_at`, retries, auto worktrees, per-directory parallelism · v0.3: web UI, built-in claude/codex/opencode adapters, *nix notifications · upstream: DSH headless-resume PR.

Design docs live in `plans/`.
