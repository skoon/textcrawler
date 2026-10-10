# Build the portable Windows EXE. Run in PowerShell from anywhere:  tools\build_exe.ps1 [-OneFolder]
# Writes only under build\ and dist\ (both git-ignored). PyInstaller cannot cross-compile, so this
# must run on Windows, not in WSL.
param([switch]$OneFolder)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:UV_PROJECT_ENVIRONMENT = ".venv-win"
$env:MTF_ONEDIR = if ($OneFolder) { "1" } else { "0" }

uv sync --group build
if ($LASTEXITCODE -ne 0) { throw "uv sync failed" }
uv run --group build pyinstaller --noconfirm minetoofar.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$out = if ($OneFolder) { "dist\minetoofar-folder\minetoofar.exe" } else { "dist\minetoofar.exe" }
$size = [math]::Round((Get-Item $out).Length / 1MB, 1)
$sha = (Get-FileHash $out -Algorithm SHA256).Hash
Write-Host "built $out ($size MB) sha256 $sha"
