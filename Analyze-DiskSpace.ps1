#Requires -Version 5.1
<#
.SYNOPSIS
    C 드라이브 용량 분석 스크립트

.DESCRIPTION
    C 드라이브의 디스크 용량 사용 현황을 분석하고, 대용량 파일/폴더와
    정리 가능한 항목들을 식별하여 리포트를 출력합니다.

.PARAMETER Drive
    분석할 드라이브 문자 (기본값: C)

.PARAMETER TopN
    상위 N개 폴더를 표시 (기본값: 20)

.PARAMETER ExportPath
    결과를 저장할 CSV 파일 경로 (선택 사항)

.EXAMPLE
    .\Analyze-DiskSpace.ps1
    .\Analyze-DiskSpace.ps1 -Drive D -TopN 30
    .\Analyze-DiskSpace.ps1 -ExportPath "$env:USERPROFILE\Desktop\DiskReport.csv"
#>
[CmdletBinding()]
param(
    [string]$Drive = "C",
    [int]$TopN = 20,
    [string]$ExportPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "SilentlyContinue"

# ── 헬퍼 함수 ──────────────────────────────────────────────────────────────

function Format-Bytes {
    param([long]$Bytes)
    if ($Bytes -ge 1TB) { return "{0:F2} TB" -f ($Bytes / 1TB) }
    if ($Bytes -ge 1GB) { return "{0:F2} GB" -f ($Bytes / 1GB) }
    if ($Bytes -ge 1MB) { return "{0:F2} MB" -f ($Bytes / 1MB) }
    if ($Bytes -ge 1KB) { return "{0:F2} KB" -f ($Bytes / 1KB) }
    return "$Bytes B"
}

function Get-FolderSize {
    param([string]$Path)
    try {
        $size = (Get-ChildItem -Path $Path -Recurse -Force -File -ErrorAction SilentlyContinue |
                 Measure-Object -Property Length -Sum -ErrorAction SilentlyContinue).Sum
        return [long]($size ?? 0)
    } catch {
        return [long]0
    }
}

function Write-Header {
    param([string]$Title)
    $line = "=" * 70
    Write-Host ""
    Write-Host $line -ForegroundColor Cyan
    Write-Host "  $Title" -ForegroundColor White
    Write-Host $line -ForegroundColor Cyan
}

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host "── $Title " -ForegroundColor Yellow -NoNewline
    Write-Host ("─" * [Math]::Max(0, 66 - $Title.Length)) -ForegroundColor DarkGray
}

function Write-Item {
    param(
        [string]$Label,
        [long]$Size,
        [string]$Note = "",
        [string]$Color = "White"
    )
    $sizeStr = (Format-Bytes $Size).PadLeft(10)
    $noteStr = if ($Note) { "  ← $Note" } else { "" }
    Write-Host ("  {0,-50} {1}{2}" -f $Label, $sizeStr, $noteStr) -ForegroundColor $Color
}

# ── 드라이브 기본 정보 ─────────────────────────────────────────────────────

Write-Header "C 드라이브 디스크 용량 분석"
Write-Host "  실행 시각: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Gray
Write-Host "  분석 대상: ${Drive}:\" -ForegroundColor Gray

$drivePath = "${Drive}:\"
$disk = Get-PSDrive -Name $Drive -ErrorAction Stop

$totalBytes = $disk.Used + $disk.Free
$usedBytes  = $disk.Used
$freeBytes  = $disk.Free
$usedPct    = if ($totalBytes -gt 0) { [Math]::Round($usedBytes / $totalBytes * 100, 1) } else { 0 }

Write-Section "전체 현황"
Write-Host ("  전체 용량  : {0}" -f (Format-Bytes $totalBytes)) -ForegroundColor White
Write-Host ("  사용 중    : {0}  ({1}%)" -f (Format-Bytes $usedBytes), $usedPct) -ForegroundColor $(if ($usedPct -ge 90) { "Red" } elseif ($usedPct -ge 75) { "Yellow" } else { "Green" })
Write-Host ("  남은 공간  : {0}" -f (Format-Bytes $freeBytes)) -ForegroundColor $(if ($freeBytes -lt 10GB) { "Red" } elseif ($freeBytes -lt 30GB) { "Yellow" } else { "Green" })

