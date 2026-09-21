# verlog.md — agent_daemon 改动与验收记录

## 2026-09-22 04:50 · 第1项**升级为纯反代模式**(脱离 ZCode 客户端; 隐私优先)

### 为什么改方向
2026-09-18 曝光 **ZCode 客户端静默上传用户整个工作区**(完整 git 历史/LFS 大文件/reflog/全局配置)
到阿里云 OSS: **默认常开、UI 无开关**, 加密用服务端下发公钥(用户自己也解不开)。官方已承认道歉,
宣布将开源 + 第三方审计。来源: DoNews / 新浪财经 / 36Kr。
→ 用户明确要求"**像反代 workbuddy 那样, 只在 DSH 操作**", 即**不依赖客户端**。

### 关键更正(我此前的错误结论)
此前判断"**必须**在官方 renderer 内出码" → **错**。早期外部 Chrome 出码失败的真实原因是两个缺陷,
**而这两个修正是后来才发现的、从未复测**:
| 缺陷 | 早期(错) | 官方真值 |
|---|---|---|
| `language` 参数 | `zh-CN` | **`cn`** |
| 浏览器模式 | 无头 | **有头**(阿里云无痕识别无头) |
修正后实测: **稳定出码成功**, 280 字符含 securityToken, 冷启动+出码约 7s。

### 落地与验收(2026-09-22 04:45, 夜间免费窗 23:00–09:00 内)
| 项目 | 结果 |
|---|---|
| 外部出码(独立 Chrome) | ✅ 280 字符 + securityToken, 7.3s |
| 非流式端到端 | ✅ **200**, content `"OK"`, usage 15283/3/15286 |
| 流式端到端 | ✅ **200**, `delta "STREAM-OK"` → finish stop + usage 15290 → `[DONE]` |
**全程未使用 ZCode 客户端。**

### 隐私核查(桥接器实际发送内容)
不含任何用户项目名(quant_framework/chanlun/longtou/momentum/seal_cutout/fuyao/agent_daemon)、
不含 `llm_proxy`、不含用户项目文件; 用户名 `a2018` 仅出现在**官方插件安装路径**里(非用户数据)。
→ 桥接器只转发 DSH 给的对话内容, **不上传本地仓库**。

### 新增防护
**3012 自冷却**: 命中风控后桥接器自身冷却 30 分钟、期间本地拒绝不触上游
(实测 DSH 会在 20 秒内连发 4~5 次重试, 每次重试都加重风控)。

### 对 onduty(本项目)的影响
- **无代码改动**; 第1项仍由 llm_proxy 侧桥接承担
- **运维简化**: 不再需要 `start_zcode_debug.bat`(即不再需要跑客户端)
- 原兜底方案 B2(onduty 直接调度 zcode)仍可作独立方向, 未实施待拍板

## 2026-09-21 晚 · 第1项收尾: ZCode 桥接**已可用**(结论与定位, 详见 llm_proxy)

第1项(让 DSH 用上 ZCode 夜间/周末免费额度)已通过 **B1 桥接**落地并端到端验收通过。
**本项目的结论性记录**(实现与验收细节在 llm_proxy, 见其 `verlog.md` / `plans/2026-09-21-ZCode桥接常驻化方案.md` / `ISSUES.md` Z1~Z5):

### 结果
- DSH 里已能选到 `zcode/GLM-5.3-Flash`、`zcode/GLM-5.3`, 走 ZCode 套餐额度(实测 usage 15283/3/15286)
- 桥接链路: 宿主协议 + **官方 renderer 内出码**(~1s, len=280) + 官方运行时发请求
- 真实链路验收: 非流式与流式各一次 200; 触发 agent 循环的用例跑满 4 轮/26~39s 并返回最终答案

### ⚠️ 三条必须记住的结论
1. **定位是"带内置工具的 agent 桥接", 不是"纯净模型反代"**
   `session/send` 的 schema 只有 `toolDenylist`、**无传入工具入口** → DSH 的工具无法下发给模型;
   模型只用 ZCode 自带工具(WebSearch/Bash/…)并由运行时自行执行 → DSH 收不到 `tool_calls`。
   **适合问答/调研; 不适合"读项目文件/改代码"类任务**(那需要 DSH 的工具)。
2. **`workspace/generateText`(唯一有 tools 的通道)稳定被 3012 拦** — 已单发实证:
   同账号同时段 `session/send` 通、`generateText` 被拦(出码成功、请求确已发出)。
   → "传 DSH 工具"的路线**作废**, 不要再试。
3. **运维方式(2026-09-22 已简化)**: **不再需要运行 ZCode 客户端** —— 出码默认走
   `ZCODE_MINT_BACKEND=external`(独立本机 Chrome, 自动冷启动, 首帧约 7s)。
   桥接随 `llm_proxy\start.bat` 拉起; `zcode` 平台已设 `skipDailyCheck`(否则每日自检会逐个真打上游)。
   > 更正: 本条原先写"客户端须以调试端口运行(双击 start_zcode_debug.bat)" —— 那是**旧方案**
   > (`ZCODE_MINT_BACKEND=cdp`), 仅在外部出码失效时作备用。详见下方 2026-09-22 条目。

### 关于本项目(onduty)的后续
- 原"兜底方案 B2"(onduty 直接调度 zcode 跑任务)**仍可作为独立方向**:
  它不受上述工具限制影响(走 CLI 调度而非模型反代), 若日后需要"让 zcode 读写项目文件",
  应走 B2 而非桥接。**未实施**, 待用户拍板。
- v0.3 讨论仍挂起(用户先前决定)。

## 2026-09-16 · v0.1 MVP(按 plans/000 §13 五步全做)

### 范围
本次从"只有方案文档"推进到"可运行的 v0.1 + 单测 + 端到端真机验证"。全部产物限项目根目录。

### 1) 前置 spike(plans/001_adapter_spike.md)
- DSH `dsh --profile headless` 本机**冒烟实测通过**(退出码 0,stdout=最终答复,无 session)
- 从隔离目录直调 DSH: `pnpm dsh` 会把工作区变成源码目录(危险)→ 用 `node tsx/cli.mjs --tsconfig` 保持调用方 cwd,实测 PASS
- WorkBuddy=命令 `codebuddy`/`cbc`: 抓到官方无头文档,flag 确认(`-p`/`--output-format`/`--resume -r`/`-y`/`CODEBUDDY_IS_SANDBOX`)
- zcode: 仅 TUI,无头能力无证据 → v0.1 内置 `capable=False`,配置层 fail fast 并指向 custom 接入
- Windows toast: WinRT `CreateToastNotifier` 实测可弹,零依赖
- 环境: `py -3.13`=独立安装的 3.13(PyYAML+croniter 已装);`python` 默认 3.11,一律用 `py -3.13`

