# A Mine Too Far — Implementation Plan

Status: v0.2 (2026-10-09). Companion: [GDD.md](GDD.md). Open questions are resolved or approved, and the portable EXE requirement is added (§1.4, M1 spike, M10). No game code exists yet.

Section references like "GDD §8.6" point to the design document.

## Contents

1. [Library and language choice](#1-library-and-language-choice)
2. [Project structure](#2-project-structure)
3. [Milestones](#3-milestones)
4. [Dependencies between systems](#4-dependencies-between-systems)
5. [Testing strategy](#5-testing-strategy)
6. [Risks and mitigations](#6-risks-and-mitigations)
7. [Working agreement](#7-working-agreement)

---

## 1. Library and language choice

### 1.1 Language and toolchain

- **Python 3.12+** (stdlib `tomllib` for data files, modern typing). WSL has Python 3.14.4; on Windows you use PowerShell with whatever Python 3 is installed (GDD §14, Q11). `requires-python = ">=3.12"`, and `uv` fetches a matching interpreter if the installed one is older, so the project does not depend on your system Python.
- **uv** for environments and running (per your standards), **pytest** for tests, **ruff** for lint and format, **mypy** (strict on `core`, `gen`, `sim`) because type hints are required.
- **Runtime dependencies: Textual only.** Everything else is stdlib. No `numpy`, no `random`. **Build-time only:** PyInstaller, in a separate `build` dependency group, for the portable EXE (§1.4).

### 1.2 TUI candidates

The hard requirement is native Windows, with Unicode graphics and a fallback. Facts marked ✓ were checked on 2026-10-09; others are from general knowledge and flagged.

| Candidate | Native Windows | Unicode and color | Input | Headless testing | Verdict |
|---|---|---|---|---|---|
| **Textual** | Yes ✓ (cross-platform; best on Windows Terminal, reduced palette on the classic console) | truecolor, 256, 16; Unicode via Rich cell-width handling | key events with names, resize events | built-in `run_test()` / Pilot | **Recommended** |
| curses + `windows-curses` | Yes, via a PDCurses wheel. ✓ PyPI has wheels for CPython 3.12 and 3.13; I could not confirm a 3.14 wheel | wide-char support is limited; no truecolor | `getch`, resize via `KEY_RESIZE`; Windows key quirks | none built in | Fallback only |
| prompt_toolkit | Yes (win32 console and VT) | good | key bindings are excellent, but it is built around prompts and layouts, not a cell grid | dummy input/output | Viable, more plumbing for a map |
| blessed | Windows support exists through the `jinxed` terminfo shim ✓, but it is a thinner path than the others | VT-sequence based | polling keys | none built in | Not chosen (you asked to avoid Unix-first libraries) |
| Rich + hand-rolled input (`msvcrt`) | Rich renders on Windows | good | you write and maintain per-OS input | n/a | Reinvents the hard part |
| urwid | historically Unix-only (not re-verified) | | | | Rejected |
| asciimatics | has its own Windows console backend (not evaluated in depth) | | | | Not evaluated |
| SDL terminals (`python-tcod`, BearLibTerminal) | Yes, but they open a window instead of using the terminal | | | | Rejected: you want a CLI |

### 1.3 Recommendation: Textual (≥ 8.2, < 9)

Textual 8.2.8 is current ✓ and declares `Requires-Python >=3.9`, so Python 3.12+ is safe.

**Why**
- **Windows is a first-class target**, not an add-on; no PDCurses wheel to lag behind new Python releases.
- **Truecolor and Unicode** support means the graveyard palette and fog dimming just work, with automatic downgrade on weaker terminals.
- **Headless testing**: Pilot runs the real app without a terminal, so UI flows (check-in, pay slip, resize) are testable in plain `pytest` on Windows and WSL.
- **Screens and modals** map naturally to check-in, pay slip, memo, and desk.
- **Mouse and layout** features cost nothing now and keep v1.1 options open.

**Tradeoffs**
- A heavier dependency (it brings Rich and a few others) and an async event loop. Mitigation: the simulation is fully synchronous; Textual only calls `game.submit(...)`.
- API churn between major versions. Mitigation: pin `textual>=8.2,<9`, and keep all Textual imports inside `ui/`.
- Per-frame overhead is higher than raw curses, but an 80×40 map is tiny.
- Legacy `conhost` shows fewer colors. Mitigation: `--glyphs ascii` plus a 16-color palette (§6).

**Escape hatch.** Only `ui/` imports Textual. The engine exposes `Game.view()` (a grid of `(glyph_id, style_id)` plus panel data) and `Game.submit(command)`. A `curses` front end would need roughly three widgets, a key map, and the glyph table; nothing in `core`, `gen`, or `sim` would change. We do not build that front end speculatively.

**Rendering approach.** A custom `MapView` widget implements `render_line(y)` and returns Rich `Strip`s built from the view grid and the active `GlyphSet`. Panels are ordinary Textual widgets. Key handling uses our own `KeyMap` (TOML-rebindable) instead of Textual `BINDINGS`, so the engine stays input-agnostic.

### 1.4 Portable EXE

**Requirement:** the game must compile to a **portable Windows EXE**: one file, no installer, no Python on the target machine, and nothing left behind on the system.

| Option | Facts (checked 2026-10-09 unless flagged) | Verdict |
|---|---|---|
| **PyInstaller** (one-file) | 6.21.0 is current per a package mirror; supports Python 3.8-3.15, including 3.14. Installs with `uv`, needs no C compiler. One-file builds unpack to a temp folder on each launch. Textual is expected to need `--collect-all textual` (my inference, not verified; the M1 spike confirms) | **Chosen** |
| PyInstaller (one-folder) | Same tool and same spec file, no self-extraction. Zipped, it is portable but not a single EXE | Fallback shipped alongside |
| Nuitka | 4.2 (August 2026) supports Python up to 3.14. On Windows with Python 3.13+, MinGW64 does not work: it needs Visual Studio 2022+ build tools. Compiles to native code | Plan B (heavier toolchain) |
| cx_Freeze, py2exe, PyApp | Not evaluated | Not chosen |

**Why PyInstaller:** simplest toolchain, mature, works with the pinned Python, and a fallback to one-folder comes free. The risks are real and listed in §6 (R15 to R17): antivirus false positives and slow cold start are common with one-file self-extracting builds, and I found no reliable measurement that Nuitka avoids them. We measure instead of assuming.

**Design rules this adds (apply from M1, so the EXE never becomes a late surprise):**
1. **Data ships inside the package** at `src/minetoofar/data/` and is read with `importlib.resources`. No `__file__`-relative paths, no reliance on the working directory.
2. **Portable save location.** A frozen build (`sys.frozen`) stores saves, `records.json`, and `keys.toml` overrides in a `MineTooFarData\` folder **next to the EXE**; a source run uses `%APPDATA%` as before. `--save-dir` overrides both. If the folder is not writable, the game stops with a clear message; there is no silent fallback.
3. **Console subsystem build** (not windowed): it is a TUI. If a frozen build fails at startup (terminal too small, missing UTF-8), it prints the reason and waits for Enter, so a double-clicked window does not vanish.
4. **Build only on Windows.** PyInstaller builds for the OS it runs on, so `tools/build_exe.ps1` runs in PowerShell with its own `.venv-win`. WSL cannot produce the Windows EXE.
5. **One checked-in spec file** (`minetoofar.spec`) builds both the one-file EXE and the one-folder fallback. `build/` and `dist/` are git-ignored generated output; the script writes nowhere else and deletes nothing outside them.
6. **Version stamping:** `--version` prints the game version, `GEN_VERSION`, Textual version, and Python version; the same text goes into the EXE's file properties.
7. **Determinism check on the EXE:** `minetoofar.exe --seed X --level N --dump` must hash identically to the source run and to the golden manifest (§5.9).
8. **Out of scope:** installers, code signing, macOS/Linux binaries.

---

## 2. Project structure

```
textcrawler/
├── pyproject.toml            # uv project; requires-python >=3.12; dep: textual; groups: dev (pytest, ruff, mypy), build (pyinstaller)
├── uv.lock
├── .python-version           # pinned interpreter for builds (proposed 3.13); tests also run on 3.12 and 3.14
├── .gitattributes            # * text=auto eol=lf   (keeps data and goldens LF on Windows)
├── .gitignore                # .venv*, __pycache__, .mypy_cache, build/, dist/
├── minetoofar.spec           # PyInstaller spec: one-file EXE + one-folder fallback
├── README.md
├── docs/                     # GDD.md, IMPLEMENTATION_PLAN.md
├── src/minetoofar/
│   ├── data/                 # balance and content tables (TOML, integers only); read via importlib.resources
│   │   ├── balance.toml  classes.toml  monsters.toml  items.toml  loot.toml
│   │   ├── rooms.toml  statuses.toml  desk.toml  keys.toml
│   │   └── text/             # templates: log.toml  memos.toml  docs.toml  speech.toml  levels.toml
│   ├── __main__.py           # CLI: --seed --glyphs --level --dump --glyph-test --version --save-dir
│   ├── core/                 # pure, no I/O, no UI, no clock
│   │   ├── rng.py            # SplitMix64 + derive()  <-- the seeded RNG lives here
│   │   ├── seed.py           # Seed parse/canonicalize, share code, GEN_VERSION
│   │   ├── geometry.py       # Pos, 8 directions, octile distance, rear arc
│   │   ├── grid.py           # Tile enum, Grid
│   │   ├── fov.py            # integer symmetric shadowcasting
│   │   └── pathing.py        # BFS / Dijkstra maps (integer costs)
│   ├── content/              # loads data/*.toml (via importlib.resources) into frozen dataclasses; rejects floats
│   ├── gen/                  # <-- the level generator lives here
│   │   ├── level_spec.py     # LevelSpec (immutable output) and dump()
│   │   ├── layout.py         # BSP, corridors, cavern blobs, validation, retry
│   │   ├── features.py       # room types, brine, rubble, graveyard conversion
│   │   ├── spawns.py         # threat budget, monsters, pre-rolled drops
│   │   ├── humans.py         # Rogue Human placement + speech templates
│   │   ├── loot.py           # items, traps, documents
│   │   └── drops.py          # supply drop schedule and store stock
│   ├── sim/                  # game rules; deterministic; synchronous
│   │   ├── game.py           # Game: new(), submit(Command)->Events, view(), to_dict/from_dict
│   │   ├── scheduler.py      # tick-based turn order
│   │   ├── actors.py         # Actor, Player, Monster, pools
│   │   ├── combat.py         # hit resolution, damage, durability, flanking
│   │   ├── statuses.py       # status engine (data-driven)
│   │   ├── abilities.py      # Cleave, Poison Blades, Dual Strike as Action data
│   │   ├── ai.py             # states, noise, per-monster brains
│   │   ├── items.py          # Item, inventory, equipment, use_charge
│   │   ├── ledger.py         # folds events into per-level ledger
│   │   ├── economy.py        # compute_slip(), Account (wallet, debt), score
│   │   ├── checkin.py        # promotion, desk stock, standard issue
│   │   └── events.py         # typed Command and Event definitions
│   ├── persist/              # I/O boundary for saves
│   │   ├── paths.py  save.py  records.py   # paths.py: portable (next to EXE) vs %APPDATA%
│   └── ui/                   # the only package that imports Textual
│       ├── app.py  keymap.py  glyphs.py  theme.tcss   # theme.tcss read via importlib.resources
│       ├── screens/          # title, newgame, game, inventory, sheet, checkin, payslip, memo, desk, death, help
│       └── widgets/          # mapview, status_panel, log_view
├── tests/
│   ├── unit/  property/  scenario/  golden/  ui/
│   └── golden/manifest.json  golden/*.txt
└── tools/                    # regen_golden.py  golden_check.py  find_bad_seeds.py  balance_sim.py  glyph_audit.py
                              # build_exe.ps1  smoke_exe.ps1   (PowerShell; Windows only)
```

Start with **one module per bullet** and split a file only when it passes roughly 400 lines. The tree is the target shape, not a day-one scaffold.

### 2.1 Module boundaries (import rules)

| Package | May import | Must not import |
|---|---|---|
| `core` | stdlib only | everything else |
| `content` | `core`, stdlib (`tomllib`) | `gen`, `sim`, `persist`, `ui` |
| `gen` | `core`, `content` | `sim`, `persist`, `ui` |
| `sim` | `core`, `content`, `gen` | `persist`, `ui`, anything with I/O |
| `persist` | `core`, `content`, `gen`, `sim` | `ui` |
| `ui` | all of the above | n/a |

A test parses every module with `ast` and fails on a forbidden import. The same test bans, inside `core`, `gen`, and `sim`: `random`, `time`, `datetime`, `uuid`, `os`, float literals, and true division (`/`). Integer-only code is enforced, not hoped for.

### 2.2 Where the key pieces live

- **Seeded RNG:** `core/rng.py`. SplitMix64, `derive()` by label, integer-only helpers. No module-level generator exists; every consumer receives an `Rng` it was handed.
- **Seed handling:** `core/seed.py` (canonicalization, share code, `GEN_VERSION`).
- **Generator:** `gen/`. Public entry point `generate_level(seed: Seed, level: int) -> LevelSpec`. Pure function; no globals.
- **Game rules:** `sim/`. The only place that rolls `play/N` random numbers.
- **Economy:** `sim/economy.py` is pure: `compute_slip(ledger, account, choices) -> Slip`.
- **UI boundary:** `Game.submit(Command) -> list[Event]` in, `Game.view() -> GameView` out.

### 2.3 Data-driven design

Balance numbers, monster stats, item tables, room weights, and text templates live in `src/minetoofar/data/`, loaded through `importlib.resources` so they work identically from source, from an installed wheel, and from the frozen EXE. A loader turns them into frozen dataclasses and fails loudly on unknown keys, missing keys, or float values. Code contains rules; data contains numbers. This gives you "configuration over convention" and keeps tuning out of the codebase.

### 2.4 Events and the ledger

The sim emits typed events (`Hit`, `Missed`, `Killed`, `ItemUsed`, `ArmorDamaged`, `TrapTriggered`, `TorchDropped`, `ClockedIn`, `StubbornInvoked`, `ValuableCollected`, `SupplyTaken`, `HumanDefeated`, `Message`, ...). The UI renders them as log lines using templates. The **ledger** folds economic events into a per-level record, and `compute_slip` reads only the ledger. That keeps the pay slip a pure, testable function of what happened.

### 2.5 Extensibility hooks for magic (shape only)

- `statuses.py` is table-driven, so a spell is a data row.
- `Actor.pools` is a dict; v1 defines only `hp`. `Ability.costs` is an empty dict in v1.
- `Action` objects carry `cost_ticks`, `windup_ticks` (0 in v1), `targeting`, and `effects`. Cleave, Poison Blades, and Dual Strike are defined this way, so there is already one real consumer of the format.

No stamina code, spell code, or ranged targeting is written in v1.

---

## 3. Milestones

Each milestone ends when its **done criterion** is demonstrably true. I stop at each one for your review. Sizes are relative: S, M, L.

### M1 — Seeded map rendered in Unicode (L)

**Scope**
- Project setup: `pyproject.toml`, uv, ruff, mypy, pytest, `.gitattributes`.
- `core/rng.py`, `core/seed.py`, `core/geometry.py`, `core/grid.py`.
- `gen/layout.py`: BSP rooms and corridors, doors, cavern blobs, entry and exit, validation, retry. Output `LevelSpec` and `dump()`.
- `ui/`: a read-only map screen with the wall autotile, Unicode and ASCII glyph sets, and `--glyph-test`.
- CLI: `--seed`, `--level`, `--glyphs`, `--dump` (prints the canonical dump without the TUI), `--version`.
- **Packaging spike:** `minetoofar.spec` and `tools/build_exe.ps1` build a one-file EXE of this M1 viewer. Data and the theme file load via `importlib.resources`. This proves Textual, PyInstaller, and Windows glyph rendering work together before any game code depends on them.

**Done when**
1. The five reference vectors in GDD §10.3 pass.
2. `uv run minetoofar --seed BRASSLAMP42 --level 3 --dump | sha256sum` gives the **same hash on native Windows and in WSL**.
3. The map displays correctly in both glyph sets in PowerShell (inside Windows Terminal and in a standalone console window) and in WSL, and you review the glyph test screen for missing characters.
4. Three golden seeds are committed with full-text dumps; a 1,000-seed fuzz finds no disconnected level and no generation failure.
5. `ruff`, `mypy`, and `pytest` are clean.
6. The one-file EXE builds with `tools/build_exe.ps1`, runs from a shell where Python is not on `PATH`, shows the map in both glyph sets, and its `--dump` hash equals the source run's. Cold-start time and EXE size are recorded in the milestone notes.

### M2 — Player movement and fog of war (M)

**Scope:** `sim/game.py` skeleton with `Move` commands, collision, door opening, `core/fov.py` (integer shadowcasting), three visibility states with remembered tiles, light radius (Hard Hat 4; Torch stub 8), camera scrolling and resize, the status panel and log frame, `x` look, run (`HJKL...`) with stop conditions.

**Done when**
1. You can walk any seed's Level 1 from entry to exit; fog renders unseen / remembered / visible distinctly.
2. FOV tests against fixture maps (ASCII) match expected visible sets and are symmetric.
3. Resizing the terminal never crashes; below 80×24 shows the "enlarge your terminal" screen.
4. Walking the whole level, per-turn compute stays well under a frame (soft target < 5 ms for FOV on 80×40).

**As built (M2).** `Close door` is deferred (nothing closes doors yet; it arrives with monsters). Opening a door by bumping costs 100 ticks. `t` toggles the Torch light (it became the real Torch item in milestone 6). The M1 viewer stays available as `--view`. Quit is `Q` with a y/N prompt (GDD 4.1). Player-facing strings live in `src/minetoofar/data/text/`. The sim hands the UI an immutable `GameView` snapshot each turn.

### M3 — Combat for one class: Fighter (L)

**Scope:** tick scheduler, `Actor`, `play/N` RNG stream, hit resolution (GDD §7.2), damage and DR, crits, armor durability, HP bar, death screen, **Stubborn**, minimal status engine (Stunned), Shambling Miner with hunt AI, generator `spawns` stage v0, debug command to set Rank.

**Done when**
1. A Fighter can fight and die against Miners on any seed.
2. Exact-enumeration tests reproduce GDD §7.2 reference numbers (80% Fighter-vs-Miner, 60% Miner-vs-Fighter).
3. A recorded input log replays to an identical end state (same hash at every checkpoint).
4. Scheduler order tests cover ties, Overtime cost scaling, and Stun delay.

**As built (M3).**
- **Deferred to M4:** facing and flanking (hit resolution already takes a `situational` modifier, but nothing applies one yet).
- **No in-game source yet** for Stunned and Overtime; they exist as data rows and the scheduler tests apply them directly. Sources arrive with M5 (Skeleton, Grimsby) and M6 (Overtime Fizz).
- **Stages:** `spawns` has its own stream, dump, and golden hash. `--stage spawns` works with `--dump` and `--hash`. Layout hashes did not change.
- **Replay:** `sim/replay.py` checkpoints a state hash after every command (a superset of "every 50 ticks"). `sim/bot.py` is the scripted player; `tools/record_replay.py` writes the committed logs in `tests/scenario/replay/`.
- **Speed:** `Grid.can_step` reads tile bytes directly and `distance_map(until=...)` stops once the wanted tiles are settled; together they take a hunting turn from about 12 ms to under 2 ms (R9).
- **Data:** `classes.toml`, `items.toml`, `monsters.toml`, `statuses.toml`; the loader rejects floats, unknown keys, and missing keys.

### M4 — Other two classes (L)

**Scope:** Rogue (finesse, Backstab, facing and rear arc, unaware states, trap spotting and Disarm against a test trap), Ranger (dual-wield rule, Tracker sensing, beast bonus, Dual Strike), ability framework with cooldown statuses, Poison status, rank table and promotion, class select and character sheet screens.

**Done when**
1. All three classes are selectable and playable against Miners and a test Vermin pack.
2. A table-driven test reproduces every number in GDD §6.3 and §6.4 (derived stats at every Rank).
3. Backstab, flank geometry, Tracker radius, Dual Strike, Cleave, and Poison each have unit tests for their edge cases.

**As built (M4).**
- **Class select** is its own small app (`ui/select.py`) shown before the game when `--class` is not given; the character sheet is `c` in game.
- **Traps:** only the Spring Trap exists and the generator places none; tests place them. The real trap stage (three types, placement, hat reduction) stays in M5.
- **Cave Vermin** exist as data with a glyph and a tested pack scenario; the swarm bonus and spawn weights are M5.
- **Rules as data:** `[combat]` in `balance.toml` (flank, beast bonus, Backstab dice, Tracker and spotting radii), `abilities.toml`, `traps.toml`, and the Poisoned and Coated statuses.
- **Replay logs re-recorded** (facing and flanking change outcomes); Rogue and Ranger logs added. The scripted bot now uses its class ability.
- `sim/views.py` holds the read-only view dataclasses (split out of `game.py`).

### M5 — Enemies and Rogue Humans (L)

**Scope:** all six monsters with AI and noise propagation; Dijkstra maps; Wraith phasing and Clock In; Eel ambush and Brine; Badger flee and burrow; Vermin swarm; graveyard roll, palette, Cemetery Plot, Mausoleum, Open Grave rising; Rogue Humans (placement, Grimsby aura, Vane traps, speech templates); traps (three types, hidden, detection); spawn budget with level gating and the beast guarantee; Overtime, Clocked In, Soaked statuses.

**Done when**
1. Scenario tests (ASCII map fixtures) pass for every monster behavior in GDD §7.6-7.7.
2. The `spawns`, `humans`, `traps` golden stages are committed.
3. A 1,000-seed fuzz proves: budget respected, ≥1 beast per level, human reachable, a Flooded Gallery exists, no entity inside a wall.
4. A debug level-skip lets you play through all 5 levels' combat (no economy yet).

**As built (M5).**
- **Pipeline:** six stages, each with its own stream, dump, and golden hash: `layout`, `theme`, `features`, `humans`, `traps`, `spawns` (`gen/world.py: generate_world`). Layout hashes changed once: the layout now retries when no room can be a Flooded Gallery (it changes GOLD0092 level 5). `check_world` in `tests/layout_checks.py` holds the cross-stage invariants the fuzz runs.
- **Behaviors** are data-driven (`behavior` in `monsters.toml`): hunter, swarm, phaser, eel, badger, overseer, trapper. `sim/behaviors.py` holds the handlers and `sim/ai.py` the pure helpers (noise reach, flee map, phase step). Tuning lives in `balance.toml [ai] [noise] [theme] [features] [humans] [spawns]`.
- **Speech:** `content/speech.py` and `data/text/speech.toml`; lines are rolled at generation and stored in the spawn, so they are part of the `spawns` hash.
- **UI:** all eight monster glyphs, graveyard palette (`GRAVEYARD_STYLES`), log rows wrap (continuation indented two spaces), `[y/N]` before a lit torch enters Brine, `>`/`Enter` descend, `F5` debug skip. The pay slip does not exist yet, so descending only carries Rank and armor wear.
- **Found by the 1,000-seed fuzz:** Level 3 could roll 3 flooded rooms when the layout only guaranteed 2 (FUZZ00694); the roll now floods what the level has, never fewer than the guarantee.
- **Replay logs re-recorded** (every level's contents changed). Bot is hazard-aware and fights adjacent enemies.

### M6 — Loot and pay slips (L)

**Scope:** item data and loaders, inventory and equipment UI, pickup, consumables and `use_charge`, torch and light, durability, valuables, loot tables, documents, ledger, `economy.compute_slip`, pay slip screen, debt, scoring.

**Done when**
1. GDD §8.6 worked examples 1-3 pass as test fixtures.
2. Property tests hold the invariants in §5.5.
3. `economy.py` has 100% branch coverage.
4. Finishing a level shows a pay slip whose lines match what actually happened (verified by a scripted playthrough test).

**As built (M6).**
- **Economy:** `sim/economy.py` is pure (`compute_slip`, `Account`, `Choices`, `score`, `title_key`) with 100% branch coverage (`uv run pytest tests/unit/test_economy.py --cov=minetoofar.sim.economy --cov-branch --cov-fail-under=100`; `pytest-cov` is a dev dependency now). The GDD 8.6 numbers live in `balance.toml [economy]`; slip labels are in `economy.py`.
- **Ledger:** `sim/ledger.py` folds events (`ValuableCollected`, `ItemUsed`, `TrapTriggered`, `TorchDropped`, `StubbornInvoked`, Clock-Ins, `HumanDefeated`) into a per-level record; `Game._bill()` adds the worn armor and the trinket.
- **Items:** the catalog is `items.toml` (weapons T1-T3, armor, shields, hats, trinkets, consumables, valuables); `loot.toml` holds the §8.4 tables and monster drops; `text/docs.toml` the document words. The pack is `list[Item]` (`Item.charge` is the use charge). `Game` gained `Pickup`, `Equip`, `UseItem`, `DropItem`, `slip()`, `check_out()`, `carry_over()`; `Game.new(..., carry=)` brings the Associate down a level.
- **Generation:** a seventh stage, `loot` (`level/N/loot`, documents on `level/N/docs`), with its own golden hash; the other six hashes did not change. `check_world` checks the loot in the fuzz.
- **UI:** pack/gold/debt/light in the panel, item glyphs, the pack screen (`i`), item menus (`e` `q` `d`), documents, the pay slip screen (R toggles repair, digits spend coupons), the posthumous slip, the performance review. The slip scrolls at 24 rows; lines do not animate (polish for M9).
- **Traps never gate the level (A68):** found on GOLD0012, where both Level 1 traps sat on the only corridors to the Down Shaft. `Grid.count_reachable` is the test; `gen/traps.scatter_safely` applies it to static traps and `Game.can_lay_trap` to Vane's. The `traps` and `loot` goldens changed; the other five stages did not.
- **Not built yet:** Storeroom and Crossroads rooms (A60), supply drops and the desk (M7), the check-in report, memo and promotion (M7).
- **Replay logs re-recorded** (the state hash now covers the pack, floor, purse and ledger).

### M7 — Check-ins and supply drops (M)

**Scope:** field report, memo templates (including contradictions), Requisitions Desk with seeded stock, bundles and services, waivers and coupons in the fixed order, Standard Issue top-up, Wellness Break, promotion at check-in, supply drop scheduling, landing, invoice UI, and billing on taken lines.

**Done when**
1. A two-level flow works end to end: level, report, slip, memo, desk, next level.
2. Golden stages `drops` and `desk` are committed.
3. Invoice math and waiver-order tests pass.
4. A Textual Pilot test walks the entire check-in flow.

**As built (M7).**
- **Stages:** two more, `drops` (`level/N/drops`) and `desk` (`store/N`: the stock and the memo); `desk` after Level 5 is empty. The other seven goldens did not move. `check_world` checks both in the fuzz.
- **Data:** `[supply]` and `[checkin]` in `balance.toml`, the catalog in `desk.toml`, the memo templates in `text/memos.toml`.
- **Sim:** `sim/supply.py` (crates and the pure invoice math), `Game` lands crates and takes `TakeSupply` orders, `sim/checkin.py` (`field_report`, `Checkin`: promotion, Wellness Break, desk purchases, `finish()` returns the `Carry`). Desk upgrades live on the Associate (`weapon_mods`, `plated`, `hp_bonus`) and travel in the `Carry`.
- **UI:** crate glyph, invoice screen, field report, memo and desk screens, wired into the descent: report, slip, memo, desk, next level. A Pilot test walks the whole flow (`tests/ui/test_checkin_ui.py`).
- **Bot:** collects crates. A seventh replay log (`fighter-GOLD0016-L1-rank5-supply.json`) covers a crate being taken.
- **Not built yet:** saving (M8), the `S` key on the desk, and animated slip lines (M9).

### M8 — Save/load (M)

**Scope:** `to_dict/from_dict` for all sim state, JSON snapshots, `save_version` and migration scaffold, atomic writes, `paths.py`, `layout_sha` check, `records.json`, title menu (Continue / New / Quit), save on quit and at check-in, delete on death/victory.

**Done when**
1. Round-trip test: save at tick T, load, run 500 more inputs; final state hash equals the uninterrupted run.
2. A foreign, corrupted, or newer-version save fails with a clear message and does not start a game.
3. An interrupted write (only the `.tmp` file exists) leaves the previous save loadable.
4. Works with Windows paths (`%APPDATA%`) and with the portable layout (`MineTooFarData\` next to the EXE, `--save-dir` override); a read-only folder fails with a clear message.

**As built (M8).**
- **State as data:** `sim/snapshot.py` (`game_to_dict`, `game_from_dict`, carry equivalents) saves only what changes during play; the level itself is regenerated from the seed. There are no `Game.to_dict` methods because the module that reads `Game` internals sits beside it, and `Game` stays free of persistence.
- **Files:** `persist/paths.py` (portable folder, per-OS folders, `--save-dir`, writability), `persist/save.py` (format, versioning and migration scaffold, atomic write, the checks), `persist/records.py`.
- **UI:** `ui/title.py` is the title menu; the game gets an Esc menu, `S` on the desk, the autosave when leaving the desk, and the record-and-delete at death and victory. A plain launch shows the title; naming a run on the command line skips it (A78).
- **Also:** the run's total turns now travel in the carry-over (for the records); the replay logs were re-recorded because the state hash covers them.
- **Not built yet:** (these two arrived in M9; see below).

### M9 — The full 5-level run (L)

**Scope:** Level 1-5 data and scaling, final slip and review screen, titles and records, help screen, `balance_sim.py` bot and tuning pass, `gen_version` freeze at 1, golden manifest locked, README and run instructions (`uv run`). The portable EXE release is M10.

**Done when**
1. You can complete a 5-level run on a given seed, in each class, and the share code reproduces the same mine on another machine.
2. The balance simulator over 200 seeds per class meets GDD §8.6 targets, or the data is retuned until it does.
3. All tests are green on native Windows and WSL.
4. A manual QA checklist (death, victory, debt, graveyard floors, resize, ASCII mode, save/load mid-fight) is passed.

**As built (M9).**
- **Balance simulator:** `tools/balance_sim.py` runs `sim/autoplay.py` (`play_run`: five levels, the slip signed as it stands, the desk shopped from a priority list with a gold reserve) on seeds `SIM0001` up, one process per core, and judges GDD 8.6. `sim/bot.py` grew a `Policy`: `RECKLESS` is the M3 bot unchanged (the replay logs still pass) and doubles as the sloppy player; `CAREFUL` is the competent stand-in, with a per-level `Memory` (route cache, grave cache, finds given up, the find it is walking to, turns spent waiting). See GDD A85 for what it does and where it is weak. 200 seeds per class takes about two minutes on 16 cores.
- **Tuning:** Base Job Fee 15 to 10 and the Boiler Suit's repair rate 3 to 2 (A83, A84). Tests that check the GDD's worked examples pin the fee at 15g; tests that read the shipped economy use `BALANCE.economy.base_fee`.
- **Bot bugs the simulator found:** it stepped onto known traps, walked into a Rogue Human's sight for loot, waited forever for a hunter stuck behind a fleeing Badger, dithered between two equally near finds, retried a pick-up the game refuses when a full torch stack sits on top of a document, and filled its pack with spare armor. The last four came from stalled runs; there are none now.
- **Screens:** `ui/personnel.py` (the employment history, `R` on the title menu), `HelpScreen` (`?`), both with their words in `log.toml`.
- **Freeze:** `tools/regen_golden.py` refuses to change a hash already in the manifest at the same `GEN_VERSION` (A86); the manifest, the 4,500 golden hashes and the cross-platform diff are unchanged by M9.
- **Tests:** full five-level runs for all three classes on one seed and by share code (`tests/scenario/test_full_run.py`), a whole run through the screens to the review and the record (`tests/ui/test_full_run_ui.py`), a save in the middle of a fight, the careful policy's behaviours, the simulator's verdicts, and the freeze.
- **Not built:** the first draft's `m` message log, `M` level overview, `C` close door and `keys.toml` rebinding (A87). They were never in a milestone's scope.

### M10 — Portable EXE release (M)

**Scope:** harden `minetoofar.spec` for the full game (all Textual submodules, all data, version resource); finalize `build_exe.ps1` (one-file EXE plus one-folder zip fallback); write `smoke_exe.ps1`; measure cold start, size, and antivirus results (VirusTotal scan); README section "Running the portable EXE" (where saves go, how to move them, how to pick a glyph set); record the SHA-256 of each release build.

**Done when**
1. `dist\minetoofar.exe` runs a full 5-level run on a Windows machine with no Python installed, in PowerShell (Windows Terminal and standalone console) and by double-click.
2. `smoke_exe.ps1` passes: `--version`, `--glyph-test`, and `--dump` for the golden seeds hash identically to the source run and the golden manifest.
3. A save made by the EXE loads in the source run and vice versa (same `save_version`, same `layout_sha`), when pointed at the same `--save-dir`.
4. Cold start is under 3 seconds on your machine (target; if missed, the one-folder zip is the recommended download and the result is documented).
5. The EXE writes only inside its own `MineTooFarData\` folder; nothing appears in `%APPDATA%` or the registry.

**As built (M10).**
- **Spec:** `minetoofar.spec` reads the version from `src/minetoofar/__init__.py` and writes the EXE's file properties (name, description, company, product and file version); collects every `textual` and `rich` submodule (Rich loads its Unicode width tables at run time) and all data files; leaves `tkinter` out.
- **Build:** `tools/build_exe.ps1` builds one file, one folder (`-OneFolder`), or `-Release`: both, `minetoofar-folder.zip` (made with .NET and counted against the folder, because `Compress-Archive` failed quietly on a file Defender had open) and `SHA256SUMS.txt`.
- **Self-checks the EXE can run without a terminal:** `--autoplay` (the bot plays a whole run and prints how it went) and `--save-selftest write|read` (`release_check.py`), so a build is proved the same game by printing the same lines as the source. They are for the smoke test; the README does not list them as play options.
- **Smoke test:** `tools/smoke_exe.ps1` works on either build (see README); it writes only inside a fresh folder in `%TEMP%`, which it removes at the end, and never touches your own `MineTooFarData`.
- **Double-click:** after a failure in a console window the process owns alone, the EXE waits for Enter, so the message can be read (`__main__.hold_window`). Run from a shell it exits at once.
- **Release record:** `docs/RELEASE.md` has the hash, size, start time, scan result and what was not tested.
- **Not done:** a VirusTotal upload (publishes the file; asked first), code signing, a check on a machine without Python, and by-hand runs in the standalone console and from Explorer.

---

## 4. Dependencies between systems

```
rng ──► seed ──► gen(layout ► features ► humans ► spawns ► loot ► drops) ──► LevelSpec
 │                                                                              │
 │          geometry ► grid ► fov ──────────────┐                               ▼
 │                       └► pathing ──────┐     │                         sim.game
 └────────────────────────► play/N stream │     │                          ├ scheduler
                                          ▼     ▼                          ├ actors ► statuses ► combat ► abilities
                                         ai ◄── noise                      ├ items ► ledger ► economy ► checkin
                                                                           └ events ► ui (log, panels, screens)
                                                                                      persist ◄─ everything serializable
```

| System | Needs | Why it comes in this order |
|---|---|---|
| RNG, seed | nothing | everything random depends on it; fixed first |
| Layout generator | RNG, grid | the first visible milestone |
| FOV, movement | grid, LevelSpec | fog of war needs terrain |
| Scheduler, actors | LevelSpec | combat and AI sit on tick order |
| Combat | scheduler, actors, statuses (Stun), items (durability) | proven on one class first |
| Classes 2 and 3 | combat, facing, abilities | they stress rules that Fighter does not (flank, dual wield, sensing) |
| AI, noise | pathing, FOV, combat | needs the six monsters' rules |
| Rogue Humans | AI, traps, speech templates, generator placement | build on monster AI |
| Items, inventory | actors, combat | durability and `use_charge` live on items |
| Ledger, economy | items, combat events | the slip needs real events to fold |
| Check-in, desk, drops | economy, items, generator `drops` stage | the desk spends the wallet |
| Save/load | everything serializable | built last so state shapes have settled |
| Balance sim | the full game | tunes after systems are stable |
| Portable EXE | everything; resource-loading discipline from M1 | released last, spiked in M1 so surprises come early |

**Critical path:** RNG → generator → sim core → combat → items → economy → check-in → save → full run → portable EXE. Tests are not a separate phase; each milestone ships its own.

**Integration rule:** a system may not read another system's internals. Cross-system communication goes through `Command`, `Event`, `LevelSpec`, and `Ledger`.

---

## 5. Testing strategy

Your rules apply: unit tests are written with every piece of business logic, and all tests run before any task is declared done. Commands: `uv run pytest`, `uv run ruff check .`, `uv run mypy src`.

### 5.1 Layers

| Layer | Location | What it covers |
|---|---|---|
| Unit | `tests/unit/` | RNG, seed parsing, geometry, FOV, pathing, hit resolution, statuses, economy, items |
| Property / fuzz | `tests/property/` | generator invariants over many seeds; economy invariants over random ledgers |
| Scenario | `tests/scenario/` | ASCII-map fixtures for AI behaviors and combat positions |
| Golden | `tests/golden/` | generation output stability across runs and platforms |
| UI | `tests/ui/` | Textual Pilot: flows, resize, glyph-set rendering |
| Replay | `tests/scenario/replay/` | recorded input logs with periodic state-hash checkpoints |

### 5.2 Golden-seed tests (generation stays identical)

- A **manifest** (`tests/golden/manifest.json`) lists ~100 seeds × 5 levels with the SHA-256 of the canonical dump **per generation stage** (`layout`, `features`, `humans`, `spawns`, `traps`, `loot`, `drops`, `desk`). Three seeds also keep their **full text dumps** for readable diffs.
- Per-stage hashes mean adding a new stage adds a new hash instead of invalidating older ones (stages use independent streams by design, GDD §10.3).
- The test regenerates each level and compares. It fails with the stage name and a unified diff of the dump when a full dump exists.
- **Regeneration is deliberate.** `tools/regen_golden.py --reason "..."` rewrites the manifest and refuses to run unless `GEN_VERSION` was bumped (after the M9 freeze) or the reason is recorded. Before the freeze, goldens may change freely as stages land.
- **Cross-platform proof:** `tools/golden_check.py` prints `seed:level:stage:sha` lines. You have two platforms on one machine (native Windows and WSL): run it on both and `diff` the output. If you later host the repo, a CI matrix of `windows-latest`, `ubuntu-latest`, and `macos-latest` × Python 3.12/3.13/3.14 runs the same check.
- **Determinism harness:** the golden test also runs generation in fresh subprocesses with `PYTHONHASHSEED=0`, `1`, and `random`, `PYTHONUTF8=0/1`, a different `LANG`/`TZ`, `-X dev`, and `-O`, and requires identical hashes. This catches set-ordering and locale leaks that a same-process rerun cannot (a second run in one process shares module state).
- **RNG vectors:** GDD §10.3 reference values are unit tests. A stream-independence test proves that extra draws in `level/N/spawns` do not change `level/N/layout/0`.
- **Static guard:** the `ast` test in §2.1 bans floats, true division, `random`, `time`, and friends in `core`, `gen`, and `sim`.

### 5.3 Generator property tests

For a large seed sample (1,000 seeds × 5 levels in CI-lite mode; 10,000 in a manual `tools/find_bad_seeds.py` run): every room reachable from entry; entry ≠ exit; exit is reachable; 8-14 rooms; Flooded Gallery exists; human room is reachable and at the required distance; spawn threat ≤ budget; at least one beast; no entity inside a wall or on another entity; items on floor tiles only; traps never in the entry room; drop counts and turn windows in range; graveyard frequency across seeds within a loose tolerance of 30%.

### 5.4 Combat and AI tests

- Table-driven formula tests for ATK, DEF, damage at every Rank for each class (GDD §6.3-6.4).
- Exact enumeration (all 20 die faces) for hit chances, plus crit and natural-1 handling. No Monte Carlo is needed for rules; seeded Monte Carlo is used only in the balance simulator.
- Scheduler: ordering, tie-breaks, Overtime (`cost*60//100`), Stun delay, Clocked In.
- Flank geometry: all 8 facings × all 8 neighbor positions.
- AI scenario maps (ASCII fixtures): noise propagation through doors, Eel ambush, Badger flee and burrow, Wraith through walls, Grimsby aura refresh, Vane trap-and-retreat.

### 5.5 Pay slip and economy tests

- **Fixtures:** GDD §8.6 examples 1-3 are loaded as tests with expected lines and totals.
- **Table-driven cases:** every gross line; every deduction line; repair rounding (`ceil`) at boundaries (0, 1, 3, 4, 5 points at each rate); Timecard cap at 5g; `use_charge` of issued / found / prepaid; Hazard Pay Fighter-only; waiver order (each one alone, then all together); Lanyard threshold (3g inclusive); Coupon on a line smaller than 3g.
- **Deficit and debt:** wallet exactly equals the shortfall; wallet zero; wallet larger than the shortfall; debt cleared by a positive net; late fee `ceil(10%)` at 1, 9, 10, 11 gold; desk closed while in debt.
- **Invariants** (randomized ledgers from a seeded RNG, no external property library): `net == gross - adjustments`; `wallet >= 0`; `debt >= 0`; and **wealth conservation**: `(wallet' - debt') == (wallet - debt) + gross - other_adjustments - late_fee`. Both branches (net ≥ 0 and net < 0) satisfy it.
- **Integration:** scripted event sequences (use a kit, get hit, trigger a trap, kill the human) fold through the ledger into the expected slip for each class.

### 5.6 Save and replay tests

- Round-trip at several points, including mid-fight; compare state hashes.
- Migration chain with a synthetic older version fixture.
- Corruption (truncated, invalid JSON, wrong `layout_sha`, newer `save_version`) fails loudly.
- Replay logs carry **state-hash checkpoints every 50 ticks**; a log with no checkpoints proves little, so the replay runner fails if it finds none.

### 5.7 UI tests

Textual Pilot (headless): launches; map renders in both glyph sets (text snapshots of the view grid); keys map to commands; resize to 80×24 and below; the check-in flow; pay slip lines appear in order. A manual checklist covers what Pilot cannot see (actual fonts and colors in Windows Terminal and the classic console).

### 5.8 Targets

≥ 90% line coverage on `core`, `gen`, and `sim`; 100% branch coverage on `sim/economy.py`. Coverage is a floor, not a goal; the invariants above are the real protection.

### 5.9 Portable EXE tests

- `tools/smoke_exe.ps1` (Windows only, run after every build): `--version`; `--glyph-test` exits cleanly; `--dump` for the golden seeds prints hashes identical to `tools/golden_check.py` from source and to `tests/golden/manifest.json`. A mismatch fails the build.
- **Clean-environment check:** run the EXE with `PATH` stripped of every Python directory, and from a folder that contains no source tree, so a hidden dependence on the dev environment shows up.
- **Resource test (runs in normal `pytest`):** every file under `src/minetoofar/data/` loads through `importlib.resources`, and an `ast` test rejects `__file__`-relative reads outside `ui/` and `persist/paths.py`.
- **Portable paths:** unit tests for `paths.py` with `sys.frozen` faked: EXE-adjacent folder, `--save-dir` override, read-only folder error.
- **Manual (needs your eyes):** double-click launch, window title and size, Unicode glyphs in the standalone console, and the Windows Defender result.

---

## 6. Risks and mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | **Windows terminal rendering of Unicode glyphs**: missing glyphs in a font, ambiguous-width characters drawing double-wide, the legacy console lacking colors | High | High | Glyph set restricted to characters shipped with Windows fonts; `--glyph-test` audit screen reviewed in M1 on your machine; `auto` detection picks ASCII for legacy consoles; ambiguous-width config flag; 16-color palette fallback; ASCII is always playable; document "use Windows Terminal" in the README |
| R2 | **Non-determinism leaks** (floats, set order, hash randomization, locale) | Medium | Critical (breaks shareable seeds) | Integer-only rule enforced by an AST test; streams derived by label; subprocess determinism harness; golden manifest on two platforms; ASCII-only seeds |
| R3 | **Generator output drifts** during development | High | Medium | Per-stage golden hashes; independent streams; `GEN_VERSION` and share codes; regeneration needs a reason |
| R4 | **Economy feels bad** (constant debt, or no pressure) | Medium | High | All numbers live in `src/minetoofar/data/*.toml`; `balance_sim.py` bot runs 200 seeds per class; targets in GDD §8.6; M9 is a tuning pass; open questions Q2, Q4, Q5 in the GDD settle the structure early |
| R5 | **Textual API changes** | Low-Medium | Medium | Pin `textual>=8.2,<9`; all Textual imports confined to `ui/`; a curses front end remains possible |
| R6 | **Input quirks on Windows** (numpad, Shift+arrow, Ctrl combinations, key repeat) | Medium | Medium | Vi keys and arrows as primary defaults; rebindable `keys.toml`; a key-echo debug screen; avoid Ctrl chords; input ignored while a prompt is pending |
| R7 | **Two environments in one folder** (the project is on `C:`, and WSL sees it at `/mnt/c`): a venv built in one cannot run in the other; file watching is slow | High | Low | Separate venv names via `UV_PROJECT_ENVIRONMENT` (`.venv-win`, `.venv-wsl`), both git-ignored; run the TUI natively on Windows for visual checks, WSL for fast unit tests |
| R8 | **CRLF changes** from git on Windows altering data or golden files | Medium | Medium | `.gitattributes` with `eol=lf` for `data/` and `tests/golden/`; goldens hash parsed content, not raw bytes; explicit `newline="\n"` on writes |
| R9 | **Python speed** (FOV, Dijkstra per turn) | Low | Low | 80×40 maps are tiny; one Dijkstra map per turn; profile in M2/M5; optimize only if over budget |
| R10 | **Scope creep** (magic, ranged, shops) | Medium | Medium | GDD §12 out-of-scope list; milestones end with a done criterion; hooks are data shapes only |
| R11 | **Save compatibility** across versions | Medium | Medium | `save_version` and `gen_version`; `layout_sha` check; refuse rather than guess; migrations tested with fixtures |
| R12 | **Flanking rule is hard to read** for players | Medium | Low | `(flanked)` marker in look text and log; tutorial text in help; open question Q6 |
| R13 | **Save directory problems** (`%APPDATA%` unset, read-only) | Low | Medium | `paths.py` fails with a clear message and a `--save-dir` override; no silent fallback |
| R14 | **Long-run fatigue or balance cliffs** (deeper levels too lethal) | Medium | Medium | Scaling is formula-driven (GDD §7.6); bot simulation reports death rate per level; tune in data |
| R15 | **The frozen EXE behaves differently from a source run** (Textual modules loaded lazily and missed by PyInstaller, missing data files, `__file__`-relative paths, working directory) | Medium | High (the EXE is a required deliverable) | M1 packaging spike; all data via `importlib.resources`; `--collect-all textual` in the spec (to be confirmed by the spike); `smoke_exe.ps1` and the dump-hash check on every build; `ast` test against `__file__`-relative reads |
| R16 | **Antivirus or SmartScreen flags the unsigned EXE**, and one-file startup is slow (it unpacks to a temp folder on every launch) | Medium | Medium | Scan with VirusTotal before sharing; the spec also builds a one-folder zip as a fallback; measure cold start (target under 3 s); Nuitka standalone is plan B; code signing is out of scope for v1 |
| R17 | **The Windows EXE cannot be built from WSL** (PyInstaller targets the OS it runs on) | Certain | Low | `tools/build_exe.ps1` runs in PowerShell with its own `.venv-win`; WSL is for tests only |

---

## 7. Working agreement

- I make **no code changes until you approve this plan and the GDD**, and I answer the open questions in GDD §14 that you care about first (Q1, Q2, Q3, and Q11 are settled: Textual; Hazard Pay is a deduction; Rogue Humans recur by name; PowerShell and WSL are the dev shells).
- I work **one milestone at a time** and stop at its done criterion for review.
- At M1 start I create a `task.md` checklist for the milestone and keep it updated.
- I do **not** run `git init`, commit, or touch `main`. Commits are yours.
- I never delete files without asking.
- Each milestone's summary lists what I verified and what I could not (for example, visual checks in Windows Terminal that need your eyes).
