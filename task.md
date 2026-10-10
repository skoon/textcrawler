# task.md

## M5: Enemies and Rogue Humans

- [x] A. Terrain: Brine, Rubble, Gravestone, Monument, Open Grave tiles; Rubble costs 200; Soaked; lit torch in Brine; falling into a grave
- [x] B. Monsters: data for all 6 + Grimsby + Vane; level gating and weights; behaviours (hunter, phaser, eel, badger, overseer, trapper)
- [x] C. AI: states (Alerted, Fleeing, Buried, Submerged), noise (BFS through doors), flee map, Wraith phasing, swarm, Clang + stun, Clocked In, Overtime aura
- [x] D. Traps: three types, Hard Hat reduction, Stun Charge, Vane's runtime traps
- [x] E. Generation: theme roll (graveyard 30%), features (room kinds, Brine, Rubble, graves, Mausoleum), humans (placement, speech), traps, spawns v1 (weights, budget, beast guarantee, packs, Eels in Brine, buried Miners); golden stages
- [x] F. UI: new glyphs/colours, graveyard palette, speech and new log lines, Brine/torch prompt, descend (`>`) and debug skip (`F5`)
- [x] G. 1,000-seed fuzz (budget, >=1 beast, human reachable, Flooded Gallery, nothing in a wall); replay logs re-recorded; GDD/plan notes; Windows; EXE
- [x] ruff, mypy, pytest clean on WSL and native Windows (1,090 pass each); 1,000-seed x 5-level fuzz (found and fixed the Level 3 flood-count bug); 3,000 golden hashes identical on both; EXE rebuilt (13.7 MB) and smoke passes on all six stages; pty run skipped through all five levels and quit

### Needs your eyes (M5)
- [ ] `uv run minetoofar --seed BRASSLAMP42 --class fighter`, then `F5` to hop levels. Look at each monster's glyph and colour (undead cool, beasts warm, humans white) and the Ranger's sensed `?`/cyan ones.
- [ ] A graveyard floor: green floor, violet walls, `†` stones, `∪` open graves. Find one with `--seed` values until the floor tints (30% of levels).
- [ ] Read a human's speech in the log (Grimsby or Vane): long lines wrap with an indent. Is the tone right?
- [ ] Balance. Details in the M5 report; short version: with no healing items until M6, the Rank 1 Fighter is in real danger from Level 2 on.

---

## M4: Rogue and Ranger

- [x] geometry: rear arc (all 8 facings x 8 neighbours); facing on actors; spawn facing (own stream, golden regen; layout hashes and monster positions unchanged)
- [x] data: Rogue and Ranger, kit items, Cave Vermin, `abilities.toml`, Poisoned/Coated statuses, test Spring Trap, `[combat]` balance
- [x] table-driven test: every derived number in GDD 6.3 and 6.4 for all 3 classes at all 5 Ranks
- [x] status engine: per-status state (power, charges, tick), cooldowns as `cd:*` statuses
- [x] combat: auto-hit, bonus dice, flat bonus; Backstab, flanking (+2), dual wield (-4 off-hand)
- [x] abilities: Cleave, Poison Blades (Coated + Poisoned ticks), Dual Strike, Rank 5 upgrades, cooldowns
- [x] Ranger: Tracker sensing (radius 5, through walls), +2 vs beasts
- [x] Rogue: trap spotting (3 tiles) and Disarm; others spot adjacent traps 1 in 3; test Spring Trap; runs refuse known traps
- [x] replay: new commands; re-recorded committed logs; Rogue and Ranger logs added; bot uses abilities
- [x] ui: class select, character sheet (`c`), ability key (`a`), ability line, sensed glyphs, trap glyphs, y/N prompts
- [x] CLI `--class`; GDD (A40-A47) / plan notes; README
- [x] ruff, mypy, pytest clean on WSL and native Windows (747 pass each); 1,000-seed fuzz; 1,000 golden hashes identical on both; EXE rebuilt (13.6 MB) and smoke passes; pty run of select -> Ranger -> sheet -> quit

### Needs your eyes (M4)
- [ ] `uv run minetoofar --seed BRASSLAMP42` (no `--class`): the class select screen, then each class. Try `--rank 3` (abilities unlock) on `--level 2`.
- [ ] Judge the three classes' feel. Scripted-bot results (it fights everything, never sneaks, 12 seeds, Level 3): at Rank 3 the Fighter loses about 1 in 4, the Rogue about 1 in 2, the Ranger about 2 in 3. The Rogue's real strength (sneak attacks, traps) is what the bot ignores; GDD open question 8 is about the Ranger.
- [ ] Character sheet (`c`), the Ranger's cyan sensed enemies through walls (ASCII shows `?`), and the Delta trap glyph in your console font.

---

## M3: Combat for one class (Fighter)

