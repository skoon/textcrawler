# Build the portable Windows EXE. Run in PowerShell from anywhere:
#   tools\build_exe.ps1                 dist\minetoofar.exe (one file)
#   tools\build_exe.ps1 -OneFolder      dist\minetoofar-folder\minetoofar.exe
#   tools\build_exe.ps1 -Release        both, plus dist\minetoofar-folder.zip and dist\SHA256SUMS.txt
# Writes only under build\ and dist\ (both git-ignored). PyInstaller cannot cross-compile, so this
# must run on Windows, not in WSL.
param([switch]$OneFolder, [switch]$Release)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:UV_PROJECT_ENVIRONMENT = ".venv-win"

function Build([bool]$Folder) {
    $env:MTF_ONEDIR = if ($Folder) { "1" } else { "0" }
    uv run --group build pyinstaller --noconfirm --clean minetoofar.spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
    $out = if ($Folder) { "dist\minetoofar-folder\minetoofar.exe" } else { "dist\minetoofar.exe" }
    $size = [math]::Round((Get-Item $out).Length / 1MB, 1)
    Write-Host "built $out ($size MB) sha256 $((Get-FileHash $out -Algorithm SHA256).Hash)"
}

uv sync --group build
if ($LASTEXITCODE -ne 0) { throw "uv sync failed" }

if (-not $Release) {
    Build $OneFolder.IsPresent
    return
}

Build $false
Build $true
$zip = Join-Path (Get-Location) "dist\minetoofar-folder.zip"
if (Test-Path $zip) { Remove-Item $zip }
Add-Type -AssemblyName System.IO.Compression.FileSystem
[IO.Compression.ZipFile]::CreateFromDirectory(
    (Join-Path (Get-Location) "dist\minetoofar-folder"), $zip, "Optimal", $false)
# a zip that is missing files is worse than none: count what went in against what is there
$packed = [IO.Compression.ZipFile]::OpenRead($zip)
$entries = @($packed.Entries | Where-Object { $_.Name }).Count
$packed.Dispose()
$files = @(Get-ChildItem "dist\minetoofar-folder" -Recurse -File).Count
if ($entries -ne $files) { throw "the zip holds $entries files, the folder has $files" }
$sums = foreach ($file in "dist\minetoofar.exe", $zip) {
    "$((Get-FileHash $file -Algorithm SHA256).Hash.ToLower())  $(Split-Path $file -Leaf)"
}
Set-Content -Path "dist\SHA256SUMS.txt" -Value $sums
Write-Host ($sums -join "`n")