# 바 그래프
$barLen   = 50
$filled   = [Math]::Round($usedPct / 100 * $barLen)
$barColor = if ($usedPct -ge 90) { "Red" } elseif ($usedPct -ge 75) { "Yellow" } else { "Green" }
$bar      = "[" + ("#" * $filled) + ("-" * ($barLen - $filled)) + "]"
Write-Host ""
Write-Host "  $bar $usedPct%" -ForegroundColor $barColor

# ── 1단계: 최상위 폴더 스캔 ────────────────────────────────────────────────

Write-Section "최상위 폴더 크기 (상위 $TopN개)"
Write-Host "  스캔 중... (수 분 소요될 수 있습니다)" -ForegroundColor DarkGray

$topFolders = Get-ChildItem -Path $drivePath -Directory -Force -ErrorAction SilentlyContinue |
    ForEach-Object {
        $sz = Get-FolderSize $_.FullName
        [PSCustomObject]@{ Path = $_.FullName; Size = $sz }
    } |
    Sort-Object Size -Descending |
    Select-Object -First $TopN

foreach ($f in $topFolders) {
    $pct   = if ($usedBytes -gt 0) { [Math]::Round($f.Size / $usedBytes * 100, 1) } else { 0 }
    $color = if ($f.Size -ge 10GB) { "Red" } elseif ($f.Size -ge 1GB) { "Yellow" } else { "White" }
    Write-Item -Label $f.Path -Size $f.Size -Note "${pct}% of used" -Color $color
}

# ── 2단계: 의심 구역 점검 ──────────────────────────────────────────────────

Write-Section "의심 구역 점검"

$suspects = [ordered]@{
    "임시 파일 (사용자)"          = "$env:LOCALAPPDATA\Temp"
    "임시 파일 (시스템)"          = "$env:SystemRoot\Temp"
    "Windows.old (구버전 윈도우)" = "${Drive}:\Windows.old"
    "WU 다운로드 캐시"            = "${Drive}:\Windows\SoftwareDistribution\Download"
    "WU 정리 대기"                = "${Drive}:\Windows\SoftwareDistribution\DataStore"
    "컴포넌트 저장소 (WinSxS)"    = "${Drive}:\Windows\WinSxS"
    "Prefetch"                    = "${Drive}:\Windows\Prefetch"
    "메모리 덤프"                 = "${Drive}:\Windows\Minidump"
    "IIS 로그"                    = "${Drive}:\inetpub\logs"
    "AppData Roaming"             = "$env:APPDATA"
    "AppData Local"               = "$env:LOCALAPPDATA"
    "AppData LocalLow"            = "$env:LOCALAPPDATA\..\LocalLow"
}

$cleanableTotal = [long]0
foreach ($kv in $suspects.GetEnumerator()) {
    $p = $kv.Value
    if (Test-Path $p) {
        $sz    = Get-FolderSize $p
        $color = if ($sz -ge 5GB) { "Red" } elseif ($sz -ge 1GB) { "Yellow" } else { "DarkGray" }
        Write-Item -Label $kv.Key -Size $sz -Note $p -Color $color
        if ($kv.Key -match "임시|WU 다운로드|Windows\.old") { $cleanableTotal += $sz }
    } else {
        Write-Host ("  {0,-50} {1}" -f $kv.Key, "    (없음)") -ForegroundColor DarkGray
    }
}

# ── 3단계: 최대절전/가상메모리 파일 ────────────────────────────────────────

Write-Section "시스템 특수 파일"

$specialFiles = @(
    @{ Path = "${Drive}:\hiberfil.sys"; Label = "최대절전모드 (hiberfil.sys)";  Tip = "사용 안 하면: powercfg /h off" }
    @{ Path = "${Drive}:\pagefile.sys"; Label = "가상 메모리 (pagefile.sys)";   Tip = "RAM 용량에 비례 — 함부로 삭제 금지" }
    @{ Path = "${Drive}:\swapfile.sys"; Label = "스왑 파일 (swapfile.sys)";     Tip = "UWP 앱 전용 스왑" }
)

foreach ($sf in $specialFiles) {
    if (Test-Path $sf.Path) {
        $sz = (Get-Item $sf.Path -Force -ErrorAction SilentlyContinue).Length ?? 0
        Write-Item -Label $sf.Label -Size $sz -Note $sf.Tip -Color $(if ($sz -ge 8GB) { "Yellow" } else { "White" })
    } else {
        Write-Host ("  {0,-50}     (없음)" -f $sf.Label) -ForegroundColor DarkGray
    }
}

# ── 4단계: Docker / WSL 가상 디스크 ────────────────────────────────────────

