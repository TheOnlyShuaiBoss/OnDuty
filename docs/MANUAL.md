# onduty 操作手册

> 让 agent 替你值班 —— 多 agent 定时/接力任务守护进程
> 本手册对应 v0.1（Windows 为主，跨平台代码可运行但 macOS/Linux 未实测）。英文版见 [MANUAL.en.md](MANUAL.en.md)。

## 目录

1. [核心概念](#1-核心概念)
2. [安装](#2-安装)
3. [五分钟快速上手](#3-五分钟快速上手)
4. [tasks.yaml 字段总表](#4-tasksyaml-字段总表)
5. [四种调度语义](#5-四种调度语义)
6. [上下文传递](#6-上下文传递prevoutput-与-mode-continue)
7. [agent 适配器](#7-agent-适配器)
8. [安全模型](#8-安全模型)
9. [通知配置](#9-通知配置)
10. [命令参考](#10-命令参考)
11. [状态与日志文件](#11-状态与日志文件)
12. [常见问题与排障](#12-常见问题与排障)
13. [路线图](#13-路线图)

## 1. 核心概念

| 概念 | 说明 |
|---|---|
| **job（任务）** | 一条声明式任务定义：用哪个 agent、在哪个目录、说什么话、何时触发 |
| **daemon（值班进程）** | 常驻循环，每 tick（默认 30s）对账：到点的 cron、排队的 `run` 请求 |
| **trigger（触发方式）** | 四选一：`cron` 定时 / `once_at` 定时点(v0.2) / `after` 前任务完成接力 / 不写即 `manual` |
| **chain（接力链）** | `schedule.after: <job名>` 把多个 job 串成 DAG；默认前段成功才接力（`on: success`） |
| **adapter（适配器）** | 每个 agent 一小类：怎么建命令行、怎么从输出提取会话 id。能力不足的配置层直接拒绝 |
| **custom agent** | 任何"命令行非交互"的 CLI 免代码接入（`{prompt}`/`{session}` 占位符） |
| **state（运行态）** | 全部落盘：`state/state.json`（会话/下次到期）、`runs.jsonl`（每次运行记录）、`logs/`（每 run 全量日志） |

一句话工作流：**写 tasks.yaml → `onduty check` 校验 → `onduty daemon` 值班 → 到点/接力自动执行 → toast/手机 webhook 收结果。**

## 2. 安装

要求：Python ≥ 3.10（仅两个依赖：PyYAML、croniter）。

```powershell
# 方式 A(推荐): 克隆仓库后源码安装,得到全局 `onduty` 命令
git clone git@github.com:<你的账号>/onduty.git
cd onduty
py -3.13 -m pip install -e .
onduty --help

# 方式 B: 免安装,直接在仓库目录用模块方式跑
py -3.13 -m onduty check
```

> ⚠️ 多版本 Python 的 Windows 机器上，裸 `python` 可能不是 3.13——请确认 `py -0p` 里选哪个解释器装依赖。

## 3. 五分钟快速上手

```powershell
# 1) 复制模板改配置: 至少填 safety.allow_roots 和第一个 job
copy tasks.example.yaml tasks.yaml
notepad tasks.yaml

# 2) 校验 + 看每个 job 最终会被拼成什么命令行(不执行)
onduty check

# 3) 先拿一个 job 试跑(前台、含 after 链、跑完退出)
onduty once daily_review

# 4) 没问题就让 TA 值夜班:
onduty daemon
# 另开一个终端:
onduty list          # 看排期
onduty status        # 看 daemon 存活与各 job 最近结果
onduty run fix_tests # 手动排队一个 job(daemon 下个 tick 执行)
onduty logs fix_tests -n 30   # 看该 job 最近一次运行日志尾部
```

## 4. tasks.yaml 字段总表

```yaml
defaults:                 # 所有 job 的兜底值
  timeout_minutes: 30     # 单任务超时,到点杀进程树并记 timeout
  notify: [log, toast]    # 通知渠道数组: log / toast / webhook
  catchup: false          # 重启后是否补跑错过的 cron(补跑一次)
  allow_danger: false     # 见 §8

scheduler:
  tick_seconds: 30        # 对账周期秒数

notify:                   # webhook 全局配置
  webhook_url: ""         # 留空则 webhook 渠道跳过(只记日志)
  webhook_body_template: '{"text": "...{{job}} {{status}} {{summary}}"}'

safety:
  allow_roots:            # 【必填】workdir 白名单根,不在其内直接拒绝加载
    - sandbox             # 支持相对路径(按 tasks.yaml 所在目录解析)

agents:                   # 每个 agent 的接入参数(见 §7)
  dsh: {command: [...]}
  workbuddy: {model_flag: "--model"}

jobs:                     # 【必填】任务列表
  - name: my_job          # 【必填】唯一名
    agent: dsh            # 【必填】dsh / codebuddy / workbuddy / zcode / 自定义名
    model: null           # 可选;该 agent 配了 model_flag 才可用
    mode: new             # new=新对话; continue=续接上次会话(需 agent 支持)
    workdir: sandbox/proj # 【必填】必须在 allow_roots 内
    prompt: 做点什么       # 与 prompt_file 二选一
    prompt_file: p.md     # 相对 tasks.yaml 解析;内容里可用 {{prev.output}}
    allow_danger: false   # 无头放权(见 §8)
    timeout_minutes: 30   # 可覆盖 defaults
    notify: [log]         # 可覆盖 defaults
    catchup: true         # 可覆盖 defaults
    schedule:             # 不写=manual;四选一:
      cron: "0 8 * * *"   #   定时
      # after: <job名>    #   接力; 配 on: success|always
      # manual: true      #   显式手动
```

## 5. 四种调度语义

### cron（定时）
标准 5 段 cron 表达式（分 时 日 月 周），**按本机时区**：

```yaml
schedule: { cron: "0 8 * * *" }      # 每天 08:00
schedule: { cron: "*/30 9-18 * * 1-5" } # 工作日 9-18 点每 30 分
```

- daemon 每 tick 检查 `next_due`，到点触发，跑完自动重排下一次。
- **补跑**：job 级 `catchup: true` 时，daemon 重启后若距上次运行错过了到点时刻，立即补跑一次（再恢复正常排期）。错过的多个点只补一次，不连环跑。

### after（接力）
```yaml
- name: step2
  schedule: { after: step1, on: success }   # success(默认)/always
```
- step1 **成功**（退出码 0）后立刻串行触发 step2，并把 step1 最终输出注入 step2 的 `{{prev.output}}`。
- `on: always` 表示失败也接力（用于"失败了就发修复指令"场景）。
- 多条链可并行存在；v0.1 执行是**全局串行**（同时只跑一个任务），链深度环检测在配置层完成。

### manual（手动）
- 不写 `schedule` 即手动。
- `onduty run <job>` 写控制文件，daemon 下个 tick 拾取；`--inline` 则当前进程直接跑。
- `onduty once <job>` 永远可用（不依赖 daemon），适合调试。

### once_at（v0.2，当前拒绝加载）
一次性时刻触发，规划中；现在写会报"once_at 是 v0.2 功能"。

## 6. 上下文传递：{{prev.output}} 与 mode: continue

接力时把"上一段"喂给下一段有两种方式：

| 方式 | 机制 | 适用 |
|---|---|---|
| `{{prev.output}}` | 把 after 依赖 job 的**最终文本输出**（截断 4000 字符）注入本段 prompt | 任何 agent；DSH 唯一选择（无 resume） |
| `mode: continue` | 从 state 取**上一轮会话 id**，经适配器 `--resume <id>` 续接同一会话（agent 侧保留全部上下文） | codebuddy / 带 `{session}` 模板的 custom |

- `continue` 模式下该 job 第一轮没有历史会话时自动按新会话跑（首轮等价 new）。
- 二者可叠加：`continue` 续接会话 + `{{prev.output}}` 注入另一条 job 的产出。
- 模板位仅支持 `prev.output`；写其他 `{{xx}}` 会被配置校验拒绝（fail fast，不静默）。

## 7. agent 适配器

### 内置

| agent 名 | 命令 | 非交互 | continue | 说明 |
|---|---|---|---|---|
| `dsh` | `dsh --profile headless "<任务>"` | ✅ | ❌ | DeepSeek Harness。无头一次性调用；session 不落 stdout。**没装全局 dsh 时看下方 command 配置** |
| `codebuddy` / `workbuddy` | `codebuddy -p "<任务>" --output-format json [-r <sid>]` | ✅ | ✅（`-r/--resume`，另有 `-c` 继续最近会话） | 两种来源：npm `@tencent-ai/codebuddy-code`，或 **WorkBuddy 桌面客户端内嵌 CLI**（`resources\app.asar.unpacked\cli\bin\codebuddy`，本机实测 plans/003）。`--model`/`--session-id`/`-w worktree` 亦实测存在。**一次性准备**：首次用需在 TUI 里 `/login`（浏览器 OAuth）。⚠️ 未登录时报错却**退出码 0**——onduty 已加"空产出判失败"防线兜底 |
| `zcode` | `--prompt "<任务>" --json --resume <sess_id>` | ✅ | ✅（`--resume sess_xxx`） | ZCode 桌面客户端内嵌官方运行时（`resources\glm\zcode.cjs`）或 npm 版；flag 本机实测 plans/003。**一次性准备**：`%USERPROFILE%\.zcode\cli\config.json` 就绪（可用 `scripts/sync-zcode-cli-config.ps1` 从桌面配置生成）且 `login` 通过。默认只读：`allow_danger=false` 自动加 `--mode plan`，true 才给 `--mode yolo`（该 CLI 的 `--prompt` 裸跑默认 yolo，我们显式接管） |

### 配置项（`agents.<name>:`，全部可省）

| 键 | 默认 | 说明 |
|---|---|---|
| `command` | `["dsh"]` / `["codebuddy"]` / `["zcode"]` | 可写字符串或 argv 列表（列表可包含 node 直调参数，见下） |
| `extra_args` | `[]` | 追加在任务参数**之前**的固定参数 |
| `env` | `{}` | 任意 agent 通用:追加环境变量(认证 token 等放这里;文件别入库) |
| `print_flag` / `format_flag` / `resume_flag` / `allow_flag` | `-p` / `--output-format` / `--resume` / `-y` | codebuddy 专用，flag 有出入时覆盖 |
| `output_format` | `json` | codebuddy：`json` 从结果解析 session_id 与最终文本；`text` 原文透传 |
| `model_flag` | codebuddy=`--model`（实测）/ 其余无 | 配置后 job 才能用 `model:` |
| `sandbox_env` | `true` | codebuddy：allow_danger 时附带 `CODEBUDDY_IS_SANDBOX=1`（官方沙箱免询问） |
| `prompt_flag` / `json` / `mode` / `safe_mode` | `--prompt` / `true` / 空=按危险度自动 / `plan` | zcode 专用（plans/003） |
| `profile` | `headless` | dsh 专用 |

**DSH 源码启动示例（本机无全局 dsh 时，实测方式）**：

> ⚠ 以下 `<尖括号>` 均为占位符，替换成真实路径后才能使用；请勿把含 `< >` 的示例行原样粘进终端（shell 会把 `<` 当重定向符）。

```yaml
agents:
  dsh:
    command:
      - "<node.exe 路径>"                       # 例: C:\Program Files\nodejs\node.exe
      - "<DSH源码目录>\\node_modules\\tsx\\dist\\cli.mjs"
      - "--tsconfig"
      - "<DSH源码目录>\\tsconfig.json"
      - "<DSH源码目录>\\apps\\cli\\src\\bin.ts"
```

WorkBuddy 客户端内嵌 CLI 同理（`["<node.exe>", "<WorkBuddy安装目录>\\resources\\app.asar.unpacked\\cli\\bin\\codebuddy"]`），zcode 亦然——**先用该 argv 直接运行一次进入 TUI 完成 `/login`/`login`**，之后 headless 长期可用。

> 用 node 直调、**不要**写 `.cmd` 批处理包装：cmd.exe 的 GBK 码页会破坏含中文/引号的 prompt（见 §12）。

### custom：接入任意非交互 CLI

```yaml
agents:
  mytool:
    type: custom
    command: ["mytool", "-p", "{prompt}", "--resume", "{session}"]
    session_keys: [session_id]   # stdout 是 JSON 时的会话 id 候选键
    output_key: result           # JSON 里最终文本的键(默认 result→text→原文)
    allow_args: ["--yes"]        # job.allow_danger=true 时追加
    env: {MY_TOKEN: "xxx"}
```

- `{prompt}` 必含；`{session}` 出现即视为支持续接（`resume: true/false` 可显式覆盖）。
- 无 session 时 `{session}` 连同**其前面的旗标参数**（以 `-` 开头）一起丢弃，首轮自动降级为新会话。
- stdout 非 JSON 时自动回退原文透传。新 agent（未内置的）都走这条路接入，实测好用欢迎提 PR 内置化。

## 8. 安全模型

无人值守 = 没人点"确认"。onduty 的默认姿态是**强制隔离 + 显式放权**：

1. **allow_roots 强制**：每个 job 的 `workdir` 必须落在 `safety.allow_roots` 之内（含子目录），否则配置直接拒绝加载、daemon 不启动。这是"agent 乱改别的项目"的硬防线。
2. **allow_danger 双条件**：默认不向 agent 传任何放权旗标——此时 codebuddy 无头模式只能读不能写（写操作被其权限系统阻止）。要真干活需 job 级 `allow_danger: true`，且 workdir 已在白名单内，二者同时满足才会加上 `-y`（codebuddy 另附 `CODEBUDDY_IS_SANDBOX=1`）。
3. **daemon 自身**：只写 `state/` 目录；不碰任务目录之外的任何文件。
4. **v0.2 计划**：`auto_git_worktree`（自动为 git 仓库任务开 worktree 分支跑）。当前写 `true` 会被拒绝。

推荐姿势：给自动任务单独开 `sandbox/`（或专门的 checkout 目录），人肉开发目录**不要**放进 allow_roots。

## 9. 通知配置

| 渠道 | 触发 | 配置 |
|---|---|---|
| `log` | 每 run 文件日志 + daemon 控制台 + runs.jsonl | 默认即有 |
| `toast` | 任务完成/失败时 Windows 通知中心弹窗 | 零依赖（WinRT）；要求系统 PowerShell 为 FullLanguage 模式（Win10/11 默认） |
| `webhook` | 同上，POST JSON | `notify.webhook_url` + 可选 `webhook_body_template`；占位符 `{{job}} {{status}} {{summary}}` |

三大机器人模板示例：

```yaml
notify:
  # Server酱: https://sctapi.ftqq.com/<SENDKEY>.send
  webhook_url: "https://sctapi.ftqq.com/XXXX.send"
  webhook_body_template: '{"text": "[onduty] {{job}} {{status}}", "desp": "{{summary}}"}'

  # Telegram bot: chat_id 必填进 body
  # webhook_url: "https://api.telegram.org/bot<TOKEN>/sendMessage"
  # webhook_body_template: '{"chat_id": "<CHAT_ID>", "text": "[onduty] {{job}} {{status}}: {{summary}}"}'

  # 企业微信群机器人
  # webhook_url: "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=***"
  # webhook_body_template: '{"msgtype":"markdown","markdown":{"content":"**[onduty] {{job}}** {{status}}\n> {{summary}}"}}'
```

通知失败只记警告，绝不影响任务状态与 daemon 存活。

## 10. 命令参考

```
onduty [--config FILE] <子命令>     # --config 默认 tasks.yaml(相对当前目录)

daemon   [--tick N]      前台启动守护进程,Ctrl+C 退出;单实例(pid 文件互斥)
once     <job>           不等 daemon,当前进程直接跑该 job(含 after 链)
check                    校验配置;逐 job 打印适配器能力与拼好的 argv(占位 <PROMPT>)
list                     所有 job 的调度与最近状态一览
status                   daemon 存活 + 每 job 运行计数/最后结果/会话/日志路径
run      <job> [--inline] 写控制文件排队给 daemon;--inline 同 once
logs     <job> [-n N]    打印该 job 最近一次运行日志尾部(默认 50 行)
```

退出码约定：`0` 成功；`1` 任务失败或 daemon 已运行；`2` 配置/参数非法。

**开机自启（Windows 任务计划程序）**：

```powershell
schtasks /Create /TN onduty /SC ONLOGON /TR "onduty daemon --config <项目目录>\tasks.yaml"
```

## 11. 状态与日志文件

```
state/
  daemon.pid      # 单实例锁(daemon 退出自动清理)
  daemon.log      # 调度流水(触发/执行结果/配置错误)
  state.json      # 每 job: last_run_at/last_status/session_id/last_output(≤8KB)/run_count/next_due
  runs.jsonl      # 每次运行一行 JSON: ts/job/agent/mode/trigger/status/exit_code/duration_s/log/session_id
  ctl/run__<job>.marker   # onduty run 写入,daemon 拾取后删除
  logs/<job>/<时间戳>.log  # 每 run: 头(参数+渲染后prompt) + exit/duration + stdout/stderr + 解析后 final
```

排查路径：`onduty status` → `onduty logs <job>` → 需要细节再打开对应 log 文件（里面完整记录了当次实际执行的 argv 与 prompt）。

## 12. 常见问题与排障

| 症状 | 原因与解法 |
|---|---|
| `workdir ... 不在 safety.allow_roots 白名单内` | §8 硬规则。把该目录纳入白名单，或把任务挪进 sandbox |
| `agent 'xxx' 无法接入` | agent 名未注册或内置适配器 `capable=False`。检查 `agents:` 拼写，或按 §7 custom 接入 |
| `mode 不能为 continue`（DSH） | 官方 headless 无 resume。改 `mode: new` + `{{prev.output}}` 传上下文 |
| codebuddy 无头只读不写 | 未开 `allow_danger: true`（v0.1 默认不放权，见 §8） |
| codebuddy 报 "Authentication required" 且被判 failed | 客户端内嵌 CLI 需一次性登录：用 `agents.codebuddy.command` 那条 argv 直接运行进 TUI → `/login` 浏览器登录 → 之后 headless 长期可用 |
| zcode 报 "Model config is missing" | CLI 独立于桌面配置。跑 `scripts/sync-zcode-cli-config.ps1` 从桌面 provider 生成 `~\.zcode\cli\config.json`（注意**必须无 BOM**，PowerShell 5 的 `Set-Content -Encoding UTF8` 会带 BOM 导致仍报缺失） |
| zcode 报 "captcha verify failed (3007)" | start-plan 网关风控。跑一次 `node <zcode.cjs> login`（或对应 `login bigmodel-coding-plan`）走官方 OAuth 后再试 |
| 退出码 0 但任务其实没干活(空输出) | 已知部分 CLI 认证失败仍返回 0。onduty 将"成功+空产出"判为 failed 并阻断 after 接力（plans/003 实测） |
| Windows 下 0.1s 假失败、stderr 乱码"不是内部或外部命令" | 你八成用 `.cmd` 包装了 agent——cmd 的 GBK 码页破坏中文/引号。改 node/可执行文件 argv 直调 |
| 控制台中文乱码 | GBK 代码页显示问题：`chcp 65001` 或 `$env:PYTHONIOENCODING='utf-8'`。落盘日志均为 UTF-8，不受影响 |
| YAML 里 `on:` 相关怪错误 | YAML 1.1 把裸 `on` 当布尔值。本工具已兼容归一化，仍建议写 `on: success` 或 `"on":` |
| 定时没触发 | `onduty status` 看 daemon 是否活着；`state/daemon.log` 看配置报错；cron 按**本机时区** |
| 睡眠错过定时 | job 加 `catchup: true`；或电源计划禁睡眠/任务计划器勾"唤醒计算机运行任务" |
| 想立刻停某链 | 删 `state/ctl/*.marker`；`Stop-Process -Id <daemon pid>`(正在跑的任务子进程会随任务超时或被 taskkill 终止,需要时手动 taskkill) |
| 重复启动 daemon | `onduty daemon` 检测到 pid 存活会直接退出(返回 1),这是特性不是 bug |

## 13. 路线图

- **v0.2**：once_at、失败重试（次数+退避）、auto git worktree、按 workdir 并行、更多模板位（`{{prev.files}}` 等）
- **v0.3**：web UI、claude code / codex / opencode 内置适配、macOS/Linux 通知适配
- **长期**：给 DSH 提 headless resume 的 PR；agent 健康度自测；成本统计

设计文档：仓库 `plans/`（000 主方案 / 001 适配 spike 实测 / 002 命名与发布）。