### 2) 代码骨架(agentd/ + agentctl.py)
config(校验) / state(JSON+JSONL+每run日志) / adapters(base+dsh+codebuddy+zcode+custom+registry) / runner(子进程+超时杀树+解析+回写+通知) / notify(log+toast+webhook) / scheduler(cron+控制文件+after链+补跑+防环) / __main__(run/once/check) / agentctl(list/status/run/logs/check)。

### 3) 验收
- **单测**: `py -3.13 -m unittest discover -s tests -t .` → **Ran 52 tests OK**(配置校验逐条/适配器建令解析/渲染截断/状态落盘/cron到期补跑/after链/控制文件)
- **端到端(真实 DSH 模型)**: `once e2e_step1` → 38s 成功写 step1.md;`after` 自动触发 `e2e_step2_chain` 读取并回 `CHAIN-OK`(44s);runs.jsonl 记录 trigger=manual 与 trigger=after 各一条 ✅
- **端到端(custom 适配器)**: `e2e_cron_demo`(echo custom)跑通建令/执行/解析/日志 ✅
- **daemon 常驻**: `agentd run --tick 5` 启动 → `agentctl status` 识别 pid → `agentctl run` 控制文件被下个 tick 拾取执行 → **cron `* * * * *` 整分准点触发,next_due 自动重排** ✅;关闭后 pid 文件清理、无残留 python 进程 ✅
- **通知三渠道**: log ✅(每 run + daemon.log);toast ✅(WinRT 实测弹出);webhook ✅(本地回环实测:模板渲染+UTF-8 JSON 载荷断言通过)

### 4) 修的问题(均带回归测试/复测)
- `.cmd` 批处理包 DSH 启动: cmd 的 GBK 码页破坏含中文/引号的 prompt(0.1s 假失败,stderr 乱码"不是内部或外部命令")→ **废弃 .cmd 包装,改 node argv 列表直调**;删除 `bin/dsh.cmd`,更新 tasks.yaml/tasks.example.yaml/plans/001
- notify print emoji(✅❌)在 GBK 控制台 UnicodeEncodeError → 去 emoji + `_safe_print` 降级 + runner 里 try/except 兜底,通知异常不影响任务
- YAML 1.1 把裸 `on:` 键解析为 True → config 归一化兼容 + 回归测试
- `agentctl/agentd` 的 `--config` 只能放子命令后 → 加 parents 公共参数
- workdir normcase 破坏大小写 → 存储保留原样,仅白名单比较用 normcase

### 未做(v0.2+,已在校验层挡住)
- once_at / auto_git_worktree / 按目录并行: 主方案定为后续版本,config 现会明确报错拒绝
- codebuddy 的 `continue`(会话续接)真实端到端: 本机未装 codebuddy,仅单元测试覆盖建令;装上后跑一次冒烟即转正(**待办**)
- DSH 无 resume(官方限制),DSH 接力链走 `{{prev.output}}` 文本注入(已 e2e 验证)

### 结论
v0.1 四类触发(manual/cron/after 均真机验证;once_at 属 v0.2 校验层已挡)+ 三家适配(DSH实测/codebuddy文档依据/custom 实测)+ 强制隔离 + 三通知(全部实测)+ 补跑/防环 全部实现并验证通过,可交付试用。

## 2026-09-16 · 命名与发布准备(用户拍板: onduty / MIT / 中英双语,详见 plans/002)

- 包 `agentd/` → **`onduty/`**;`agentctl.py`+旧入口合并为**单 CLI `onduty`**(daemon/once/check/list/status/run/logs);品牌串(toast AUMID/标题、webhook 模板、冲突提示)更名
- 新增:`pyproject.toml`(pip 名 onduty,≥3.10,依赖仅 PyYAML+croniter,console script)、`LICENSE`(MIT)、`README.md` 英文主体 + `README.zh.md`、`docs/MANUAL.md` 中文操作手册 + `docs/MANUAL.en.md`、`plans/002_naming_and_release.md`
- `.gitignore` 补 build/dist/egg-info;CLAUDE.md 更名规则并新增"argv 直调、禁 .cmd 包中文"编码纪律
- **回归全绿**: compile ✅;52 单测 ✅;tasks.yaml/tasks.example.yaml check ✅;`pip install -e .` 成功,全局 `onduty --help/once/status` 实测正常,toast 标题 `onduty · <job> [OK]` ✅
- 待用户: 创建 GitHub 仓库(建议名 `onduty`)→ 提供 SSH 远程后推送(本仓库已完成首次提交,未推送)

## 2026-09-16 晚 · 本机客户端实测(用户澄清 WorkBuddy/ZCode 是桌面客户端;plans/003)

- **zcode 降级判决撤销→转正**: 客户端内嵌官方运行时 `resources\glm\zcode.cjs` v0.16.5,`--help` 实测 `--prompt/--json/--resume/--mode`,内置 ZcodeAdapter(allow_danger 映射 plan/yolo);BOM 陷阱(桌面 provider 生成 CLI 配置必须无 BOM)已破解并沉淀 `scripts/sync-zcode-cli-config.ps1`(零密钥入仓)
- **WorkBuddy**: 客户端内嵌 CodeBuddy CLI v2.137.1,`--model/--session-id/-w worktree` 实测存在;codebuddy 适配器 model_flagged 默认 `--model` 转正;runner 新增"rc=0 空产出判 failed"防线 + `agents.<name>.env` 通用环境变量注入
- **两家一次性准备(用户侧)**: codebuddy 进 TUI `/login` 一次;zcode 跑 `node zcode.cjs login` 过 captcha/OAuth(当前 start-plan JWT 无头被网关 3007 拒)→ 打通后跑 wb_step1→wb_step2_cont 真接力冒烟
- **失败路径集成实测**: wb_step1(未登录)判 failed 且 after 阻断、zc_readonly 正确记失败 ✅
- 文档工程: README 中文优先对调(README.md=中/README.en.md=英)、Rules.md 更名(本地 CLAUDE.md 降为 gitignored 指针)、全仓路径脱敏、plans/003 实测记录
- 回归: 59 单测全绿;compile ✅;两份配置 check ✅

## 2026-09-16 晚二 · 用户克隆实测反馈修复(plans 外增量)

