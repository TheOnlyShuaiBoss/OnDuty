# agent_daemon 总体方案(000 号·主方案)

- 状态: 草案,待用户批准
- 日期: 2026-09-16
- 工作路径: 本地专用工作目录(全部工作严格限该目录;克隆后为 `<repo目录>`)

## 1. 定位

本地开源小守护进程: 用一份声明式 `tasks.yaml` 驱动多个 CLI agent,按"定时 / 前任务完成"自动接力执行无人值守任务。

一句话: **cron for agents —— 多 agent、可续接、声明式的本地任务接力器。**

痛点: 现在的 coding agent 大多"跑完一个任务就停",下一条指令要人守着发。本项目把"下一条指令"写成配置,由 daemon 按时间或完成事件自动投喂。

## 2. 已拍板决策(2026-09-16 用户确认)

| 决策项 | 结果 |
|---|---|
| 首批适配 agent | DSH / WorkBuddy / zcode |
| 链式输入 | 固定文本 + `{{prev.output}}` 模板 |
| 安全策略 | 强制隔离目录(放权需显式双条件) |
| 界面 | tasks.yaml + CLI,web 界面二期 |
| 技术栈 | Python 3.13 |
| 通知 | 日志文件 + Windows toast + webhook |

## 3. 竞品对照(联网核实后)

| 项目 | 形态 | 与本项目差异 |
|---|---|---|
| LIhong42/claude-queue-manager | Claude 批量任务平台 | 单 agent,无续接链 |
| csabika98/claudequeue | Claude 无人值守队列 | 单 agent,无 cron+续接组合 |
| aptx-health/agent-minder | Go 写的 cron 触发 Claude | 单 agent |
| phildougherty/claudecron | MCP 服务器挂 cron | 依赖 MCP 宿主,单 agent |
| SpillwaveSolutions/agent-cron | agent cron skill | skill 形态,非独立调度器 |
| OpenClaw cron | 个人助理网关带 cron | 重量级网关,非轻量编码任务接力 |
| **本项目** | 多 agent + 续接链 + cron/完成双触发 + 声明式 yaml + 强制隔离 | — |

注意: "定时跑 agent"本身已有不少轮子,开源文案**不打"首创定时"**,卖点写准三条: **多 agent 适配层 + 会话续接链 + 安全隔离默认**。

## 4. 接入能力现状(2026-09-16 核实)

| agent | 非交互调用 | 会话续接 | 依据 |
|---|---|---|---|
| DSH | ✅ `dsh --profile headless "task"`(退出码 0/1,stdout=最终答复) | ❌ 当前不支持(每次 fresh session,官方 Known Limitations 明确) | 本地源码文档实证 |
| WorkBuddy | ✅ 官方无头模式文档存在 | 待 spike 核实(疑似 claude-code 兼容) | codebuddy.cn/docs/cli/headless |
| zcode | ✅ CLI 与配置文档存在 | 待 spike 核实 | github.com/kingsword09/zcode-cli |
| (参考) claude code | ✅ `claude -p --output-format json` | ✅ `--resume <session_id>` | 官方文档 |
| (参考) codex | ✅ `codex exec` | ✅ resume 能力 | 官方 advanced 文档 |
| (参考) opencode | ✅ `opencode run` | ✅ `--session` / `--continue` | 官方 flags 文档 |

直接影响:
- DSH 任务 v0.1 只支持 `mode: new`;对 DSH 的"接力"用 `{{prev.output}}` 文本注入传递上下文,代替会话续接。
- WorkBuddy / zcode 的确切 flag、输出格式、resume 能力**不猜**,列入实施前置 spike(§10)。

## 5. 配置形态(tasks.yaml)

完整可运行示例见根目录 `tasks.example.yaml`。字段速览:

- `jobs[]`: `name` / `agent` / `model`(可选) / `mode: new|continue` / `workdir` / `prompt|prompt_file` / `schedule` / `timeout_minutes` / `allow_danger` / `notify`
- `schedule` 四选一:
  - `cron: "0 8 * * *"` —— 定时
  - `once_at: "2026-09-20 08:00"` —— 一次性(v0.2)
  - `after: <job名>` + `on: success|always` —— 前任务完成自动接力
  - 不写 `schedule` —— manual,`agentctl run <job>` 手动触发
- 模板位: `{{prev.output}}` = 前一任务最终文本产出(截断 4000 字符)

## 6. 架构

单进程 daemon + 单文件 CLI,无外部服务依赖:

