# verlog.md — agent_daemon 改动与验收记录

## 2026-09-16 · v0.1 MVP(按 plans/000 §13 五步全做)

### 范围
本次从"只有方案文档"推进到"可运行的 v0.1 + 单测 + 端到端真机验证"。全部产物限 `D:\ClaudeData\agent_daemon\`。

### 1) 前置 spike(plans/001_adapter_spike.md)
- DSH `dsh --profile headless` 本机**冒烟实测通过**(退出码 0,stdout=最终答复,无 session)
- 从隔离目录直调 DSH: `pnpm dsh` 会把工作区变成源码目录(危险)→ 用 `node tsx/cli.mjs --tsconfig` 保持调用方 cwd,实测 PASS
- WorkBuddy=命令 `codebuddy`/`cbc`: 抓到官方无头文档,flag 确认(`-p`/`--output-format`/`--resume -r`/`-y`/`CODEBUDDY_IS_SANDBOX`)
- zcode: 仅 TUI,无头能力无证据 → v0.1 内置 `capable=False`,配置层 fail fast 并指向 custom 接入
- Windows toast: WinRT `CreateToastNotifier` 实测可弹,零依赖
- 环境: `py -3.13`=D:\Python(PyYAML+croniter 已装);`python` 默认 3.11,一律用 `py -3.13`

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
