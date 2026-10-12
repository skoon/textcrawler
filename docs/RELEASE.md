# Releases

One entry per release build, newest first. The hashes are SHA-256 of the files in `dist\`
(`SHA256SUMS.txt` is written by `tools\build_exe.ps1 -Release`). A rebuild changes them, so a
hash here names one build, not the source.

## 0.1.0, generator 1 (2026-10-11)

Built on Windows 11 (10.0.26300) with Python 3.13.15, PyInstaller 6.22.3, Textual 8.2.8.

| File | Size | SHA-256 |
|---|---|---|
| `minetoofar.exe` | 14,580,149 bytes | `c791e221aed78ea7fe0ff9c739d80a22672047c688ec0b0acb09f1f166e0377a` |
| `minetoofar-folder.zip` | 14,459,529 bytes (29 MB unzipped) | `cdefafe487809dbfb969fe1a9c8d9416889b59b315419fc3cd6c2f928ab783ce` |

**Start time** (this machine, `--ui-selftest`: the whole game starts, headless): one file 1.05 to 1.12 s, with the first-ever launch of `--version` at 0.89 s; folder build 0.41 to 0.43 s. The target was under 3 s.

**Checks** (`tools\smoke_exe.ps1`, both builds): `--version` and the file properties agree; the generator hashes for three seeds and all nine stages equal the golden manifest; a five-level run on `SIM0007` for each class prints the same line as the source; a save written by the EXE is read by the source and the reverse, with the same state hash; a lone copy writes only `MineTooFarData` beside itself; no change in any `MineTooFar` folder under AppData or the home folder, no `HKCU\Software\MineTooFar` key, and no `_MEI` folder left in `%TEMP%`. The registry check is for that key only, since there was no way to watch every write.

**Antivirus.** Windows Defender (platform 4.18.26080.4), custom scan of both files: no threats found. Not scanned with VirusTotal: uploading a file to it publishes the file, so that waits for a go-ahead; the hash above can be looked up there without uploading anything.

**Not tested here.** A machine that has never had Python installed (the smoke test only takes Python off `PATH`), the standalone console host, and double-clicking from Explorer. The window staying open on a failure was checked by starting the EXE in its own console window and seeing it still waiting after five seconds.
