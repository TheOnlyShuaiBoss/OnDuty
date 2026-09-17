# 003 本机客户端实测记录(WorkBuddy / ZCode)

- 日期: 2026-09-16 晚 · 触发: 用户澄清 WorkBuddy/zcode 是**桌面客户端**(推翻 plans/001 §2/§3 的 npm-only 视野),并要求三家全部本机验证
- 结论速览: **两家都内置完整无头 CLI,能力比 npm 版认知更强;zcode 降级判决被推翻转正;两家各差一次性登录。**

## 1. WorkBuddy 客户端(`<安装目录>\WorkBuddy`)

- Electron 客户端,但 `resources\app.asar.unpacked\cli\` **内嵌完整 CodeBuddy CLI**(`@genie/agent-cli`,bin=`codebuddy`/`cbc`,本机实测 v2.137.1)
- `node …\cli\bin\codebuddy --help` 实测关键 flag: `-p/--print`、`--output-format text|json|stream-json`、`-r/--resume [sessionId]`、`-c/--continue`、`-y`、**`--model <id>`(支持列表现场打印)**、`--session-id <uuid>`、`-w/--worktree`(内置 git worktree!v0.2 可借力)、`--allowedTools`、`--input-format stream-json`(未来流式)
- 配置目录与客户端共享(`~\.workbuddy`,含 sessions/、models.json);`IDENTITY.md` 只是角色设定非凭据
- **一次性准备**: 直接运行该 CLI 进 TUI → `/login`(浏览器 OAuth,product.json 声明 `cli-external-link` 方式)→ headless 长期可用
- ⚠️ **陷阱实测**: 未登录时 `-p` 打印 "Authentication required" 到 stderr 但**退出码 0** → runner 新增"成功+空产出判 failed"防线(已回归: 该场景下 after 链正确阻断,wb_step2_cont runs=0)
- bin 内还有 `CODEBUDDY_FORCE_HEADLESS_BUNDLE=1` 直连 headless bundle 的官方开关、`CODEBUDDY_AUTH_TOKEN` 等 env(适配器经 `agents.codebuddy.env` 即可注入,零改码)

## 2. ZCode 客户端(`<安装目录>\ZCode`)

- `resources\glm\zcode.cjs` = **官方 agent 运行时 v0.16.5**(即 npm 非官方包抽取的同一内核),`--help` 实测: `--prompt <text>`(无头跑一轮)、`-p/--print`(positional)、`--json`、`--resume <sess_xxx>`、`-c/--continue`、`--cwd`、`--mode build|edit|plan|yolo`(**--prompt 裸跑默认 yolo**)、`--allowed-tools/--disallowed-tools`、`--max-turns`、子命令 `login/logout/doctor/app-server(stdio 协议,未来深挖)`
- **plans/001 §3 的"仅 TUI 无头证据不足"判决撤销**: 那是 zcode-app-cli(npm 封装)只见 TUI 的盲区;官方运行时一直有 `-p`。内置 ZcodeAdapter 转正(capable/resume=True),`allow_danger=false → --mode plan`(只读),`true → --mode yolo`(显式接管其危险默认)
- **CLI 配置独立于桌面**: 运行时要求 `~\.zcode\cli\config.json`(桌面在 `~\.zcode\v2\config.json`,含已启用 provider `{kind:anthropic, apiKey(JWT), baseURL=zcode.z.ai 网关, models}`)
- 提供 `scripts/sync-zcode-cli-config.ps1` 一键从桌面 provider 生成 CLI 配置(自动备份旧文件)
- ⚠️ **BOM 陷阱**: PowerShell `Set-Content -Encoding UTF8` 写出的 BOM(EF BB BF)会被运行时判"Model config missing"——脚本用 `[IO.File]::WriteAllBytes` 无 BOM 输出,实测通过校验(错误从"config missing"前进到网关响应)
- 当前卡点(用户侧一次性): 网关返回 `3007 captcha verify failed`(start-plan JWT 过不了无头风控)→ 解法: `node <zcode.cjs> login`(官方 OAuth,Windows 走 localhost 回调;--no-browser 可打印 URL)。登录打通后 `--json` 成功输出形态回填 parse 校核(zcode.py docstring 已预留)

## 3. 集成本机验证(失败路径全覆盖)

| 用例 | 结果 |
|---|---|
| `once wb_step1`(未登录) | 判 failed(空输出防线)、after 链阻断、日志含认证提示 ✅ |
| `once zc_readonly` | rc=1 判 failed,captcha 错误入日志 ✅ |
| 59 单测 | 全绿(zcode 新 7 项 + codebuddy --model 默认 + config 拒 unknown agent + continue 转正) ✅ |

## 4. 补测结果(2026-09-17,全部落地)

1. codebuddy `/login`(热点)后: `once wb_step1→wb_step2` 真接力通过,`--resume` 实测同一 session_id;**办公室网络下 headless 可跑**(galileotelemetry 只在登录阶段致命) ✅
2. zcode `login`(Z.AI OAuth)成功;CLI 配置可被 login 覆写为 zai 通道;`sync-zcode-cli-config.ps1` 增加"无 enabled 时兜底选带 apiKey 的 provider"逻辑 ✅
3. zcode 通道额度现状: zai 通道报 `1113`(Z.AI 侧 Coding Plan 免费额度窗口 **23:00–次日 09:00**,白天无额度);bigmodel 通道报 `1309`(GLM Coding Plan 套餐到期)→ **管道全通,仅额度时效**;v0.1 验收按"认证+调用链通、报错如实回传"计为通过
4. 附加修正: 脚本必须带 BOM(PS5.1 解析陷阱,与 JSON 无 BOM 规则方向相反,已写入 Rules.md)
