# 005 DSH 重装后诊断与修复方案（⚠️ 全部待批准，未执行）

- 日期: 2026-09-18 凌晨 · 状态: **方案存档，零改动——用户审阅后逐项授权执行**
- 背景: 用户重装 DSH（旧 checkout `D:\DSH\deepseek-harness` v0.1.1-rc.2 → 新 checkout `D:\DSH\deepseek-harness-0.1.6-alpha.1`，另有 `upgrade-backup-20260917-191021` 备份目录），要求通读方案/问题记录/版本记录后找出问题与 bug 并给出修复方案
- 诊断结论速览: **1 个真 bug（tasks.yaml DSH 路径过时）+ 1 个验收遗留（zcode 夜间窗���+ 1 个结构性立项建议（路径抗升级）；其余全部健康**

## 0. 诊断过程与已排除疑点（2026-09-18 凌晨全部实测核实）

| 检查项 | 方法 | 结论 |
|---|---|---|
| onduty 本体 | `py -3.13 -m unittest discover -s tests -t .` | **80 单测全绿**（0.926s），DSH 重装未波及 |
| 配置加载 | `onduty check` | 8 个 job 全部通过校验 |
| settings.yaml | 严格模式 YAML 解析（遇重复键即抛错） | **健康，无重复键**；19 处 `reasoningEfforts` 是不同模型小节下的合法键（缩进一致、各属不同父节点），上次"第 132 行重复键"事故未复发 |
| 新 checkout 完整性 | 逐一 Test-Path | `apps\cli\src\bin.ts`、`node_modules\tsx\dist\cli.mjs`、`tsconfig.json` 三件齐全 |
| headless 调用机制 | 新版 `apps/cli/src/args.ts` 源码核实 | `dsh --profile headless "任务"` 不变（args.ts:80 示例原文）；**`--resume` 仍仅限 tui profile**（args.ts:10/82）→ onduty 对 DSH 的 `{{prev.output}}` 文本注入接力设计依然正确，v0.3"提 headless resume PR"路线图仍有效 |
| daemon.log 乱码疑云 | read 工具按 UTF-8 直读文件 | 文件本身标准 UTF-8 无误（"启动/触发/重试"等中文全部正常）；此前乱码只是 GBK 控制台显示问题，MANUAL §12 已有记载，**非 bug** |
| `~/.dsh` 凭据与 profile | Test-Path | `.credentials.yaml`、`profiles\headless`、`settings.yaml` 均在，重装未清除 |
| 仓库状态 | `git status` / `git log` | `main` 与 `origin/main`（github.com:TheOnlyShuaiBoss/OnDuty）同步，工作树干净——verlog"待推送"事项用户已自行完成 |

## 1. 问题 1【高·真 bug】tasks.yaml 的 DSH 命令指向过时 checkout

