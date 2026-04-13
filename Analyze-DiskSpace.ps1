#Requires -Version 5.1
<#
.SYNOPSIS
    Windows Disk Space Analyzer

.DESCRIPTION
    Scans a drive and reports space usage: top folders, known cleanup
    targets (Temp, Windows.old, SoftwareDistribution), system files
    (hiberfil/pagefile), Docker/WSL VHDX, dev caches, browser caches,
    and the top 20 largest files.  Prints a cleanup guide at the end.

.PARAMETER Drive
    Drive letter to analyze (default: C)

.PARAMETER TopN
    Number of top-level folders to display (default: 20)

.PARAMETER ExportPath
    Optional CSV file path to export results

.EXAMPLE
    .\Analyze-DiskSpace.ps1
    .\Analyze-DiskSpace.ps1 -Drive D -TopN 30
    .\Analyze-DiskSpace.ps1 -ExportPath "$env:USERPROFILE\Desktop\DiskReport.csv"
#>
[CmdletBinding()]
param(
    [string]$Drive     = "C",
    [int]   $TopN      = 20,
    [string]$ExportPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "SilentlyContinue"

# ── Helpers ────────────────────────────────────────────────────────────────

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
        $result = Get-ChildItem -Path $Path -Recurse -Force -File -ErrorAction SilentlyContinue |
                  Measure-Object -Property Length -Sum -ErrorAction SilentlyContinue
        if ($null -eq $result -or $null -eq $result.Sum) { return [long]0 }
        return [long]$result.Sum
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
    $pad = "-" * [Math]::Max(0, 66 - $Title.Length)
    Write-Host ""
    Write-Host "-- $Title $pad" -ForegroundColor Yellow
}

function Write-Item {
    param(
        [string]$Label,
        [long]  $Size,
        [string]$Note  = "",
        [string]$Color = "White"
    )
    $sizeStr = (Format-Bytes $Size).PadLeft(10)
    $noteStr = if ($Note) { "  <- $Note" } else { "" }
    Write-Host ("  {0,-50} {1}{2}" -f $Label, $sizeStr, $noteStr) -ForegroundColor $Color
}

# ── Drive summary ──────────────────────────────────────────────────────────