Write-Section "Docker / WSL 가상 디스크 (VHDX)"

$vhdxSearchPaths = @(
    "$env:LOCALAPPDATA\Docker\wsl\data"
    "$env:LOCALAPPDATA\Docker\wsl\distro"
    "$env:LOCALAPPDATA\Packages"
    "${Drive}:\Users"
)

$vhdxFiles = @()
foreach ($sp in $vhdxSearchPaths) {
    if (Test-Path $sp) {
        $found = Get-ChildItem -Path $sp -Filter "*.vhdx" -Recurse -Force -ErrorAction SilentlyContinue
        $vhdxFiles += $found
    }
}

if ($vhdxFiles.Count -gt 0) {
    $vhdxFiles | Sort-Object Length -Descending | ForEach-Object {
        $color = if ($_.Length -ge 20GB) { "Red" } elseif ($_.Length -ge 5GB) { "Yellow" } else { "White" }
        Write-Item -Label $_.Name -Size $_.Length -Note $_.FullName -Color $color
    }
} else {
    Write-Host "  Docker/WSL 가상 디스크 없음" -ForegroundColor DarkGray
}

# ── 5단계: 개발 환경 캐시 ──────────────────────────────────────────────────

Write-Section "개발 환경 캐시 / 패키지"

$devCaches = [ordered]@{
    "npm 캐시"              = "$env:LOCALAPPDATA\npm-cache"
    "yarn 캐시"             = "$env:LOCALAPPDATA\Yarn\Cache"
    "pip 캐시"              = "$env:LOCALAPPDATA\pip\Cache"
    "conda 패키지"          = "$env:USERPROFILE\.conda\pkgs"
    "Conda envs"            = "$env:USERPROFILE\.conda\envs"
    "Gradle 캐시"           = "$env:USERPROFILE\.gradle\caches"
    "Maven 로컬 저장소"     = "$env:USERPROFILE\.m2\repository"
    "NuGet 캐시"            = "$env:LOCALAPPDATA\NuGet\Cache"
    "Cargo (Rust)"          = "$env:USERPROFILE\.cargo\registry"
    "Go 모듈 캐시"          = "$env:USERPROFILE\go\pkg\mod"
    "Android SDK/AVD"       = "$env:LOCALAPPDATA\Android\Sdk"
    "JetBrains IDE 캐시"    = "$env:LOCALAPPDATA\JetBrains"
    "VS Code 확장"          = "$env:USERPROFILE\.vscode\extensions"
}

foreach ($kv in $devCaches.GetEnumerator()) {
    $p = $kv.Value
    if (Test-Path $p) {
        $sz    = Get-FolderSize $p
        if ($sz -gt 0) {
            $color = if ($sz -ge 5GB) { "Red" } elseif ($sz -ge 1GB) { "Yellow" } else { "White" }
            Write-Item -Label $kv.Key -Size $sz -Note $p -Color $color
        }
    }
}

# node_modules 탐색 (홈 디렉터리 한정, 너무 깊이 파지 않도록)
Write-Host ""
Write-Host "  node_modules 탐색 중 (홈 디렉터리)..." -ForegroundColor DarkGray
$nodeModules = Get-ChildItem -Path $env:USERPROFILE -Filter "node_modules" -Directory -Recurse -Force -Depth 5 -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch "node_modules\\node_modules" } |
    ForEach-Object {
        $sz = Get-FolderSize $_.FullName
        [PSCustomObject]@{ Path = $_.FullName; Size = $sz }
    } |
    Sort-Object Size -Descending

if ($nodeModules.Count -gt 0) {
    $nodeTotal = ($nodeModules | Measure-Object -Property Size -Sum).Sum
    Write-Host ("  node_modules 총계 ({0}개) : {1}" -f $nodeModules.Count, (Format-Bytes $nodeTotal)) -ForegroundColor $(if ($nodeTotal -ge 5GB) { "Red" } elseif ($nodeTotal -ge 1GB) { "Yellow" } else { "White" })
    $nodeModules | Select-Object -First 5 | ForEach-Object {
        Write-Item -Label "  └─ $($_.Path)" -Size $_.Size
    }
} else {
    Write-Host "  node_modules 없음" -ForegroundColor DarkGray
}

# ── 6단계: 브라우저 캐시 ───────────────────────────────────────────────────

Write-Section "브라우저 캐시"

