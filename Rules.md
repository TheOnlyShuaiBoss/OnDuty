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
- **输出语言**: 文档中文优先（README.md/手册中文，英文版并存），与用户交流用中文。
