# onduty 项目规则（Rules.md）

> 叠加全局规则（`D:\ClaudeData\CLAUDE.md`），冲突时以本文件为准。

- **命名**: 产品/pip 包/CLI 均为 `onduty`（拍板见 plans/002）；本地目录名保持 `D:\ClaudeData\agent_daemon`（工作路径约束，与 repo 名解耦）。
- **工作范围**: 仅限 `D:\ClaudeData\agent_daemon\` 内，禁止改动其他项目。
- **技术栈**: Python 3.13（打包声明 ≥3.10）；依赖最小化（仅 PyYAML、croniter，引新包先说明理由）；CLI 单入口 `onduty/cli.py`（daemon/once/check/list/status/run/logs）。
- **方案先行**: 方案文档一律写 `plans/` 目录，编号递增；代码改动须方案获批后动手。
- **运行产物**: `state/`、`sandbox/`、`tasks.yaml` 为运行态/用户配置，不入库；排查先看 `state/` 日志。
- **数据源**: 本项目不涉及行情数据源，全局数据源约定不适用。
- **适配纪律**: 内置 dsh / codebuddy（workbuddy 别名）/ zcode / custom；各家 CLI 能力结论以 `plans/001、003` 本机实测为准，禁止凭印象写 flag。
- **Windows 编码纪律**: agent 命令行一律 argv 直调，禁止 .cmd/.bat 包装中文/引号 prompt；写 JSON 给 node 读必须**无 BOM** UTF-8（zcode 实测 BOM 会被拒）；落盘文件统一 UTF-8。
- **PowerShell 脚本编码**: 脚本内含中文的 `.ps1` 在 PS5.1 下必须存成**带 BOM** UTF-8（无 BOM 会被按 ANSI 解析，中文注释可能吞掉下一行代码——make-social-preview.ps1 实测）；与上一条方向相反，按目标程序定。
- **退出码不信任原则**: 新 agent 接入前必测三种路径——成功输出形态、失败输出形态、**未登录/认证失败时的退出码与输出**（codebuddy 实测：未登录报错却 exit 0）。runner 已有"成功+空产出判 failed"防线兜底，接新 CLI 仍要人工核。
- **YAML 陷阱清单**: 裸 `on/off/yes/no` 键或值是布尔（schedule.on 已做归一化）；文档示例中的 `<占位符>` 必须标注"替换后运行"——用户整段粘贴会被 shell 当重定向符（PS 实测 `<` 报错）。
- **推送前纪律**: 每次 push 前跑泄露终扫（`git ls-files` + Select-String 本机用户名/盘符路径）；运行态（state/sandbox/tasks.yaml）零入库。
- **客户端类 agent 侦查方法**: 先解剖安装目录（`resources\app.asar.unpacked\cli\`、`resources\glm\*.cjs` 等常内嵌完整 CLI），别轻信 npm 文档视野；能力判定按"--help 清点 → 最小无工具 prompt → 失败形态"三步实测。
- **ZCode 版本纪律（2026-09-20 晚修订）**: 客户端**当前版本 3.14.0.7681（运行时 0.16.9，cjs 14.8MB / 9-19 构建），用户拍板保持此版、不要再手动升级/降级**。历史教训: ①3.12.3 起打包缺失 `resources\glm\provider\zcode-builtin.json`，`--prompt` 路径启动即报"无法定位 CLI ZCode Built-in Provider Config"（0.8s 退出）；②升级会重建 `~\.zcode` 并清掉 `~\.zcode\cli\config.json`（随后报 Model config is missing）；③客户端版本churn（升级/回退/多次登录）会被上游判定 unusual activity（3012）。版本相关恢复手段: ①`scripts/sync-zcode-cli-config.ps1` 重建 CLI 配置（无 BOM）；②若缺 provider 文件，注入 `ZCODE_BUILTIN_PROVIDER_CONFIG_FILE` + `ZCODE_PERSONAL_PROVIDER_CONFIG_FILE` 绕过文件查找（3.12.3 实测有效）。**动版本前必须先确认目标版本可用性，且改动前先在项目内记录方案。**
- **ZCode 免费额度事实（2026-09-20 用户澄清）**: 夜间包（23:00–09:00）/周末包**只有 Z.AI 登录的账号有**（bigmodel 登录没有）；且额度用的不是用户明文 key，而是**绑定 ZCode 自身的加密凭据**——从桌面 provider 同步 apiKey 给外部 CLI 的旧路子只够"能发出请求"，**吃不到夜间/周末免费额度**（同步 key 实测报 1113）。要复用该额度必须经 ZCode 运行时中转（方向: 参考"DSH 反代 WorkBuddy"的既有成功方案，待立项）。
- **输出语言**: 文档中文优先（README.md/手册中文，英文版并存），与用户交流用中文。
