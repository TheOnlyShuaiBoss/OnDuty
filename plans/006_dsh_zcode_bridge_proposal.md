# 006 DSH 复用 ZCode 夜间/周末免费额度（方案草案，⚠️ 待批准）

- 日期: 2026-09-20 · 状态: **待批准**（拟落地在 `llm_proxy`，**跨项目改动需用户明确同意**）
- 触发: 用户要求「实现 DSH 可以用 zcode 里夜间包和周末包的方案」，参考已成功的「DSH 反代 WorkBuddy」
- 前置: plans/005 修复 2 复验结论（明文 key 三条通道全部吃不到免费额度）

## 0. 已实测事实（2026-09-20 侦察）

| 事实 | 证据 |
|---|---|
| 明文 key 吃不到免费额度 | 三通道实测：`builtin:zai-coding-plan`(api.z.ai) → **1113**；`builtin:zai-start-plan`(zcode.z.ai 计划网关) → **3007 captcha verify failed**；`builtin:bigmodel-coding-plan` → **1113** |
| ZCode 凭据加密存储 | `~/.zcode/v2/credentials.json` 全部值为 `enc:v1:…`（含 `oauth:zai:access_token`）→ 外部**无法解密**，印证"绑定 ZCode 的加密 key" |
| 但 **Coding Plan JWT 是明文** | `~/.zcode/v2/config.json` → `provider["builtin:zai-start-plan"].options.apiKey`（255 字符 3 段 JWT；声明 `user_id/token_version/sub`，**iat=本日 09:57**、无 exp；桌面端每次启动刷新） |
| 运行时带客户端身份 + 网关签名 | 请求头 `User-Agent: ZCode/<ver>`、`X-ZCode-App-Version`、`X-Platform`、`X-Release-Channel`、`X-Title`；对网关走 `createClientSigningFetch` 签名 |
| 计划网关的关键门槛：**阿里云无痕验证参数** | [zcode2api](https://github.com/dengyie/zcode2api) README：JWT 模式需请求头 `X-Aliyun-Captcha-Verify-Param`；其用 **Node + jsdom 跑官方无痕 SDK 免浏览器求解**；我们的 3007 即验证码失败 |
| 免费额度官方规则 | [Plan Update](https://docs.z.ai/devpack/notice/usage-revision)：**周末全天按 off-peak 计费**；峰值=周一至周五 14:00–18:00 (UTC+8)；GLM-5.3 off-peak 1×/peak 3×、Flash 0.4×/1.2×。llm_proxy 既有记录为「周末全天 或 每天 23:00-06:00」 |
| 桌面端驱动运行时的方式 | 进程实测：`ZCode.exe "…\zcode.cjs" app-server --stdio --surface desktop`（私有 stdio 协议，含 `off-peak-run` 消息） |
| llm_proxy 已有可直接复用的能力 | `apiKeyFileJson`（文件+点分字段读令牌）、`extraHeaders`、`streamOnlyUpstream`、**`freeWindows` + `onlyInWindow`**（免费窗闸门）、Anthropic 入口 |

## 1. 候选路线

### 路线 A（推荐）: 在 `llm_proxy` 新增 `zcode` 平台（Anthropic 上游 + 无痕验证参数）
- **令牌**: 复用 `apiKeyFileJson` 读取 `~/.zcode/v2/config.json` 的 `provider.builtin:zai-start-plan.options.apiKey`（字段名含冒号，需扩展点分路径解析）
- **上游**: `https://zcode.z.ai/api/v1/zcode-plan/anthropic`（Anthropic Messages 协议，流式）
- **验证码**: 二选一
  - **A1 自研**: Node + jsdom 跑阿里云官方无痕 SDK 求 `verifyParam`（zcode2api 的做法；仅参考思路，若直接复用其代码须遵守 **AGPL-3.0**）
  - **A2 旁挂**: 本机部署 zcode2api，llm_proxy 只加一个指向 `http://127.0.0.1:<port>/v1/messages` 的 provider（工作量最小，但引入第三方 + 多一个常驻服务）
- **免费窗**: 复用 llm_proxy 既有 `freeWindows` + `onlyInWindow`（按官方规则配：周末全天 / 夜间时段）
- **优点**: 与 workbuddy 反代同构；DSH 侧零改动（只加 provider + 模型名）；流式与工具调用原生可用

### 路线 B: 桥接 ZCode 运行时（不碰验证码）
- 桥接器驱动 `zcode.cjs app-server --stdio`（桌面端同款通道）或 `--prompt`
- **优点**: 官方通道，额度/签名/风控全由运行时处理
- **缺点**: 语义是"再跑一个 agent"而非"给 DSH 一个模型"（工具调用无法映射）；app-server 为私有协议需逆向；工作量大

### 路线 C: 等 Z.AI 侧恢复对外开放（不做）

## 2. 建议步骤与待决事项

**建议**: 先做**可行性探针**（不写生产代码）：取得一次 `verifyParam` → 用现成 JWT 手工打计划网关 → 期望 200 + 流式。探针通过后，再决定 A1/A2 与工程化细节。

**需用户拍板**:
1. 是否允许改动 `llm_proxy`（跨项目；其自身规则要求触碰项目外文件逐次征得同意）
2. 验证码走 **A1 自研**（贴合架构、无第三方）还是 **A2 旁挂 zcode2api**（最快见效）
3. 是否接受新增依赖（Node + jsdom，仅 A1 需要）

## 4. 探针执行结果（2026-09-20 10:12~10:22，已实测）

探针落在 `llm_proxy/test/zcode_probe/`（其规则要求隔离验证入 `test/<场景名>/`），明细见该目录 `README.md`。

| 环节 | 结果 |
|---|---|
| 读明文 JWT | ✅ `~/.zcode/v2/config.json` → `provider["builtin:zai-start-plan"].options.apiKey` |
| 拉验证码配置 | ✅ `GET /api/v1/client/configs?app_version=3.10.2` → sceneId/region/prefix |
| **本地求解验证码** | ✅ **2.2~2.7s / 280 字符**（happy-dom 无浏览器求解；偶发失败需重试） |
| 鉴权形式 | `x-api-key` → 401；**`Authorization: Bearer <jwt>` → 通过鉴权** |
| 套餐只读端点 | ✅ `GET /api/v1/zcode-plan/billing/balance` → **200**：`zcode-v3-start-plan-0817`「ZCode Start Plan」**active**，GLM-5.3 **每日 3,000,000 token** |
| **对话端点** | ❌ **405 `{"code":3012,...unusual activity}`**（流式/非流式、darwin/win32 指纹均同） |

**判断**：账号未整体风控（billing 200 + 桌面端日志 `hasActiveStartPlan:true`），3012 是 messages 端点专属风控。候选原因：验证码参数与 HTTP 指纹不匹配／缺宿主侧 provider registry 身份链／短时间多次尝试触发临时限制。

**下一步（待拍板）**：①请用户在 ZCode 桌面端发一条消息确认 app 当前可用（用于区分"请求特征问题"与"账号冷却"）；②冷却 30 分钟后单次重试；③仍不通则退路：仅旁挂 zcode2api 或改走 app-server 桥接。

## 5. 合规提示
- 免浏览器求解无痕验证 = 绕过客户端风控，仅限本人账号自用；平台条款风险请用户自行判断（zcode2api 亦声明同款免责）
- 令牌来源为用户本机 `~/.zcode` 明文 JWT（桌面端自动刷新）；**不得入库、不得外传**，测试脚本按 llm_proxy 规则从文件读、不写死
- 探针中的 `solver.js` 为第三方 AGPL-3.0 代码，**生产实现须自研**