$browserCaches = [ordered]@{
    "Chrome 캐시"           = "$env:LOCALAPPDATA\Google\Chrome\User Data\Default\Cache"
    "Chrome GPU 캐시"       = "$env:LOCALAPPDATA\Google\Chrome\User Data\Default\GPUCache"
    "Edge 캐시"             = "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default\Cache"
    "Firefox 캐시"          = "$env:LOCALAPPDATA\Mozilla\Firefox\Profiles"
    "Brave 캐시"            = "$env:LOCALAPPDATA\BraveSoftware\Brave-Browser\User Data\Default\Cache"
    "Opera 캐시"            = "$env:APPDATA\Opera Software\Opera Stable\Cache"
}

foreach ($kv in $browserCaches.GetEnumerator()) {
    if (Test-Path $kv.Value) {
        $sz    = Get-FolderSize $kv.Value
        $color = if ($sz -ge 2GB) { "Yellow" } else { "White" }
        Write-Item -Label $kv.Key -Size $sz -Color $color
    }
}

# ── 7단계: 큰 파일 Top 20 ──────────────────────────────────────────────────

Write-Section "단일 파일 크기 Top 20 (${Drive}:\)"

Write-Host "  전체 파일 스캔 중... (시간이 걸릴 수 있습니다)" -ForegroundColor DarkGray

$largeFiles = Get-ChildItem -Path $drivePath -File -Recurse -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Length -ge 500MB } |
    Sort-Object Length -Descending |
    Select-Object -First 20

if ($largeFiles.Count -gt 0) {
    foreach ($f in $largeFiles) {
        $ext   = $f.Extension.ToLower()
        $color = switch ($ext) {
            { $_ -in ".vhdx", ".vmdk", ".vdi" } { "Red" }
            { $_ -in ".iso", ".img", ".wim" }   { "Yellow" }
            default                              { "White" }
        }
        Write-Item -Label $f.Name -Size $f.Length -Note $f.DirectoryName -Color $color
    }
} else {
    Write-Host "  500MB 이상 파일 없음" -ForegroundColor DarkGray
}

# ── 8단계: 정리 권고 ───────────────────────────────────────────────────────

Write-Header "정리 권고 사항"

Write-Host @"

  [ 즉시 정리 가능 ]
  1. 설정 → 시스템 → 저장소 → 임시 파일
     (다운로드 폴더 제외 항목 체크 → 파일 제거)

  2. 관리자 권한 명령 프롬프트:
     cleanmgr /sageset:1   ← 정리 항목 선택 (Windows.old 포함)
     cleanmgr /sagerun:1   ← 실행

  3. 임시 폴더 직접 정리:
     %LOCALAPPDATA%\Temp   (내용물 전체 삭제 가능)
     %SystemRoot%\Temp     (내용물 전체 삭제 가능)

  [ 용량이 크면 검토 ]
  4. Docker Desktop → Troubleshoot → Clean / Purge data
     또는 WSL2: wsl --shutdown && Optimize-VHD 실행

  5. 개발 캐시 정리:
     npm cache clean --force
     pip cache purge
     conda clean --all

  6. 최대절전모드 비활성화 (RAM ≥ 16GB 이상이면 절전 안 쓸 때):
     (관리자) powercfg /h off   → hiberfil.sys 삭제됨

  [ 주의 필요 ]
  * AppData\Roaming  : 앱 설정 포함 — 확인 후 개별 삭제
  * Windows\WinSxS   : 직접 삭제 금지 (dism /online /cleanup-image 사용)
  * pagefile.sys     : 가상메모리 — 함부로 삭제/이동 금지

"@ -ForegroundColor White

# ── CSV 내보내기 ────────────────────────────────────────────────────────────

if ($ExportPath -ne "") {
    $rows = @()
    $rows += $topFolders | ForEach-Object {
        [PSCustomObject]@{ Category = "TopFolder"; Path = $_.Path; SizeBytes = $_.Size; SizeHuman = Format-Bytes $_.Size }
    }
    $rows += $largeFiles | ForEach-Object {
        [PSCustomObject]@{ Category = "LargeFile"; Path = $_.FullName; SizeBytes = $_.Length; SizeHuman = Format-Bytes $_.Length }
    }
    $rows | Export-Csv -Path $ExportPath -NoTypeInformation -Encoding UTF8
    Write-Host "  CSV 저장 완료: $ExportPath" -ForegroundColor Green
}

Write-Host ""
Write-Host ("  분석 완료 — {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss")) -ForegroundColor Gray
Write-Host ""
