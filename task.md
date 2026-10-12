# task.md

## M9: The full 5-level run

- [x] A. Bot policies (`RECKLESS` unchanged, `CAREFUL` new) with a per-level `Memory`; `sim/autoplay.py` plays whole runs; tests in `tests/scenario/test_bot_policies.py` and `test_autoplay.py`
- [x] B. `tools/balance_sim.py` (200 seeds per class, all cores, GDD 8.6 verdicts, exit 1 on a miss); verdict tests
- [x] C. Tuning: Base Job Fee 15 to 10, Boiler Suit repair rate 3 to 2 (GDD A83, A84); tests that check the GDD's worked examples pin the fee at 15
- [x] D. Employment history (`R` on the title menu) and help screen (`?`), words in `log.toml`; unit and Pilot tests
- [x] E. Generator freeze: `tools/regen_golden.py` refuses to change an existing hash at the same `GEN_VERSION`; tests
- [x] F. Full-run tests: all three classes finish SIM0007; share code replays the same run; a whole run through the screens to the review and the record; save in the middle of a fight
- [x] G. Docs: GDD A83 to A87 and 8.6 "As tuned", plan "As built (M9)", README (Balance, Help, freeze)
- [x] ruff, mypy clean; pytest WSL (1,723 pass) and native Windows (1,722 pass, one POSIX-permission test skipped); generator untouched, so no fuzz; 4,500 golden hashes (9 stages) identical on both; `balance_sim.py --seeds 40` output identical on both; EXE rebuilt (13.8 MB) and smoke passes; pty run of the history (`R`) and help (`?`) screens at 80x24

### Balance (200 seeds per class, careful bot, `SIM0001`-`SIM0200`)

| | Fighter | Rogue | Ranger | Target |
|---|---|---|---|---|
| Median net per cleared level | 9 | 10 | 9 | 4-10 |
| Winning runs ending in debt | 6 of 82 | 0 of 24 | 7 of 51 | under 15% |
| Median score of a full run | 79 | 86 | 80 | 60-110 |
| Runs won | 41% | 12% | 26% | (no target) |
| Sloppy play, median slip | -22 | -17 | -20 | negative |

### Needs your eyes (M9)
- [ ] **Grimsby.** The bot's main killer in every class (45 of 118 Fighter deaths, 79 of 176 Rogue, 86 of 149 Ranger). Is he too strong at Level 1 for a 22 HP Rogue, or is it the bot that cannot sneak or retreat? Play `uv run minetoofar --seed SIM0003 --class rogue` and look for his office.
- [ ] **Rogue at 12%.** Is the Rogue meant to be this hard to finish? The bot never backstabs a sleeper on purpose.
- [ ] `uv run minetoofar`: press `R` (employment history; empty at first, then after you die or finish), `?` in play (does the help match how the game feels?).
- [ ] QA list, by hand: **death** (stand next to a Miner and wait), **victory** (`F5` five times, or play it), **debt** (use kits until the slip is negative: the desk should say it is closed), **graveyard floors** (`--seed GOLD0001`, Level 2: green floor, violet walls, a Hazard Premium on the slip), **resize** (make the window smaller than 80x24 and back), **ASCII** (`--glyphs ascii`, and `F2` in play), **save and load in a fight** (`Esc`, `S` with a monster beside you; relaunch and `C`).
- [ ] Keys the first draft lists but the game does not have: `m` message log, `M` level overview, `C` close door, `keys.toml`. Build them, or strike them from the GDD? (A87)

---

## M8: Save and load