```
agent_daemon/
  agentd/                 # Python 包
    __main__.py           # daemon 入口: python -m agentd
    config.py             # yaml 加载+校验(含安全校验,fail fast)
    scheduler.py          # 对账循环: cron 到期 / after 依赖 / 补跑
    runner.py             # subprocess 执行 + 超时强杀 + 退出码判定
    state.py              # state.json + runs.jsonl + 每 run 日志落盘
    notify.py             # log / toast / webhook
    adapters/
      base.py             # 适配器协议: build_cmd / parse_output / 是否支持 resume
      dsh.py  workbuddy.py  zcode.py
  agentctl.py             # CLI: list / status / run <job> / logs <job>
  tasks.yaml              # 用户配置(gitignored,参照 tasks.example.yaml)
  state/                  # 运行态(gitignored): state.json / runs.jsonl / logs/
  sandbox/                # 自动任务隔离工作目录(gitignored)
  plans/  tests/
```

- 调度循环: 每 30s 对账;`after` 由完成事件直接触发,不等对账。
- 并发: 同一 `workdir` 串行(目录锁);v0.1 可先全局串行,最简。
- 补跑: 状态落盘;daemon 重启后对账,错过的 cron 按 job 级 `catchup: true` 补跑一次。
- 依赖最小: `PyYAML` + `croniter`;webhook 用标准库 `urllib`;toast 优先 PowerShell(BurntToast),不行再引包。

## 7. 安全模型(强制,不可关)

1. 每个 job 必须声明 `workdir`,且必须落在 `safety.allow_roots` 白名单内,否则配置校验拒绝加载。
2. 默认不向 agent 传任何放权旗标;`allow_danger: true` 需**逐 job 显式声明**,且 workdir 必须在白名单内——双条件同时满足才生效。
3. `auto_git_worktree: true` 时(v0.2)对 git 仓库任务自动建 worktree 执行,跑完汇报分支名。
4. daemon 自身只写 `state/` 目录,不碰任务目录外的任何文件。

## 8. 完成判定与链式

- 完成 = 进程退出: 退出码 0 成功,非 0 失败;超时强杀记失败(`timeout_minutes`)。
- `after` 链默认 `on: success` 才接力,可配 `always`。
- `mode: continue` 时适配器从 state 取该 job 上次的 session_id 拼接 resume 参数;agent 不支持 resume 则**配置校验直接报错**(fail fast,不静默降级)。
- 链式传话: `{{prev.output}}` 渲染时注入,渲染结果写入当次 run 日志,可追溯。

## 9. 通知

| 渠道 | 时机 | 实现 |
|---|---|---|
| 日志 | 全程 | 每 run 一个日志文件 + `runs.jsonl` 结构化记录 |
| Windows toast | 完成/失败 | PowerShell BurntToast 优先 |
| webhook | 完成/失败 | POST JSON 到 `notify.webhook_url`,body 模板可配(兼容 Server酱 / Telegram / 企业微信自建机器人) |

## 10. 实施前置 spike(动工第一步,产出 `plans/001_adapter_spike.md`)

1. WorkBuddy: 无头模式确切 flag、输出格式、resume/会话 id 支持、权限旗标。
2. zcode: 同上。
3. DSH: 本机复核 headless 调用与输出(无 resume 结论已确认,复核即可)。
4. Windows toast 零依赖方案实测。

降级原则: 任一家不支持 resume → 该 agent 标为 new-only,主线不被卡。

## 11. 分期

- **v0.1 MVP**: yaml 配置 + daemon 对账循环 + DSH/WorkBuddy/zcode(new 模式) + cron/after/manual + `{{prev.output}}` + 日志/toast/webhook + 强制隔离校验 + agentctl(list/status/run/logs)
- **v0.2**: once_at + 补跑 + continue 模式(对支持的 agent) + 失败重试(次数+退避) + auto git worktree + 按目录并行
- **v0.3+**: web UI / claude code·codex·opencode 适配 / 给 DSH 提 headless resume PR

## 12. 风险与对策

| 风险 | 对策 |
|---|---|
| workbuddy/zcode 能力不足 | spike 前置;降级 new-only,主线不被卡 |
| DSH 无续接 | 文档写清;DSH 链用 `{{prev.output}}` 文本传递 |
| 无人值守被确认提示卡死 | 强制隔离 + 显式放权双条件;放权旗标收敛在适配层 |
| 同目录并发互踩 | 目录串行锁 |
| 睡眠错过 cron | 状态落盘 + 重启对账补跑(catchup) |
| 竞品已多 | 卖点写准: 多 agent + 续接链 + 安全默认 |

## 13. 批准后的实施步骤

1. spike 核实三家 agent CLI → `plans/001_adapter_spike.md`
2. 骨架: config / state / scheduler / runner + manual 触发跑通
3. 三家适配器 + cron / after
4. 通知三渠道
5. 测试 + README 收尾 + verlog.md 记录验收
