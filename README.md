# onduty

**让 agent 替你值班——你去生活。**

一个本地小守护进程，驱动 CLI 编码 agent（DSH、WorkBuddy/CodeBuddy、ZCode，或**任何**有非交互调用能力的命令行）按 **cron 定时**或**接力链**执行任务：前一个任务一跑完，下一条指令（可携带上一段的产出）自动接上，不需要人守着。

English README: [README.en.md](README.en.md) · 完整操作手册：[docs/MANUAL.md](docs/MANUAL.md)（[EN](docs/MANUAL.en.md)）

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE) [![Python](https://img.shields.io/badge/python-≥3.10-green.svg)](https://python.org) [![Status](https://img.shields.io/badge/status-alpha-orange.svg)]()

## 为什么

现在的 agent 跑完一个任务就停下等你发话；"手机推送"类方案仍然要你点一下"继续"。onduty 把"下一条消息"变成**配置**：

- ⏰ **定时**：`cron: "0 8 * * *"`，晨报/测试/巡检到点自动跑
- 🔗 **接力**：`after: <job>` 自动交棒；`{{prev.output}}` 注入上一段产出，或 `mode: continue` 续接同一会话
- 🧰 **多 agent**：每家一个约 50 行的适配器，能力全部**本机实测**（见 plans/001、003）；其他 CLI 用 `{prompt}/{session}` 命令模板免代码接入
- 🔒 **安全默认**：无人值守任务必须落在 `allow_roots` 白名单目录内；放权旗标需逐任务 `allow_danger: true` 双条件；退出码 0 但无输出会被判失败（防"假成功"接力）
- 📣 **通知**：结构化日志 + Windows 原生 toast（零依赖）+ webhook（Server酱 / Telegram / 企业微信），下班不用回头看屏幕

## 快速上手

```powershell
pip install -e .                    # 或 python -m onduty 免安装
copy tasks.example.yaml tasks.yaml  # 编辑 allow_roots 与第一个 job
onduty check                        # 校验 + 预览每个 job 拼好的命令行
onduty once fix_tests               # 前台试跑(含 after 接力链)
onduty daemon                       # 开始值班
onduty list / status / run <job> / logs <job>
```

```yaml
safety:
  allow_roots: [sandbox]            # 无人值守强制隔离

jobs:
  - name: fix_tests
    agent: codebuddy
    workdir: sandbox/proj
    prompt: 运行测试,失败项写入 report.md
    allow_danger: true              # 无头放权(codebuddy→ -y)

  - name: followup                  # fix_tests 成功后自动接力
    agent: codebuddy
    mode: continue                  # 续接同一会话,agent 记得全部上下文
    workdir: sandbox/proj
    prompt: |
      上一段结论: {{prev.output}}
      修复第一个失败项。
    schedule: { after: fix_tests, on: success }

  - name: daily_review
    agent: zcode
    workdir: sandbox/daily
    prompt: 汇总昨天的改动,输出 CHANGELOG 草案
    schedule: { cron: "0 8 * * *" }
```

## 支持 agent（v0.1，flag 均本机实测）

| agent | 无头调用 | 会话续接 | 一次性准备 |
|---|---|---|---|
| **DSH** | ✅ `--profile headless` 实测 | ❌ 官方限制 → `{{prev.output}}` 传话 | 无 |
| **CodeBuddy / WorkBuddy**（客户端内嵌 CLI 或 npm 版） | ✅ `-p --output-format json` 实测 | ✅ `--resume <id>` 实测存在 | CLI 内 `/login` 一次（浏览器 OAuth） |
| **ZCode**（客户端内嵌运行时或 npm 版） | ✅ `--prompt --json` 实测 | ✅ `--resume sess_xxx` | `login` 一次（OAuth）；CLI 配置可用 `scripts/sync-zcode-cli-config.ps1` 从桌面 provider 生成。注意 **Z.AI 免费额度窗口 23:00–09:00**（夜间任务正适合它） |
| 任意非交互 CLI | ✅ | 按其能力 | `agents.<名>: {type: custom, command: [...{prompt}...]}` |
| claude code / codex / opencode | ✅（文档核实） | ✅ | v0.3 内置化 |

## 与同类的区别

"定时跑某个 agent"的轮子已有不少（claudequeue / agent-minder / claudecron / OpenClaw cron）。没有的是这个组合：**多 agent 适配层 + 会话续接接力链 + 声明式 YAML + 强制沙箱隔离**，一个轻量本地守护进程全带上。

## 工作原理

```
tasks.yaml ──► onduty daemon ──► 调度对账(cron 到期 / 手动排队 / after 接力)
                    │
                    ├─► adapter.build(argv) ─► 子进程(workdir 隔离 + 超时杀进程树) ─► adapter.parse(取 session/产出)
                    ├─► state.json · runs.jsonl · 每 run 完整日志
                    └─► 通知: log · WinRT toast · webhook
```

单进程、按 workdir 并行（同目录严格串行）、状态全落盘——重启不丢，错过的定时可按 `catchup` 补跑一次。

## 仓库结构

```
onduty/            # daemon 包(config/state/scheduler/runner/notify/adapters/cli)
docs/MANUAL.md     # 中文操作手册(字段总表/FAQ/排障) · MANUAL.en.md 英文版
plans/             # 设计文档:000 主方案 · 001/003 适配实测 · 002 命名
scripts/           # 辅助脚本(zcode CLI 配置生成等,零密钥)
tasks.example.yaml # 带注释的参考配置
tests/             # 80 个标准库单测
Rules.md           # 项目工作规则
```

## 状态与路线图

- **2026-09-17 · v0.2 完成**：once_at 一次性定时、失败重试（max+退避）、按 workdir 并行、auto git worktree、state_dir 覆盖；80 单测全绿，全部真机验收（见 verlog.md）
- 2026-09-16 · v0.1 完成并公开：三家 agent 适配（WorkBuddy/ZCode 客户端内嵌 CLI 实测）
- **下一步 v0.3**：web UI、claude/codex/opencode 内置适配、Z.AI 夜间额度窗实测（管道已就绪，纯额度时效）

## 许可

[MIT](LICENSE)
