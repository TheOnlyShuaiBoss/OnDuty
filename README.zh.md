# onduty（中文版）

**让 agent 替你值班——你去生活。**

一个本地小守护进程，驱动 CLI 编码 agent（DSH、CodeBuddy/WorkBuddy，或**任何**有非交互调用能力的命令行）按 **cron 定时**或**接力链**执行任务：前一个任务一跑完，下一条指令（可携带上一段的产出）自动接上，不需要人守着。

English README: [README.md](README.md) · 完整手册 [docs/MANUAL.md](docs/MANUAL.md)

## 为什么

现在的 agent 跑完一个任务就停下等你发话；"手机推送"类方案仍然要点一下"继续"。onduty 把"下一条消息"变成**配置**：

- ⏰ **定时**：`cron: "0 8 * * *"`，晨报/测试/巡检到点自动跑
- 🔗 **接力**：`after: <job>` 自动交棒；`{{prev.output}}` 注入上一段产出，或 `mode: continue` 续接同一会话
- 🧰 **多 agent**：每家一个约 40 行的适配器；其他 CLI 用 `{prompt}/{session}` 命令模板免代码接入
- 🔒 **安全默认**：无人值守任务必须落在 `allow_roots` 白名单目录内；放权旗标需逐任务 `allow_danger: true` 双条件
- 📣 **通知**：结构化日志 + Windows 原生 toast（零依赖）+ webhook（Server酱 / Telegram / 企业微信），下班不用回头看屏幕

## 快速上手

```bash
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
    allow_danger: true

  - name: followup                  # fix_tests 成功后自动接力
    agent: codebuddy
    mode: continue                  # 续接同一会话,agent 记得全部上下文
    workdir: sandbox/proj
    prompt: |
      上一段结论: {{prev.output}}
      修复第一个失败项。
    schedule: { after: fix_tests, on: success }
```

## 支持 agent（v0.1）

| agent | 无头调用 | 会话续接 | 状态 |
|---|---|---|---|
| DSH | ✅ 本机实测 | ❌（官方限制）→ 用 `{{prev.output}}` 传话 | 内置 |
| CodeBuddy / WorkBuddy | ✅ 官方无头文档 | ✅ `--resume <id>` | 内置 |
| 任意非交互 CLI | ✅ | 按其能力 | custom 适配器 |
| zcode（目前仅 TUI） | ❌ 无证据 | — | 实测命令后用 custom 接入 |
| claude code / codex / opencode | ✅ | ✅ | v0.3 规划 |

## 与同类的区别

"定时跑某个 agent"的轮子已有不少（claudequeue / agent-minder / claudecron / OpenClaw cron）。没有的是这个组合：**多 agent 适配层 + 会话续接接力链 + 声明式 YAML + 强制沙箱隔离**，一个轻量本地守护进程全带上。

## 目录结构

```
onduty/            # daemon 包(config/state/scheduler/runner/notify/adapters)
docs/MANUAL.md     # 中文操作手册(字段总表/FAQ/排障) · MANUAL.en.md 英文版
plans/             # 设计文档:000 主方案 · 001 适配实测证据 · 002 命名与发布
tasks.example.yaml # 带注释的参考配置
tests/             # 52 个标准库单测
```

## 许可

[MIT](LICENSE)
