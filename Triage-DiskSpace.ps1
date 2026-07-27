#Requires -Version 5.1
<#
.SYNOPSIS
    C Drive Triage -- categorizes space usage for cleanup decisions

.DESCRIPTION
    Scans the C drive and outputs a structured report split into:
      [A] Safe to delete immediately
      [B] Can move to D drive
      [C] Do NOT touch (system / app)
      [D] Review manually (large, unknown)

    Run as Administrator for full access.
    Output is saved to a .txt file on the Desktop so you can share it.
#>

$ErrorActionPreference = "SilentlyContinue"
$ReportPath = "$env:USERPROFILE\Desktop\DiskTriage_$(Get-Date -Format 'yyyyMMdd_HHmm').txt"

function Format-GB { param([long]$b); "{0:F1} GB" -f ($b/1GB) }
function Format-MB { param([long]$b); "{0:F0} MB" -f ($b/1MB) }
function Format-Auto {
    param([long]$b)
    if ($b -ge 1GB) { return Format-GB $b }
    return Format-MB $b
}

function Get-Size {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return [long]0 }
    try {
        $r = Get-ChildItem $Path -Recurse -Force -File -ErrorAction SilentlyContinue |
             Measure-Object -Property Length -Sum -ErrorAction SilentlyContinue
        if ($null -eq $r -or $null -eq $r.Sum) { return [long]0 }
        return [long]$r.Sum
    } catch { return [long]0 }
}

function Get-FileSize {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return [long]0 }
    $f = Get-Item $Path -Force -ErrorAction SilentlyContinue
    if ($null -eq $f) { return [long]0 }
    return [long]$f.Length
}

$lines = [System.Collections.Generic.List[string]]::new()
function Out {
    param([string]$Text = "", [switch]$NoFile)
    Write-Host $Text
    $lines.Add($Text)
}

Out "================================================================"
Out "  C DRIVE TRIAGE REPORT"
Out ("  Generated : {0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"))
Out ("  User      : {0}" -f $env:USERNAME)
Out "================================================================"

# ── Drive stats ────────────────────────────────────────────────────────────
$disk      = Get-PSDrive C -ErrorAction Stop
$total     = $disk.Used + $disk.Free
$used      = $disk.Used
$free      = $disk.Free
$usedPct   = [Math]::Round($used / $total * 100, 1)

Out ""
Out ("  Total: {0}   Used: {1} ({2}%)   Free: {3}" -f (Format-GB $total),(Format-GB $used),$usedPct,(Format-GB $free))
Out ""

# ── [A] SAFE TO DELETE ─────────────────────────────────────────────────────
Out "================================================================"
Out "  [A] SAFE TO DELETE  (no risk, straightforward cleanup)"
Out "================================================================"

