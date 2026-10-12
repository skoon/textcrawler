# Smoke-test a built EXE. Usage:  tools\smoke_exe.ps1 [-Exe dist\minetoofar.exe] [-MaxStartSeconds 3]
# Checks run with every Python directory stripped from PATH, so a hidden dependence on the dev
# environment shows up. What the EXE prints must equal what the source prints (hashes, a whole
# bot-played run per class, a save written by one and read by the other), and the golden manifest.
# It writes only under a fresh folder in %TEMP%, which it removes at the end; it never touches
# your own MineTooFarData.
param([string]$Exe = "dist\minetoofar.exe", [double]$MaxStartSeconds = 3)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$Exe = (Resolve-Path $Exe).Path
$manifest = Get-Content tests\golden\manifest.json -Raw | ConvertFrom-Json
$env:UV_PROJECT_ENVIRONMENT = ".venv-win"
$work = Join-Path $env:TEMP "mtf-smoke-$([guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Path $work | Out-Null

$savedPath = $env:PATH
$strippedPath = ($env:PATH -split ";" | Where-Object { $_ -notmatch "(?i)python|uv|\.venv" }) -join ";"

# What the source says: run it with the real PATH, then go back to the stripped one.
function FromSource([string[]]$Rest) {
    $env:PATH = $savedPath
    try { (& uv run --no-sync minetoofar @Rest | Out-String).Trim() } finally { $env:PATH = $strippedPath }
}
function FromExe([string[]]$Rest) { (& $Exe @Rest | Out-String).Trim() }

# Every folder that could be this game's, and when each file in it last changed.
function Footprint {
    $roots = @($env:APPDATA, $env:LOCALAPPDATA, $env:USERPROFILE, [Environment]::GetFolderPath("MyDocuments"))
    $found = foreach ($root in $roots) {
        Get-ChildItem $root -Directory -Filter "*MineTooFar*" -ErrorAction SilentlyContinue |
            ForEach-Object { Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue }
    }
    ($found | ForEach-Object { "$($_.FullName) $($_.LastWriteTimeUtc.Ticks)" } | Sort-Object) -join "`n"
}
function TempBundles { @(Get-ChildItem $env:TEMP -Filter "_MEI*" -Directory -ErrorAction SilentlyContinue).Count }

