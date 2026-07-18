# 启动 Stage 2 专用 Chrome（CDP 只读 POC，D-0009）
# - 专用 user-data-dir：项目 tmp/xhs_cdp_profile/（已 gitignore）
# - 调试端口仅绑定 127.0.0.1:9222；可见窗口（非 headless）
# - 已存在专用实例时复用，不重复启动；绝不触碰用户日常 Chrome
param(
    [string]$NoteUrl = "https://www.xiaohongshu.com/explore/6a4903ad000000002003b221"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ProfileDir = Join-Path $ProjectRoot "tmp\xhs_cdp_profile"
$ChromeCandidates = @(
    "C:\Program Files\Google\Chrome\Application\chrome.exe",
    "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)
$Chrome = $ChromeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Chrome) { Write-Error "未找到本机 Chrome 稳定版"; exit 1 }

# 复用检测：CDP 端点已响应则直接退出（不重复启动）
try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:9222/json/version" -TimeoutSec 3 -UseBasicParsing
    if ($resp.StatusCode -eq 200) { Write-Output "REUSE existing dedicated Chrome on 127.0.0.1:9222"; exit 0 }
} catch { }

New-Item -ItemType Directory -Force -Path $ProfileDir | Out-Null
$args = @(
    "--remote-debugging-address=127.0.0.1",
    "--remote-debugging-port=9222",
    "--user-data-dir=$ProfileDir",
    "--no-first-run",
    "--no-default-browser-check",
    $NoteUrl
)
Start-Process -FilePath $Chrome -ArgumentList $args
Write-Output "STARTED dedicated Chrome (profile: $ProfileDir) -> $NoteUrl"
