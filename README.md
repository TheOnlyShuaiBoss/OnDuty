# onduty

**Send your coding agents on shift — go live your life.**

A tiny local daemon that runs CLI coding agents (DSH, CodeBuddy/WorkBuddy, or *anything* with a non-interactive command) on a **cron schedule** or as a **relay chain**: when one task finishes, the next instruction — optionally carrying the previous run's output — is fed in automatically. No human babysitting required.

简体中文 README 见 [README.zh.md](README.zh.md) · 完整手册见 [docs/MANUAL.en.md](docs/MANUAL.en.md)（[中文](docs/MANUAL.md)）

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE) [![Python](https://img.shields.io/badge/python-≥3.10-green.svg)](https://python.org) [![Status](https://img.shields.io/badge/status-alpha-orange.svg)]()

## Why

Agents today stop after each task and wait for you to type the next message. Phone-ping integrations still need a human to tap "continue". onduty treats "the next message" as **configuration**:

- ⏰ **Scheduled** — `cron: "0 8 * * *"`, fire daily reviews/tests/lint at will
- 🔗 **Relay chains** — `schedule: { after: job_x }` hands the baton automatically; inject the previous result via `{{prev.output}}`, or resume the same session with `mode: continue`
- 🧰 **Multi-agent** — per-agent adapters (~40 lines each); any other CLI plugs in via a `{prompt}`/`{session}` argv template, zero code
- 🔒 **Safe by default** — unattended runs must live inside an explicit `allow_roots` whitelist; permission-bypass flags require a per-job `allow_danger` double-condition
- 📣 **Notifications** — structured logs, native Windows toasts (zero deps), and webhooks (ServerChan / Telegram / WeCom) so your phone knows when the shift ends

## Quick start

```bash
pip install -e .          # or: python -m onduty ...
cp tasks.example.yaml tasks.yaml   # edit allow_roots + your first job
onduty check              # validate config, preview the exact argv per job
onduty once fix_tests     # foreground test run, including after-chains
onduty daemon             # go on shift
```

```yaml
safety:
  allow_roots: [sandbox]           # mandatory isolation for unattended runs

jobs:
  - name: fix_tests
    agent: codebuddy
    workdir: sandbox/proj
    prompt: Run the tests, write failures to report.md
    allow_danger: true

  - name: followup                 # fires automatically when fix_tests succeeds
    agent: codebuddy
    mode: continue                 # same session, agent remembers everything
    workdir: sandbox/proj
    prompt: |
      Previous result: {{prev.output}}
      Fix the first failure.
    schedule: { after: fix_tests, on: success }
```

## Agent support (v0.1)

| Agent | Headless run | Session resume | Status |
|---|---|---|---|
| DSH (`dsh --profile headless`) | ✅ live-tested | ✗ upstream limit → use `{{prev.output}}` | built-in |
| CodeBuddy / WorkBuddy (`codebuddy -p --resume`) | ✅ official headless docs | ✅ `--resume <id>` | built-in |
| Any CLI with a non-interactive mode | ✅ | ✅ if it has one | `custom` adapter |
| zcode (TUI-only today) | ✗ evidence | — | use `custom` once verified |
| claude code / codex / opencode | ✅ | ✅ | planned v0.3 |

## How it works

```
tasks.yaml ──► onduty daemon ──► scheduler (tick: cron due / queued run markers / chains)
                    │
                    ├─► adapter.build(argv) ─► subprocess(workdir, timeout) ─► adapter.parse
                    ├─► state: state.json · runs.jsonl · logs/<job>/<ts>.log
                    └─► notify: log · WinRT toast · webhook
```

Single process, serial execution, everything on disk — restart-safe with optional cron catch-up.

## How is this different?

Cron/queue wrappers for a single agent exist (claudequeue, agent-minder, claudecron, OpenClaw cron…). What's not out there: **multi-agent adapters + session-resume relay chains + declarative YAML + enforced sandbox isolation** in one lean local daemon.

## Repository layout

```
onduty/            # the daemon package (config/state/scheduler/runner/notify/adapters)
docs/MANUAL.*.md   # full operations manual (zh/en)
plans/             # design docs: 000 master plan · 001 adapter spike evidence · 002 naming
tasks.example.yaml # annotated reference config
tests/             # 52 unit tests, stdlib unittest
```

## License

[MIT](LICENSE)