try {
    $footBefore = Footprint
    $bundlesBefore = TempBundles
    $env:PATH = $strippedPath

    $cold = (Measure-Command { $version = FromExe "--version" }).TotalSeconds
    Write-Host "$version  (cold start $([math]::Round($cold, 2)) s)"
    if ($LASTEXITCODE -ne 0) { throw "--version failed" }
    $numbers = ($version -split " ")[1]
    $props = (Get-Item $Exe).VersionInfo
    if ($props.ProductVersion -ne $numbers -or $props.FileDescription -ne "A Mine Too Far") {
        throw "file properties say $($props.ProductVersion) / $($props.FileDescription), --version says $numbers"
    }
    Write-Host "file properties: $($props.ProductName) $($props.ProductVersion), $($props.CompanyName)"

    & $Exe --glyph-test | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "--glyph-test failed" }
    $where = FromExe "--where"
    $want = Join-Path (Split-Path $Exe -Parent) "MineTooFarData"
    if ($where -ne $want) { throw "portable save folder is $where, expected $want" }
    Write-Host "saves go in $where"

    # a save folder that cannot be made is refused, not worked around
    $blocked = Join-Path $work "blocker"
    Set-Content -Path $blocked -Value "not a folder"
    $before = $ErrorActionPreference
    $ErrorActionPreference = "Continue"  # the refusal is printed on stderr; that is the point
    $message = (& $Exe --seed GOLD0001 --save-dir (Join-Path $blocked "inside") 2>&1 | Out-String)
    $code = $LASTEXITCODE
    $ErrorActionPreference = $before
    if ($code -ne 2 -or $message -notmatch "cannot use the save folder") { throw "bad save dir not refused ($code): $message" }

    # the game starts, and how long that takes
    $times = 1..3 | ForEach-Object {
        $t = (Measure-Command { $ui = FromExe "--ui-selftest", "--seed", "GOLD0001", "--level", "2" }).TotalSeconds
        if ($LASTEXITCODE -ne 0 -or -not $ui.StartsWith("ui ok")) { throw "--ui-selftest failed: $ui" }
        $t
    }
    Write-Host $ui
    $shown = ($times | ForEach-Object { [math]::Round($_, 2) }) -join ", "
    Write-Host "game start: $shown s"
    if (($times | Measure-Object -Minimum).Minimum -gt $MaxStartSeconds) {
        Write-Warning "starting the game takes more than $MaxStartSeconds s; the one-folder zip starts faster"
    }

    # generator output equals the golden manifest
    foreach ($case in @(@("GOLD0001", "1"), @("GOLD0042", "3"), @("GOLD0100", "5"))) {
        $stages = $manifest.seeds.($case[0]).($case[1]).PSObject.Properties
        foreach ($entry in $stages) {
            $got = FromExe "--seed", $case[0], "--level", $case[1], "--stage", $entry.Name, "--hash"
            if ($got -ne $entry.Value) { throw "$($entry.Name) hash mismatch for $($case -join ' L'): $got <> $($entry.Value)" }
        }
        Write-Host "ok  $($case[0]) level $($case[1]) ($(($stages | ForEach-Object Name) -join ', '))"
    }

    # a whole five-level run per class plays out the same in the EXE as in the source
    foreach ($class in "fighter", "rogue", "ranger") {
        $got = FromExe "--autoplay", "--seed", "SIM0007", "--class", $class
        $expected = FromSource "--autoplay", "--seed", "SIM0007", "--class", $class
        if ($got -ne $expected -or -not $got.StartsWith("autoplay ok")) { throw "run differs for ${class}:`n  exe    $got`n  source $expected" }
        Write-Host "ok  $got"
    }

    # a save written by one build is read by the other, each way, and says the same
    $a = Join-Path $work "from-exe"; $b = Join-Path $work "from-source"
    $written = FromExe "--seed", "SIM0007", "--class", "ranger", "--save-dir", $a, "--save-selftest", "write"
    $readBySource = FromSource "--save-dir", $a, "--save-selftest", "read"
    if ($readBySource -ne $written.Replace("save written:", "save ok:")) { throw "source misread the EXE's save:`n  $written`n  $readBySource" }
    $written2 = FromSource "--seed", "SIM0007", "--class", "ranger", "--save-dir", $b, "--save-selftest", "write"
    $readByExe = FromExe "--save-dir", $b, "--save-selftest", "read"
    if ($readByExe -ne $written2.Replace("save written:", "save ok:")) { throw "EXE misread the source's save:`n  $written2`n  $readByExe" }
    if ($written -ne $written2) { throw "the two builds wrote different saves:`n  $written`n  $written2" }
    Write-Host "ok  $readByExe  (each build reads the other's save)"

    # a copy of the EXE (with its folder, if it has one), alone in a new place, keeps its saves
    # beside itself and nowhere else
    $lone = Join-Path $work "lone"
    New-Item -ItemType Directory -Path $lone | Out-Null
    Copy-Item "$(Split-Path $Exe -Parent)\*" $lone -Recurse -Exclude "MineTooFarData"
    $names = { (Get-ChildItem $lone | ForEach-Object Name | Sort-Object) -join "," }
    $present = & $names
    $null = & (Join-Path $lone "minetoofar.exe") --seed SIM0007 --class fighter --save-selftest write
    if ($LASTEXITCODE -ne 0) { throw "the lone copy could not save" }
    $made = (& $names)
    if ($made -ne ((@($present -split ",") + "MineTooFarData" | Sort-Object) -join ",")) { throw "the lone copy changed: $present -> $made" }
    Write-Host "ok  a lone copy made only MineTooFarData beside itself"
} finally {
    $env:PATH = $savedPath
    if (Test-Path $work) { Remove-Item -Recurse -Force $work }
}

if ((Footprint) -ne $footBefore) { throw "something changed in an AppData or home MineTooFar folder" }
$ErrorActionPreference = "Continue"  # reg prints its "not found" on stderr; that is the good answer
reg query "HKCU\Software\MineTooFar" 2>$null | Out-Null
$found = $LASTEXITCODE -eq 0
$ErrorActionPreference = "Stop"
if ($found) { throw "a MineTooFar registry key exists" }
if ((TempBundles) -ne $bundlesBefore) { throw "the EXE left an unpacked copy of itself in $env:TEMP" }
Write-Host "nothing written outside MineTooFarData, no registry key, no temp leftovers"
Write-Host "smoke test passed"