Write-Header "Windows Disk Space Analyzer  (Drive: ${Drive}:)"
Write-Host ("  Time    : {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss")) -ForegroundColor Gray
Write-Host ("  Target  : {0}:\" -f $Drive) -ForegroundColor Gray

$drivePath  = "${Drive}:\"
$disk       = Get-PSDrive -Name $Drive -ErrorAction Stop
$totalBytes = $disk.Used + $disk.Free
$usedBytes  = $disk.Used
$freeBytes  = $disk.Free
$usedPct    = if ($totalBytes -gt 0) { [Math]::Round($usedBytes / $totalBytes * 100, 1) } else { 0 }

Write-Section "Overall Usage"
Write-Host ("  Total   : {0}" -f (Format-Bytes $totalBytes)) -ForegroundColor White

$usedColor = if ($usedPct -ge 90) { "Red" } elseif ($usedPct -ge 75) { "Yellow" } else { "Green" }
Write-Host ("  Used    : {0}  ({1}%)" -f (Format-Bytes $usedBytes), $usedPct) -ForegroundColor $usedColor

$freeColor = if ($freeBytes -lt 10GB) { "Red" } elseif ($freeBytes -lt 30GB) { "Yellow" } else { "Green" }
Write-Host ("  Free    : {0}" -f (Format-Bytes $freeBytes)) -ForegroundColor $freeColor

# Bar chart
$barLen  = 50
$filled  = [Math]::Round($usedPct / 100 * $barLen)
$bar     = "[" + ("#" * $filled) + ("-" * ($barLen - $filled)) + "]"
$barClr  = if ($usedPct -ge 90) { "Red" } elseif ($usedPct -ge 75) { "Yellow" } else { "Green" }
Write-Host ""
Write-Host "  $bar $usedPct%" -ForegroundColor $barClr

# ── Top-level folders ──────────────────────────────────────────────────────

Write-Section "Top $TopN Folders  (scanning...)"

$topFolders = Get-ChildItem -Path $drivePath -Directory -Force -ErrorAction SilentlyContinue |
    ForEach-Object {
        $sz = Get-FolderSize $_.FullName
        [PSCustomObject]@{ Path = $_.FullName; Size = $sz }
    } |
    Sort-Object Size -Descending |
    Select-Object -First $TopN

foreach ($f in $topFolders) {
    $pct   = if ($usedBytes -gt 0) { [Math]::Round($f.Size / $usedBytes * 100, 1) } else { 0 }
    $clr   = if ($f.Size -ge 10GB) { "Red" } elseif ($f.Size -ge 1GB) { "Yellow" } else { "White" }
    Write-Item -Label $f.Path -Size $f.Size -Note "${pct}% of used" -Color $clr
}

# ── Suspect areas ──────────────────────────────────────────────────────────

Write-Section "Suspect Areas"

# Build list as array of key-value pairs to avoid encoding issues in ordered hashtable literals
$suspectList = @(
    [PSCustomObject]@{ Label = "User Temp";                   Path = "$env:LOCALAPPDATA\Temp" }
    [PSCustomObject]@{ Label = "System Temp";                 Path = "$env:SystemRoot\Temp" }
    [PSCustomObject]@{ Label = "Windows.old (prev Windows)";  Path = "${Drive}:\Windows.old" }
    [PSCustomObject]@{ Label = "WU Download Cache";           Path = "${Drive}:\Windows\SoftwareDistribution\Download" }
    [PSCustomObject]@{ Label = "WU DataStore";                Path = "${Drive}:\Windows\SoftwareDistribution\DataStore" }
    [PSCustomObject]@{ Label = "WinSxS (component store)";   Path = "${Drive}:\Windows\WinSxS" }
    [PSCustomObject]@{ Label = "Prefetch";                    Path = "${Drive}:\Windows\Prefetch" }
    [PSCustomObject]@{ Label = "Memory Dumps (Minidump)";     Path = "${Drive}:\Windows\Minidump" }
    [PSCustomObject]@{ Label = "IIS Logs";                    Path = "${Drive}:\inetpub\logs" }
    [PSCustomObject]@{ Label = "AppData\Roaming";             Path = "$env:APPDATA" }
    [PSCustomObject]@{ Label = "AppData\Local";               Path = "$env:LOCALAPPDATA" }
)

foreach ($item in $suspectList) {
    if (Test-Path $item.Path) {
        $sz  = Get-FolderSize $item.Path
        $clr = if ($sz -ge 5GB) { "Red" } elseif ($sz -ge 1GB) { "Yellow" } else { "DarkGray" }
        Write-Item -Label $item.Label -Size $sz -Note $item.Path -Color $clr
    } else {
        Write-Host ("  {0,-50}     (not found)" -f $item.Label) -ForegroundColor DarkGray
    }
}

# ── System special files ───────────────────────────────────────────────────

Write-Section "System Special Files"

$specialFiles = @(
    [PSCustomObject]@{ Path = "${Drive}:\hiberfil.sys"; Label = "Hibernate file  (hiberfil.sys)"; Tip = "To remove: powercfg /h off" }
    [PSCustomObject]@{ Path = "${Drive}:\pagefile.sys"; Label = "Virtual memory  (pagefile.sys)"; Tip = "Do NOT delete -- proportional to RAM" }
    [PSCustomObject]@{ Path = "${Drive}:\swapfile.sys"; Label = "Swap file       (swapfile.sys)"; Tip = "UWP app swap" }
)

foreach ($sf in $specialFiles) {
    if (Test-Path $sf.Path) {
        $item = Get-Item $sf.Path -Force -ErrorAction SilentlyContinue
        $sz   = if ($null -ne $item) { $item.Length } else { [long]0 }
        $clr  = if ($sz -ge 8GB) { "Yellow" } else { "White" }
        Write-Item -Label $sf.Label -Size $sz -Note $sf.Tip -Color $clr
    } else {
        Write-Host ("  {0,-50}     (not found)" -f $sf.Label) -ForegroundColor DarkGray
    }
}

# ── Docker / WSL virtual disks ─────────────────────────────────────────────

Write-Section "Docker / WSL Virtual Disks (.vhdx)"

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
        if ($null -ne $found) { $vhdxFiles += $found }
    }
}

if ($vhdxFiles.Count -gt 0) {
    $vhdxFiles | Sort-Object Length -Descending | ForEach-Object {
        $clr = if ($_.Length -ge 20GB) { "Red" } elseif ($_.Length -ge 5GB) { "Yellow" } else { "White" }
        Write-Item -Label $_.Name -Size $_.Length -Note $_.FullName -Color $clr
    }
} else {
    Write-Host "  No Docker/WSL virtual disks found" -ForegroundColor DarkGray
}

# ── Developer caches ───────────────────────────────────────────────────────

