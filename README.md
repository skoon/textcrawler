# A Mine Too Far

A terminal dungeon crawler. Design: [docs/GDD.md](docs/GDD.md). Plan: [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md).
Status: milestone 5 (all six monsters, Rogue Humans, traps, graveyard floors; five playable levels). No items, loot, or pay slips yet.

## Run (PowerShell on Windows, or WSL)

Use a separate environment per shell, because a venv built in one cannot run in the other:

```powershell
$env:UV_PROJECT_ENVIRONMENT = ".venv-win"      # WSL: export UV_PROJECT_ENVIRONMENT=.venv-wsl
uv sync
uv run minetoofar --seed BRASSLAMP42 --level 3
```

Game keys: arrows, `hjkl yubn`, numpad digits or Home/End/PgUp/PgDn move; `Shift` + a vi key
(`HJKL YUBN`) runs; `.` `5` or space waits; `x` looks (cursor, `Esc` leaves); `t` toggles the
torch light (stand-in until the item exists); `F2` toggles the glyph set; `Ctrl+L` redraws;
`a` uses your class ability (from Rank 3), `c` opens the character sheet, `>` or `Enter` on the Down Shaft descends, `F5` skips to the next level (debug, until the pay slip exists), `Q` quits (asks first). Walking into Brine with a lit torch, or onto a revealed trap, asks first. Bump a door to open it, or a monster to hit it. The window must be at least 80x24. When the Fighter
dies an incident report offers `R` retry this seed, `N` new seed, `Q` quit.

`--view` opens the milestone 1 level viewer instead (everything revealed): arrows or `hjkl` pan,
`[` `]` change level, `F2` toggles glyphs, `q` quits.

Useful flags: `--class fighter|rogue|ranger` (skip the class select screen), `--rank 1-5` (start at a higher Rank, for testing), `--glyphs auto|unicode|ascii`, `--dump` (canonical text) and `--hash` (its sha256), each with `--stage layout|theme|features|humans|traps|spawns`,
`--glyph-test` (print every glyph so you can spot missing characters), `--version`.
A share code (`1:BRASSLAMP42`) works anywhere a seed does.

## Test

```
uv run pytest                       # fast suite
uv run pytest -m slow tests/property  # 1,000-seed generator fuzz (about 2.5 minutes)
uv run ruff check . ; uv run mypy
```

Cross-platform check: run `uv run python tools/golden_check.py` on Windows and in WSL and diff the output.
After an intentional generator change: `uv run python tools/regen_golden.py --reason "why"`.

## Portable EXE (Windows only, build in PowerShell)

```powershell
tools\build_exe.ps1            # dist\minetoofar.exe (one file); add -OneFolder for a folder build
tools\smoke_exe.ps1            # checks the EXE with Python removed from PATH
```
