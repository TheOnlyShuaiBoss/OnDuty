# 生成 GitHub 社交预览图 1280x640(docs/assets/social-preview.png)
# 纯 System.Drawing 本地渲染,无外部素材。跑法: powershell -File scripts/make-social-preview.ps1
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing
$out = Join-Path $PSScriptRoot "..\docs\assets\social-preview.png"
New-Item -ItemType Directory -Force (Split-Path $out) | Out-Null

$W = 1280; $H = 640
$bmp = [System.Drawing.Bitmap]::new($W, $H)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::ClearTypeGridFit

# 背景: 深蓝实色 + 两处半透明光晕(避免渐变刷的 PS 绑定坑)
$cBg = [System.Drawing.Color]::FromArgb(255, 13, 22, 38)
$bBg = [System.Drawing.SolidBrush]::new($cBg)
$g.FillRectangle($bBg, [single]0, [single]0, [single]$W, [single]$H)
$cGlow = [System.Drawing.Color]::FromArgb(26, 64, 196, 255)
$bGlow = [System.Drawing.SolidBrush]::new($cGlow)
$g.FillEllipse($bGlow, [single]820, [single]-220, [single]640, [single]640)
$g.FillEllipse($bGlow, [single]-240, [single]400, [single]560, [single]560)

# 装饰: 接力点线 + 节点(呼应"relay chain")
$accent = [System.Drawing.Color]::FromArgb(255, 64, 196, 255)
$dotPen = [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(90, 64, 196, 255), 3)
$dotPen.DashStyle = [System.Drawing.Drawing2D.DashStyle]::Dot
$g.DrawLine($dotPen, 60.0, 505.0, 1220.0, 505.0)
$nodeBrush = [System.Drawing.SolidBrush]::new($accent)
foreach ($x in 60, 420, 780, 1140) {
    $g.FillEllipse($nodeBrush, [float]($x - 9), 496.0, 18.0, 18.0)
}

# 时钟图标(左上,呼应"值班")
$clockPen = [System.Drawing.Pen]::new($accent, 6)
$g.DrawEllipse($clockPen, 70.0, 90.0, 120.0, 120.0)
$g.DrawLine($clockPen, 130.0, 150.0, 130.0, 105.0)
$g.DrawLine($clockPen, 130.0, 150.0, 168.0, 162.0)

function Draw-Text([string]$s, [System.Drawing.Font]$f, [System.Drawing.Brush]$b, [single]$x, [single]$y) {
    $pt = [System.Drawing.PointF]::new($x, $y)
    $script:g.DrawString($s, $f, $b, $pt) | Out-Null
}

# 标题与副题
$white = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::White)
$subBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(230, 180, 210, 235))
$fTitle = [System.Drawing.Font]::new("Segoe UI", [single]88, [System.Drawing.FontStyle]::Bold)
$fSub = [System.Drawing.Font]::new("Segoe UI", [single]30)
$fZh = [System.Drawing.Font]::new("Microsoft YaHei UI", [single]22)
Draw-Text "OnDuty" $fTitle $white 230 95
Draw-Text "Send your coding agents on shift." $fSub $subBrush 72 250
Draw-Text "让 agent 替你值班 —— cron 定时 · 接力链 · 多 CLI · 声明式 · 强制隔离" $fZh $subBrush 74 320

# 命令行小票
$mono = [System.Drawing.Font]::new("Consolas", [single]19)
$dimBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(200, 120, 190, 160))
Draw-Text '$ onduty daemon   * * 0 8 * * *  ->  job1 done  ->  job2 --resume' $mono $dimBrush 68 540

$g.Dispose()
$bmp.Save($out, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
"OK: $out  size=$((Get-Item $out).Length)"
