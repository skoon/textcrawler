# Smoke-test a built EXE. Usage:  tools\smoke_exe.ps1 [-Exe dist\minetoofar.exe]
# Checks run with every Python directory stripped from PATH, so a hidden dependence on the dev
# environment shows up. Hashes must equal tests\golden\manifest.json (same as the source run).
param([string]$Exe = "dist\minetoofar.exe")
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$Exe = (Resolve-Path $Exe).Path
$manifest = Get-Content tests\golden\manifest.json -Raw | ConvertFrom-Json

$savedPath = $env:PATH
$env:PATH = ($env:PATH -split ";" | Where-Object { $_ -notmatch "(?i)python|uv|\.venv" }) -join ";"
try {
    $version = & $Exe --version
    if ($LASTEXITCODE -ne 0) { throw "--version failed" }
    Write-Host $version
    & $Exe --glyph-test | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "--glyph-test failed" }
    $where = (& $Exe --where | Out-String).Trim()
    $want = Join-Path (Split-Path $Exe -Parent) "MineTooFarData"
    if ($where -ne $want) { throw "portable save folder is $where, expected $want" }
    Write-Host "saves go in $where"
    $blocked = Join-Path $env:TEMP "mtf-smoke-blocker"
    Set-Content -Path $blocked -Value "not a folder"
    $before = $ErrorActionPreference
    $ErrorActionPreference = "Continue"  # the refusal is printed on stderr; that is the point
    $message = (& $Exe --seed GOLD0001 --save-dir (Join-Path $blocked "inside") 2>&1 | Out-String)
    $code = $LASTEXITCODE
    $ErrorActionPreference = $before
    Remove-Item $blocked
    if ($code -ne 2 -or $message -notmatch "cannot use the save folder") { throw "bad save dir not refused ($code): $message" }
    $ui = (& $Exe --ui-selftest --seed GOLD0001 --level 2 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $ui.StartsWith("ui ok")) { throw "--ui-selftest failed: $ui" }
    Write-Host $ui
    foreach ($case in @(@("GOLD0001", "1"), @("GOLD0042", "3"), @("GOLD0100", "5"))) {
        $stages = $manifest.seeds.($case[0]).($case[1]).PSObject.Properties
        foreach ($entry in $stages) {
            $got = (& $Exe --seed $case[0] --level $case[1] --stage $entry.Name --hash | Out-String).Trim()
            if ($got -ne $entry.Value) { throw "$($entry.Name) hash mismatch for $($case -join ' L'): $got <> $($entry.Value)" }
        }
        Write-Host "ok  $($case[0]) level $($case[1]) ($(($stages | ForEach-Object Name) -join ', '))"
    }
} finally {
    $env:PATH = $savedPath
}
Write-Host "smoke test passed"
