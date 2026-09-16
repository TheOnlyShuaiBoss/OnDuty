# sync-zcode-cli-config.ps1 — 从 ZCode 桌面配置生成 CLI 配置(~/.zcode/cli/config.json)
# 背景: zcode CLI 运行时独立读取 ~/.zcode/cli/config.json,桌面客户端配置在 ~/.zcode/v2/config.json。
# 本脚本把桌面已启用的 provider(apiKey/baseURL/models)复刻成 CLI 模板结构(plans/003)。
# 关键: 必须无 BOM UTF-8 —— 带 BOM 会被运行时当无效配置(实测)。
# 用法:
#   .\scripts\sync-zcode-cli-config.ps1                          # 自动挑 enabled 的 provider
#   .\scripts\sync-zcode-cli-config.ps1 -ProviderKey "builtin:bigmodel-start-plan"
param(
    [string]$ProviderKey = "",
    [string]$DesktopConfig = "$env:USERPROFILE\.zcode\v2\config.json",
    [string]$Target = "$env:USERPROFILE\.zcode\cli\config.json"
)
$ErrorActionPreference = "Stop"
if (-not (Test-Path $DesktopConfig)) { Write-Error "找不到桌面配置: $DesktopConfig"; exit 2 }
$v2 = Get-Content $DesktopConfig -Raw -Encoding UTF8 | ConvertFrom-Json
if ($ProviderKey) { $name = $ProviderKey }
else {
    $name = $v2.provider.PSObject.Properties | Where-Object { $_.Value.enabled -eq $true } | Select-Object -First 1 -ExpandProperty Name
    if (-not $name) { Write-Error "桌面配置里没有 enabled:true 的 provider,请手动指定 -ProviderKey"; exit 3 }
}
$all = $v2.provider.PSObject.Properties.Name -join ", "; "可选 provider: $all"
$p = $v2.provider.$name
if (-not $p.options.apiKey -or -not $p.options.baseURL) { Write-Error "该 provider 缺 apiKey/baseURL,换一个 -ProviderKey"; exit 4 }
$modelNames = @($p.models.PSObject.Properties.Name)
$models = [ordered]@{}
foreach ($m in $modelNames) { $models[$m] = [ordered]@{ name = $m } }
$conf = [ordered]@{
    provider = [ordered]@{ onduty = [ordered]@{
        kind    = $p.kind; name = "onduty-synced provider"
        options = [ordered]@{ apiKey = $p.options.apiKey; baseURL = $p.options.baseURL }
        headers = [ordered]@{}; models = $models } }
    model    = [ordered]@{ main = "onduty/$($modelNames[0])"; lite = $(if ($modelNames.Count -gt 1) { "onduty/$($modelNames[1])" } else { "onduty/$($modelNames[0])" }) }
    permission = [ordered]@{ mode = "build"; allowedTools = @(); disallowedTools = @(); autoApproveHighRisk = $false; allowMediumRiskInAuto = $false }
    storage  = [ordered]@{ dir = "~/.zcode"; sessionDbPath = "~/.zcode/cli/db/db.sqlite" }
    network  = [ordered]@{ timeout = 180000 }
    features = [ordered]@{ compact = $true; rewind = $true; subagent = $true; memory = $true; skill = $true; mcp = $true }
}
$dir = Split-Path $Target -Parent
if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
if (Test-Path $Target) { Copy-Item $Target "$Target.bak-$(Get-Date -Format yyyyMMddHHmmss)" }
# 无 BOM UTF-8(关键!)
[IO.File]::WriteAllBytes($Target, [Text.Encoding]::UTF8.GetBytes(($conf | ConvertTo-Json -Depth 8)))
"已写入: $Target  模型: $($modelNames -join ', ')"
"验证: node <zcode.cjs 路径> --prompt 'ping' --json   (不再报 Model config missing 即成)"
