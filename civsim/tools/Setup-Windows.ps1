<#
.SYNOPSIS
    CivSim 윈도우 개발 환경 부트스트랩.

.DESCRIPTION
    1) .NET 8 SDK, Python 3 확인(없으면 winget으로 설치 제안)
    2) numpy, pillow 설치
    3) dotnet test 로 코어 검증
    4) 합성 지형(또는 -RealDem 시 실제 Copernicus DEM) 베이크
    5) -LinkUnity 지정 시: Unity 프로젝트(civsim\unity)에 코어 폴더 정션 생성 + 지형 파일 복사

.EXAMPLE
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
    .\tools\Setup-Windows.ps1                 # 도구 확인 + 테스트 + 합성 지형
    .\tools\Setup-Windows.ps1 -RealDem        # 실제 DEM 다운로드 후 베이크
    .\tools\Setup-Windows.ps1 -LinkUnity      # Unity 프로젝트를 만든 뒤 실행 (관리자 권한 불필요, 정션은 일반 권한으로 생성됨)
#>
[CmdletBinding()]
param(
    [switch]$RealDem,
    [switch]$LinkUnity,
    [switch]$SkipTests,
    [double]$ResolutionM = 30
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot   # civsim\
Set-Location $root

# This file is UTF-8 with a BOM so Windows PowerShell 5.1 reads its Korean text correctly.
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
# PowerShell 7 turns a native command's stderr into a terminating error under ErrorActionPreference
# 'Stop'; pip and dotnet write ordinary notices there, so exit codes are checked explicitly.
if ($PSVersionTable.PSVersion.Major -ge 7) { $PSNativeCommandUseErrorActionPreference = $false }

function Test-Command($name) { return $null -ne (Get-Command $name -ErrorAction SilentlyContinue) }

function Ensure-Tool($cmd, $wingetId, $label) {
    if (Test-Command $cmd) { Write-Host "[ok] $label : $((Get-Command $cmd).Source)"; return }
    Write-Warning "$label 이(가) 없습니다."
    if (Test-Command 'winget') {
        $ans = Read-Host "winget으로 $label 을(를) 설치할까요? (y/N)"
        if ($ans -match '^[yY]') {
            winget install --id $wingetId -e --accept-source-agreements --accept-package-agreements
            Write-Host "설치 후 새 PowerShell 창을 열고 이 스크립트를 다시 실행하세요."
        }
    } else {
        Write-Host "수동 설치: $label ($wingetId)"
    }
    exit 1
}

Write-Host "== 1. 도구 확인 =="
Ensure-Tool 'dotnet' 'Microsoft.DotNet.SDK.8' '.NET 8 SDK'
Ensure-Tool 'python'  'Python.Python.3.12'   'Python 3'
$dotnetVer = (dotnet --version).Trim()
$dotnetBase = $dotnetVer.Split('-')[0]
if ([version]$dotnetBase -lt [version]'8.0.0') { throw ".NET SDK 8.0 이상이 필요합니다 (현재 $dotnetVer)" }
Write-Host "[ok] dotnet $dotnetVer"

Write-Host "`n== 2. Python 패키지 =="
python -m pip install --quiet --upgrade numpy pillow
python tools\test_astro_reference.py

if (-not $SkipTests) {
    Write-Host "`n== 3. 코어 테스트 =="
    dotnet test --nologo
    if ($LASTEXITCODE -ne 0) { throw "dotnet test 실패. 출력을 확인하세요." }
}

Write-Host "`n== 4. 지형 베이크 =="
New-Item -ItemType Directory -Force -Path data\baked | Out-Null
if ($RealDem) {
    python tools\bake_dem.py --download data\raw
    python tools\bake_dem.py --tiles data\raw --out data\baked\seoul --res $ResolutionM
} else {
    python tools\bake_dem.py --synthetic --out data\baked\seoul --res $ResolutionM
}

if ($LinkUnity) {
    Write-Host "`n== 5. Unity 연결 =="
    $assets = Join-Path $root 'unity\Assets'
    if (-not (Test-Path $assets)) {
        throw "unity\Assets 가 없습니다. 먼저 Unity Hub에서 URP 3D 템플릿으로 '$root\unity' 에 프로젝트를 만드세요."
    }
    $link = Join-Path $assets 'CivSim\Core'
    $target = Join-Path $root 'src\CivSim.Core'
    New-Item -ItemType Directory -Force -Path (Split-Path $link) | Out-Null
    if (Test-Path $link) {
        Write-Host "[ok] 정션 이미 존재: $link"
    } else {
        New-Item -ItemType Junction -Path $link -Target $target | Out-Null
        Write-Host "[ok] 정션 생성: $link -> $target"
    }
    $sa = Join-Path $assets 'StreamingAssets\terrain'
    New-Item -ItemType Directory -Force -Path $sa | Out-Null
    Copy-Item data\baked\seoul.r16, data\baked\seoul.json -Destination $sa -Force
    Write-Host "[ok] 지형 파일 복사: $sa"
    Write-Host "`nUnity 에디터에서 씬을 README.md '3. 씬 구성' 대로 만들고 재생하세요."
}

Write-Host "`n완료."
