<#
.SYNOPSIS
    서울 문명 시뮬레이터를 윈도우에서 실행한다.

.DESCRIPTION
    Node.js 확인 → 의존성 설치 → 개발 서버 실행 → 브라우저 열기.
    이미 설치돼 있으면 바로 실행한다.

.EXAMPLE
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
    .\Run-Windows.ps1            # 개발 서버로 실행
    .\Run-Windows.ps1 -Build     # 정적 빌드 후 미리보기 서버로 실행
    .\Run-Windows.ps1 -Test      # 단위 테스트만 실행
    .\Run-Windows.ps1 -Mini      # 화면 구석에 작은 창으로 띄우기
#>
[CmdletBinding()]
param(
    [switch]$Build,
    [switch]$Test,
    [switch]$Mini,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

# This file is UTF-8 with a BOM so Windows PowerShell 5.1 reads its Korean text correctly;
# this makes the console print it correctly too.
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

# PowerShell 7 turns a native command's stderr into a terminating error under ErrorActionPreference
# 'Stop'. npm writes ordinary warnings to stderr, so exit codes are checked explicitly instead.
if ($PSVersionTable.PSVersion.Major -ge 7) { $PSNativeCommandUseErrorActionPreference = $false }

# Only needed to place the small window near the right edge of the screen.
try { Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop } catch { }

function Test-Command($name) { return $null -ne (Get-Command $name -ErrorAction SilentlyContinue) }

# In PowerShell, a bare `npm` resolves to npm.ps1, which a restricted execution policy blocks.
# npm.cmd is a batch file and runs whatever the policy says, so prefer it.
# Chrome and Edge can open a page as a bare window with no tabs or address bar, which is what you
# want parked in a corner. Falls back to the default browser when neither is installed.
function Find-Browser {
    $candidates = @(
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
        "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
        "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
        "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
    )
    foreach ($path in $candidates) { if ($path -and (Test-Path $path)) { return $path } }
    return $null
}

function Open-Viewer([string]$url, [bool]$small) {
    if (-not $small) { Start-Process $url; return }
    $browser = Find-Browser
    if (-not $browser) {
        Write-Warning '크롬이나 엣지를 찾지 못했습니다. 기본 브라우저로 엽니다.'
        Start-Process $url
        return
    }
    $w = 560
    $h = 400
    # Park it near the right edge when the screen width is known, otherwise somewhere sensible.
    $x = 900
    try {
        $screenWidth = [int]([System.Windows.Forms.SystemInformation]::VirtualScreen.Width)
        if ($screenWidth -gt 0) { $x = [Math]::Max(0, $screenWidth - $w - 24) }
    } catch { }
    Start-Process $browser -ArgumentList "--app=$url", "--window-size=$w,$h", "--window-position=$x,80"
}

function Resolve-Npm {
    foreach ($candidate in 'npm.cmd', 'npm.exe', 'npm') {
        $found = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($found -and $found.Source -and $found.Source -notmatch '\.ps1$') { return $found.Source }
    }
    $fallback = Get-Command 'npm' -ErrorAction SilentlyContinue
    if ($fallback) { return $fallback.Source }
    return $null
}

Write-Host '== Node.js 확인 ==' -ForegroundColor Cyan
if (-not (Test-Command 'node')) {
    Write-Warning 'Node.js가 없습니다. 20 이상이 필요합니다.'
    if (Test-Command 'winget') {
        $ans = Read-Host 'winget으로 Node.js LTS를 설치할까요? (y/N)'
        if ($ans -match '^[yY]') {
            winget install --id OpenJS.NodeJS.LTS -e --accept-source-agreements --accept-package-agreements
            Write-Host '설치 후 새 PowerShell 창에서 다시 실행하세요.' -ForegroundColor Yellow
        }
    } else {
        Write-Host 'https://nodejs.org 에서 LTS를 설치하세요.'
    }
    exit 1
}
# Parse the version in PowerShell: passing a quoted expression to node.exe loses its inner
# quotes to Windows argument handling.
$nodeVersion = (node -v).Trim()
$nodeMajor = 0
if ($nodeVersion -match '^v?(\d+)\.') { $nodeMajor = [int]$Matches[1] }
if ($nodeMajor -lt 20) { throw "Node.js 20 이상이 필요합니다 (현재 $nodeVersion)." }
Write-Host "[ok] Node.js $nodeVersion"

$npm = Resolve-Npm
if (-not $npm) {
    throw 'npm을 찾을 수 없습니다. Node.js를 다시 설치하거나 PowerShell 창을 새로 여세요.'
}
if ($npm -match '\.ps1$') {
    Write-Warning 'npm.cmd를 찾지 못해 npm.ps1을 씁니다. 실행 정책에 막히면 Run-Windows.cmd로 실행하세요.'
}

if (-not (Test-Path 'node_modules')) {
    Write-Host "`n== 의존성 설치 ==" -ForegroundColor Cyan
    & $npm install
    if ($LASTEXITCODE -ne 0) {
        throw "npm install이 실패했습니다 (종료 코드 $LASTEXITCODE). 위에 찍힌 메시지를 확인하세요."
    }
}

if (-not (Test-Path 'public\data\dem.bin')) {
    Write-Warning '지형 데이터(public\data\dem.bin)가 없습니다.'
    Write-Host '저장소에 포함돼 있어야 합니다. 직접 만들려면 상위 폴더에서:'
    Write-Host '  pip install numpy rasterio'
    Write-Host '  python tools\bake_dem.py --download data\raw'
    Write-Host '  python tools\bake_world.py --raw data\raw --out web\public\data'
    exit 1
}

if ($Test) {
    Write-Host "`n== 단위 테스트 ==" -ForegroundColor Cyan
    & $npm test
    exit $LASTEXITCODE
}

if ($Build) {
    Write-Host "`n== 빌드 ==" -ForegroundColor Cyan
    & $npm run build
    if ($LASTEXITCODE -ne 0) { throw "빌드가 실패했습니다 (종료 코드 $LASTEXITCODE)." }
    $url = 'http://127.0.0.1:4173/'
    Write-Host "`n미리보기: $url  (Ctrl+C로 종료)" -ForegroundColor Green
    if (-not $NoBrowser) { Open-Viewer $url $Mini.IsPresent }
    & $npm run preview
} else {
    $url = 'http://127.0.0.1:5173/'
    Write-Host "`n개발 서버: $url  (Ctrl+C로 종료)" -ForegroundColor Green
    Write-Host '브라우저가 자동으로 열리지 않으면 위 주소를 직접 입력하세요.' -ForegroundColor DarkGray
    if ($Mini) {
        Write-Host '앱 창으로 엽니다. 창 안의 "항상 위에" 단추를 누르면 다른 창 위에 고정됩니다.' -ForegroundColor DarkGray
    }
    $browserPath = if ($Mini) { Find-Browser } else { $null }
    if (-not $NoBrowser) {
        # The dev server runs in the foreground so Ctrl+C stops it; the browser is opened from a
        # background job once the port is up.
        Start-Job -ScriptBlock {
            for ($i = 0; $i -lt 40; $i++) {
                Start-Sleep -Milliseconds 500
                try {
                    $c = New-Object System.Net.Sockets.TcpClient
                    $c.Connect('127.0.0.1', 5173)
                    $c.Close()
                    $u = 'http://127.0.0.1:5173/'
                    if ($using:Mini) {
                        $b = $using:browserPath
                        if ($b) {
                            Start-Process $b -ArgumentList "--app=$u", '--window-size=560,400', '--window-position=900,80'
                            return
                        }
                    }
                    Start-Process $u
                    return
                } catch { }
            }
        } | Out-Null
    }
    & $npm run dev
}
