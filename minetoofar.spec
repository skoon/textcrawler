# PyInstaller spec. One-file EXE by default; set MTF_ONEDIR=1 for the one-folder fallback.
# Build with tools/build_exe.ps1 (PowerShell, Windows only).
import os
import re
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

onedir = os.environ.get("MTF_ONEDIR") == "1"

# The one place the version is written is src/minetoofar/__init__.py; the EXE's file properties
# (right-click, Properties, Details) read it from there.
version = re.search(r'__version__ = "([^"]+)"', Path("src/minetoofar/__init__.py").read_text())
assert version, "no __version__ in src/minetoofar/__init__.py"
numbers = (version.group(1).split(".") + ["0", "0", "0"])[:4]
tuple_text = ", ".join(numbers)
Path("build").mkdir(exist_ok=True)
version_file = Path("build/version_info.txt")
version_file.write_text(
    f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({tuple_text}), prodvers=({tuple_text}), mask=0x3f, flags=0x0,
                    OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable("040904B0", [
      StringStruct("CompanyName", "Dungeonco Independent Contractors"),
      StringStruct("FileDescription", "A Mine Too Far"),
      StringStruct("FileVersion", "{version.group(1)}"),
      StringStruct("InternalName", "minetoofar"),
      StringStruct("OriginalFilename", "minetoofar.exe"),
      StringStruct("ProductName", "A Mine Too Far"),
      StringStruct("ProductVersion", "{version.group(1)}")])]),
    VarFileInfo([VarStruct("Translation", [1033, 1200])])
  ]
)
""",
    encoding="utf-8",
)

datas, binaries, hiddenimports = collect_all("textual")
datas += collect_data_files("minetoofar")  # data/*.toml, data/text/*.toml and ui/theme.tcss
hiddenimports += collect_submodules("minetoofar")
# Rich loads its Unicode width tables with importlib at run time, where the build cannot see them.
hiddenimports += collect_submodules("rich")

a = Analysis(
    ["src/minetoofar/__main__.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)

if onedir:
    exe = EXE(
        pyz, a.scripts, [], exclude_binaries=True, name="minetoofar", console=True, upx=False,
        version=str(version_file),
    )  # fmt: skip
    COLLECT(exe, a.binaries, a.datas, name="minetoofar-folder", upx=False)
else:
    EXE(
        pyz, a.scripts, a.binaries, a.datas, [],
        name="minetoofar", console=True, upx=False, version=str(version_file),
    )  # fmt: skip