Write-Section "Developer Caches / Packages"

$devCacheList = @(
    [PSCustomObject]@{ Label = "npm cache";              Path = "$env:LOCALAPPDATA\npm-cache" }
    [PSCustomObject]@{ Label = "yarn cache";             Path = "$env:LOCALAPPDATA\Yarn\Cache" }
    [PSCustomObject]@{ Label = "pip cache";              Path = "$env:LOCALAPPDATA\pip\Cache" }
    [PSCustomObject]@{ Label = "conda packages";         Path = "$env:USERPROFILE\.conda\pkgs" }
    [PSCustomObject]@{ Label = "conda envs";             Path = "$env:USERPROFILE\.conda\envs" }
    [PSCustomObject]@{ Label = "Gradle cache";           Path = "$env:USERPROFILE\.gradle\caches" }
    [PSCustomObject]@{ Label = "Maven local repo";       Path = "$env:USERPROFILE\.m2\repository" }
    [PSCustomObject]@{ Label = "NuGet cache";            Path = "$env:LOCALAPPDATA\NuGet\Cache" }
    [PSCustomObject]@{ Label = "Cargo registry (Rust)";  Path = "$env:USERPROFILE\.cargo\registry" }
    [PSCustomObject]@{ Label = "Go module cache";        Path = "$env:USERPROFILE\go\pkg\mod" }
    [PSCustomObject]@{ Label = "Android SDK/AVD";        Path = "$env:LOCALAPPDATA\Android\Sdk" }
    [PSCustomObject]@{ Label = "JetBrains IDE cache";    Path = "$env:LOCALAPPDATA\JetBrains" }
    [PSCustomObject]@{ Label = "VS Code extensions";     Path = "$env:USERPROFILE\.vscode\extensions" }
)

foreach ($item in $devCacheList) {
    if (Test-Path $item.Path) {
        $sz = Get-FolderSize $item.Path
        if ($sz -gt 0) {
            $clr = if ($sz -ge 5GB) { "Red" } elseif ($sz -ge 1GB) { "Yellow" } else { "White" }
            Write-Item -Label $item.Label -Size $sz -Note $item.Path -Color $clr
        }
    }
}

# node_modules search (home dir, max depth 5)
Write-Host ""
Write-Host "  Scanning node_modules (home dir, depth 5)..." -ForegroundColor DarkGray

$nodeModules = Get-ChildItem -Path $env:USERPROFILE -Filter "node_modules" -Directory -Recurse -Force -Depth 5 -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch "node_modules\\node_modules" } |
    ForEach-Object {
        $sz = Get-FolderSize $_.FullName
        [PSCustomObject]@{ Path = $_.FullName; Size = $sz }
    } |
    Sort-Object Size -Descending

if ($null -ne $nodeModules -and @($nodeModules).Count -gt 0) {
    $nodeArr   = @($nodeModules)
    $nodeTotal = ($nodeArr | Measure-Object -Property Size -Sum).Sum
    $clr       = if ($nodeTotal -ge 5GB) { "Red" } elseif ($nodeTotal -ge 1GB) { "Yellow" } else { "White" }
    Write-Host ("  node_modules total ({0} dirs) : {1}" -f $nodeArr.Count, (Format-Bytes $nodeTotal)) -ForegroundColor $clr
    $nodeArr | Select-Object -First 5 | ForEach-Object {
        Write-Item -Label ("    -> " + $_.Path) -Size $_.Size
    }
} else {
    Write-Host "  No node_modules found" -ForegroundColor DarkGray
}

# ── Browser caches ─────────────────────────────────────────────────────────

Write-Section "Browser Caches"

$browserList = @(
    [PSCustomObject]@{ Label = "Chrome cache";  Path = "$env:LOCALAPPDATA\Google\Chrome\User Data\Default\Cache" }
    [PSCustomObject]@{ Label = "Chrome GPU";    Path = "$env:LOCALAPPDATA\Google\Chrome\User Data\Default\GPUCache" }
    [PSCustomObject]@{ Label = "Edge cache";    Path = "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default\Cache" }
    [PSCustomObject]@{ Label = "Firefox";       Path = "$env:LOCALAPPDATA\Mozilla\Firefox\Profiles" }
    [PSCustomObject]@{ Label = "Brave cache";   Path = "$env:LOCALAPPDATA\BraveSoftware\Brave-Browser\User Data\Default\Cache" }
    [PSCustomObject]@{ Label = "Opera cache";   Path = "$env:APPDATA\Opera Software\Opera Stable\Cache" }
)