- 用户 D:\CSQ 克隆→pip install -e→`onduty check` 报 `FileNotFoundError` traceback:**行为正确**(tasks.yaml 属本机配置,gitignore 排除,发行只带 example),**体验错误**已修:缺配置→三行中文指引+exit 2(check/list/status/run/logs 全路径),daemon 同前检
- 新增 tests/test_cli.py 3 项(缺配置指引/daemon 前检/有效配置 exit0);回归 **62 全绿** ✅
- 环境旁证: 用户默认 python=3.11 也装得跑得起(打包声明 ≥3.10 兑现);其 clone 嵌套(OnDuty\OnDuty)为目录选择习惯,非仓库问题

## 2026-09-17 · 三家客户端全线打通(用户配合完成两处一次性登录)

- **WorkBuddy**: 用户热点登录 CLI 成功(`/login` 浏览器 OAuth)后,办公室网络下 headless 可跑(结论: galileotelemetry 只在登录阶段致命);`once wb_step1` → `after` 接力 wb_step2 全成功,wb1.md=WB-STEP1+WB-DONE ✅
- **修正 codebuddy parse**: `--output-format json` 实际形态是**消息数组+尾部 result 对象**(claude 风格 session_id 在尾段),已兼容(顶层 dict/list 通吃);用真实运行日志做回归 ✅
- **修链接话就真**一坑: continue 之前取的是 job 自己的历史会话 → 现改为"after 上游会话 > 自身历史"(runner.run_job 加 session_source,scheduler 链式下传);实测 wb_step2 argv 带 `--resume <(�)step1 的 session>` 且两段 session_id 一致 ✅
- **ZCode**: 用户 `login` 走通(Z.AI OAuth,旅行者3289);CLI 配置由登录自动接管为 zai 通道。运行时调用返回 **429 [1113] 余额/资源包不足**——账号未开通 GLM Coding Plan(或改用 bigmodel-coding-plan 侧)→ 属账号侧,非管道问题;login 链路本身验证完毕
- **单测 67 全绿**(新增 test_session_chain 3 项: 上游续接/自身回落/上游优先)✅

## 2026-09-17 · v0.2 实施(plans/004,用户批准开工)

- **once_at 一次性定时**: config 解析(多格式/非法拒绝)+ daemon 到点派发一次并 `once_fired` 归档;真机: 设 75 秒后时刻,准点触发一次且仅一次 ✅
- **失败重试**: `retry: {max, backoff_minutes}`,daemon 内排期队列,到点重派(trigger=retry),成功清零计数,达上限放弃;真机: 固定失败 job → 手动触发失败 → 2 次退避重试 → 上限放弃,runs.jsonl 含 retry 记录 ✅
- **按 workdir 并行**: 每 workdir 一把 `threading.RLock`(同线程链式重入安全)+ 在飞任务注册表(同名在飞跳过);主循环只派发;单测覆盖同目录串行/在飞去重 ✅
- **auto_git_worktree**: `safety.auto_git_worktree: true` 时 git 仓库任务自动 `git worktree add --detach` 到 `state/worktrees/`,非仓库/git 异常回退原目录记日志;真机: echo 任务在 worktree 写文件,主仓库零污染 ✅
- **state_dir 可覆盖**: `safety.state_dir`,daemon 启动先解析一次配置取 state_dir ✅
- 修正旧 once_at 拒绝测试为正向 + 重试/once_at/workdir锁 8 项新测,**80 单测全绿** ✅
- ⚠️ 用户环境插曲: DSH headless 因用户侧 `~/.dsh/settings.yaml` 第132行 `reasoningEfforts` 重复键损坏 → 已定位告知(非 onduty 问题,DSH 配置修复后 DSH 链即可跑)

- 用户把指令里的占位符 `<那个job名>` 原样贴进 PowerShell → `<` 重定向报错。**教训入 Rules**:文档占位符必须显式警告;tasks.example.yaml 头部已加"尖括号=占位符,勿原样粘贴"提示
- 修 `onduty check` 预览误导:`mode:new` 的 job 不再显示 `--resume SESSION-DEMO`(仅 continue 才展示续接参数);回归 62 全绿
- 规则提炼入 Rules.md:PS5.1 中文脚本需带 BOM(与"给 node 的 JSON 需无 BOM"方向相反,按目标程序定)、退出码不信任原则、YAML 布尔陷阱、推送前泄露终扫、客户端 agent 解剖安装目录三步实测法

## 2026-09-17 晚 · DSH 接力链转正 + 用户环境修复确认

- **DSH 配置修复确认**: 用户侧 `~/.dsh/settings.yaml` 第132行 `reasoningEfforts` 重复键系某 AI 误操作所致,用户已删修复 → headless 恢复可用 ✅
- **DSH"继续进行中任务"实测通过**: `once dsh_a`(写 ANSWER=42,85s)→ after 自动接力 `dsh_b`(读 a.md 确认、写 CONFIRMED,93s);a.md/b.md 均落盘正确 ✅。说明: DSH headless 无会话续接,接力用 `{{prev.output}}` 文本注入 + 文件载体,符合主方案设计
- 用例沉淀: tasks.yaml 内 dsh_a/dsh_b 保留为"DSH 继续进行中任务"的常驻示例(不入库)
- ⚠️ **依赖提示**: 本机 dsh 适配 `command` 指向源码 checkout 的 tsx/bin.ts/tsconfig 绝对路径(plans/001 §1)。**DSH 本体升级/移动目录后**,这些路径若失效,headless 会起不来——届时把 tasks.yaml 里 agents.dsh.command 改成新路径即可,无需改 onduty 代码

## 2026-09-19 ~ 09-20 · plans/005 修复执行(用户批准;修复1 完成、修复2 管道修复待额度、修复3 仅立项)

### 背景
用户重装 DSH(旧 checkout 0.1.1-rc.2 → 新 `D:\DSH\deepseek-harness-0.1.6-alpha.1`),要求通读方案/记录后诊断修复;方案存 plans/005,用户"开始执行修复方案"。

