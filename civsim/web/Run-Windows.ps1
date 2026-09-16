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
#>
[CmdletBinding()]
param(
    [switch]$Build,
    [switch]$Test,
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

function Test-Command($name) { return $null -ne (Get-Command $name -ErrorAction SilentlyContinue) }

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

if (-not (Test-Command 'npm')) {
    throw 'npm을 찾을 수 없습니다. Node.js를 다시 설치하거나 PowerShell 창을 새로 여세요.'
}

if (-not (Test-Path 'node_modules')) {
    Write-Host "`n== 의존성 설치 ==" -ForegroundColor Cyan
    npm install
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
    npm test
    exit $LASTEXITCODE
}

if ($Build) {
    Write-Host "`n== 빌드 ==" -ForegroundColor Cyan
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "빌드가 실패했습니다 (종료 코드 $LASTEXITCODE)." }
    $url = 'http://127.0.0.1:4173/'
    Write-Host "`n미리보기: $url  (Ctrl+C로 종료)" -ForegroundColor Green
    if (-not $NoBrowser) { Start-Process $url }
    npm run preview
} else {
    $url = 'http://127.0.0.1:5173/'
    Write-Host "`n개발 서버: $url  (Ctrl+C로 종료)" -ForegroundColor Green
    Write-Host '브라우저가 자동으로 열리지 않으면 위 주소를 직접 입력하세요.' -ForegroundColor DarkGray
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
                    Start-Process 'http://127.0.0.1:5173/'
                    return
                } catch { }
            }
        } | Out-Null
    }
    npm run dev
}
