# A Mine Too Far

A terminal dungeon crawler. Design: [docs/GDD.md](docs/GDD.md). Plan: [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md).
Status: milestone 9 (the whole five-level run: three classes, the check-in, one save slot, the employment history, a help screen, and a tuned economy). The portable EXE release is milestone 10.

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

## Portable EXE (Windows only, build in PowerShell)

```powershell
tools\build_exe.ps1            # dist\minetoofar.exe (one file); add -OneFolder for a folder build
tools\smoke_exe.ps1            # checks the EXE with Python removed from PATH
```