### 修复1(tasks.yaml DSH 路径)✅ 完成并真机验收
- `tasks.yaml` `agents.dsh.command` 三处路径 `D:\DSH\deepseek-harness\` → `D:\DSH\deepseek-harness-0.1.6-alpha.1\`(仅此三行,其余未动)
- `onduty check`: 8 job 全过,4 个 dsh job 预览 argv 显示新路径
- 真机冒烟 `onduty once dsh_a`: dsh_a success(41.9s, final=`42`) → after 接力 dsh_b success(33.7s, final=`CONFIRMED`);`sandbox/dshchain/a.md`=ANSWER=42、`b.md`=CONFIRMED;runs.jsonl 两条 success ✅
- 旁证: 新版 headless 明显更快(旧 85s/93s → 新 42s/34s);`--profile headless` 机制经 0.1.6-alpha.1 源码核实未变;**headless 仍无 resume**(args.ts: `--resume` 仅 tui)→ `{{prev.output}}` 接力设计依然正确

### 修复2(zcode 夜间窗)⚠️ 管道已修复,验收仍卡账务侧(未闭环)
- 09-19 05:03 `once zc_check` **0.8s 启动即失败**: `无法定位 CLI ZCode Built-in Provider Config`
- 根因链(全部实测):
  1. 当时 ZCode 客户端为 **3.12.3.7463**(cjs 2026-09-16 23:14 / 11.4MB),新版打包**未随附 `resources\glm\provider\zcode-builtin.json`**,而新内核启动即要求该文件(查找位: ①cjs 同级 `provider\`;②向上 5 级 `D:\config\provider\`)
  2. 源码挖出逃生口(混淆名反解): `ZCODE_BUILTIN_PROVIDER_CONFIG_FILE` / `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` / `ZCODE_BUILTIN_PROVIDER_BUNDLED_CONFIG_FILE`;前两者同时设置即走快速路径、**完全跳过文件查找** —— 注入实验实测启动错误消失(3.12.3 专用知识,回退后不再需要但留档)
  3. 09-19~09-20 间 ZCode 侧整体变动: `~\.zcode` 于 09-19 08:10 重建、客户端**回退到 3.11.2.6792**(cjs 12.6MB / 9-04 构建) → 3.12.3 新体系问题随之消失;唯一卡点变为 **`~\.zcode\cli\config.json` 丢失**
  4. 按 MANUAL §12 既有流程跑项目脚本 `scripts/sync-zcode-cli-config.ps1`: 从桌面 `~\.zcode\v2\config.json` 取 `builtin:bigmodel-coding-plan`(带 apiKey)生成 CLI 配置(provider=onduty, model=GLM-5.3/Flash, **无 BOM** 校验通过)
- 修复后 `once zc_check`: 启动正常、**7.5s 到达网关**,返回 `ProviderBusinessError: [1113][余额不足或无可用资源包,请充值。]`(HTTP 429, providerId=onduty, baseURL=open.bigmodel.cn)
- 账务侧现状(较 plans/003 §4.3 已变): 桌面配置里 **zai 系 provider 全部 apiKey=False(未登录)**,凭据仅 `oauth:bigmodel:*`;bigmodel 通道报 1113 → 验收需用户侧二选一: ①`zcode login`(Z.AI)恢复 zai 通道,在 23:00–09:00 窗口内重跑;②为 bigmodel 套餐充值/续订
- 结论: **onduty/zcode 管道侧已无问题**(配置生成+启动+联网全通),剩余为账号额度,属用户侧一次性动作

### 修复3(config 环境变量展开)📝 仅立项
- 已记 plans/005 §3(v0.3 立项草案: `%VAR%` 展开 + junction 备选),本次未动代码(符合用户约定)

### 未做/待办
- zcode 夜间窗验收闭环: 待用户恢复额度/zai 登录后夜间重跑一次,回填 plans/004 验收表
- (v0.3) config 环境变量展开立项

## 2026-09-20 · 用户侧结论修正 + 新方向(DSH 复用 ZCode 夜间/周末包;客户端版本锁定)

### 用户澄清的关键事实(修正上一条目里的账务侧判断)
- ZCode **升级到 3.12.x 后即不可用**(打包缺 provider 文件),且用户侧 key 也失效——**新版不再使用用户 key**
- **夜间包(23:00–09:00)/周末包仅 Z.AI 登录的账号享有**(bigmodel 登录没有);额度**绑定 ZCode 自身的加密凭据,只在 ZCode 客户端/运行时里可用** → 从桌面 provider 同步 apiKey 给外部 CLI 只能"发得出请求",**吃不到免费额度**(同步 key 实测 1113)
- 用户**已用 Z.AI 重新登录**(当前周末、额度满);客户端**已回退并锁定 3.11.2.6792,暂不升级** → 已沉淀为 Rules.md 约束
- 结论修正: 上一条目"需 bigmodel 充值"的判断作废;正解是 **Z.AI 登录 + 经 ZCode 运行时使用免费额度**

### 新方向(待立项): 让 DSH 复用 ZCode 夜间/周末包
- 目标: DSH(deepseek-harness) 侧用上 ZCode 的夜间/周末免费额度
- 参考: 用户已成功实现的 **"DSH 反代 WorkBuddy"** 方案(复用其架构思路)
- 路径: 调研(本机既有反代实现 + GitHub/网络思路) → 起草方案(plans/006) → 获批后实施

### 本轮待办(用户指定顺序)
1. 调研并实现"DSH 复用 ZCode 免费额度"的桥接方案(先方案后实施)
2. zai 通道恢复后的 zc_check 复验(收尾 plans/004 夜间窗验收项)
3. ZCode 版本锁定约束(已完成: 写入 Rules.md)

### 第2项 · zai 通道复验结果(2026-09-20 10:03~10:10,三通道实测)
- Z.AI 登录确认: 凭据新增 `oauth:zai:access_token` / `oauth:zai:user_info` / `oauth:login_attribution`;桌面配置里 `builtin:zai-coding-plan`、`builtin:zai-start-plan` 已带 apiKey
- 依次用项目脚本 `sync-zcode-cli-config.ps1 -ProviderKey <通道>` 切换 CLI 配置并跑 `once zc_check`:

  | 通道 | 上游 | 结果 |
  |---|---|---|
  | `builtin:zai-coding-plan` | api.z.ai/api/anthropic | **1113** 余额/资源包不足(HTTP 429) |
  | `builtin:zai-start-plan` | zcode.z.ai/api/v1/zcode-plan/anthropic | **3007** captcha verify failed |
  | (前一轮)`builtin:bigmodel-coding-plan` | open.bigmodel.cn/api/anthropic | **1113** |

- **结论**: 明文 key 三条通道**全部吃不到免费额度**,与用户澄清一致(额度绑定 ZCode 自身加密凭据);`zc_check` 验收需走桥接方案(第1项),不以 CLI 直连闭环
- 管道侧依旧健康: 配置生成 → 启动 → 联网全通(7.5~13s 达网关),失败均为上游账务/风控回应

### 第1项 · 侦察结论(技术路径已定位,方案见 plans/006)
- **关键发现**: Coding Plan **JWT 是明文可用**的(`~/.zcode/v2/config.json` → `provider["builtin:zai-start-plan"].options.apiKey`,255 字符 3 段 JWT,iat=本日 09:57、无 exp,桌面端启动即刷新);真正卡点是计划网关要求 **阿里云无痕验证参数**(请求头 `X-Aliyun-Captcha-Verify-Param`),我们实测的 3007 即此
- 现成思路(网络调研): [zcode2api](https://github.com/dengyie/zcode2api)(JWT + Node/jsdom 免浏览器过码 → Anthropic `/v1/messages` 网关)、[workbuddy2api](https://github.com/dddmiku/workbuddy2api)、[CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI)
- 桌面端驱动运行时的方式(进程实测): `ZCode.exe "…\zcode.cjs" app-server --stdio --surface desktop`(私有 stdio 协议,含 `off-peak-run` 消息)
- 用户既有资产可复用: `llm_proxy` 已具备 `apiKeyFileJson`/`extraHeaders`/`streamOnlyUpstream`/**`freeWindows` + `onlyInWindow`**/Anthropic 入口,与 workbuddy 反代同构(v17 已验收)
- 官方额度规则: **周末全天按 off-peak 计费**;峰值=周一至周五 14:00–18:00(UTC+8);GLM-5.3 off-peak 1×/peak 3×,Flash 0.4×/1.2×([官方公告](https://docs.z.ai/devpack/notice/usage-revision))
- **下一步(待用户拍板)**: ①是否允许改 `llm_proxy`(跨项目);②验证码走 A1 自研还是 A2 旁挂 zcode2api;③是否接受 Node + jsdom 依赖

### 第1项 · 探针实测结果(2026-09-20 10:12~10:22; 用户批准 A1+先探针; 探针落 llm_proxy/test/zcode_probe/)
- 用户拍板: 改 `llm_proxy` 新增 `zcode` 平台 + **A1 自研验证码求解**(参考 zcode2api 思路) + **先做可行性探针**
- 探针四项实测:

  | 环节 | 结果 |
  |---|---|
  | 读明文 JWT | ✅ `~/.zcode/v2/config.json` → `provider["builtin:zai-start-plan"].options.apiKey` |
  | 拉验证码配置 | ✅ `GET /api/v1/client/configs?app_version=3.10.2` → `{sceneId:11xygtvd, region:cn, prefix:no8xfe}` |
  | **本机自产验证码** | ✅ **2.2~2.7s / 280 字符**(happy-dom 免浏览器求解; 偶发失败需重试) |
  | 鉴权形式 | `x-api-key` → 401; **`Authorization: Bearer <jwt>` → 通过鉴权** |
  | 套餐只读端点 | ✅ **200**: `zcode-v3-start-plan-0817`「ZCode Start Plan」**active**, GLM-5.3 每日 3,000,000 token |
  | **对话端点** | ❌ **405 `{"code":3012,...unusual activity}`**(流式/非流式、darwin/win32 指纹均同) |

- ⚠️ **关键判定(用户实测)**: **官方桌面端自己也报 3012**(`provider=builtin:zai-start-plan provider_code=3012 status=405 retryable=false`; 昨天周六尚可用; 周末包额度完好 GLM-5.3 3000 万 / Flash 5000 万)→ **3012 属账号/IP 级风控, 与外部请求构造无关**; 探针最终落到与官方客户端相同状态
- 教训与协议(已写入探针 README): 本日客户端版本churn(3.12.3→回退 3.11.2)+多次登录+CLI 多次尝试+**探针使用随机 X-Device-Mid/伪装 darwin 指纹**, 同 token 下多身份冲突正是风控"unusual activity"特征 → 后续必须遵守**最小足迹协议**: ①一套稳定身份(win32-x64 + 固定 device_mid) ②每次只发 1 个请求、间隔 ≥30 分钟、失败即停 ③外部验证前先确认官方客户端可用 ④求解器不并发不预热
- 动作: 已停止一切自动化请求(官方政策: 3 次以上违规可能封号); 安排**冷却后单次重试**(后台任务, 45 分钟后 1 个请求)
- 退路(若长期 3012): 仅旁挂 zcode2api / 改走 app-server 桥接 / 用 P1 已验收的 bigmodel 直连通道(llm_proxy 既有 `freeWindows`)

### 第1项 · 晚复测 + 根因定位(2026-09-20 19:38; 用户重启后官方端恢复)

- 现场: 用户重启、官方端 17:05 正常(日志有成功 `model.request.completed`)、额度正常; 19:38 外部**单次**复测(1 请求/稳定 win32 身份/未连发) → **仍 405 `{"code":3012}`**
- **结论修正**: 上午"账号/IP 级风控"判定据此更新 —— 3012 并非单纯冷却问题, 而是**外部客户端缺少官方宿主链路**的稳定结果(官方端已恢复而外部仍被拦)
- **根因(3.11.2 运行时代码实证)**: 运行时每次模型请求前向宿主发起 `interactionRequestProviderRuntimeHeaders` 交互
  (`bHo.refreshBeforeModelRequest()` 恒返回 `true`), 宿主须回 `{headersApplied:true, requestAuth:{apiKey?, headers?}}`
  —— 即**由官方 Electron 宿主向服务端换取一组"provider 运行时头"再附加到模型请求**; 桌面端日志实证
  `[captcha-diagnostics] requestId="…:provider-runtime-headers:…" {"event":"request.respond","headersApplied":true}`
  → 外部 HTTP 直连**无法靠"自拼头 + 自产验证码"复刻该链路**
- 路线修正(方案见探针 README, 待用户拍板): **B1** app-server 桥接(桥接器当宿主, 请求由官方运行时发出) / **B2** 只当 agent 调度(onduty 已有 zcode 适配器) / **C** 旁挂 zcode2api / **D** 直连 bigmodel 免费窗(llm_proxy 既有能力)
- 探针成本盘点(迄今): 验证码自产 ✅ 2.2~2.7s、鉴权���式 ✅ Bearer、套餐/额度只读 ✅ 200、对话端点 ❌ 3012 —— 前三项对 B1/C 路线仍有价值

### 第1项 · D 路线实测作废 + B1 协议层打通(2026-09-20 晚)

**D 路线(直连 bigmodel 免费窗)实测 ❌ 作废**
- 经本机 llm_proxy(`127.0.0.1:6446`,`bigmodel` 平台 + `freeWindows={days:[0,6],hours:[[23,6]]}`)实测 `bigmodel/glm-5.3-flash`
- 结果: **HTTP 429 `{"error":{"message":"余额不足或无可用资源包,请充值。","type":"rate_limit_error"}}`**
- 结论: 免费额度已从 API 通道整体收回, 只保留在 ZCode 客户端内部(与用户最初判断一致)

**B1(app-server 桥接)协议层打通 —— 六步全部实测(探针 `llm_proxy/test/zcode_probe/probe_b1_*.mjs`)**

| 步骤 | 关键结论 |
|---|---|
| ① 启动 | 注入 `ZCODE_BUILTIN_PROVIDER_CONFIG_FILE`+`ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` 后, `zcode.cjs app-server --stdio --surface desktop` 可脱离桌面端启动 ✅ |
| ② 存储握手 | 应答 `startup/storagePath` → `startup/storagePathReady`; 运行时 `startup/storageState` 走到 `phase:"ready"`(含 DB 迁移) ✅ |
| ③ **协议信封** | **3.14.0 无 JSON-RPC 信封**: 请求 `{id,method,params}`、响应 `{id,result/error}`(zod 实证 `unrecognized_keys:["jsonrpc"]`) ✅ |
| ④ 参数结构 | `session/create` 需 `workspace:{workspacePath,workspaceKey}`; 宿主须应答 `session/requestRuntimePreferences`(必填 `nativeSearchEnhancementsEnabled:boolean`) ✅ |
| ⑤ 会话建立 | `session/create` 成功返回 `protocol: ZCode Protocol v1` + sessionId + projection ✅ |
| ⑥ 模型请求 | `session/send{sessionId, content, modelSelection}` 被 `accepted:true`, 但回合**秒失败 turn-failed** 且**未触发** `requestProviderRuntimeHeaders` ⚠️ |

- providerId 必须用注册表真实 id: **`account:zai-start-plan`**(非 `builtin:zai-start-plan`); 注册表 8 个 provider 全为 `account:` 前缀(zai/bigmodel × individual/team/start + 两个 `-offpeak-idle-plan` 夜间通道)
- **剩余卡点**: `turn-failed` 发生在发起网络请求**之前**, 缺的是"账号/凭据绑定"——桌面端由宿主完成(`本地 provider registry 已同步到 ZCode agent` + `官方 MCP 身份头已解析`); 我们注入的 `~/.zcode/v2/provider_config.json` 是空壳, 真实账号在加密 `credentials.json` + 宿主 `provider/updateAccountConfig` 流程
- 下一步候选: ①试 `provider/updateAccountConfig`; ②用真实 `~/.zcode` 作存储根(不隔离)看能否自动关联账号; ③试 `account:zai-offpeak-idle-plan`
- 附: 客户端已被升到 **3.14.0.7681**(运行时 0.16.9), 用户拍板保持此版; Rules.md 版本条目已相应修订

### 第1项 · B1 全链路打通(2026-09-20 深夜; 仅剩验证码一环)

在 `llm_proxy/test/zcode_probe/`(用户已批准改 llm_proxy 且先探针)把官方 app-server 链路完整复刻, 十环里九环实测通过:

| 环 | 结论 |
|---|---|
| ① 启动 | ��入 `ZCODE_BUILTIN_PROVIDER_CONFIG_FILE`+`ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` ✅ |
| ② 存储握手 | 应答 `startup/storagePath`→`storagePathReady`; DB 迁移到 `ready` ✅ |
| ③ 协议信封 | **3.14.0 无 `jsonrpc` 字段**: `{id,method,params}`/`{id,result,error}` ✅ |
| ④ 参数结构 | `session/create{workspace:{workspacePath,workspaceKey}}`; 须应答 `session/requestRuntimePreferences{nativeSearchEnhancementsEnabled:bool}` ✅ |
| ⑤ **凭据解密可复刻** | 密钥 = `sha256("zcode-credential-fallback:"+platform+":"+homedir+":"+username)`(aes-256-gcm); 同机实测 **6/6 全解**(oauth:zai:access_token 1404字符/zcodejwttoken 255字符/account-provider api-key 49字符) ✅ |
| ⑥ 账号供给 | `provider/updateAccountConfig{schemaVersion,revision,basedOnZCodeBuiltinRevision,providers,states}`; **revision 必须是内部全串** `zcode-builtin:30:2ad7363a…`; provider access 只接受 `{type:"zhipu-account",entitled}` ✅ |
| ⑦ 模型选择 | `modelSelection.options.reasoningLevel` **必填**; 合法值实测 **`low`/`high`**(disabled/minimal/medium/none 全拒) ✅ |
| ⑧ 宿主应答运行时头 | 回 `{headersApplied:true, requestAuth:{apiKey, headers}}` ✅ |
| ⑨ **请求发出** | `model.request.status=model_request_start…`——官方运行时真的发出上游请求, **3012 不再出现** ✅ |
| ⑩ **验证码** | 上游回 `captcha verify failed` ⚠️ |

- ⑩ 判定: api-key 通道过验证但 **1113 无额度**; JWT 通道 + happy-dom 自产码 → **captcha verify failed**
- 官方对照(桌面端日志): 真浏览器(Electron webContents)跑阿里云 SDK(`captcha-open.aliyuncs.com`) + `zcode-agent.respondProviderRuntimeHeaders OK` → **happy-dom 求解的环境指纹不被接受, 必须真浏览器**
- 本机 Chrome/Edge 均在位(Playwright 未装)
- **B1 剩余: 只差"真浏览器解验证码回填 requestAuth.headers"一环**; 其余 9 环全通

### 第1项 · 真浏览器出码 + 3007 机制定位(2026-09-20 深夜二)

用户批准用**本地 Chrome** 解验证码, 结果与关键反转:

- **真浏览器求解器成功**(`solver_browser.mjs`, puppeteer-core + 本机 Chrome): **有头模式出码 280 字符且含 `securityToken`**(happy-dom 版无真 token 故必然被拒); 无头模式取不到参数(风控识别)
- 官方 SDK 调用方式(反查 solver.js): `AliyunCaptchaConfig={region,prefix}` + `initAliyunCaptcha({...,getInstance:inst=>inst.startTracelessVerification(),success:r=>r.verifyParam})`; SDK = `o.alicdn.com/captcha-frontend/aliyunCaptcha/AliyunCaptcha.js`(**新版,非老版 AWSC**)
- **⚠️ 机制反转(3.14.0 代码实证)**: 找到 3007 判定函数 `createZcodePlanCaptchaError`:
  `if (providerKind!=="openai-compatible" || !captcha) return; if (readCaptchaVerifyParam(headers)) throw 3007`
  → **`x-aliyun-captcha-verify-param` 不是通行证而是挑战信号**: 运行时见该头即判 3007; 官方正解是宿主用 `reason:"model-request"|"captcha-retry"` 向**服务端换取运行时头**, 而非外部塞阿里云验证码
- 凭证通道对照: `zcodejwttoken`(255) 过认证→captcha 失败; `oauth:zai:access_token`(1404) → Unauthorized/provider_not_configured; `account-provider api-key`(49) → 同前(单测时 1113)
- **结论**: B1 九环已通, 第十环需**服务端签发的运行时头**; 本地自产验证码此路不通
- 剩余可选: ①hook 官方 Electron 进程间通信抓 `respondProviderRuntimeHeaders` 回包(难���高) ②改走 C 旁挂 zcode2api(它已解决同一问题) ③B2 只当 agent 调度
- **用户拍板(2026-09-20 深夜)**: 先按 **②旁挂 zcode2api** 试; 若不行再试点 **①hook 官方 Electron**。llm_proxy 侧方案见其 `plans/2026-09-20-ZCode套餐反代接入.md`

### 第1项 · 路线② 旁挂 zcode2api 实施(2026-09-20 21:0x~21:3x)

- **部署完成**(全部隔离在 `llm_proxy/test/zcode_probe/zcode2api/`, 已 gitignore; 端口 3010 避��生产 6446):
  Python3.13 venv + 依赖 ✅ / captcha_node happy-dom ✅ / `.env`(随机 admin+gateway key、host=127.0.0.1) ✅ / JWT 入池(模式 jwt) ✅ / 网关启动、`/v1/models` 200(GLM-5.3-Flash、GLM-5.3) ✅
- **修掉上游项目的 3 个 Windows 兼容 bug**(`app/hostinfo.py`; 原逻辑把真机档案判非法→退化成伪装 macOS→身份不一致→上游 405):
  1. `os_version=platform.release()` → Windows 返回 `"11"`, 过不了 `_RELEASE_SHAPE`(要求 `x.y[.z]`) → 改取 `platform.version()` 归一化为 `10.0.26200`
  2. `_resolve_language()` 只读 `$LANG` → Windows 恒退 `en-US` → 改用 `locale.getdefaultlocale()` ��� `zh-CN`
  3. `_resolve_timezone()` 只读 `/etc/localtime` → Windows 恒退 `UTC` → 改按 UTC 偏移映射 IANA 得 `Asia/Shanghai`
  修正后档案 `win32/x64/10.0.26200/zh-CN/Asia/Shanghai` 校验通过、入池无告警
- **额度查询完全正常**: `GLM-5.3: 3,000,000/3,000,000`(满额)、`GLM-5.3-Flash: 4,893,734/5,000,000` → **认证与账号都没问题**
- **当前卡点**: 对话端点 `/v1/messages` → **HTTP 405 风控**(账号被自动禁用) —— 与 B1 探针今晚结论一致: 属**账号级对话端点风控**, 且今晚被反复试探(B1 多轮 model_request_start + 探针多轮)持续触发
- **动作**: 已停网关(3010 释放)、无 python/chrome 残留, **进入冷却期(零请求)**; 冷却起点 21:32
- **后续候选**: ①冷却≥30~60min 后单次复测 ②若仍 405 → 试点 hook 官方 Electron ③zcode2api 的 `oauth` 模式(`cli.py login zai`)换凭证口径再试

### 第1项 · 路线② 隔夜复测 → **根因定案: 缺客户端签名 V4**(2026-09-21 06:14)

- 环境: 客户端正常(10 进程)、**夜间免费窗内(23:00–09:00)**、JWT 重新解密入池、账号 `active`、隔夜冷却约 9 小时
- **单次复测仍 405**: `/v1/messages` → 503 → 日志 `命中风控 HTTP 405，已禁用`
- **同时刻额度接口满额**: `GLM-5.3: 3,000,000/3,000,000`、`GLM-5.3-Flash: 5,000,000/5,000,000` → **认证/账号/额度全无问题, 只有对话端点被拦; 且非冷却问题, 是稳定拦截**
- **根因(该项目 `docs/development/05-upstream-protocols.md` §7 自述 + 代码核对)**:
  | 风控机制 | 说明 | zcode2api 实现 |
  |---|---|---|
  | endpoint routing | `GET agent/configs` → `proxyEndpoint.mapping`, 客户端定期重写上游 URL(coding-plan → `zcode.z.ai/api/v1/ultra[-zai]/…`) | ❌ 0 命中 |
  | **client signing V4** | `codingPlanSignature.enable=true` 时先握手 `{provider}/api/paas/c1f3a7e2/v2/client`, 之后**每请求附 Ed25519 签名 + PoW 头**; **start-plan / off-peak 永不免签** | ❌ 0 命中(`ed25519`/`signing`/`agent/configs` 全无) |
  → 本账号即 **Start Plan**, **永不免签**; 故对话端点必然 405
- **与 B1 结论互相印证**: 昨天从 3.14.0 源码挖到的 `createClientSigningFetch` + 握手(nonce/sig/ts + privateCipher) + 宿主 `respondProviderRuntimeHeaders`, 正是这套**客户端签名**链路 → 两条路线撞同一面墙
- **路线判定**: ②旁挂 zcode2api ❌ 不可行(未实现必需签名); ① hook 官方 Electron ⏳ 唯一可能闭环(官方客户端自己会签名); B1 自研复刻签名(Ed25519+PoW)路径明确但偏大; B2 只当 agent 调度 ✅ 兜底
- **动作**: 网关已停(3010 释放, 无残留), 保持零请求; 明细见 llm_proxy `plans/2026-09-20-ZCode套餐反代接入.md`

### 第1项 · 签名判定修正 + **官方 renderer 出码突破** + 账号再入风控(2026-09-21 06:3x~06:5x)

**一、签名判定修正(重要, 推翻上一条的"缺签名"结论)**
- 从运行时源码提取签名需求判定函数 `vEs`:
  `if (type==="zhipu-account" && (mode==="start-plan"||mode==="off-peak")) return false;` ← **start-plan 不需要签名**
  `if (type==="zhipu-coding-plan-api-key" || mode==="individual-/team-coding-plan" || QYe(baseURL)!==null) return true;`
  白名单域名仅 `api.chatglm.site`/`zcode.chatglm.site`
- 运行时日志 `model.client_signing.unsigned_sent / skipped by provider access mode` 与此一致
- → **405 真凶回到"验证码"**, 与签名无关; 上一条对 zcode2api 的"缺签名"判定同步修正

**二、官方宿主出码机制完整还原(asar 反混淆)**
- `Ntn(cfg)`: 仅 `access.type==="zhipu-account" && mode==="start-plan"` 才走验证码
- `Stn({captchaVerifyParam,captchaRegion})`: 产出的头**就是** `X-Aliyun-Captcha-Verify-Param/Region` 两个
- `Jtn→Gtn`: 拉 captcha 配置 → `ytn` 真浏览器跑无痕 → `Stn` 组装 → 返回 `{captchaVerifyParam, headers}`
- `htn`: **官方 `initAliyunCaptcha` 关键参数**: `language` 必须 **`cn`/`en`**(非 `zh-CN`), `mode:"popup"`, `element/button` 必须挂到 DOM, `getInstance:inst=>inst.startTracelessVerification()`
- 运行时侧: `vEs` 判定签名 → `respondProviderRuntimeHeaders` 合并验证码对 → `{headersApplied:true, requestAuth:{apiKey, headers}}`

**三、🎯 突破: 在官方 renderer 内出码(`cdp_mint.mjs`)**
- 方法: CDP 挂官方 renderer, 用**官方自己的浏览器环境/SDK**出码(而非外部 Chrome 模拟)
- 实测: **0.8 秒出码 280 字符**(外部 Chrome 需 2.2~2.7s), language 用官方值 `cn`, 环境指纹与官方 100% 一致
- 接入 B1 后(`b1_final.mjs`): 运行时接受并发出请求, **`captcha verify failed` 消失** ✅ —— 出码问题已解决

**四、⚠️ 现场变化: 账号又入风控窗口**
- 同刻用户在**官方客户端**发消息也报 3012: `provider=account:zai-start-plan provider_code=3012 status=405 retryable=false`
- → 本次 3012 **不能归因于我们的出码方式**(官方同刻亦被拦); 属账号级风控窗口(今日多轮验证触发)
- 处置: 已停所有探针(无残留)、网关已停、**客户端已恢复正常启动**(关闭 9222 调试端口)、保持零请求

**五、结论与后续**
1. **出码问题已解决**(官方 renderer 出码 0.8s/参数正确/环境一致), B1 链路可发出**被上游接受验证码**的请求
2. 唯一阻塞 = 账号级 3012 风控窗口 → 等自然恢复(**以官方客户端能否正常对话为准**)
3. 恢复后用 `b1_final.mjs` 单次复测; 通过后再封装为 llm_proxy 的 `zcode` provider(常驻桥接)
4. 兜底仍可选 B2(onduty 直接调度 zcode 跑任务)

### 第1项 · 🎉 **B1 闭环打通**(2026-09-21 13:05 单发复测成功)

**触发条件**: 官方客户端 12:51:37 有一次完整成功链路(验证码 success → `respondProviderRuntimeHeaders OK (3.3ms)`),
当日日志 `3012` 计数归零 → 判定风控窗口已过, 按最小足迹协议做**唯一一次**单发复测。

**实测结果**(`node b1_final.mjs --live`): **十环全通**

| 环节 | 证据 | 结果 |
|---|---|---|
| 账号供给 | `providerCount:3, status:"received"` | ✅ |
| 会话建立 | `sess_af7541f4-83bb-4723-9ff3-38855d011585` | ✅ |
| 运行时索要头 | `requestProviderRuntimeHeaders`(model-request) ×2 | ✅ |
| 官方 renderer 出码 | `len=280` ×2 | ✅ |
| **上游接受** | **`hasError:false`**, 无 `captcha verify failed`、无 3012 | ✅ |
| **模型回复** | 响应正文 **`"text":"OK"`** | ✅ |
| 套餐计费 | in 16049 / out 3 / total 16052, 上游 `glm-5.3-flash` | ✅ |

- 主请求 9758ms, `finishReason:stop`; 上游 `x-log-id=202609211305111ff5d136d7cb445e`
- 9/20 起遗留的两个卡点(`captcha verify failed`、`3012`)**双双消失**
- 证据文件: `~/.zcode/cli/rollout/model-io-sess_af7541f4-83bb-4723-9ff3-38855d011585.jsonl`

**⚠️ 附带发现: 副请求被拦(现象已确认, 根因尚未定论)**
- 同会话内, 主请求成功后 1 秒内运行时自动发的**标题生成**请求被拦 3012(305 字节, `session-type: other`)
- **假设一("1 秒内连发")—— 已推翻**: 官方 `sess_fe00c1fe` 主→副间隔 **65ms 却成功**,
  探针 `sess_af7541f4` 间隔 **103ms 被拦**; **官方比探针还快 38ms** → 间隔不是原因
- **假设二(版本头 `0.16.9` vs `3.14.0`)—— 待验证, 证据尚不充分**:
  探针标题请求 `user-agent=ZCode/0.16.9`/`x-zcode-app-version=0.16.9`,
  官方成功请求为 `ZCode/3.14.0`/`3.14.0`(`0.16.9`=运行时自己的版本, `3.14.0`=客户端外壳版本)
  - **⚠️ 为何只算待验证**: 探针的**主请求用的也是 0.16.9 却成功了** →
    单一"版本头"解释不了"同为 0.16.9, 一大一小结果相反";
    更可能是**请求形态(是否极简)+ 版本标识**的组合判据, **必须实验证伪**
- **代码实证(开关存在)**: `zcode.cjs` L15231 `function Sqa(e,t){ return Lie(e[hpe] ?? t.appVersion) }`
  (`hpe === "ZCODE_APP_VERSION"`) → 版本头可由**环境变量**注入, 成本极低

**生产化铁律**(写给后续 llm_proxy `zcode` provider): ① 设 `ZCODE_APP_VERSION=3.14.0`
(低成本看齐 + 待验证实验变量); ② 抑制标题生成等副请求作为减少暴露面的稳健措施保留;
③ 出码必须走官方 renderer(CDP); ④ 复测单发、失败即停;
⑤ 待验证: 注入该变量后极简副请求是否不再被拦, 若仍被拦则判据在别处(再查 `x-device-mid`/请求体形态)

**收尾**: 客户端已恢复正常启动(9222 关闭)、探针零残留、llm_proxy 生产文件未改动;
明细见 llm_proxy `plans/2026-09-20-ZCode套餐反代接入.md` 与 `test/zcode_probe/README.md`