### 现状
`tasks.yaml` 第 13–18 行 `agents.dsh.command` 的 3 处路径仍指向旧 checkout `D:\DSH\deepseek-harness\`（v0.1.1-rc.2）。影响 4 个 job：`e2e_step1` / `e2e_step2_chain` / `dsh_a` / `dsh_b`。

- 目前旧目录未删，这些 job **暂时能跑**，但跑的是旧版 DSH（落后 0.1.1-rc.2 → 0.1.6-alpha.1 若干版本）
- 一旦清理旧目录或备份目录，这 4 个 job 将直接 `FileNotFoundError`，headless 起不来
- verlog 2026-09-17 晚已预警此依赖，并写明修复方式：**只改 tasks.yaml 路径，无需改 onduty 代码**

### 修复步骤（批准后执行）
1. `tasks.yaml` 三处路径替换（仅此三行，其余不动）：
   - 第 15 行：`"D:\\DSH\\deepseek-harness\\node_modules\\tsx\\dist\\cli.mjs"` → `"D:\\DSH\\deepseek-harness-0.1.6-alpha.1\\node_modules\\tsx\\dist\\cli.mjs"`
   - 第 17 行：`"D:\\DSH\\deepseek-harness\\tsconfig.json"` → `"D:\\DSH\\deepseek-harness-0.1.6-alpha.1\\tsconfig.json"`
   - 第 18 行：`"D:\\DSH\\deepseek-harness\\apps\\cli\\src\\bin.ts"` → `"D:\\DSH\\deepseek-harness-0.1.6-alpha.1\\apps\\cli\\src\\bin.ts"`
2. `onduty check` 复核：4 个 dsh job 预览 argv 应显示新路径
3. 真机冒烟：`onduty once dsh_a`（前台跑，约 90 秒；成功后 after 链会自动接力 `dsh_b`，一并验证）

### 验收标准
- `runs.jsonl` 新增 dsh_a（trigger=manual）与 dsh_b（trigger=after）各一条 status=success
- `sandbox/dshchain/a.md` 含 `ANSWER=42`、`b.md` 含 `CONFIRMED`
- 新版 DSH 0.1.6-alpha.1 的 headless 输出仍可被现有 parse 正确取到 final 文本

### 风险与回退
- 低。新版调用机制已源码核实一致；若冒烟失败，回退方式 = 把三处路径改回旧值（旧目录仍在）
- 顺带建议（不属于本次修复）：冒烟通过并稳定运行几天后，可清理旧 checkout 与 `upgrade-backup-*` 目录释放磁盘——由用户自行决定

## 2. 问题 2【中·验收遗留】zcode 夜间额度窗验证未闭环

### 现状
plans/004 v0.2 验收表中"zcode 夜间窗"一项状态 ⏸。`runs.jsonl` 里 `zc_check` 只有白天失败记录（2026-09-17 12:50、13:35，报 `1113` 余额不足——白天无免费额度属预期行为）。管道本身已验证通畅（plans/003 §4），差的只是"夜间 23:00–次日 09:00 窗口内真实跑通一次"。

### 修复步骤（批准后执行，注意时效）
**当前凌晨 5 点正在免费窗口内，距 09:00 关窗约 4 小时，批准后应尽快跑**：

1. `onduty once zc_check`（前台，job 已在 tasks.yaml：数目录文件数、只回数字，timeout 6 分钟）
2. 成功 → ① verlog 记录验收结果；② plans/004 验收表该项 ⏸ → ✅；③ README 路线图"Z.AI 夜间额度窗实测"划掉
3. 失败 → 保存 `state/logs/zc_check/<时间戳>.log`，按报错码对照 MANUAL §12（1113=窗口/额度，3007=登录态，1309=套餐到期）定性

### 验收标准
- `runs.jsonl` 新增 zc_check 一条 status=success，final 输出为数字
- plans/004 验收表闭环，v0.2 全部验收项 ✅

## 3. 问题 3【低·v0.3 立项建议】DSH 路径抗升级：config 支持环境变量展开

### 现状
onduty 对 DSH 的依赖形态是"源码 checkout 绝对路径"，而 DSH 每次升级目录名带版本号（0.1.1-rc.2 → 0.1.6-alpha.1），**每次升级都要手改 tasks.yaml 三处路径**。本次重装即触发了这个问题（问题 1 的根因）。

### 立项草案（记入 v0.3 计划，与 web UI、claude/codex/opencode 内置适配并列）
- config.py 加载 `tasks.yaml` 后，对字符串值做 Windows 风格 `%VAR%` 环境变量展开（展开发生在校验前，变量未定义 → fail fast 报错并指明变量名）
- 用户设一次系统环境变量如 `DSH_HOME=D:\DSH\deepseek-harness-0.1.6-alpha.1`，tasks.yaml 写 `"%DSH_HOME%\\node_modules\\tsx\\dist\\cli.mjs"`；以后升级只改环境变量，不动配置
- 设计考量：是否只展开 `agents.*.command` / 路径类字段还是全部字符串值（倾向后者，规则简单）；展开结果要进 `onduty check` 预览以便核对；单测覆盖（变量存在/缺失/嵌套路径）
- 备选更轻方案：约定固定 junction（`mklink /J D:\DSH\current ...`），零代码——但多一步手工链接维护，二选一在 v0.3 方案里定

## 4. 执行清单（用户逐项打勾授权后执行）

- [x] **修复 1**：tasks.yaml 三处 DSH 路径切到 0.1.6-alpha.1 + check + once dsh_a/dsh_b 冒烟（§1）→ **2026-09-19 完成并真机验收**
- [~] **修复 2**：窗口内跑 once zc_check，回填 verlog 与 plans/004 验收表（§2）→ **管道已修复，验收待额度侧**（见 §5）
- [x] **修复 3**：已记入本文档 §3（v0.3 立项草案）；未动代码（符合约定）

> 本文档本身即本次交付物：诊断已实测、方案已存档、代码与配置零改动。

## 5. 执行记录（2026-09-19 ~ 09-20，用户批准后执行）

- **修复 1 ✅ 完成并验收**：`tasks.yaml` 三处 DSH 路径已切到 `D:\DSH\deepseek-harness-0.1.6-alpha.1\`；`onduty check` 8 job 全过；真机冒烟 `once dsh_a` → dsh_a success(41.9s, final=42) + after 接力 dsh_b success(33.7s, final=CONFIRMED)；`a.md`/`b.md`/`runs.jsonl` 全部达标
- **修复 2 [~] 管道已修复、验收未闭环**：
  1. 09-19 05:03 首次尝试 → 0.8s 启动即失败：`无法定位 CLI ZCode Built-in Provider Config`（当时 ZCode=3.12.3.7463，新版打包缺失 `resources\glm\provider\zcode-builtin.json`）
  2. 源码反解出 3.12.3 的环境变量逃生口（`ZCODE_BUILTIN_PROVIDER_CONFIG_FILE` + `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` 同设即跳过文件查找），注入实验实测通过启动阶段（该知识留档；客户端回退后不再需要）
  3. 09-19~09-20 ZCode 侧整体变动：`~\.zcode` 重建、客户端回退 **3.11.2.6792**；卡点变为 `~\.zcode\cli\config.json` 丢失
  4. 用项目脚本 `scripts/sync-zcode-cli-config.ps1` 从桌面配置恢复 CLI 配置（provider=onduty / GLM-5.3，无 BOM 校验通过）
  5. 再跑 `once zc_check`：启动正常、7.5s 达网关，返回 `[1113] 余额不足或无可用资源包`（bigmodel 通道）→ 待复验；**2026-09-20 用户澄清正解**：免费额度（夜间/周末包）仅 Z.AI 登录账号有、且绑定 ZCode 自身加密凭据，桌面同步 key 吃不到 → 需 Z.AI 登录并经 ZCode 运行时使用（用户已登录），详见 verlog 09-20 条目
- **修复 3 ✅（仅立项）**：§3 已记录，未动代码
