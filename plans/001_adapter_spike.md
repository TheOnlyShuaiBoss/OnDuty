# 001 适配器前置 spike 实测记录

- 日期: 2026-09-16(主方案 §10 要求,动工第一步)
- 结论速览: **DSH ✅实测通过(仅 new);WorkBuddy/codebuddy ✅文档证据充分(new+resume,本机未装);zcode ❌无无头证据(降级,用 custom 适配兜底);toast/cron/凭据环境 ✅全部就绪。**

## 1. DSH —— 本机实测通过

| 项 | 结果 |
|---|---|
| 调用 | `dsh --profile headless "<任务>"`,退出码 0/1,stdout=最终答复文本 |
| 冒烟 | 两次实测(31s/一次即时):输出"好"/"PASS",无工具调用 ✅ |
| 会话续接 | ❌ 无。官方 Known Limitations 明示 one-shot;`--resume` 仅属 tui profile。headless 不输出 session_id → `parse` 恒得 session=None |
| 凭据 | `C:\Users\a2018\.dsh\.credentials.yaml` 存在,无需 .env ✅ |
| profile | `C:\Users\a2018\.dsh\profiles\headless` 已初始化 ✅ |

**坑与解法(实测发现)**: 本机 PATH 无 `dsh`;`pnpm dsh` 只能在 checkout 目录跑,而 **agent 的 workspace=进程启动目录**——直接 `pnpm dsh` 会把 DSH 源码目录变成 agent 工作区(危险)。从其他目录用 node+tsx 直调 `apps/cli/src/bin.ts` 会因 tsconfig paths 不锚定而报 `@deepseek-ai/cordis` 导出错误。
✅ 解法(已实测): `node <tsx>/dist/cli.mjs --tsconfig <checkout>/tsconfig.json <checkout>/apps/cli/src/bin.ts --profile headless "<任务>"` —— 保持调用方 cwd 作为 workspace。
⚠️ 二次教训(实施期发现): 曾把上述命令封装进 `bin\dsh.cmd` 批处理,但 **cmd.exe 按 GBK 码页逐行解析批处理,含中文注释/中文 prompt/内嵌引号时会解析错乱**(实测 0.1s 假失败,stderr 乱码"不是内部或外部命令")。已废弃 .cmd 包装,Python 侧一律用 **argv 列表直调 node**(写入 tasks.yaml `agents.dsh.command`,见 tasks.example.yaml)。

适配器能力声明: `capable=True, supports_resume=False, 模型由 profile 默认(DSH_HOME 配置),prompt 走单 positional 参数`。

## 2. WorkBuddy(CodeBuddy CLI,命令 `codebuddy`/`cbc`)—— 文档证据充分,本机未装

- npm 包: `@tencent-ai/codebuddy-code@2.151.0`,bin=`codebuddy`,`cbc`
- 官方无头模式文档(www.codebuddy.cn/docs/cli/headless,已抓取正文)关键 flag:
  - `-p / --print "查询"` 非交互
  - `--output-format text|json|stream-json`
  - `--resume, -r <session_id>` 会话续接 ✅;`--continue, -c` 继续最近会话
  - `-y / --dangerously-skip-permissions`: **无头模式必需**,否则文件读写/命令执行被阻止;HIGH/CRITICAL 仍可能确认
  - `CODEBUDDY_IS_SANDBOX=1`: 隔离沙箱内配合 `-p -y` 真正全程免询问(官方原文,高危)
- 无头模式自带 CronCreate/CronList/CronDelete 工具(佐证竞品现状:单 agent 生态在长自动化,但不解决多 agent 接力)
- ⚠️ 本机未安装,**未实测**;适配器按上述文档写,`supports_resume=True`(文档依据),命令名/flag 全部可在 `tasks.yaml agents.*` 覆盖。装上后跑一次冒烟即转正(列入 verlog 待办)。
- `--model` flag 文档片段未确认 → **不默认传**,仅当用户在 agent 配置里写了 `model_flag` 才传。

## 3. zcode —— 无头能力证据不足,v0.1 降级

- `zcode-app-cli`(npm, v3.11.2-25): 官方 zcode.cjs runtime + 本地 pi-tui 的**交互式 TUI 客户端**
- HOST_INTEGRATION.md: 交互需宿主分配 PTY;"for non-interactive commands, preserve the inherited standard-stream contract"——提到存在非交互命令但**未给出任何命令名/flag**;README 亦无 `-p/--print` 证据
- 按主方案 §10 降级原则: `zcode` 内置适配器 `capable=False`,配置校验直接 fail fast 并给出指引: 在 `tasks.yaml` 用 `agents.zcode.type: custom` + 实测过的命令模板自行接入(例: `{prompt}`/`{session}` 占位符)
- 待用户本机装好后提供实际无头命令,再转正为内置适配器

## 4. Windows toast —— 零依赖方案实测通过

- PowerShell `FullLanguage` 模式 + **WinRT** `ToastNotificationManager.CreateToastNotifier("agent_daemon")` 成功弹出 ✅(本机 BurntToast 未装,故弃 BurntToast,用 WinRT 内联脚本,零新依赖)
- 实现: `notify.py` 调 `powershell -NoProfile -NonInteractive -Command <脚本>`,标题/正文经单引号转义注入

## 5. 环境与依赖核实

| 项 | 结果 |
|---|---|
| Python | `py -3.13` = `D:\Python\python.exe` 3.13.13 ✅;注意默认 `python`=3.11 → **全部命令用 `py -3.13`** |
| PyYAML | 3.13 下 6.0.3 ✅ |
| croniter | 3.13 下本次已安装 ✅(主方案批准的第二个依赖) |
| claude code | 本机有 `claude.exe`(参考实现,v0.3 再做) |
| 网络 | r.jina.ai 不可达;codebuddy.cn 文档直抓可行;npm registry 可达 |

## 6. 对实现的直接影响

1. 适配器能力用数据声明: `capable / supports_resume / model_flag 需用户显式配置`——config 校验 fail fast,不静默降级(主方案 §8)。
2. `allow_danger` 映射: codebuddy → `-y` + `CODEBUDDY_IS_SANDBOX=1`;DSH → 无放权旗标可传(profile 侧配),传了也只是无操作,配置校验仍要求 workdir 在 allow_roots 内。
3. 所有 agent 的 argv 构成参数化(`agents.<name>.command/extra_args/resume_flag/output_format/...`),flag 存疑时用户改配置即可,不动代码。
4. 新增 `custom` 适配器类型作为多 agent 通用扩展位(zcode 兜底、未来 agent 免代码接入)。
5. `bin/dsh.cmd` 封装脚本入项目(本机的 DSH 无头启动器,含 --tsconfig 锚定)。