- [x] content: strict table loader; `classes.toml`, `items.toml`, `monsters.toml`, `statuses.toml`
- [x] sim/combat.py: d20 hit rule, crits, damage, DR (exact-enumeration tests: 80% / 60%)
- [x] sim/statuses.py + scheduler: Stunned, Overtime, `ready_at` order, tie-breaks, cost scaling
- [x] sim/actors.py: Player stats from class, rank, kit (GDD 6.3 numbers); Monster scaling (7.6)
- [x] gen/spawns.py: `spawns` stage v0 (Miners), own dump + golden hash (layout hashes unchanged) + fuzz
- [x] sim/ai.py + game: bump attack, hunt AI, sleep/wake, scheduler loop, death, Stubborn, armor wear
- [x] sim/replay.py: state hash, recorder, replay checker, scripted bot, 3 committed logs
- [x] ui: monsters on the map, status panel (HP bar, Nearby), combat log, death screen, `--rank`
- [x] run stops when a monster is in view; Spotted event
- [x] Speed: `Grid.can_step` on raw bytes, `distance_map(until=)` (hunting turn about 12 ms -> under 2 ms)
- [x] GDD (A33-A39) / plan notes, README
- [x] ruff, mypy, pytest clean on WSL and native Windows (565 pass each); 1,000-seed fuzz incl. spawns; 1,000 golden hashes identical on both; EXE rebuilt (13.6 MB, headless start about 1.2 s) and smoke passes (layout + spawns hashes)

### Needs your eyes (M3)
- [ ] Play a fight in Windows Terminal: `uv run minetoofar --seed BRASSLAMP42` (Miners are on every level; `--rank 5 --level 5` for a hard one). Check the Miner glyph/color, HP bar, Nearby list, log wording, and the incident report on death (`R` / `N` / `Q`).
- [ ] Judge the feel: is a Rank 1 Fighter's Level 1 fight about right (4 Miners, 30 HP, Stubborn once)? The scripted bot, fighting everything it can find, survives about 20 of 20 on Level 1 and about half on Level 3.

---

## M2: Player movement and fog of war

- [x] Grid: open-door tile (`DOOR_OPEN`), sight-blocking rule, door diagonal rule covers both
- [x] core/fov.py: integer symmetric shadowcasting + radius; ASCII fixtures; symmetry property test
- [x] balance.toml `[play]` (light radii, action costs) + loader; `data/text` (log lines, level names) + loader
- [x] sim/events.py + sim/game.py: Move, Run, Wait, ToggleTorch; doors; visibility (unseen/remembered/visible)
- [x] Run stop conditions; scripted walk entry -> exit on 100 seeds; FOV timing under 5 ms (measured 0.05-0.11 ms mean)
- [x] ui/camera.py: middle-third follow (pure, tested)
- [x] ui: MapView fog + player + look cursor; status panel; log; too-small screen; keymap
- [x] CLI: game is the default, `--view` keeps the M1 map viewer; `--ui-selftest` runs the game
- [x] GDD/plan notes updated (open-door cost, run rule, `u` key clash, Q13); README
- [x] ruff, mypy, pytest clean on WSL and native Windows
- [x] EXE rebuild + smoke (13.6 MB, headless start about 1 s)
- [x] Real-terminal run in a WSL pty: boots, keys work, `Q` `y` exits 0

### Needs your eyes (M2)
- [x] (colors and dimming confirmed good) `uv run minetoofar --seed BRASSLAMP42 --level 3` (and `dist\minetoofar.exe ...`) in Windows Terminal and in a standalone PowerShell window: walk to the `>` Down Shaft; judge whether remembered tiles are dim enough but still readable (`DIM_PERCENT` in `ui/mapview.py`)
- [x] (confirmed working) Shrink the window below 80x24 (enlarge screen appears) and grow it again; try a very tall window (log grows)
- [x] Open question 13 decided: Use item is `q` (GDD updated; binding arrives with items in M6)

---

## M1: Seeded map rendered in Unicode

- [x] Scaffolding: pyproject, uv env (WSL + Windows), ruff/mypy/pytest wired
- [x] core/rng.py: SplitMix64, derive, helpers (GDD 10.3 vectors)
- [x] core/seed.py: canonical seed, share code
- [x] core/geometry.py + grid.py: Pos, directions, tiles, step rule, Dijkstra
- [x] content/balance.py + data/balance.toml (importlib.resources, ints only)
- [x] gen/layout.py: BSP, caves, corridors, doors, entry/exit, validation, retry
- [x] LevelSpec.dump() + sha256
- [x] ui/glyphs.py: Unicode + ASCII sets, wall autotile, auto detect
- [x] ui MapView app (pan, level switch, glyph toggle)
- [x] CLI: --seed --level --glyphs --dump --hash --glyph-test --version
- [x] AST guard test (no floats/random/time/etc. in core/gen/sim)
- [x] Golden seeds (manifest + 3 full dumps), subprocess determinism test
- [x] 1,000-seed fuzz (slow marker)
- [x] Packaging spike: minetoofar.spec + tools/build_exe.ps1, EXE dump hash == source
- [x] ruff, mypy, pytest all clean
- [x] Windows-native check (PowerShell): hash equals WSL

## Needs your eyes (cannot be verified from WSL)
- [ ] Run `uv run minetoofar --glyph-test` and `dist\minetoofar.exe --glyph-test` in Windows Terminal and in a standalone PowerShell window; note any missing or double-wide glyphs
- [ ] Run `dist\minetoofar.exe --seed BRASSLAMP42 --level 3` (and `--glyphs ascii`); check the map looks right in both consoles