$catA = @(
    [PSCustomObject]@{ Label="User Temp (%LOCALAPPDATA%\Temp)";         Path="$env:LOCALAPPDATA\Temp";                                     HowTo="del /s /q `"%LOCALAPPDATA%\Temp\*`"" }
    [PSCustomObject]@{ Label="System Temp (Windows\Temp)";              Path="$env:SystemRoot\Temp";                                        HowTo="del /s /q `"%SystemRoot%\Temp\*`"" }
    [PSCustomObject]@{ Label="Windows Update Download Cache";           Path="C:\Windows\SoftwareDistribution\Download";                    HowTo="Settings > Windows Update > Advanced > Delivery Optimization" }
    [PSCustomObject]@{ Label="Windows.old (previous Windows version)";  Path="C:\Windows.old";                                             HowTo="cleanmgr -> Previous Windows Installation" }
    [PSCustomObject]@{ Label="Windows Prefetch";                        Path="C:\Windows\Prefetch";                                         HowTo="del /s /q C:\Windows\Prefetch\*" }
    [PSCustomObject]@{ Label="Memory Dump files";                       Path="C:\Windows\Minidump";                                         HowTo="del /s /q C:\Windows\Minidump\*" }
    [PSCustomObject]@{ Label="Chrome Cache";                            Path="$env:LOCALAPPDATA\Google\Chrome\User Data\Default\Cache";     HowTo="Chrome: Settings > Privacy > Clear browsing data" }
    [PSCustomObject]@{ Label="Edge Cache";                              Path="$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default\Cache";    HowTo="Edge: Settings > Privacy > Clear browsing data" }
    [PSCustomObject]@{ Label="Firefox Cache";                           Path="$env:LOCALAPPDATA\Mozilla\Firefox\Profiles";                  HowTo="Firefox: Settings > Privacy > Clear Data" }
    [PSCustomObject]@{ Label="npm cache";                               Path="$env:LOCALAPPDATA\npm-cache";                                 HowTo="npm cache clean --force" }
    [PSCustomObject]@{ Label="pip cache";                               Path="$env:LOCALAPPDATA\pip\Cache";                                 HowTo="pip cache purge" }
    [PSCustomObject]@{ Label="conda packages cache";                    Path="$env:USERPROFILE\.conda\pkgs";                                HowTo="conda clean --all" }
    [PSCustomObject]@{ Label="yarn cache";                              Path="$env:LOCALAPPDATA\Yarn\Cache";                                HowTo="yarn cache clean" }
    [PSCustomObject]@{ Label="Gradle cache";                            Path="$env:USERPROFILE\.gradle\caches";                             HowTo="delete folder contents" }
    [PSCustomObject]@{ Label="NuGet cache";                             Path="$env:LOCALAPPDATA\NuGet\Cache";                               HowTo="dotnet nuget locals all --clear" }
    [PSCustomObject]@{ Label="IIS Logs";                                Path="C:\inetpub\logs";                                             HowTo="delete old log files" }
    [PSCustomObject]@{ Label="Thumbnail cache";                         Path="$env:LOCALAPPDATA\Microsoft\Windows\Explorer";                HowTo="cleanmgr -> Thumbnails" }
)

$totalA = [long]0
foreach ($item in $catA) {
    $sz = Get-Size $item.Path
    if ($sz -gt 0) {
        $flag = if ($sz -ge 1GB) { "  ***" } elseif ($sz -ge 100MB) { "  **" } else { "" }
        Out ("  {0,-48} {1,8}{2}" -f $item.Label, (Format-Auto $sz), $flag)
        Out ("    How: {0}" -f $item.HowTo)
        $totalA += $sz
    }
}
Out ""
Out ("  [A] SUBTOTAL : {0}" -f (Format-GB $totalA))

# ── hibernate / pagefile ───────────────────────────────────────────────────
Out ""
Out "  -- Hibernate / Page file --"
$hib  = Get-FileSize "C:\hiberfil.sys"
$page = Get-FileSize "C:\pagefile.sys"
if ($hib -gt 0) {
    Out ("  hiberfil.sys  {0,8}   <- safe to remove if you never hibernate" -f (Format-Auto $hib))
    Out "    How: (admin) powercfg /h off"
}
if ($page -gt 0) {
    Out ("  pagefile.sys  {0,8}   <- virtual memory, do NOT delete" -f (Format-Auto $page))
}

# ── [B] CAN MOVE TO D ─────────────────────────────────────────────────────
Out ""
Out "================================================================"
Out "  [B] CAN MOVE TO D DRIVE  (user data, projects, large installs)"
Out "================================================================"

$catB = @(
    [PSCustomObject]@{ Label="Documents";            Path="$env:USERPROFILE\Documents" }
    [PSCustomObject]@{ Label="Downloads";            Path="$env:USERPROFILE\Downloads" }
    [PSCustomObject]@{ Label="Pictures";             Path="$env:USERPROFILE\Pictures" }
    [PSCustomObject]@{ Label="Videos";               Path="$env:USERPROFILE\Videos" }
    [PSCustomObject]@{ Label="Music";                Path="$env:USERPROFILE\Music" }
    [PSCustomObject]@{ Label="Desktop";              Path="$env:USERPROFILE\Desktop" }
    [PSCustomObject]@{ Label="OneDrive local cache"; Path="$env:USERPROFILE\OneDrive" }
    [PSCustomObject]@{ Label="Steam library";        Path="C:\Program Files (x86)\Steam\steamapps" }
    [PSCustomObject]@{ Label="Steam library (alt)";  Path="C:\SteamLibrary" }
    [PSCustomObject]@{ Label="Epic Games";           Path="C:\Program Files\Epic Games" }
    [PSCustomObject]@{ Label="Riot Games";           Path="C:\Riot Games" }
    [PSCustomObject]@{ Label="Battle.net";           Path="C:\Program Files (x86)\Battle.net" }
    [PSCustomObject]@{ Label="Origin/EA games";      Path="C:\Program Files (x86)\Origin Games" }
)

$totalB = [long]0
foreach ($item in $catB) {
    $sz = Get-Size $item.Path
    if ($sz -gt 0) {
        $flag = if ($sz -ge 5GB) { "  ***" } elseif ($sz -ge 1GB) { "  **" } else { "" }
        Out ("  {0,-48} {1,8}{2}" -f $item.Label, (Format-Auto $sz), $flag)
        $totalB += $sz
    }
}

# Dev projects in home
Out ""
Out "  -- Development project folders (in home dir) --"
$devPaths = @("$env:USERPROFILE\Projects","$env:USERPROFILE\Dev","$env:USERPROFILE\Source",
              "$env:USERPROFILE\repos","$env:USERPROFILE\workspace","$env:USERPROFILE\git",
              "C:\Projects","C:\Dev","C:\Source","C:\repos")
foreach ($p in $devPaths) {
    $sz = Get-Size $p
    if ($sz -gt 0) {
        Out ("  {0,-48} {1,8}  ** (move project folder, keep node_modules out)" -f $p, (Format-Auto $sz))
        $totalB += $sz
    }
}

# node_modules
Out ""
Out "  -- node_modules inside home dir (top 5) --"
$nms = Get-ChildItem $env:USERPROFILE -Filter node_modules -Directory -Recurse -Force -Depth 5 -ErrorAction SilentlyContinue |
       Where-Object { $_.FullName -notmatch "node_modules\\node_modules" } |
       ForEach-Object { $sz = Get-Size $_.FullName; [PSCustomObject]@{Path=$_.FullName;Size=$sz} } |
       Sort-Object Size -Descending
if ($null -ne $nms -and @($nms).Count -gt 0) {
    $nma = @($nms)
    $nmTotal = ($nma | Measure-Object -Property Size -Sum).Sum
    Out ("  node_modules total ({0} dirs): {1}" -f $nma.Count, (Format-Auto $nmTotal))
    Out "  Tip: delete node_modules before moving project, then npm install on D:\"
    $nma | Select-Object -First 5 | ForEach-Object {
        Out ("    {0,-55} {1,8}" -f $_.Path, (Format-Auto $_.Size))
    }
    $totalB += $nmTotal
}

# Docker/WSL VHDX
Out ""
Out "  -- Docker / WSL virtual disks --"
$vPaths = @("$env:LOCALAPPDATA\Docker\wsl","$env:LOCALAPPDATA\Packages","C:\Users")
$vhdxAll = @()
foreach ($vp in $vPaths) {
    if (Test-Path $vp) {
        $found = Get-ChildItem $vp -Filter *.vhdx -Recurse -Force -ErrorAction SilentlyContinue
        if ($null -ne $found) { $vhdxAll += $found }
    }
}
if ($vhdxAll.Count -gt 0) {
    foreach ($v in ($vhdxAll | Sort-Object Length -Descending)) {
        Out ("  {0,-55} {1,8}" -f $v.Name, (Format-Auto $v.Length))
        Out ("    Path: {0}" -f $v.FullName)
        Out "    Tip : Docker Desktop -> Settings -> Resources -> change WSL disk location to D:\"
        $totalB += $v.Length
    }
} else {
    Out "  (none found)"
}

Out ""
Out ("  [B] SUBTOTAL : {0}" -f (Format-GB $totalB))
Out "  NOTE: 'Move to D' means changing the folder location in Windows settings."
Out "        Do NOT simply copy-paste Program Files folders -- reinstall to D:\ instead."

# ── [C] DO NOT TOUCH ──────────────────────────────────────────────────────
Out ""
Out "================================================================"
Out "  [C] DO NOT TOUCH  (system / app -- deleting breaks things)"
Out "================================================================"

$catC = @(
    [PSCustomObject]@{ Label="Windows system";      Path="C:\Windows" }
    [PSCustomObject]@{ Label="Program Files";       Path="C:\Program Files" }
    [PSCustomObject]@{ Label="Program Files (x86)"; Path="C:\Program Files (x86)" }
    [PSCustomObject]@{ Label="ProgramData";         Path="C:\ProgramData" }
    [PSCustomObject]@{ Label="AppData\Roaming";     Path="$env:APPDATA" }
    [PSCustomObject]@{ Label="AppData\Local (apps)";Path="$env:LOCALAPPDATA" }
    [PSCustomObject]@{ Label="pagefile.sys";        Path="C:\pagefile.sys" }
)

foreach ($item in $catC) {
    $sz = Get-Size $item.Path
    if ($sz -gt 0) {
        Out ("  {0,-48} {1,8}  <- leave alone" -f $item.Label, (Format-GB $sz))
    }
}
Out ""
Out "  Exception: inside AppData\Local you CAN clean caches listed in [A] above."
Out "             WinSxS: use  dism /online /cleanup-image /startcomponentcleanup"

# ── [D] REVIEW MANUALLY ────────────────────────────────────────────────────
Out ""
Out "================================================================"
Out "  [D] REVIEW MANUALLY  (large, purpose unclear)"
Out "================================================================"

# Top-level folders not in the known lists
$knownRoots = @("Windows","Program Files","Program Files (x86)","ProgramData","Users",
                "Windows.old","hiberfil.sys","pagefile.sys","swapfile.sys","Recovery",
                "System Volume Information","$Recycle.Bin","Boot","EFI","SteamLibrary",
                "Riot Games","Projects","Dev","Source","repos")

$topFolders = Get-ChildItem C:\ -Directory -Force -ErrorAction SilentlyContinue |
    Where-Object { $knownRoots -notcontains $_.Name } |
    ForEach-Object { $sz = Get-Size $_.FullName; [PSCustomObject]@{Name=$_.Name;Path=$_.FullName;Size=$sz} } |
    Sort-Object Size -Descending

if ($null -ne $topFolders -and @($topFolders).Count -gt 0) {
    foreach ($f in @($topFolders) | Where-Object { $_.Size -gt 100MB }) {
        Out ("  {0,-55} {1,8}" -f $f.Path, (Format-Auto $f.Size))
    }
}

# Large files >= 1GB anywhere (excluding known system paths)
Out ""
Out "  -- Single files >= 1 GB (top 15, excluding Windows dir) --"
$bigFiles = Get-ChildItem C:\ -File -Recurse -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Length -ge 1GB -and $_.FullName -notmatch "^C:\\Windows\\" } |
    Sort-Object Length -Descending |
    Select-Object -First 15

if ($null -ne $bigFiles -and @($bigFiles).Count -gt 0) {
    foreach ($f in $bigFiles) {
        Out ("  {0,8}  {1}" -f (Format-Auto $f.Length), $f.FullName)
    }
} else {
    Out "  (no files >= 1 GB outside Windows dir)"
}

# ── Summary ────────────────────────────────────────────────────────────────
Out ""
Out "================================================================"
Out "  SUMMARY"
Out "================================================================"
Out ("  [A] Immediately deletable : {0}" -f (Format-GB $totalA))
Out ("  [B] Movable to D drive    : {0}  (approx, incl. user data)" -f (Format-GB $totalB))
Out ("  Free now                  : {0}" -f (Format-GB $free))
$projected = $free + $totalA
Out ("  Free after [A] cleanup    : {0}  (estimated)" -f (Format-GB $projected))
Out ""
Out ("  Report saved to: {0}" -f $ReportPath)
Out "================================================================"

# Save to file
[System.IO.File]::WriteAllLines($ReportPath, $lines.ToArray(), [System.Text.UTF8Encoding]::new($false))
Write-Host ""
Write-Host "Report saved to: $ReportPath" -ForegroundColor Green
Write-Host "Please share the contents of that file." -ForegroundColor Yellow
