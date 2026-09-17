# verlog.md — agent_daemon 改动与验收记录

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

- 用户把指令里的占位符 `<那个job名>` 原样贴进 PowerShell → `<` 重定向报错。**教训入 Rules**:文档占位符必须显式警告;tasks.example.yaml 头部已加"尖括号=占位符,勿原样粘贴"提示
- 修 `onduty check` 预览误导:`mode:new` 的 job 不再显示 `--resume SESSION-DEMO`(仅 continue 才展示续接参数);回归 62 全绿
- 规则提炼入 Rules.md:PS5.1 中文脚本需带 BOM(与"给 node 的 JSON 需无 BOM"方向相反,按目标程序定)、退出码不信任原则、YAML 布尔陷阱、推送前泄露终扫、客户端 agent 解剖安装目录三步实测法