- [x] A. `persist/paths.py`: save folder (portable `MineTooFarData\` next to the EXE, per-OS defaults, `--save-dir`), writability check; tests with faked platform/env
- [x] B. `sim/snapshot.py`: `Game.to_dict` / `from_dict` (+ Carry); round-trip tests (state hash, then 500 more inputs)
- [x] C. `persist/save.py`: JSON file, `save_version` + migration scaffold, atomic write, `layout_sha` check; errors for foreign, corrupt, newer, wrong-mine saves; interrupted write
- [x] D. `persist/records.py`: `records.json` (the personnel file), appended on death and victory
- [x] E. UI: title menu (Continue / New / Quit), Esc menu (Save & quit), `S` on the desk, autosave at check-in, delete on death/victory, `--save-dir`; Pilot tests
- [x] F. Docs; Windows; EXE (portable folder); manual checks
- [x] ruff, mypy, pytest clean on WSL (1,658 pass) and native Windows (all pass, one POSIX-permission test skipped); generator untouched, so no fuzz or golden change; EXE rebuilt (13.8 MB), smoke passes including the portable folder (`MineTooFarData` beside the EXE) and a refused bad `--save-dir`; pty run of New run, Esc, S, relaunch, Continue

### Needs your eyes (M8)
- [ ] `uv run minetoofar` (no flags): the title menu. Start a New run, play a bit, `Esc` then `S`; run it again and `C` to Continue. Check the wording and that your position, pack and log are all back.
- [ ] Take a Down Shaft and leave the desk with `Enter` (autosave), then quit with `Q` and Continue: you should arrive on the next level with your purchases. Also try `S` on the desk.
- [ ] Die once: `run.json` should be gone and `records.json` should have a line (look in `uv run minetoofar --where`).
- [ ] Try the EXE: `dist\minetoofar.exe --where` should print the folder beside it.

---

## M7: Check-ins and supply drops

- [x] A. Data: `[supply]` balance, `desk.toml` catalog, `memos.toml` templates, loaders
- [x] B. `drops` stage: 0-2 drops a level, trigger turns, pre-rolled crate contents; golden hash; fuzz
- [x] C. `desk` stage: seeded stock (first slot a Bundle) and the memo; golden hash
- [x] D. Sim: crate landing, invoice math (handling, delivery, prepaid), taking lines, billing on the slip
- [x] E. Sim: check-in (field report, promotion, Wellness Break, Standard Issue, desk purchases and their effects)
- [x] F. UI: crate glyph, invoice screen, field report, memo, desk, the whole flow; Pilot test of the full check-in
- [x] G. Bot and replay logs; docs; Windows; EXE
- [x] ruff, mypy, pytest clean on WSL and native Windows (1,529 pass each); 1,000-seed x 5-level fuzz incl. drops and desk; 4,500 golden hashes (9 stages) identical on both; EXE rebuilt (13.8 MB) and smoke passes on all nine stages; pty run of four `F5` skips (Rank 5 on Level 5) and the pack screen

### Needs your eyes (M7)
- [ ] Take the Down Shaft (`>`) on any level and walk the whole check-in: field report, pay slip, memo, desk. Read the memos (they should contradict each other now and then) and the desk wording.
- [ ] Find a supply crate (`■`, lands from turn 120 to 700, roughly 3 levels in 4 have one): step on it, tick lines with Space or a digit, and check the invoice math against what lands on your next slip.
- [ ] Judge the desk: are the prices and the "one sale a slot" rule right, and does Rank 2 after Level 1 feel right as the only promotion?

---

## M6: Loot and pay slips

- [x] A. Economy (pure): `Ledger`, `Account`, `compute_slip`, score and titles; GDD 8.6 examples 1-3; table-driven cases; invariants; 100% branch coverage
- [x] B. Content: full item catalog (weapons T1-T3, armor, shields, hats, trinkets, consumables, valuables), `loot.toml`, `docs.toml`, `[economy]` balance
- [x] C. Items in the sim: pack, carry limits, equip/use/drop/pickup, `use_charge`, torch burn, Detergent/Fizz/Kit, new weapon and trinket effects
- [x] D. Ledger folding + Game: floor items, valuables, monster/human drops, bounty, check-out (slip, repair, Standard Issue), account carried between levels
- [x] E. Generation: `loot` stage (items, documents, drops) with golden hash; fuzz invariants
- [x] F. UI: panel (pack, gold, debt, light), item glyphs, inventory/equip/use/drop/pickup, document screen, pay slip screen (coupon), posthumous slip, descend flow
- [x] G. Scripted bot and replay logs; scripted-playthrough slip test; docs; Windows; EXE
- [x] ruff, mypy, pytest clean on WSL and native Windows (1,370 pass each); economy.py 100% branch coverage; 1,000-seed x 5-level fuzz incl. loot; 3,500 golden hashes (7 stages) identical on both; EXE rebuilt (13.8 MB) and smoke passes on all seven stages; pty run of pack screen, torch and five skipped levels
- [x] Fix: traps never wall off part of the level (assumption A68); `traps` and `loot` goldens regenerated

### Needs your eyes (M6)
- [ ] Play a level with loot: `uv run minetoofar --seed GOLD0012 --class fighter`. Check the item glyphs and colours (`↑ [ ° ¡ ¤ ◊ ≡`), `g` / `i` / `e` / `q` / `d`, and the wording of the new log lines.
- [ ] Walk to the Down Shaft and read the pay slip (`>`): does the layout read like the GDD mock-up? At 24 rows it scrolls (Up/Down); at 40 rows it fits. Try `R` (decline repair) and a coupon (find a `≡` that says COUPON).
- [ ] Dying shows the Posthumous Pay Slip, then the incident report with score and title.
- [ ] Balance: see the M6 report. The reckless bot loses money on most levels; do you want the economy tuned now or in M9?

---

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
