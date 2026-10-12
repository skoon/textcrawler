# A Mine Too Far

A terminal dungeon crawler. Design: [docs/GDD.md](docs/GDD.md). Plan: [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md).
Status: milestone 10 (the whole game, a tuned economy, and a portable Windows EXE in two forms: see "Running the portable EXE").

## Run (PowerShell on Windows, or WSL)

Use a separate environment per shell, because a venv built in one cannot run in the other:

```powershell
$env:UV_PROJECT_ENVIRONMENT = ".venv-win"      # WSL: export UV_PROJECT_ENVIRONMENT=.venv-wsl
uv sync
uv run minetoofar --seed BRASSLAMP42 --level 3
```

Game keys: arrows, `hjkl yubn`, numpad digits or Home/End/PgUp/PgDn move; `Shift` + a vi key
(`HJKL YUBN`) runs; `.` `5` or space waits; `x` looks (cursor, `Esc` leaves); `t` toggles the
torch (lighting takes one from the pack); `g` or `,` picks up, `i` shows the pack, `e` equips (a capital letter puts a light weapon in the off hand), `q` uses, `d` drops; `F2` toggles the glyph set; `Ctrl+L` redraws; `?` shows the keys and the rules of the job;
`a` uses your class ability (from Rank 3), `c` opens the character sheet, `>` or `Enter` on the Down Shaft starts the check-in: field report, pay slip (`R` declines armor repair, a digit spends a coupon, `Enter` signs), company memo, and the Requisitions Desk (a digit buys, `Enter` goes down); a supply crate (`■`) opens its invoice when you step on it (`Space` or a digit ticks a line, `Enter` takes them); `F5` skips a level quietly (debug), `Esc` opens the menu (Save & quit); `Q` quits without saving (asks first). Walking into Brine with a lit torch, or onto a revealed trap, asks first. Bump a door to open it, or a monster to hit it. The window must be at least 80x24. When the Fighter
dies an incident report offers `R` retry this seed, `N` new seed, `Q` quit.

`--view` opens the milestone 1 level viewer instead (everything revealed): arrows or `hjkl` pan,
`[` `]` change level, `F2` toggles glyphs, `q` quits.

Useful flags: `--class fighter|rogue|ranger` (skip the class select screen), `--rank 1-5` (start at a higher Rank, for testing), `--glyphs auto|unicode|ascii`, `--dump` (canonical text) and `--hash` (its sha256), each with `--stage layout|theme|features|humans|traps|spawns|loot|drops|desk`,
`--glyph-test` (print every glyph so you can spot missing characters), `--save-dir PATH` (where the saved run and the personnel file live), `--version`.
A share code (`1:BRASSLAMP42`) works anywhere a seed does, and names the same mine on any machine: the generator is frozen at version 1, so a code from this build will not change meaning later (a change would bump the version, and old codes would be refused by name).

## Saving

Running `minetoofar` with no seed or class shows the title menu: Continue the saved run, start a New run, read the Employment history (`R`: your last eight finished runs, newest first), or Quit. One run is saved at a time: with `Esc`, then `S` at any moment; with `S` on the Requisitions Desk; and automatically whenever you leave the desk. Dying or finishing the run removes the save and adds a line to `records.json`. A run started with `--seed` or `--class` never replaces a saved one without asking.

The files live in `MineTooFarData\` next to the EXE (portable build), otherwise in `%APPDATA%\MineTooFar\` (Windows), `~/.local/share/minetoofar/` (Linux) or `~/Library/Application Support/MineTooFar/` (macOS); `--save-dir` overrides all of these. A folder that cannot be written stops the game with a message.

## Test

```
uv run pytest                       # fast suite
uv run pytest -m slow tests/property  # 1,000-seed generator fuzz (about 6 minutes)
uv run ruff check . ; uv run mypy
uv run pytest tests/unit/test_economy.py --cov=minetoofar.sim.economy --cov-branch --cov-fail-under=100
```

Cross-platform check: run `uv run python tools/golden_check.py` on Windows and in WSL and diff the output.
The generator is frozen at version 1: `tools/regen_golden.py --reason "why"` refuses to change a hash that is already in the manifest unless `GEN_VERSION` (in `core/seed.py`) has been bumped first.

## Balance

```
uv run python tools/balance_sim.py                 # 200 seeds per class, a careful scripted player
uv run python tools/balance_sim.py --policy reckless   # a sloppy one: it must lose money
uv run python tools/balance_sim.py --seeds 40 --classes fighter
```

The simulator plays whole runs with a scripted bot (`sim/bot.py`, `sim/autoplay.py`) on seeds `SIM0001` upward, all cores at once, and checks the GDD 8.6 targets: median net pay per cleared level 4 to 10g, fewer than 15% of winning runs ending in debt, a median full-run score of 60 to 110. The bot is a stand-in for a competent player, not a measure of how hard the game is for a person; see GDD assumption A85 for what it does and where it is weak. Exit status is 1 when a target is missed.

## Running the portable EXE (Windows)

Two builds, same game. Pick one:

- `minetoofar.exe`, a single file (about 14 MB). It unpacks itself into `%TEMP%` for each launch and cleans up on exit, and starts in about a second.
- `minetoofar-folder.zip`: unzip it anywhere and run `minetoofar.exe` inside. It starts in under half a second.

No Python is needed. Double-click it, or run it from PowerShell or Windows Terminal; the window must be at least 80x24. If the box-drawing characters look wrong in an old console, run `minetoofar.exe --glyphs ascii` (or press `F2` in play). `--glyph-test` shows every symbol in both sets.

**Where your saves go.** In a `MineTooFarData\` folder next to the EXE: `run.json` (the saved run) and `records.json` (the employment history). To move a game, move the EXE and that folder together. `minetoofar.exe --where` prints the folder, and `--save-dir PATH` uses another. Nothing is written to `%APPDATA%` or the registry, and a folder it cannot write to stops the game with a message instead of picking another place.

**Windows may warn you.** The EXE is not code-signed, so SmartScreen can show "Windows protected your PC" the first time: choose "More info", then "Run anyway". If the window closes on a failure when you double-click, it now waits for Enter so you can read why.

**Checking a download.** `SHA256SUMS.txt` lists the hash of each file; compare with `Get-FileHash minetoofar.exe`. The hashes of each release are recorded in [docs/RELEASE.md](docs/RELEASE.md).

**Building it yourself** (PowerShell, on Windows; PyInstaller cannot cross-compile):

```powershell
tools\build_exe.ps1               # dist\minetoofar.exe
tools\build_exe.ps1 -OneFolder    # dist\minetoofar-folder\
tools\build_exe.ps1 -Release      # both, minetoofar-folder.zip, and SHA256SUMS.txt
tools\smoke_exe.ps1               # also: -Exe dist\minetoofar-folder\minetoofar.exe
```

`smoke_exe.ps1` runs the EXE with Python taken off `PATH` and checks that it prints exactly what the source prints: the generator hashes against the golden manifest, a whole five-level run for each class (`--autoplay`), and a save written by one build and read by the other (`--save-selftest write|read`). It also times the start, checks the file properties, and confirms nothing was written outside `MineTooFarData` and no registry key or temp leftover appeared.