foreach ($item in $browserList) {
    if (Test-Path $item.Path) {
        $sz  = Get-FolderSize $item.Path
        $clr = if ($sz -ge 2GB) { "Yellow" } else { "White" }
        Write-Item -Label $item.Label -Size $sz -Color $clr
    }
}

# ── Top 20 large files ─────────────────────────────────────────────────────

Write-Section "Largest Single Files  (>= 500 MB, scanning...)"

$largeFiles = Get-ChildItem -Path $drivePath -File -Recurse -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Length -ge 500MB } |
    Sort-Object Length -Descending |
    Select-Object -First 20

if ($null -ne $largeFiles -and @($largeFiles).Count -gt 0) {
    foreach ($f in $largeFiles) {
        $ext = $f.Extension.ToLower()
        $clr = if ($ext -eq ".vhdx" -or $ext -eq ".vmdk" -or $ext -eq ".vdi") { "Red" }
               elseif ($ext -eq ".iso" -or $ext -eq ".img" -or $ext -eq ".wim") { "Yellow" }
               else { "White" }
        Write-Item -Label $f.Name -Size $f.Length -Note $f.DirectoryName -Color $clr
    }
} else {
    Write-Host "  No files >= 500 MB found" -ForegroundColor DarkGray
}

# ── Cleanup guide ──────────────────────────────────────────────────────────

Write-Header "Cleanup Recommendations"

Write-Host ""
Write-Host "  [Safe to clean immediately]" -ForegroundColor Green
Write-Host "  1. Settings -> System -> Storage -> Temporary files" -ForegroundColor White
Write-Host "     (check items, then 'Remove files')" -ForegroundColor Gray
Write-Host ""
Write-Host "  2. Disk Cleanup (admin cmd):" -ForegroundColor White
Write-Host "       cleanmgr /sageset:1    <- choose items (include Windows.old)" -ForegroundColor Gray
Write-Host "       cleanmgr /sagerun:1    <- run" -ForegroundColor Gray
Write-Host ""
Write-Host "  3. Temp folders (safe to delete contents):" -ForegroundColor White
Write-Host "       %LOCALAPPDATA%\Temp" -ForegroundColor Gray
Write-Host "       %SystemRoot%\Temp" -ForegroundColor Gray
Write-Host ""
Write-Host "  [Review if large]" -ForegroundColor Yellow
Write-Host "  4. Docker/WSL:  Docker Desktop -> Troubleshoot -> Clean / Purge data" -ForegroundColor White
Write-Host "     WSL: wsl --shutdown  then optimize with Optimize-VHD" -ForegroundColor Gray
Write-Host ""
Write-Host "  5. Dev caches:" -ForegroundColor White
Write-Host "       npm cache clean --force" -ForegroundColor Gray
Write-Host "       pip cache purge" -ForegroundColor Gray
Write-Host "       conda clean --all" -ForegroundColor Gray
Write-Host ""
Write-Host "  6. Hibernate file (if unused, RAM >= 16 GB):" -ForegroundColor White
Write-Host "       powercfg /h off    <- deletes hiberfil.sys" -ForegroundColor Gray
Write-Host ""
Write-Host "  [Do NOT touch]" -ForegroundColor Red
Write-Host "  * AppData\Roaming  : app settings -- check before deleting" -ForegroundColor White
Write-Host "  * Windows\WinSxS   : use  dism /online /cleanup-image /startcomponentcleanup" -ForegroundColor White
Write-Host "  * pagefile.sys     : virtual memory -- leave it alone" -ForegroundColor White

# ── CSV export ─────────────────────────────────────────────────────────────

if ($ExportPath -ne "") {
    $rows = @()
    $rows += $topFolders | ForEach-Object {
        [PSCustomObject]@{ Category = "TopFolder"; Path = $_.Path; SizeBytes = $_.Size; SizeHuman = Format-Bytes $_.Size }
    }
    if ($null -ne $largeFiles) {
        $rows += $largeFiles | ForEach-Object {
            [PSCustomObject]@{ Category = "LargeFile"; Path = $_.FullName; SizeBytes = $_.Length; SizeHuman = Format-Bytes $_.Length }
        }
    }
    $rows | Export-Csv -Path $ExportPath -NoTypeInformation -Encoding UTF8
    Write-Host ""
    Write-Host "  CSV saved: $ExportPath" -ForegroundColor Green
}

Write-Host ""
Write-Host ("  Done -- {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss")) -ForegroundColor Gray
Write-Host ""
