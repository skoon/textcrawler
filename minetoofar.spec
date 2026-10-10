# PyInstaller spec. One-file EXE by default; set MTF_ONEDIR=1 for the one-folder fallback.
# Build with tools/build_exe.ps1 (PowerShell, Windows only).
import os

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

onedir = os.environ.get("MTF_ONEDIR") == "1"

datas, binaries, hiddenimports = collect_all("textual")
datas += collect_data_files("minetoofar")  # data/*.toml and ui/theme.tcss
hiddenimports += collect_submodules("minetoofar")

a = Analysis(
    ["src/minetoofar/__main__.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    noarchive=False,
)
pyz = PYZ(a.pure)

if onedir:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="minetoofar", console=True, upx=False)
    COLLECT(exe, a.binaries, a.datas, name="minetoofar-folder", upx=False)
else:
    EXE(
        pyz, a.scripts, a.binaries, a.datas, [],
        name="minetoofar", console=True, upx=False,
    )  # fmt: skip
