# A Mine Too Far — Game Design Document

Status: v0.2 (2026-10-09). Open questions resolved or approved; portable EXE requirement added. Companion: [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).

All numbers in this document are **starting values**. They live in data files (`src/minetoofar/data/*.toml`), not in code, and will be tuned by the balance simulator (Implementation Plan, milestone 9). Where a rule is a structural decision rather than a tuning value, it says so.

## Contents

1. [Lore bible](#1-lore-bible)
2. [Vision and design pillars](#2-vision-and-design-pillars)
3. [Core loop](#3-core-loop)
4. [Controls and input scheme](#4-controls-and-input-scheme)
5. [Screen layout](#5-screen-layout)
6. [Classes](#6-classes)
7. [Combat rules](#7-combat-rules)
8. [Items, loot, supply drops, and the gold economy](#8-items-loot-supply-drops-and-the-gold-economy)
9. [Dungeon structure](#9-dungeon-structure)
10. [Procedural generation spec](#10-procedural-generation-spec)
11. [Save/load and permadeath](#11-saveload-and-permadeath)
12. [Out of scope for v1](#12-out-of-scope-for-v1)
13. [Assumptions](#13-assumptions)
14. [Open questions](#14-open-questions)

---

## 1. Lore bible

### 1.1 Premise

The Gilded Deep was a silver mine. Its owners planned five levels. Somebody dug a sixth cut, "the Extra Level," one level too far, and broke into old caverns that were not on any survey. The mine closed. Silver prices recovered. **Dungeonco**, a cleaning corporation, acquired the mine's liabilities in what its press release calls "a friendly, non-negotiated transaction," and now needs the workings cleared so the mine can reopen.

The player is a freelance **Independent Remediation Associate**: a contractor, not an employee, with no benefits beyond "exposure." The whole run is **one job** (Job GD-0001) made of **five Work Orders** (one per level). Each Work Order ends with a **pay slip**.

**There is no final truth.** Documents found in the mine offer contradictory explanations for what is down there (a cost-cutting measure, a miners' curse, a survey error, a typo in a cleaning schedule). None is ever confirmed. The final level ends when the Work Order is signed off, not when a mystery is solved. Writers: never confirm, always leave plausible deniability.

### 1.2 Dungeonco

- Tagline: *"Dungeonco: We Handle the Hard-to-Reach™"*
- Voice: relentlessly upbeat HR/facilities language. Every disaster is an "opportunity"; every injury is "feedback."
- Memos come from the **Regional Facilities Optimization Office**. They contradict each other and are always cheerful about it.
- Dungeonco always bills. It never threatens. It just itemizes.

### 1.3 The pay slip system (lore view)

Gross pay is a flat Job Fee plus premiums and bounties. Dungeonco then deducts **Adjustments** for everything the Associate used, wore out, or dropped. The comedy and the pressure are the same thing: the company is delighted by your results and the arithmetic is merciless. Mechanical rules are in §8.

### 1.4 Threats

Dungeonco's euphemisms are used in all system text. The in-fiction names (what monsters look like) are used in descriptions.

| Class | Dungeonco calls them | Members |
|---|---|---|
| Undead | Persistent Personnel | Shambling Miner, Gravedigger Skeleton, Timecard Wraith |
| Beasts | Wildlife Interface Events | Cave Vermin, Blind Ore-Eel, Gem Badger |
| Rogue Humans | Unauthorized Personnel | Foreman Grimsby, Prospector Vane |

- **Foreman Grimsby** refuses to accept that the shift ended. He believes everyone, living or dead, is on his clock. Dungeonco's records say he has been "terminated" four times and cannot confirm the current status.
- **Prospector Vane** staked a claim here before the mine existed and booby-trapped it. He considers Dungeonco a claim jumper and the player its tool.
- Both recur: each is a named individual who can appear on any level (see §9.6). They are the problems that won't go away. Dungeonco files them under "Recurring Issues" and attributes the repeats to a "records error." Writers: lean into it. Each return should feel like a bad habit, not a new enemy ("Grimsby, again. Last quarter's resolution has been reopened.").

### 1.5 Tone guidelines

1. **Corporate cheer is the contrast.** All UI chrome, memos, and pay slips are bland, positive, and precise. Menace comes from understatement.
2. **Pulp is the content.** Monster descriptions are lurid and fast: "A skeleton in a safety vest, still carrying a shovel and a grudge."
3. **Money jokes always have a number.** "Dropped torch: -2g" beats "you are charged for the torch."
4. **Short lines.** Log lines fit 76 characters. Memos fit 56-character lines.
5. **Euphemism table (use consistently):**

| Plain | Dungeonco |
|---|---|
| Kill | resolve, close out, decommission |
| Die | separation from the project |
| Trap | site hazard |
| Wound | feedback |
| Deductions | adjustments |
| Undead | persistent personnel |
| Healing rest | wellness break |

6. **Gore is PG-13 and slapstick.** No slurs, no real-world cruelty, nothing that punches at the player's real life.
7. **Humans are grievance-lords.** Rogue Humans complain about process, pay, and property lines, then try to kill you.

### 1.6 Sample flavor text

**Kill messages**
- "The Shambling Miner has been resolved. Please remember to recycle."
- "You backstab the Cave Vermin for 11. It is no longer a vermin concern."
- "The Gem Badger drops 2 Rough Gems and a look of profound betrayal."

**Hits taken**
- "Cave Vermin bites you for 2. Feedback received."
- "The Timecard Wraith CLOCKS YOU IN. You lose a turn. Timecard Irregularity: -1g."

**Environment**
- "A sign reads: PLEASE KEEP HANDS AND FEET OUT OF THE ABYSS."
- "Your torch hisses out in the brine. Dropped torch: -2g."

**Level arrival blurbs**
- L1: "Work Order 1: Light Housekeeping. Dungeonco thanks you for choosing to be here."
- L5: "Work Order 5: Final Walkthrough. Please do not walk through the walls. Some things here can."

**Memo excerpt**
> RE: Your Valued Feedback. Team! Per Section 9.4, Level 3 has been reclassified as a "Memorial Environment." Please treat all gravestones with the same care you would treat any billable surface. Reminder: undead are not employees. Employees are undead only on Fridays.

**Found documents (samples; each contradicts the others)**
- "ASSAY NOTE 14: Sixth cut approved by verbal agreement. Nobody remembers who spoke."
- "Dear Diary, the caverns are very warm and they hum my shift song. I am not worried. — M."
- "SURVEY ERRATUM: 'Level 6' was a typographical error. Please disregard the digging."
- "CLEANING SCHEDULE: Mondays - mop. Tuesdays - mop. Wednesdays - ask the quiet ones to leave."

**Rogue Human lines**
- Grimsby, on sight: "Clock in, contractor! Nobody told me the shift ended. Boys, put in some overtime!"
- Grimsby, on death: "Write me up. I'll be... back by... Monday..."
- Vane, on sight: "Fresh claim-jumper. Mind the wire. No, really, mind it."
- Vane, retreating: "Not a retreat. A relocation of assets."

**Death screen**
> SEPARATION FROM THE PROJECT. Your Work Order has been reassigned. Dungeonco regrets nothing, and has itemized the regret on the attached slip.

---

## 2. Vision and design pillars

**One sentence:** A short, seedable, Windows-native terminal dungeon crawler where every gold piece is a decision and the dungeon is a cheerful workplace nightmare.

**Pillars**

1. **Every gold piece is a decision.** Net pay hovers near zero, so each potion, torch, and repaired armor point is a trade against profit.
2. **Cheerful menace.** Bland corporate voice against pulpy monsters. Tone is a feature, not garnish.
3. **Same seed, same mine.** A seed fully determines dungeon, monsters, items, and Rogue Humans on any platform. Seeds are shareable.
4. **Readable at a glance.** Unicode glyphs, clear fog of war, and a log that explains every number. Keyboard-first.
5. **Short, sharp runs.** 15-20 minutes per level; a full run in about 75-100 minutes. Permadeath, but quick to restart on the same seed.

**Audience:** roguelike players comfortable with a terminal; Windows first.
**Target session:** one level per sitting is satisfying; a full run in one evening.
**Non-goals:** real-time action, graphics beyond terminal text, deep build crafting, a story with an answer.

---

## 3. Core loop

```
 ┌─────────────────────────── one Work Order (level) ───────────────────────────┐
 │ explore ──► fight ──► loot ──► (supply drop?) ──► reach the Down Shaft ──┐    │
 │    ▲                                                                     │    │
 └────┼─────────────────────────────────────────────────────────────────────┼────┘
      │                                                                     ▼
   descend ◄── requisitions desk ◄── memo ◄── PAY SLIP ◄── field report (check-in)
```

Per level (target 500-900 player turns, 15-20 minutes):

1. **Explore.** Arrive at the Entry stairs with a torch in the pack. Fog of war hides everything not seen.
2. **Fight.** Melee only. Time is tick-based so speed differences matter (§7.1).
3. **Loot.** Valuables become Salvage Credit; consumables and gear are found; documents give lore or small benefits.
4. **Check in.** Taking the Down Shaft ends the level. A report, a pay slip, a company memo, and the Requisitions Desk follow.
5. **Pay slip.** Gross pay minus adjustments. Net goes to the wallet; a shortfall becomes debt (§8.6).
6. **Descend.** HP is restored for free at check-in; armor repair is billed. Promotion to the next Rank happens here.

Meta loop: choose class and seed, play up to 5 levels, die or finish, get a score and a personnel record, retry the same seed or a new one.

---

## 4. Controls and input scheme

Keyboard only in v1. All bindings are rebindable via `keys.toml`. The UI maps raw keys to `Action` enums; the engine only ever sees commands.

### 4.1 Default bindings

| Action | Keys |
|---|---|
| Move (8 directions) | Arrow keys + Home/PgUp/End/PgDn (diagonals), numpad 1-9, or vi keys `h j k l y u b n` |
| Run (until something interesting) | `H J K L Y U B N` (Shift + vi key) |
| Wait one turn | `.` or `5` or `Space` |
| Bump attack / open door / interact | Move into the thing |
| Pick up | `g` or `,` |
| Descend (on Down Shaft) | `>` or `Enter` |
| Inventory | `i` |
| Equip | `e` (from inventory: select, Enter) |
| Use item | `q` |
| Drop item | `d` |
| Ability | `a` (uses your class's ability; with one ability per class in v1 there is no list to open) |
| Disarm trap (Rogue) | Move into a revealed trap, confirm with `y` |
| Look / examine | `x` (cursor mode; arrows move, `Esc` exits) |
| Character sheet | `c` |
| Full message log | `m` |
| Level overview map | `M` |
| Close door | `C` then direction |
| Help | `?` |
| Glyph set toggle | `F2` |
| Redraw | `Ctrl+L` |
| Menu (save & quit, options) | `Esc` |
| Quit without saving | `Q` (confirmation required) |

Notes:
- `Space`/`.`/`5` wait. Waiting never heals; it burns torch time and lets enemies act.
- Dangerous moves (stepping into Brine with a lit torch, walking onto a revealed trap) require confirmation. `Esc` cancels any prompt.
- Menus use letter or digit selection, `Enter` to confirm, `Esc` to back out. No mouse in v1.
- Key repeat is allowed; the engine rejects input while an animation or `-- more --` prompt is pending.
- Minimum terminal 80×24. Below that, the game shows a "please enlarge your terminal" screen and does not run.
- **Run** (`Shift` + a move key) repeats the step until something changes: a refused step, a door (it stops after opening one and again when it steps onto an open door), the stairs, or the walkable tiles abreast of the heading change (a corridor branch, a doorway, the end of a wall). It does not follow corridor bends. Any event other than a plain step also ends a run, so later systems (a monster coming into view, an item underfoot) stop it for free.
- **Look** (`x`) moves a cursor one tile per key; the map frame's lower border names what is under it ("Unexplored" for tiles never seen, "(remembered)" for tiles out of view). `x` or `Esc` leaves look mode.
- **Walking into a trap you know about** asks first: a Rogue is offered **Disarm** (`y`), everyone else "Step on it?" (`y`). A run never steps onto a known trap. A disarmed trap is walked over freely.
- **Dual Strike** targets the first adjacent enemy clockwise from north. **Cleave** needs at least one enemy in reach; an ability with nobody to use it on costs nothing and does not start its cooldown.
- `t` lights or snuffs your torch (the same as using a Torch from the pack). Lighting takes a Torch from the pack the first time; a partly burned one relights free.
- **`u` is vi north-east, so Use item is `q`** (open question 13). `q` opens the use menu; capital `Q` quits.

---

## 5. Screen layout

### 5.1 Main game screen (80×24 minimum)

Map viewport scrolls with the player (camera keeps the player in the middle third, clamped to level bounds). Larger terminals grow the map viewport and log height; the status panel stays 28 columns wide.

```
┌─ The Flooded Drifts · L3 ────────────────────────┐┌─ Status ─────────────────┐
│                                                  ││ Rook the Rogue      Rk3  │
│  ╔═════════╗         ╔═════════════════╗         ││ HP ██████████░░ 21/26    │
│  ║·········║         ║·················║         ││ DEF 5  ATK +6  DMG 1d6+3 │
│  ║·····↑···╚═════════╝··≈≈≈≈≈≈≈≈·······║         ││ Light: Torch 212t        │
│  ║··¡······+···@··νν·/··≈≈≈≈≈≈≈≈····¤··║         │├─ Abilities ──────────────┤
│  ║·····Ξ···╔═════════╗··≈≈≈≈≈≈≈≈·······║         ││ [a] Poison Blades  rdy   │
│  ║·········║         ║·≡···············║         │├─ Pack ───────────────────┤
│  ╚═══╗+╔═══╝         ║·········◊·······║         ││ ¡ Patch-Up Kit  x2       │
│      ║·║             ╚═════════════════╝         ││ ¡ Torch         x1       │
│      ║·║                                         ││ Gold 14g   Debt 0g       │
│      ║·║                                         │├─ Nearby ─────────────────┤
│   ╔══╝·╚════╗                                    ││ Ξ Gravedigger  20/20     │
│   ║·········║                                    ││ ν Cave Vermin  x2        │
│   ║···▼·····║                                    ││                          │
│   ╚═════════╝                                    ││ Turn 417                 │
│                                                  ││ Seed 1:BRASSLAMP42       │
└──────────────────────────────────────────────────┘└──────────────────────────┘
┌─ Log ────────────────────────────────────────────────────────────────────────┐
│ The Gravedigger Skeleton's shovel goes CLANG. Everyone nearby is notified.   │
│ You backstab the Cave Vermin for 11. It is no longer a vermin concern.       │
│ Cave Vermin bites you for 2. Feedback received.                              │
│ Your Hard Hat's lamp flickers. A reminder: torches are 2g.                   │
└──────────────────────────────────────────────────────────────────────────────┘
```

Fog of war is not visible in plain text: **visible** tiles are drawn bright, **remembered** tiles (seen before, not in view) are drawn dim, **unseen** tiles are blank. Monsters are drawn only while visible (or sensed by the Ranger). Items stay on the map as remembered until seen gone.

Panel rules:
- "Nearby" lists up to 5 visible/sensed enemies, nearest first, with HP.
- `Gold` is the wallet; `Debt` is the outstanding balance. Both are always shown so the economy is never hidden.
- The log shows the last 4-10 lines depending on terminal height. Any line produced by a gold change shows the amount.

### 5.2 Pay slip screen

```
╔══════════════════════════════════════════════════════════════╗
║ DUNGEONCO  ·  Independent Remediation Associate Pay Slip     ║
║ Work Order 2 of 5: The Stamp Mill & Assay Floor              ║
║ Associate: Hale (Fighter, Rank 2)           Slip #GD-0002    ║
╟══════════════════════════════════════════════════════════════╢
║ GROSS PAY                                                    ║
║   Base Job Fee ········································· 15g ║
║   Salvage Credit: Silver Nugget x2 @2g ·················· 4g ║
║   Salvage Credit: Rough Gem x1 @4g ······················ 4g ║
║   Gross ················································ 23g ║
╟──────────────────────────────────────────────────────────────╢
║ ADJUSTMENTS                                                  ║
║   Armor repair: Boiler Suit, 8 pts ····················· -6g ║
║   Consumables: Patch-Up Kit x1 @5g ····················· -5g ║
║   Consumables: Patch-Up Kit x1 @3g (reclaimed stock) ··· -3g ║
║   Consumables: Torch x1 @2g ···························· -2g ║
║   Hazard Pay (Stubborn invoked) ························ -5g ║
║   Timecard Irregularity x1 ····························· -1g ║
║   Total adjustments ··································· -22g ║
╟══════════════════════════════════════════════════════════════╢
║ NET PAY ················································ +1g ║
║ Wallet: 0g -> 1g          Balance owing: 0g                  ║
║                                                              ║
║ Thank you for your continued flexibility!                    ║
╚══════════════════════════════════════════════════════════════╝
```

Lines appear one at a time (Enter to skip the animation). Coupons and waivers are applied on this screen in the fixed order in §8.6. The math above is a test fixture for the economy module.

### 5.3 Check-in screens

```
╔══════════════ CHECK-IN 2 OF 5  ·  FIELD REPORT ══════════════╗
║ Work Order 2: The Stamp Mill & Assay Floor .......... CLOSED ║
║                                                              ║
║ Persistent Personnel resolved ............................ 5 ║
║ Wildlife Interface Events resolved ....................... 7 ║
║ Unauthorized Personnel (Foreman Grimsby) .......... AT LARGE ║
║ Valuables turned in ...................................... 3 ║
║ Turns on site .......................................... 612 ║
║                                                              ║
║ Wellness Break: HP restored to 35/35. No charge.             ║
║ Standard Issue topped up: Patch-Up Kit x2, Torch x1.         ║
║                                                              ║
║ [Enter] Pay slip     [Esc] Skip to memo                      ║
╚══════════════════════════════════════════════════════════════╝
```

```
╔══ COMPANY MEMO  ·  FROM: Regional Facilities Optimization ═══╗
║ RE: Your Valued Feedback (Graveyard Initiative)              ║
║                                                              ║
║ Team! Per Section 9.4, Level 3 has been reclassified as      ║
║ a "Memorial Environment." Please treat all gravestones       ║
║ with the same care you would treat any billable surface.     ║
║                                                              ║
║ Reminder: undead are not employees. Employees are            ║
║ undead only on Fridays.                                      ║
║                                                              ║
║ Hazard Premium of 5g applies. Enjoy!                         ║
║                                                              ║
║ [Enter] Requisitions Desk                                    ║
╚══════════════════════════════════════════════════════════════╝
```

```
╔ REQUISITIONS DESK  ·  Wallet 1g  ·  Account in good standing ╗
║ [1] Torch Bundle (3 prepaid torches) ............... 5g      ║
║ [2] Property Damage Waiver (next level, up to 6g) ... 5g     ║
║ [3] Sharpening Service (+1 weapon damage) .......... 12g     ║
║ [4] Wellness Seminar (+3 max HP) ................... 10g     ║
║                                                              ║
║ Armor repair is billed on the pay slip. [R] decline repair.  ║
║                                                              ║
║ [1-4] Buy     [Enter] Descend to Level 3     [S] Save & quit ║
╚══════════════════════════════════════════════════════════════╝
```

The memo always announces the next level's graveyard status (if any) and any premium. Memos are generated from templates; each may contradict a previous one.

### 5.4 Glyph sets

Three render tiers, selected by `--glyphs auto|unicode|ascii` (default `auto`), toggled in-game with `F2`.

- `auto` picks `unicode` when stdout encoding is UTF-8 and the terminal is not a legacy console (Windows Terminal sets `WT_SESSION`); otherwise `ascii`.
- Every glyph has an ASCII fallback. Color is never the only signal: each monster has a distinct glyph shape.
- Glyph picks must come from fonts shipped with Windows (Consolas, Cascadia Mono, Lucida Console). A glyph-audit screen (`--glyph-test`) prints every glyph in both sets so a player can see missing characters at a glance. Anything that fails the audit is swapped for an alternate before release.
- Ambiguous-width characters (box drawing, `·`, Greek letters, `†`) are treated as narrow. A config flag (`ambiguous_width = "narrow"|"wide"`) lets CJK-locale users compensate; `ascii` always works.

**Terrain and features**

| Thing | Unicode | ASCII | Notes |
|---|---|---|---|
| Constructed wall | autotiled `═ ║ ╔ ╗ ╚ ╝ ╠ ╣ ╦ ╩ ╬` | `#` | mine timbers and stonework |
| Natural rock (cavern wall) | `▒` | `#` | |
| Floor | `·` | `.` | mine: brown; cavern: grey |
| Door, closed | `+` | `+` | blocks sight; bump to open |
| Door, open | `/` | `/` | |
| Entry stairs (arrival) | `▲` | `<` | one-way; cannot go up |
| Down Shaft (exit) | `▼` | `>` | |
| Brine (wet) | `≈` | `~` | walkable; Eel home; torch hazard |
| Rubble | `∴` | `:` | walkable, costs 200 ticks |
| Support beam / iron fence | `╫` | `\|` | blocks movement, not sight |
| Trap, revealed | `Δ` | `^` | hidden traps look like floor |
| Trap, disarmed | `×` | `x` | |
| Supply crate | `■` | `=` | |

**Graveyard palette (graveyard floors only)**

| Thing | Unicode | ASCII | Notes |
|---|---|---|---|
| Gravestone | `†` | `T` | blocks movement, not sight |
| Monument / tomb | `‡` | `H` | blocks movement and sight |
| Open grave | `∪` | `u` | enter: fall, 1d4 damage, 2 turns to climb out; Miners rise from some |
| Iron fence | `╫` | `\|` | |
| Floor / wall tint | dark green / grey-violet | n/a | palette swap, same glyphs |

**Items**

| Thing | Unicode | ASCII |
|---|---|---|
| Weapon | `↑` | `)` |
| Armor / shield / hat | `[` | `[` |
| Trinket | `°` | `"` |
| Consumable | `¡` | `!` |
| Silver | `¤` | `$` |
| Gem | `◊` | `*` |
| Document | `≡` | `?` |

**Actors**

| Actor | Unicode | ASCII |
|---|---|---|
| Player | `@` | `@` |
| Shambling Miner | `M` | `M` |
| Gravedigger Skeleton | `Ξ` | `S` |
| Timecard Wraith | `Ω` | `W` |
| Cave Vermin | `ν` | `v` |
| Blind Ore-Eel | `ε` | `e` |
| Gem Badger | `β` | `b` |
| Foreman Grimsby | `Γ` | `G` |
| Prospector Vane | `Π` | `V` |

**UI**

| Thing | Unicode | ASCII |
|---|---|---|
| Panel border | `┌ ┐ └ ┘ ─ │ ├ ┤` | `+ - \|` |
| Modal border | `╔ ═ ╗ ║ ╚ ╝ ╟ ╢` | `+ = \|` |
| HP bar | `█` full, `░` empty | `#` full, `-` empty |
| Fog (unseen) | blank | blank |
| Fog (remembered) | same glyph at 45% of its color's brightness | same (a darker color, never the terminal's dim attribute, so it works on every console) |
| Sensed (Ranger) | actor glyph, dim cyan | actor glyph, underlined or `?` |

**Wall autotile.** Each wall tile looks at its four orthogonal neighbours (N=1, E=2, S=4, W=8) and picks from a 16-entry table: `0→▪, 1→║, 2→═, 3→╚, 4→║, 5→║, 6→╔, 7→╠, 8→═, 9→╝, 10→═, 11→╩, 12→╗, 13→╣, 14→╦, 15→╬`. Only "wall" neighbours count; unseen tiles do not.

**Colors.** Semantic tokens (`floor`, `wall`, `brine`, `undead`, `beast`, `human`, `gold`, `danger`, `graveyard_floor`, ...) map to truecolor, then 256, then 16 colors; Textual handles the downgrade. Undead are cool colors, beasts are warm, humans are bright white.

---

## 6. Classes

### 6.1 Common rules

- Two attributes: **STR** and **DEX**. Modifier = `(score - 10) // 2` (integer floor division).
- **ATK** = `2 + rank_atk + mod(weapon_stat) + weapon.atk + trinket.atk`
- **DEF** = `mod(DEX) + body.def + offhand.def + head.def + status`
- **Weapon stat** is STR for normal weapons and the higher of STR/DEX for **finesse** weapons.
- **Damage** = weapon dice + `mod(weapon_stat)` + weapon.dmg + `rank_dmg`.
- **Equipment slots (5):** Main Hand, Off Hand, Head, Body, Trinket. Two-handed weapons need an empty Off Hand.
- **Light** is not a slot. The Hard Hat's lamp has radius 4. A lit Torch has radius 8 (§8.2).
- **HP** is fixed per class and Rank (below). There is no natural regeneration. HP is restored in full at check-in.
- **Ranks** replace XP. You hold Rank 1 on Level 1; each check-in promotes you one Rank. "Promotion" is a line in the memo.

### 6.2 Class summary

| | Fighter | Rogue | Ranger |
|---|---|---|---|
| Role | tank, area control | burst, scouting traps | tracker, beast-slayer, two weapons |
| HP (Rank 1) | 30 | 22 | 26 |
| STR / DEX | 16 / 10 (+3 / 0) | 10 / 16 (0 / +3) | 13 / 13 (+1 / +1) |
| Armor class | heavy | light | medium |
| Signature | Stubborn | Backstab (+ disarm) | Tracker |
| Rank 3 unlock | Cleave | Poison Blades | Dual Strike |

### 6.3 Starting kits and derived stats (Rank 1)

| | Fighter | Rogue | Ranger |
|---|---|---|---|
| Main Hand | Company Pickaxe, 1d8, STR | Box Cutter, 1d6, finesse | Hatchet, 1d6, STR |
| Off Hand | Sheet-Metal Shield (DEF +1) | empty | Hatchet, 1d6 |
| Head | Hard Hat | Hard Hat | Hard Hat |
| Body | Boiler Suit (heavy: DR 2, DEF 0, Dur 18) | Hi-Vis Vest (light: DR 0, DEF +2, Dur 10) | Padded Coveralls (medium: DR 1, DEF +1, Dur 14) |
| Trinket | none | none | none |
| Pack (issued) | Patch-Up Kit ×2, Torch ×1 | same | same |
| **ATK** | +5 | +5 | +3 main, -1 off-hand |
| **DEF** | 1 | 5 | 2 |
| **Damage** | 1d8+3 (avg 7.5) | 1d6+3 (avg 6.5) | 1d6+1 (avg 4.5) |
| **DR** | 2 | 0 | 1 |

### 6.4 Progression

| Rank | Reached | Fighter | Rogue | Ranger |
|---|---|---|---|---|
| 1 | start | HP 30 | HP 22 | HP 26 |
| 2 | after L1 | HP 35, +1 ATK | HP 26, +1 ATK | HP 30, +1 ATK |
| 3 | after L2 | **Cleave** | **Poison Blades** | **Dual Strike** |
| 4 | after L3 | HP 40, +1 damage | HP 30, +1 damage | HP 34, +1 damage |
| 5 | after L4 | HP 45, Cleave upgrade | HP 34, Poison upgrade | HP 38, Dual Strike upgrade |

Promotion changes numbers on the character sheet and unlocks the ability. There are no skill trees or choices in v1.

### 6.5 Signature mechanics

**Fighter: Stubborn (passive).** Once per level, damage that would reduce HP to 0 or below sets HP to 1 instead. Other effects of that hit still apply. The pay slip receives **Hazard Pay (Stubborn invoked): -5g** (a deduction; see assumption A7). Resets at the start of each level. Log: "You are STUBBORN. HR has been notified."

**Rogue: Backstab (passive) and Disarm.**
- *Backstab:* an attack against a target that is **flanked**, **stunned**, **unaware**, or **fleeing** adds **+2d4** damage (once per attack, however many conditions apply). Attacks against stunned or unaware targets automatically hit; the other two roll normally.
- *Unaware* means Asleep, Dormant, Buried, or awake-but-not-yet-alerted to the player.
- *Disarm:* the Rogue automatically spots hidden traps within 3 tiles (line of sight). Moving into a revealed trap offers **Disarm** (one action, always succeeds). A disarmed trap never triggers, so the Hazard Surcharge is avoided. No other class can disarm; they can only walk around a revealed trap.

**Backstab details.** An attack that is "automatic" still rolls the d20 (a natural 20 is still a critical). A critical doubles the weapon dice only; the 2d4 is not doubled. *Unaware* means the monster is Asleep or Idle (has not noticed you). Fleeing monsters do not exist until milestone 5.

**Ranger: Tracker (passive).** All enemies within radius 5 (integer circle: `dx² + dy² ≤ 25`) are shown through walls as dim "sensed" glyphs. Buried monsters are not shown until they rise. Attacks deal **+2 damage against beasts**. The Ranger cannot be ambushed: a submerged Eel inside the Tracker radius is revealed and loses its ambush bonus.

### 6.6 Abilities (active)

| Ability | Class | Effect | Cooldown | Rank 5 upgrade |
|---|---|---|---|---|
| Cleave | Fighter | Attack every adjacent enemy once, -2 ATK per attack; damage rolled separately. One action. | 4 turns | no penalty, cooldown 3 |
| Poison Blades | Rogue | Next 5 weapon hits apply **Poisoned** (2 damage per turn for 5 turns; reapplying refreshes duration, does not stack). Poison ignores DR. | 30 turns | 3 damage per turn, 6 hits |
| Dual Strike | Ranger | Both hatchets strike one adjacent target in one action, both at full ATK (no off-hand penalty), +1 damage each. | 5 turns | cooldown 3, +2 damage each |

**As built:** abilities are rows in `abilities.toml` (kind, unlock Rank, cooldown, and one `value`/`charges` pair each with a Rank 5 twin). A cooldown starts when the ability is used and runs from that moment. Poison Blades spends a charge on every weapon hit, including a killing one, and Poisoned damage is collected on the target's own turns (a monster poisoned at tick 100 takes its first 2 at tick 200). Dual Strike's off-hand hatchet still gets no attribute modifier to damage; it only loses the -4 ATK.

All ability data carries `costs: {}` (empty in v1) and `cooldown_ticks`, so a shared stamina pool can be added later without changing the shape (§7.7).

### 6.7 Dual wielding (rule)

When both hands hold one-handed melee weapons (Ranger's starting state), each attack action makes a **main-hand attack** and then an **off-hand attack at -4 ATK** with no attribute modifier to damage. Dual Strike removes the penalty and adds damage. A Rogue or Fighter who finds a second light weapon can use the same rule.

---

## 7. Combat rules

### 7.1 Time and turn order

**Movement rule (shared by the player, AI, and level generation):** moves are in 8 directions. A diagonal step is refused if either orthogonal neighbor is a wall, rock, or undug tile (no cutting corners), and no diagonal step may enter or leave a door tile. Path costs are 10 orthogonal, 14 diagonal.

**Melee reach** follows the same rule: you cannot attack, and nothing can attack you, around a corner or diagonally into or out of a doorway. Moving into a monster attacks it.

Time is measured in **ticks**; **100 ticks = 1 standard turn**.

- Every actor has `ready_at`. The scheduler always runs the actor with the smallest `ready_at`. Ties: the player first, then lower actor id (spawn order). This makes order deterministic.
- After acting, `ready_at += action_cost`. Standard cost is 100.

| Action | Cost (ticks) |
|---|---|
| Move (player, most enemies) | 100 |
| Move over Rubble | 200 |
| Attack | weapon cost (100; Sledgehammer 130) |
| Use item / equip | 100 |
| Pick up | 50 |
| Disarm | 100 |
| Open door (bump) | 100 |
| Close door | 50 |
| Shambling Miner move | 150 |
| Cave Vermin move | 50 |
| Gem Badger move | 80 |

- Cost modifiers multiply: **Overtime** sets cost to 60% (integer: `cost * 60 // 100`).
- **Stunned / Clocked In** add 100 ticks to the afflicted actor's `ready_at`.
- All durations, cooldowns, and poison ticks are measured in ticks, not turns. "Turn" in this document means 100 ticks.

### 7.2 Hit resolution

1. Attacker rolls **d20**. Natural 1 always misses. Natural 20 always hits and is a **critical**.
2. A hit succeeds when `d20 + ATK + situational >= 10 + DEF` (natural 1 and 20 override).
3. **Situational ATK modifiers:** +2 flanking (attacker in target's rear arc, §7.4); +4 Eel ambush; Vermin swarm +1 per other Vermin adjacent to the target (max +3); -2 Cleave; -4 off-hand.
4. On a hit: **damage** = weapon dice + modifiers. A critical **doubles the dice** (e.g., 1d8 becomes 2d8) before flat bonuses.
5. Subtract the target's **DR** (damage reduction). A hit always deals at least 1 damage (poison ignores DR).
6. Apply on-hit effects (status application, Backstab bonus, Wraith clock-in), then durability loss, then death/Stubborn checks.

Reference numbers (Rank 1, normal floor): Fighter or Rogue hit a Miner (DEF 0) 80% of the time; Ranger 70%. A Miner (ATK +2) hits a Fighter 60%, a Ranger 55%, a Rogue 40%.

### 7.3 Armor durability and repair

- Body armor has **durability** (Dur). Each time a hit lands on the wearer, armor loses 1 Dur (2 on a critical). At Dur 0 the armor is **Broken**: its DR and DEF bonus are zero until repaired.
- Shields, hats, and trinkets do not wear.
- Repair is done at check-in and billed on the pay slip (§8.6): cost per missing point depends on the armor's `repair_rate` (quarter-gold per point). You may decline repair at the Requisitions Desk (saves gold, keeps the damage).

### 7.4 Facing and flanking

- Every actor has a **facing** (one of 8 directions), set by its last move or attack. A sleeping or stunned actor keeps its last facing.
- The **rear arc** is the three tiles opposite the facing. An attack from the rear arc is **flanking**: +2 to hit for any attacker.
- Enemies re-face when they act against a target, so flanking in practice happens against: enemies still walking elsewhere, slow movers (Miners), **fleeing** enemies (Badger, Vane), and anything stunned or asleep. It also works against the player: being surrounded in the open lets enemies in your rear arc get +2.
- The look command shows `(flanked)` on any target that currently is (not built yet).
- **Starting facing:** the player starts facing south; each monster rolls a facing at generation on its own stream (`level/N/spawn_facing`). Opening a door, moving, and attacking all turn an actor toward what it did.

### 7.5 Status effects

Statuses are **data-driven**. A status definition has: `id`, `duration_ticks`, `tick_interval`, `stacking` (`refresh`, `charges`, or `none`), `modifiers` (ATK, DEF, damage, cost percent, flags), and `on_tick` effects. Cooldowns are modeled as hidden statuses (`cd:cleave`), so one engine handles everything.

| Status | Source | Effect | Duration |
|---|---|---|---|
| Poisoned | Poison Blades | 2 damage per 100 ticks, ignores DR | 500 ticks, refresh |
| Coated (charges) | Poison Blades | next N hits apply Poisoned | until charges spent |
| Stunned | Sledgehammer/Shovel critical, Stun Charge trap | lose next action (+100 ticks) | immune to Stun for 300 ticks afterwards |
| Clocked In | Timecard Wraith (35% on damaging hit) | lose next action; billed Timecard Irregularity -1g (cap -5g per level) | immune for 500 ticks afterwards |
| Overtime | Grimsby aura, Overtime Fizz | action costs ×60% | aura: 300 ticks, refreshed every 100 while within 5 tiles; Fizz: 800 ticks |
| Soaked | standing in Brine | DEF -1 | while in Brine + 200 ticks |
| Detergent Coat | Sanctified Detergent | +2 damage against Undead | 5000 ticks |
| `cd:*` | using an ability | blocks reuse | the ability's cooldown |

### 7.6 Enemy roster

Level scaling (L = level 1-5): `HP = base_hp * (100 + 12*(L-1)) // 100`; `ATK = base_atk + (L-1)//2`; flat damage `+ (L-1)//2` on top of the dice. Threat cost is used by the spawner (§9.4).

| Monster | Faction | HP | ATK | DEF | Damage | DR | Move / Attack cost | Sight | Threat |
|---|---|---|---|---|---|---|---|---|---|
| Shambling Miner | Undead | 12 | +2 | 0 | 1d6+1 | 0 | 150 / 100 | 5 | 3 |
| Gravedigger Skeleton | Undead | 20 | +3 | 2 | 1d8 | 1 | 100 / 100 | 7 | 5 |
| Timecard Wraith | Undead | 14 | +4 | 4 | 1d4 | 0 | 100 / 100 | 6 (ignores walls) | 6 |
| Cave Vermin | Beast | 6 | +1 | 2 | 1d3 | 0 | 50 / 100 | 6 | 3 per pack of 3-5 |
| Blind Ore-Eel | Beast | 18 | +4 | 1 | 1d6+2 | 0 | 100 / 100 | touch (2) | 4 |
| Gem Badger | Beast | 16 | +3 | 2 | 1d6+1 | 0 | 80 / 100 | 6 | 3 |
| Foreman Grimsby | Human | 40 | +4 | 2 | 1d8+2 | 1 | 100 / 100 | 9 | n/a |
| Prospector Vane | Human | 32 | +4 | 4 | 1d6+1 | 0 | 100 / 100 | 9 | n/a |

Worked scaling: a Level 5 Shambling Miner has `12*148//100 = 17` HP, ATK +4, damage 1d6+3.

**Special rules**

- **Shambling Miner.** Slow mover. Some are **Buried** in Open Graves on graveyard floors and rise (one action) when the player comes within 3 tiles.
- **Gravedigger Skeleton.** Its shovel is loud. Every move or attack emits **Clang** noise (radius 8). A natural 20 stuns the player.
- **Timecard Wraith.** **Phases**: it moves through wall tiles (treats walls as passable, cost 100) but cannot end its move inside another actor. While inside a wall tile it has +4 DEF. On a damaging hit, 35% chance to apply **Clocked In**.
- **Cave Vermin.** Spawn in packs of 3-5. Swarm bonus (+1 ATK per other Vermin adjacent to the target, max +3). Fast movers.
- **Blind Ore-Eel.** Lives only in Brine tiles. **Submerged** Eels are invisible and untargetable. At the start of its turn, if the player is adjacent to its tile, it **ambushes**: +4 ATK first strike, then surfaces. It resubmerges after 2 turns with no adjacent target. Eels never leave Brine.
- **Gem Badger.** Aggressive until HP ≤ 40%, then **flees** at its (fast) move speed. If it stays out of sight for 12 turns it digs away ("The Gem Badger has retired to a private burrow"). Drops 1d2 Rough Gems (4g each) on death. The drop is pre-rolled at generation (§10.6), so a kill always drops the same thing.
- **Foreman Grimsby.** *Aura:* undead within 5 tiles gain **Overtime** (refreshed every 100 ticks). He supervises from behind his undead, keeping distance 2-3; when no undead remain in his aura, he charges.
- **Prospector Vane.** *Traps and retreat:* every 6 turns, if he has line of sight to the player within 6 tiles and has traps left (max 4 per level), he lays a hidden trap on his tile and then retreats along the flee map. When out of traps or cornered, he fights. Retreating Vane is **fleeing** (Backstab and flank apply).

### 7.7 Enemy AI

**States:** `Asleep` → `Idle` → `Alerted(target_pos)` → `Hunting(target)` → `Fleeing` → `Returning`. `Buried` is a special Asleep state. Initial state is rolled at generation.

**Perception**
- An awake enemy that sees the player (line of sight within its Sight radius) switches to `Hunting`.
- A sleeping enemy wakes (to `Alerted`) when damaged, or each of its ticks with chance: player within 4 tiles: 1-in-6; adjacent: 1-in-2 (rolled on the play RNG).
- **Noise:** events emit noise with a radius: player melee attack 5, Sledgehammer or Shovel attack 8, opening a door 3, Skeleton Clang 8. Noise spreads by breadth-first search through passable tiles (closed doors block, open doors pass). Awake non-hunting enemies in range become `Alerted` toward the source; sleepers wake with 50% chance.

**Movement**
- One **Dijkstra map** from the player is computed per player turn (octile integer costs `14·min(dx,dy) + 10·|dx−dy|`, Rubble ×2, walls impassable). Hunters descend the gradient; ties break by fixed direction order (N, NE, E, SE, S, SW, W, NW). Flee uses the negated map, rescanned.
- Wraiths ignore walls in their own map. Eels use a Brine-only map.
- No float math anywhere in AI or pathing.

**Per-monster behavior**: see §7.6. Only Foreman Grimsby and Prospector Vane speak (§9.6).

**As built (milestone 3, Shambling Miner only).** States are `Asleep`, `Idle`, and `Hunting`; `Alerted` and noise arrive in milestone 5, so a sleeper that wakes, or an idle monster that sees the player, goes straight to `Hunting`. A sleeper rolls to wake once per turn of its own (100 ticks). Hunters open closed doors by bumping them (it costs their move cost) and keep hunting for good. A monster that cannot step toward the player waits a turn.

### 7.8 Extensibility hooks for future magic (not implemented in v1)

These are data-shape decisions only. No spell code ships in v1.

1. **General status-effect system.** §7.5 is table-driven with stacking, charges, tick effects, modifiers, and expiry events. Spells later add rows, not engine code.
2. **Shared stamina/resource pool.** Actors have `pools: dict[str, Pool]`. v1 defines only `hp`. Abilities carry `costs: dict[str, int]` (empty in v1). A `stamina` pool can later be enabled in the class data and read by abilities and spells.
3. **Action queue.** The scheduler already runs on `ready_at` with variable action costs. Actions are objects with `cost_ticks`, an optional `windup_ticks` (cast time, 0 in v1), `targeting`, and a list of `effects` (damage, heal, apply status, move, spawn). Cleave, Poison Blades, and Dual Strike are expressed in this format so spells can reuse it.

---

## 8. Items, loot, supply drops, and the gold economy

### 8.1 Equipment

**Weapons** (found tiers: T1 from L1, T2 from L3, T3 only on L5)

| Weapon | Tier | Dice | Stat | Notes |
|---|---|---|---|---|
| Company Pickaxe | 1 | 1d8 | STR | Fighter start |
| Box Cutter | 1 | 1d6 | finesse | Rogue start; light |
| Hatchet | 1 | 1d6 | STR | Ranger start; light |
| Prybar | 1 | 1d6 | STR | +1 ATK |
| Utility Knife | 1 | 1d4 | finesse | light, good off-hand |
| Gravedigger's Shovel | 2 | 1d8 | STR | noisy (noise 8); critical stuns |
| Surveyor's Pick | 2 | 1d8 | finesse | |
| Sledgehammer | 2 | 1d12 | STR | two-handed, attack cost 130, noise 8, critical stuns |
| Foreman's Pickaxe | 3 | 1d10 | STR | +1 ATK |
| Assay Blade | 3 | 1d8 | finesse | +1 damage |

**Body armor** (`repair_rate` = quarter-gold per missing durability point)

| Armor | Class | Tier | DR | DEF | Dur | Repair rate |
|---|---|---|---|---|---|---|
| Hi-Vis Vest | light | 1 | 0 | +2 | 10 | 1 |
| Ballistic Vest (surplus) | light | 2 | 1 | +2 | 12 | 2 |
| Padded Coveralls | medium | 1 | 1 | +1 | 14 | 2 |
| Welder's Jacket | medium | 2 | 2 | +1 | 16 | 3 |
| Boiler Suit | heavy | 1 | 2 | 0 | 18 | 2 (3 in the first draft; A84) |
| Miner's Plate | heavy | 2 | 3 | -1 | 20 | 4 |

**Shields and hats**

| Item | Slot | Effect |
|---|---|---|
| Sheet-Metal Shield | Off Hand | DEF +1 |
| Riot Shield (surplus) | Off Hand | DEF +2 |
| Hard Hat | Head | lamp radius 4; trap and cave-in damage -2 |
| Reinforced Hard Hat | Head | as above, DEF +1 |
| Headlamp Hard Hat | Head | lamp radius 5; trap and cave-in damage -2 |

**Trinkets**

| Trinket | Effect |
|---|---|
| Laminated Lanyard | the first incident line of 3g or less each level is waived |
| Company Challenge Coin | +1 ATK |
| Thermos | +3 max HP |

Found armor and weapons spawn with a **condition** (armor durability 50-100% of max, rolled at generation). Equipping damaged armor means the repair bill comes sooner.

### 8.2 Consumables

| Item | Effect | List price | Found price (billed on use) |
|---|---|---|---|
| Patch-Up Kit | heal 10 HP | 5g | 3g |
| Torch | light radius 8 for 400 turns of burn time | 2g | 1g |
| Overtime Fizz | **Overtime** (actions cost 60%) for 8 turns | 7g | 4g |
| Sanctified Detergent | **Detergent Coat** (+2 damage vs Undead) for 50 turns | 6g | 3g |

Found price is `ceil(list / 2)`.

**Billing rule (structural).** Every consumable stack carries a `use_charge` in gold, set when you acquire it:
- **Issued** (Standard Issue at each check-in): `use_charge = list price`.
- **Found** on the map (reclaimed stock): `use_charge = ceil(list / 2)`.
- **Prepaid** (Requisitions bundles, supply drop pickups): `use_charge = 0`.

The charge is billed on the pay slip **when the item is used** (a Torch when first lit; a partly burned Torch can be snuffed and relit free). Items are free to carry, expensive to waste.

**Carrying.** Standard Issue tops up to **Patch-Up Kit ×2, Torch ×1** at each check-in (and at start). Carry limits: Kit 4, Torch 3, Fizz 2, Detergent 2. Pack size is not otherwise limited in v1; equipment on the floor is picked up one item per action.

**Light.** FOV uses integer symmetric shadowcasting. Visible radius is the best of the Hard Hat lamp (4-5) and a lit Torch (8). Unlit tiles beyond that radius are dark even in line of sight. Enemies do not need light to see the player.

### 8.3 Valuables and documents

**Valuables** (Salvage Credit; picked up automatically when stepped on; turned in at check-in)

| Valuable | Credit | Loot weight |
|---|---|---|
| Silver Nugget | 2g | 50 |
| Rough Gem | 4g | 30 |
| Silver Ingot | 6g | 12 |
| Cut Gem | 9g | 8 |

**Documents** (max 2 per level plus a guaranteed one in Foreman's Office / Prospector's Camp)

| Outcome | Chance | Effect |
|---|---|---|
| Flavor memo/diary | 70% | lore text only |
| Coupon | 20% | -3g from any one adjustment line on the next pay slip |
| Map fragment | 10% | reveals the room layout of the current level |

### 8.4 Loot tables

Items per level: `7 + L` (L1: 8, L5: 12), plus 2 extra for each Storeroom and Mausoleum.

**Category weights:** Consumable 40, Valuable 25, Equipment 20, Document 15 (documents capped at 2 per level; rerolled as Valuable).
**Consumable sub-weights:** Patch-Up Kit 40, Torch 30, Overtime Fizz 15, Sanctified Detergent 15.
**Equipment sub-weights:** Weapon 30, Body armor 25, Trinket 20, Hat 15, Shield 10. Tier is chosen by level: L1-2: T1 only; L3-4: T1 70 / T2 30; L5: T2 70 / T3 30.
**Placement weights by room type:** Storeroom 5, Mausoleum 6, Office/Camp 4, Collapse 3, Gallery 2, Bunk Room 2, Flooded Gallery 2, Cemetery Plot 2. Entry room: none.

Expected valuables if everything is collected: about 9-12g per level. Typical play collects half or less.

### 8.5 Supply drops and the Requisitions Desk

**Supply drops (mid-level).**
- Each level rolls 0, 1, or 2 drops (weights 25 / 55 / 20). Each has a **trigger turn** in `[120, 700]` (second drop at least 250 turns after the first), pre-rolled at generation.
- At the trigger turn, a crate (`■`) lands on the nearest free floor tile within radius 3 of the player (ring search in row-major order, deterministic). Log: "Supply drop inbound! Please do not look up."
- Contents: 3 consumable lines (quantity 1-2 each) plus a 25% chance of one equipment line (tier by level). Contents are pre-rolled.
- Opening the crate shows an **itemized invoice**:

```
 SUPPLY DROP INVOICE #1 (Express Cavern Delivery)
   Patch-Up Kit  x2 @ 5g ........................... 10g
   Overtime Fizz x1 @ 7g ...........................  7g
   Welder's Jacket (T2) ........................... 22g
   Subtotal ........................................ 39g
   Expedited Handling (20%, rounded up) ............  8g
   Delivery fee (if anything taken) ................  2g
   [space] toggle lines   [Enter] accept   [Esc] leave
```

- Only taken lines are billed (at the next pay slip, not from the wallet), plus handling on taken lines and the delivery fee if anything is taken. Taken consumables are **prepaid** (`use_charge 0`). Untaken items stay in the crate; leaving the level forfeits them at no charge.
- Equipment prices: T1 12g, T2 22g, T3 34g.

**Requisitions Desk (every check-in).** The desk offers 4 items rolled from the catalog (weighted, deterministic per seed and level; the first slot is always a Bundle). Prices are paid immediately from the wallet.

| Item | Effect | Price |
|---|---|---|
| Torch Bundle | 3 prepaid Torches | 5g |
| Kit Bundle | 2 prepaid Patch-Up Kits | 8g |
| Sharpening Service | +1 damage on main-hand weapon (max +3) | 12g |
| Hone & Balance | +1 ATK on main-hand weapon (max +2) | 12g |
| Armor Plating | body armor +4 max Dur and +1 DR (once per armor) | 18g |
| Reinforced Hard Hat | Head slot item with DEF +1 | 10g |
| Wellness Seminar | +3 max HP (permanent) | 10g |
| Repair Plan | next armor repair line is halved (rounded up) | 6g |
| Property Damage Waiver | next level: incidentals waived up to 6g (not Hazard Pay) | 5g |
| Hazard Waiver | next level: Hazard Surcharge and Shoring Damage waived | 6g |

If you have **debt**, the desk is closed ("Account on hold") but Standard Issue still applies.

### 8.6 The gold economy and pay slip math

All money is integer gold. Rounding is always **ceiling** (`-(-a // b)`). No floats.

**Gross pay**

| Line | Amount |
|---|---|
| Base Job Fee | 10g (15g in the first draft and in the worked examples below; A83) |
| Hazard Premium (graveyard floors only) | +5g |
| Unauthorized Personnel Retrieval Bounty (if the level's Rogue Human was defeated) | +6g |
| Salvage Credit (each valuable turned in, itemized) | per §8.3 |

There is no depth allowance: pay stays flat while deductions grow with danger, so the squeeze deepens. (Proposal; see A8.)

**Adjustments (deductions)**

| Line | Rule |
|---|---|
| Armor repair | `ceil(missing_Dur * repair_rate / 4)` per piece (restores to full). Declinable. |
| Consumables | each used item × its `use_charge` (itemized by stack) |
| Supply drop invoice(s) | taken lines + handling + delivery |
| Dropped torch | 2g, when a lit Torch is lost: 50% on entering Brine lit, 25% when you take a critical hit |
| Hazard Surcharge | 3g per trap triggered (disarmed traps never trigger) |
| Shoring Damage | 4g when a Tripwire Charge (cave-in) triggers, in addition to the surcharge |
| Timecard Irregularity | 1g per Wraith Clock-In, capped at 5g per level |
| Hazard Pay (Stubborn invoked) | 5g, Fighter only, once per level |
| Balance carried forward | any debt from earlier slips |
| Administrative late fee | `ceil(10% of balance carried forward)` |

**Waivers and coupons** are applied in this fixed order, after the lines above are computed:
1. Repair Plan (halves the repair line, rounded up)
2. Hazard Waiver (zeroes Hazard Surcharge and Shoring Damage)
3. Property Damage Waiver (zeroes incidentals up to a 6g total; never Hazard Pay)
4. Laminated Lanyard (zeroes the first incident line of 3g or less)
5. Coupon (-3g on one line the player picks; minimum line value 0)

**Net and the wallet**

```
gross  = base + premium + bounty + salvage
adjust = repair + consumables + supply + incidentals + carried_balance + late_fee   (after waivers)
net    = gross - adjust

if net >= 0:  wallet += net;  debt = 0
else:         shortfall = -net
              paid      = min(wallet, shortfall)
              wallet   -= paid
              debt      = shortfall - paid        # becomes next slip's "balance carried forward"
```

Since the carried balance and late fee are already inside `adjust`, a positive net clears all earlier debt. **If deductions exceed gross pay:** the shortfall first drains the wallet; whatever remains becomes **debt**, which appears next slip as "Balance carried forward" plus a 10% late fee. Debt cannot kill the run. While in debt the Requisitions Desk is closed. Final score subtracts debt (§8.8).

**Worked example 1 (slip in §5.2).** Level 2 Fighter, no bounty. Gross `15 + 4 + 4 = 23`. Adjustments: repair `ceil(8 × 3 / 4) = 6`; kits `5 + 3 = 8`; torch 2; Hazard Pay 5; Timecard 1 → 22. Net **+1**. Wallet 0 → 1.

**Worked example 2 (graveyard floor, deficit).** Level 3 Fighter, wallet 1g. Gross `15 + 5 (Hazard Premium) + 2 (one Silver Nugget) = 22`. Adjustments: repair `ceil(9 × 3 / 4) = 7`; consumables `2 × 5 + 1 × 3 + 1 × 2 = 15` (two issued kits, one found kit, one torch); dropped torch 2; trap surcharge 3; Hazard Pay 5 → 32. Net **-10**. The wallet pays 1; **debt 9**.

**Worked example 3 (following slip).** Level 4: the slip opens with "Balance carried forward 9g" and "Administrative late fee `ceil(9 × 10 / 100) = 1g`", adding 10g to adjustments. A strong level 4 clears it; a weak one deepens the hole.

**Tuning targets (balance simulator).** Median net pay per level for competent play: 4-10g. Sloppy play: negative. Fewer than 15% of competent runs end the game in debt. Full-run score for a competent run: 60-110.

**As tuned (M9).** `tools/balance_sim.py` plays 200 seeds per class with the scripted bot of A85. With the first-draft numbers the median net was 13 to 15g a level, well over target, so the Base Job Fee went from 15g to 10g (A83) and the Boiler Suit's repair rate from 3 to 2 (A84). Careful play now has a median net of 9g (Fighter), 10g (Rogue) and 9g (Ranger); 6 of 82, 0 of 24 and 7 of 51 winning runs end in debt; the median score of a full run is 79, 86 and 80; and sloppy play loses 17 to 22g a slip. The worked examples above keep the first-draft figures, and the tests that check their arithmetic pin the fee at 15g.

### 8.7 Rogue Human bounty

Defeating the level's Rogue Human before descending adds the 6g bounty and a salvage chance (see §9.6). The human is optional: you may skip them and take the Down Shaft.

### 8.8 Scoring and titles

`score = (wallet - debt) + 10 × levels_cleared + 5 × bounties_collected`

| Score | Final title |
|---|---|
| ≤ 0 | Terminated for Cause |
| 1-29 | Probationary Contractor |
| 30-59 | Valued Associate |
| 60-99 | Senior Associate |
| 100+ | Employee of the Month |

On death, the final slip is a **Posthumous Pay Slip**: no Base Job Fee, normal adjustments for the partial level, plus a 5g Uniform Recovery Fee. It is shown for flavor and included in the score.

---

## 9. Dungeon structure

### 9.1 Levels

Every level is **80×40 tiles**, generated from the seed alone (not from anything the player does).

| L | Name | Work Order | Cavern rooms | Threat budget | Hidden traps | Items |
|---|---|---|---|---|---|---|
| 1 | Upper Galleries | Light Housekeeping | 0% | 14 | 2 | 8 |
| 2 | Stamp Mill and Assay Floor | Deep Clean: Processing | 20% | 18 | 3 | 9 |
| 3 | Flooded Drifts | Moisture Remediation | 40% | 22 | 4 | 10 |
| 4 | Old Timbers | Structural Tidy | 60% | 26 | 5 | 11 |
| 5 | The Extra Level | Final Walkthrough | 90% | 30 | 6 | 12 |

Threat budget formula: `10 + 4·L`. Graveyard floors multiply the budget by 125/100 (rounded down). Monster scaling is §7.6.

Introductions: **Skeletons** appear from L2; **Wraiths** from L3. Level 1 has Miners, Vermin, Badgers, and Eels only (plus one Rogue Human). Level 3 guarantees extra Flooded Galleries (2-3). Level 5 is mostly caverns and its Rogue Human is stationed near the exit.

### 9.2 The five-pay-slip rule

Taking the Down Shaft ends the level and always leads to check-in. There is no going back up. The level 5 Down Shaft is the "Surface Lift" and leads to the final slip and review.

### 9.3 Room types

| Room | Notes |
|---|---|
| Entry (Lift Landing) | arrival tile, no monsters or loot |
| Down Shaft Chamber | exit, no loot |
| Gallery | standard; most common |
| Storeroom | 2 extra loot, 40% guarded |
| Flooded Gallery | at least 30% Brine tiles; **every level has at least one**; Eel home; loot on the shore |
| Bunk Room | sleepers: monsters start Asleep with 80% chance (35% elsewhere) |
| Collapse | cavern-shaped, Rubble |
| Crossroads | 3-4 doors; patrolling monsters |
| Foreman's Office | Grimsby's lair; guaranteed document |
| Prospector's Camp | Vane's lair; 2 pre-laid traps; guaranteed document |
| Cemetery Plot | graveyard floors; gravestones and Open Graves |
| Mausoleum | graveyard floors; one per graveyard level; 2 extra loot; guarded |

### 9.4 Graveyard roll

- Each level is **independently** rolled as a graveyard floor with **30%** probability. The roll uses a dedicated stream (`level/N/theme`), so it is identical for every player of the seed.
- Over five levels: no graveyard floors 16.8% of runs; one 36.0%; two 30.9%; three or more 16.3%.
- **Effect:** undead spawn weights ×4 (Miner 30, Skeleton 20, Wraith 14; beasts reduced: Vermin 10, Eel 8, Badger 8), threat budget ×125/100, **Hazard Premium +5g**, and 50% of non-special rooms become Cemetery Plots plus exactly one Mausoleum. Open Graves hold buried Miners.
- At least one beast monster is still guaranteed on every floor (reserve its threat cost before filling the budget).
- Normal-floor spawn weights: Vermin 25, Eel 20, Badger 20, Miner 15, Skeleton 8, Wraith 5 (subject to level gating).

### 9.5 Spawning

1. Roll the level's threat budget (above).
2. Reserve one beast spawn (Vermin pack or Badger, weighted).
3. Draw monsters by weighted choice (with level gating) until the budget is spent. Eels need a Flooded Gallery and are placed only in Brine.
4. Place each in a valid room (not the Entry room, not within 8 path-steps of the entry) with per-room caps (max 6 actors).
5. Roll each monster's initial state (Asleep / Idle) and its death drop.

### 9.6 Rogue Humans

- **One per level**, always. Type is a 50/50 weighted draw per level (so a run can have the same human several times, with their "records error" gag).
- **Placement:** pick the room whose BFS distance from the entry is at least 50% of the entry-to-exit distance (L5: at least 75%), excluding Entry and Exit rooms; the room becomes a Foreman's Office (Grimsby) or Prospector's Camp (Vane). Ties break by lowest `(y, x)`.
- **Stats:** §7.6 with level scaling. They are optional; killing one gives the 6g bounty and a guaranteed document or valuable from their pre-rolled drop.
- **Speech:** template-generated at level generation and stored in the level data, so the same seed always shows the same words. Each human gets a **mood** (Cheerful, Petty, or Grandiose), a **tic** (a signature phrase), and a template for each of five events: `on_sight`, `on_hit`, `on_hurt` (below 50% HP), `on_flee` (Vane only), `on_death`. Example grammar for Grimsby:

```
on_sight = "{greet}, {epithet}! {shift_line} {order}"
greet    = Clock in | Look alive | Morning | Right on time (you're not)
epithet  = contractor | temp | new hire | fresh hands
shift_line = Shift's not over. | Nobody told me the shift ended. | Quota's not met.
order    = Get back to work! | Boys, put in some overtime! | Sign the sheet or sign the wall.
tic      = "-- and that's on the clock."   (appended to ~1 in 3 lines)
```

Vane's grammar has `greet = Fresh claim-jumper | Evening, trespasser | You again?`, `claim = This vein's mine. | I staked this drift before there was a drift.`, and `warn = Mind the wire. | Watch your step. (No, really.)`.

### 9.7 Traps

| Trap | Effect | Surcharge |
|---|---|---|
| Spring Trap | 1d6+2 damage | Hazard Surcharge 3g |
| Tripwire Charge | cave-in: 2d4 damage (Hard Hat: -2) | Hazard Surcharge 3g + Shoring Damage 4g |
| Stun Charge | Stunned 1 turn, no damage | Hazard Surcharge 3g |

A trap that triggers is spent; a disarmed one never triggers. Monsters walk over traps without setting them off. Passive spotting is rolled once per turn that passes (not per keypress). The Hard Hat's -2 trap damage arrives with the real trap stage in milestone 5; until then the Spring Trap is a test trap placed by tests.

Static traps are placed at generation (counts in §9.1) in corridors and doorways, **never where one would be the only way on** (A68). Vane lays more at runtime, under the same rule. Traps are **hidden** until revealed: the Rogue auto-spots within 3 tiles; other classes get a passive check when adjacent (1-in-3 per turn, play RNG). Enemies avoid known traps and do not trigger them.

---

## 10. Procedural generation spec

### 10.1 Goals and guarantees

- **Same seed, same dungeon**, including terrain, monsters, items, traps, drops, documents, and Rogue Human and speech, on any platform and any supported Python version.
- Generation depends **only on the seed and the level number**. It never depends on class, prior play, wall-clock time, locale, or hash randomization.
- Level N can be generated without generating levels 1..N-1.

### 10.2 Seed

- **Canonical form:** uppercase `A-Z0-9`, 1-32 characters. Spaces and hyphens are stripped before validation, so `brass-lamp-42` and `BRASSLAMP42` are the same seed. Anything else is rejected (fail loudly). Non-ASCII is not allowed, which removes any dependence on Unicode normalization tables between Python versions.
- **Auto-generated seeds** are 12 characters of Crockford base32 from 60 random bits (the only use of OS entropy, at new-game time), displayed grouped `XXXX-XXXX-XXXX`.
- **Share code:** `<gen_version>:<seed>`, e.g., `1:BRASSLAMP42`. A colon (not a hyphen) separates the version because hyphens are legal inside seeds, and auto-generated seeds can start with digits. `gen_version` is an integer that is bumped whenever generator output changes. A mismatched code is refused with a clear message, because the same seed would produce a different mine.
- **Master value:** `master64 = int.from_bytes(sha256(b"AMTF|" + canonical.encode("ascii")).digest()[:8], "big")`.

### 10.3 The PRNG (implemented in-project)

- **SplitMix64**, written in pure Python with explicit masking (`& (2**64 - 1)`). No `random` module, no `numpy`.
- State is one 64-bit integer, which makes saving it trivial.

```
next_u64():
    state = (state + 0x9E3779B97F4A7C15) & M
    z = state
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & M
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & M
    return z ^ (z >> 31)
```

**API (integers only):** `below(n)` (unbiased by rejection: draw until `x < 2**64 - (2**64 % n)`, return `x % n`), `randrange(a, b)` (half-open), `chance(num, den)`, `dice(count, sides)`, `pick(seq)`, `weighted(items)` (integer weights, cumulative scan), `shuffle(list)` (Fisher-Yates, in place).

**Stream derivation (by identity, never by cursor).** Each purpose gets its own stream so that adding a draw in one stage cannot shift another stage:

```
derive(parent64, *labels):
    h = sha256(); h.update(parent64.to_bytes(8, "big"))
    for label in labels:
        b = str(label).encode("ascii"); h.update(bytes([len(b)])); h.update(b)
    return int.from_bytes(h.digest()[:8], "big")      # new stream's initial state
```

**Stream names** (all labels ASCII; each slash separates one label, so `level/3/layout/0` is `derive(master, "level", 3, "layout", 0)`): `level/N/theme`, `level/N/layout/<attempt>`, `level/N/rooms`, `level/N/features`, `level/N/spawns`, `level/N/loot`, `level/N/traps`, `level/N/human`, `level/N/speech`, `level/N/drops`, `level/N/docs`, `level/N/cosmetic`, `store/N`. Runtime randomness uses `play/N` (§10.7).

**Reference vectors** (produced by a throwaway script during design; the real implementation must reproduce them in the first milestone, and this document is the tiebreaker):

| Check | Expected |
|---|---|
| `SplitMix64(0)` first three outputs | `0xe220a8397b1dcdaf`, `0x6e789e6aa1b965f4`, `0x06c45d188009454f` |
| `master64("BRASSLAMP42")` | `0x7867809c6ad657af` |
| `derive(master, "level", 3, "layout", 0)` | `0x296105eac18a7de6` |
| first three `next_u64()` of that stream | `0xb08ef064d634c4b3`, `0x5ec888633491ca2e`, `0x9027c51723eec10b` |
| first six `below(100)` of that stream | `79, 34, 95, 4, 93, 39` |

### 10.4 Level generation pipeline

1. **Theme roll** (`theme`): graveyard? (30%); Rogue Human type (50/50); mood; tic.
2. **Layout** (`layout/<attempt>`): **BSP rooms-and-corridors**. Region 80×40 with a 1-tile border. Split recursively (75% chance to cut the longer axis, comparing width with twice the height because terminal cells are about twice as tall as wide; minimum leaf 12×9; max depth 5; 15% early stop from depth 3). Place a room in each leaf with a 2-tile margin (size 5..leaf-4, capped at 24×12). Each room's shape: rectangle, or a **cavern blob** with probability = the level's cavern share. A blob is made by cellular automata: fill 35% walls (`below(100) < 35`), run 3 iterations of the "wall if ≥5 of the 3×3 neighborhood are walls" rule, and keep the largest 4-connected floor region. The region must cover at least 30% of the room's rectangle; otherwise the blob is redrawn (up to 4 tries) and finally falls back to a rectangle.
3. **Corridors:** connect each pair of sibling subtrees with an L-shaped 1-tile corridor between their nearest rooms (orientation by RNG); add `1 + L//2` extra connections between non-adjacent rooms to create loops. Place doors where a corridor meets a room wall (60%).
4. **Features** (`features`): assign room types (§9.3); fill Flooded Galleries with Brine (leaving a 1-tile shore); scatter Rubble in Collapse rooms; graveyard conversion (Plots, gravestones, Open Graves, Mausoleum).
5. **Validation:** flood-fill from the entry across passable tiles. Every room, the exit, and the human's room must be reachable; room count 8-14. On failure, retry with `layout/<attempt+1>` (max 20 attempts). Exhausting attempts raises an error (fail loudly); a fuzz test hunts for such seeds before release.
6. **Entry and exit:** entry = room chosen by weighted draw from rooms; exit = the room whose anchor is farthest from the entry stairs tile by path distance (ties: lowest anchor `(y, x)`). The entry stairs sit on the entry room's top-left floor tile, the exit stairs on the exit room's.
7. **Rogue Human** (`human`, `speech`): placement per §9.6; speech strings are rendered now and stored.
8. **Traps** (`traps`): hidden static traps; Prospector's Camp pre-laid traps.
9. **Spawns** (`spawns`): §9.5, including initial states and pre-rolled drops.
10. **Loot** (`loot`) and **documents** (`docs`): §8.4, §8.3.
11. **Supply drop schedule** (`drops`): counts, trigger turns, and contents.
12. **Cosmetic variants** (`cosmetic`): decorative floor variations, drawn in row-major order.
13. **Output:** an immutable `LevelSpec` with a canonical text `dump()` used for hashing and golden files.

### 10.5 Determinism rules (enforced by code review and tests)

- **No floats** in generation or game rules. Tuning values in data files are integers; the loader rejects floats.
- **No `random`, `time`, `datetime`, `uuid`, `os.urandom`** except `secrets` for new-game seed creation in the UI layer.
- **No iteration over `set` or over `dict` where order came from a set;** sets of strings are hash-randomized per process. Use lists or `dict` (insertion-ordered) and `sorted()` with a total-order key (include a unique id as the last tie-break).
- **No `hash()`**, no `id()`, no reliance on `os.listdir` order. Data tables are loaded from TOML and kept in file order.
- **Pathfinding costs are integers** (octile `14/10`), and open-set ties break on `(f, h, y, x, sequence)`.
- **Explicit file encoding and newlines** (`encoding="utf-8"`, `newline="\n"`) wherever generator input or output touches disk.
- **Python integer semantics** are identical across platforms; `//` and `%` use floor semantics, and the code uses them deliberately.
- **Canonical dump:** UTF-8, `\n` line endings, fixed field order, entities sorted by `(kind, y, x, id)`.

### 10.6 Pre-rolled outcomes

Anything that must be the same for every player of a seed is rolled at generation: monster death drops, Rogue Human drop and speech, supply drop timing and contents, document text, Requisitions Desk stock (`store/N`). This keeps "same seed, same items" true no matter how or when you kill something.

### 10.7 Runtime randomness

Combat, noise wakes, stealth checks, trap spotting, and similar rolls use `play/N` (one stream per level, derived from the seed). Its state is a single 64-bit integer saved with the game. It is consumed in the order the deterministic scheduler runs actors. The same seed plus the same input sequence therefore reproduces the same game, which is used by replay tests (Implementation Plan §5).

---

## 11. Save/load and permadeath

**Recommendation:** permadeath with **one save slot**, using **state snapshots** (not input replay).

- **What is saved** (JSON, human-readable, versioned): seed, `gen_version`, class, Rank, current level, turn/tick counters, `play` RNG state, scheduler queue, all actors (position, HP, statuses, cooldowns, facing, AI state), inventory and equipment (including `use_charge` and durability), the level's discovered-tile map, picked-up flags, the ledger for the current level, wallet, debt, pending coupons/waivers, and the Requisitions stock.
- **What is not saved:** the level terrain and spawn layout. It is **regenerated from the seed** on load, which keeps files small and proves the generator is deterministic. The save stores `layout_sha` (hash of the canonical dump); on load it is compared with the regenerated level, and a mismatch stops the load with a clear error ("This save was made with a different mine"). No silent fallback.
- **Atomic writes:** write `run.json.tmp`, flush and fsync, then `os.replace` (atomic on Windows and POSIX on one volume).
- **When it saves:** on Save & Quit (any time, even mid-fight) and automatically at every check-in (just before descending). Loading does **not** delete the file.
- **When it is removed:** on death or victory, the run is deleted and a record is appended to `records.json` (personnel file: seed code, class, score, title, levels cleared, cause of death, turns). The death/victory screen offers "Retry this seed" and "New seed."
- **Location:** the **portable EXE** keeps everything in a `MineTooFarData\` folder next to the EXE (A28). Source runs use Windows `%APPDATA%\MineTooFar\`, Linux `$XDG_DATA_HOME/minetoofar/` (or `~/.local/share/minetoofar/`), macOS `~/Library/Application Support/MineTooFar/`. `--save-dir` overrides all of these. If the chosen folder is not writable, the game stops with a clear message instead of picking another location.
- **Versioning:** `save_version` integer with a forward migration chain. A save from a newer version than the game refuses to load.

**Why not input replay as the save format:** it is brittle across any code change and slow to load late in a run. Replay logs are still recorded in memory (with periodic state-hash checkpoints) for bug reports and tests, but are not a save.

**Save-scumming:** possible by copying the file, accepted for a single-player game. An optional `ironman = true` config would delete the save on load; it is not built in v1.

**As built (M9).** The title menu's `R` shows the employment history (the last eight lines of `records.json`, newest first) and a damaged file is reported there instead of stopping the game. `?` in play opens the help screen. `tools/regen_golden.py` refuses to change a golden hash at the same `GEN_VERSION`. See A86 and A87.

**As built (M8).** `persist/` holds `paths.py`, `save.py` and `records.py`; the game state is turned to and from plain data by `sim/snapshot.py`. A test saves a game at several moments, loads it, and plays 500 more inputs on both copies; the state hash never differs. See A76-A82.

---

## 12. Out of scope for v1

- **Magic** (hooks only, §7.8) and **ranged combat** (thrown items, bows, Ranger ranged attacks).
- Companions, allies, summons, faction infighting.
- More than 5 levels, branching paths, side dungeons, going back upstairs.
- Buying/selling loot at shops, crafting, enchanting, item identification, curses, hunger.
- Multiple save slots, undo, cloud saves, online leaderboards, daily seeds.
- Mouse input, gamepad, sound or music, localization.
- Locked doors and keys; secret doors.
- Auto-explore and travel commands.
- Difficulty settings (one "Standard" difficulty; a `pay_multiplier` data key exists at 100%).
- A tutorial (a single help screen only).
- Procedural item affixes and random enchantments.
- Installers (MSI, winget), code signing, and macOS/Linux binaries. The **portable Windows EXE is in scope** (Implementation Plan §1.4 and M10).

---

## 13. Assumptions

Defaults chosen without asking. Each can be changed in data files unless noted as structural.

| # | Assumption |
|---|---|
| A1 | **TUI library: Textual**, behind a thin renderer boundary (see Implementation Plan §1). Confirmed by you. |
| A2 | Python **3.12+**, packaged with **uv** (which fetches the interpreter if needed); no dependency beyond Textual at runtime. Dev shells: PowerShell and WSL. |
| A3 | Map size is **80×40** for every level; minimum terminal **80×24**; no mouse. |
| A4 | Turn system is **tick-based** (100 ticks per turn) so fast/slow monsters and Overtime work. |
| A5 | **No natural HP regeneration.** HP is fully restored free at check-in ("Wellness Break"). |
| A6 | Consumables are **free to carry and billed on use** (issued, found at half, or prepaid), per §8.2. |
| A7 | **Hazard Pay is a deduction** (5g), not a bonus. The Stubborn ability costs the Fighter money. Confirmed by you. |
| A8 | Pay: **15g** base, **+5g** graveyard premium, **+6g** human bounty, no depth allowance. Starting wallet **0g**. |
| A9 | Deficit becomes **debt with a 10% late fee**; debt closes the Requisitions Desk and reduces final score; debt never ends the run. |
| A10 | **Graveyard chance is 30%** per level, independently, on any level including L1. |
| A11 | Rogue Humans are **recurring named individuals** (Grimsby and Vane), 50/50 per level. They are optional to defeat. Confirmed by you. |
| A12 | **Flanking** means attacking from a target's rear arc (+2 to hit for anyone). Rogue Backstab applies to flanked, stunned, unaware, or fleeing. |
| A13 | **Ranks** replace XP: promotion at each check-in; no skill choices. Ability unlocks at **Rank 3**. |
| A14 | Armor wears **1 Dur per hit taken** (2 on a critical); repair restores to full and is billed; declinable. |
| A15 | Stats are only **STR and DEX**; modifier `(score-10)//2`; no CON/INT/WIS. |
| A16 | **Rogue starts with an empty Off Hand**; Fighter has a shield; Ranger has twin hatchets. |
| A17 | **Light is a mechanic:** Hard Hat lamp radius 4, Torch radius 8 for 400 turns of burn. |
| A18 | **Traps:** three types, static counts per level, Vane lays up to 4 more; enemies avoid known traps. |
| A19 | **Scoring and titles** per §8.8; high scores stored locally only. |
| A20 | **Seeds** are ASCII `A-Z0-9`, case-insensitive, hyphens ignored; share code is prefixed with `gen_version`. |
| A21 | **Dungeon is independent of class.** The same seed yields the same mine for all three classes. |
| A22 | **Save:** single slot, snapshot JSON, autosave at check-ins and on quit, deleted on death/victory. |
| A23 | **Death** ends the run (permadeath); there is no continue/second chance. |
| A24 | **Glyphs:** `auto` selection; Greek letters used for some monsters; ASCII fallback is always available. |
| A25 | **Supply drops** are billed when items are taken (not when used); Requisitions purchases are paid from the wallet immediately. |
| A26 | **Documents** have small mechanical effects (coupon, map fragment) in addition to lore. |
| A27 | Balance targets in §8.6 are a goal, verified by simulation in milestone 9, not guaranteed by this draft. |
| A28 | **Portable EXE saves next to the EXE** in `MineTooFarData\` (leaves nothing on the system); source runs use `%APPDATA%`. `--save-dir` overrides both. Not writable means a clear error, not a fallback. |
| A29 | **Portable EXE is built with PyInstaller** (one-file, plus a one-folder zip fallback), Windows only, built in PowerShell. Unsigned in v1. |
| A30 | **Movement:** 8-direction, no diagonal corner-cutting and no diagonal steps through doors (§7.1). Generation measures path distance with the same rule. |
| A31 | **Run** stops at refusals, doors, stairs, and changes in the open sides of the path; it does not follow corridor bends (§4.1). |
| A32 | **Remembered tiles** are drawn in a darker color rather than with a dim attribute (§5.4). |
| A33 | **Melee reach** obeys the movement rule: no attacks around corners or diagonally through doorways (§7.1). |
| A34 | **Monsters open doors** by bumping, at their move cost, and path through closed doors as if open (§7.7). |
| A35 | **Waking** is rolled once per monster turn (100 ticks), not once per tick; "within 4 tiles" is the integer circle `dx² + dy² ≤ 16` and "adjacent" is one tile in any direction (§7.7). |
| A36 | **Spawns v0:** only Miners; the threat budget `10 + 4·L` is spent drawing Miners; none in the entry or exit room or within 8 straight steps (path cost 80) of the entry; at most 6 per room; 35% start Asleep, the rest Idle. Bunk Rooms (80% Asleep) arrive with room types (§9.5). |
| A37 | **Armor wears** on every hit that lands, including one Stubborn absorbs, and before the death check (§7.2 step 6). |
| A38 | **Debug:** `--rank N` starts the run at Rank N with that Rank's HP. |
| A39 | **Death screen:** Retry restarts the same seed at the same start level and Rank; New seed rolls a fresh one. A full 5-level run restart arrives with milestone 9. |
| A40 | **Classes:** Rogue and Ranger kits, HP, and Rank tables are exactly §6.3 and §6.4; a table-driven test checks every derived number at every Rank. |
| A41 | **Backstab** adds +2d4 once per attack; the dice are not doubled by a critical; automatic hits still roll the d20 (§6.5). |
| A42 | **Dual wield:** every normal attack is a main-hand swing then an off-hand swing at -4 ATK with no attribute modifier to damage; the off-hand swing is skipped if the main hand killed the target. Dual Strike removes only the -4 (§6.7). |
| A43 | **Abilities:** one per class, unlocked at Rank 3, upgraded at Rank 5, used with `a`. A cooldown runs from the moment of use; a refused use is free. Cleave attacks every enemy in reach clockwise from north, one action; Dual Strike picks the first. |
| A44 | **Poison** ignores DR and ticks every 100 ticks for 500 ticks, collected on the victim's turns; reapplying refreshes the length and keeps the rhythm. |
| A45 | **Tracker** senses in the integer circle `dx² + dy² ≤ 25` through walls; sensed enemies are not inspectable and show as `~ Name` in the Nearby list. |
| A46 | **Traps (test):** the Rogue sees hidden traps within `dx² + dy² ≤ 9` in plain view; others notice an adjacent one 1 time in 3 per turn; Disarm costs 100 ticks and always works; a sprung trap is spent. |
| A47 | **Facing:** the player starts facing south; flanking is +2 to hit for anyone attacking from the rear arc, including monsters attacking the player (§7.4). |
| A48 | **Room types (M5):** the GDD gives no odds, so these are mine. Of non-special rooms, a cave room is a Collapse 50% of the time (Rubble on 25% of its floor) and any other room is a Bunk Room 20% of the time. A Flooded Gallery needs at least 30% of its floor to be interior (no neighbour is a wall, door, or prop) and is filled with Brine on that interior only, so a 1-tile shore remains. Level 3 floods 2-3 rooms (all it has if fewer qualify, never fewer than 2); every other level floods 1. On a graveyard floor 50% of the remaining rooms are Cemetery Plots (open graves on 6% and gravestones on 12% of the interior) and one room is the Mausoleum (2 monuments). All tunable in `balance.toml [features]`. |
| A49 | **Brine and the torch:** stepping into Brine with a lit torch loses it 1 time in 2; taking a critical hit with it lit loses it 1 time in 4 (§8.5). The game asks `[y/N]` before any such step. Standing in Brine keeps you Soaked (DEF -1) and for 200 ticks after. |
| A50 | **Noise:** a melee blow is heard 5 steps away, a door opening 3, and a Skeleton's step or swing 8 (its Clang). Sound travels by steps through floor and open doors; closed doors stop it. A sleeper that hears a sound wakes 1 time in 2; an idle monster that hears one becomes Alerted and walks to where it came from. |
| A51 | **Buried and Submerged:** a Buried Miner rises (one action) when the player is within `dx² + dy² ≤ 9`. A graveyard Miner starts Buried in an open grave 50% of the time when the floor has one. A Submerged Eel ambushes with +4 ATK, and dives again after 200 ticks with nobody beside it. Falling into an open grave costs 1d4 and 200 ticks to climb out. |
| A52 | **Wraith:** moves one tile a turn straight toward the player through walls, never onto another actor; +4 DEF while inside a wall; a damaging hit Clocks you In 35% of the time (lose the next action, then 500 ticks of immunity). |
| A53 | **Beasts:** a Gem Badger flees at 40% HP or less and burrows away after 1200 ticks out of sight. Cave Vermin come in packs of 3-5; each gets +1 ATK per other Vermin beside its target, up to +3. A whole pack costs one pack's worth of threat. |
| A54 | **Rogue Human placement:** the lair is the first room, by path distance from the entry (ties: lowest y, x), that is at least 50% of the way to the Down Shaft (75% on Level 5), never the Entry, Exit, a Flooded Gallery, or the Mausoleum; if none is far enough, the farthest room. Its lines are rolled at generation time, so a seed always shows the same words. |
| A55 | **Grimsby and Vane:** Grimsby's Overtime aura reaches `dx² + dy² ≤ 25`, lasts 300 ticks and is renewed every turn; he holds 2-3 tiles back from the fight. Vane lays a hidden trap where he stands at most every 600 ticks while he sees the player within `dx² + dy² ≤ 36`, up to 4 a level, then retreats for 300 ticks; his camp starts with 2 traps. |
| A56 | **Traps (M5):** each level has 2, 3, 4, 5, 6 hidden traps (Levels 1-5), on corridor tiles and the floor on either side of a door, never in the Entry room. Three kinds: Spring Trap (1d6+2), Tripwire Charge (2d4), Stun Charge (no damage; stuns one turn). A Hard Hat reduces trap damage by its `trap_reduction`, never below 1. |
| A57 | **Spawning (M5):** budget `10 + 4L` (×125/100 on graveyard floors), one beast reserved first, nothing within 80 path cost (8 straight steps) of the entry, at most 6 actors a room. 35% start asleep (80% in a Bunk Room), the rest idle. |
| A58 | **Descending (M5):** `>` or `Enter` on the Down Shaft starts the next level with Rank and armor wear carried and HP restored; elsewhere it is refused. `F5` is a debug skip from anywhere until the pay slip exists. Retry restarts the level you died on, in the armor you arrived in. |
| A59 | **Found gear (M6):** the tier table of §8.4 applies to weapons, armor, shields, hats and trinkets alike. Only weapons have a T3, so a roll of T3 on anything else falls back to the best lower tier it has. Tiers for the items the GDD leaves open are mine: Hard Hat T1, Reinforced and Headlamp Hard Hats T2; Sheet-Metal Shield T1, Riot Shield T2; every trinket T1. Found armor is rolled at 50-100% of its Dur; consumables are found at `ceil(list / 2)`. |
| A60 | **Loot placement (M6):** `7 + L` items, plus 2 per Mausoleum, in rooms chosen by weight (Mausoleum 6, the human's lair 4, Collapse 3, Gallery, Bunk Room, Flooded Gallery and Cemetery Plot 2); never in the Entry or Exit room; one to a tile, on bare floor, away from monsters, traps and the human. Storeroom and Crossroads rooms do not exist yet (A48), so their weights and extra loot are unused. At most 2 documents a level, and the lair always holds one more, placed first. |
| A61 | **Drops (M6):** a Gem Badger leaves 1d2 Rough Gems; each Rogue Human leaves one find, a valuable or a document by the §8.4 weights. Both are rolled with the level (`loot` stage, by monster number), so a kill always drops the same thing. The bounty is earned when the human dies, however it dies. |
| A62 | **Picking up (M6):** valuables jump into the pack when stepped on, free, and are turned in at check-in; `g` or `,` takes one other thing a time (50 ticks); a document is read where it lies (a coupon goes on the account, a map fragment marks every room as remembered, a memo is only words); dropping costs 50 ticks. Carry limits are per item over every stack; a pickup that would pass one is refused whole and free. |
| A63 | **Torch (M6):** the first lighting takes a Torch from the pack and bills its use charge; it then burns for 400 turns of lit time in all, however often it is snuffed, and goes out when spent. A torch lost to Brine or a critical hit is gone with whatever burn time it had (and costs the 2g). Lighting with none is refused. A Patch-Up Kit at full HP is refused for free rather than wasted. |
| A64 | **Gear rules (M6):** equipping takes 100 ticks and puts what was worn in the pack (armor keeps its condition). A light weapon (Box Cutter, Hatchet, Utility Knife) may be held in the off hand; a two-handed weapon puts the off-hand item away and forbids a new one; heavy weapons and shields cannot be dual-wielded. A Thermos adds 3 max HP and heals 3; taking it off trims current HP to the new maximum. A Shovel or Sledgehammer blow is heard 8 away and a critical stuns; Detergent Coat adds 2 damage against the undead. |
| A65 | **The slip (M6):** lines are repair, each consumable stack, supply, then Dropped torch, Hazard Surcharge, Shoring Damage, Hazard Pay, Timecard, Uniform Recovery Fee, balance carried forward and late fee. Surcharges and Timecard are one line with a count. Prepaid use shows at 0g. The Property Damage Waiver forgives incidentals in slip order, part of a line if need be; a Repair Plan waits for a repair line; coupons are spent on any adjustment line except the old balance, and unspent ones are kept. |
| A66 | **Death (M6):** the Posthumous Pay Slip takes only the Base Job Fee off the pay of §8.6: a Hazard Premium, a bounty and salvage already earned still count, repair is billed, and the 5g Uniform Recovery Fee is added. Score and title are shown on the incident report. Retrying a level restores the purse and pack as they were on arrival. |
| A67 | **Run flow (M6):** `>` or `Enter` on the Down Shaft opens the slip; signing it restocks Standard Issue and starts the next level. Rank promotion, the report, the memo and the desk arrive with M7. Finishing Level 5 ends in the performance review (score and title). `F5` signs the books quietly and skips, for testing. |
| A68 | **Traps never gate the level (M6 fix):** only a Rogue can disarm a trap, and the dungeon is the same for every class, so a trap may not be the only way on. A static trap is refused where, with it and every trap already down counted as walls, any walkable tile would no longer be reachable from the entry; Vane's runtime traps obey the same test against every live trap, and a trap that is disarmed stops counting. A level with few loops therefore holds fewer traps than §9.1 lists (about a quarter fewer overall, most on Level 5), and a corridor that is the only way somewhere is never trapped. |
| A69 | **Supply drops (M7):** the trigger turn counts player turns on the level. The first drop is drawn from turn 120 to 450 so the second, at least 250 turns later, still fits before 700. A crate holds 3 distinct consumable lines of 1-2 each, drawn by the §8.4 sub-weights, and 25% of the time one piece of equipment by the tier table, delivered new (full Dur). It lands on the first free floor tile in row order of the smallest ring around the player; with no free tile within 3 it waits until one appears. |
| A70 | **Taking supplies (M7):** stepping onto the crate, or `g` on it, shows the invoice; accepting ticked lines takes a turn. Taken stock arrives prepaid. Handling is 20% of the taken lines rounded up, the 2g delivery fee is billed once per crate however many times you return, and untaken lines stay in the crate until you leave the level. A pack that cannot hold the whole order refuses all of it, free. The bill reaches the next pay slip as "Supply Drop Invoice #n". |
| A71 | **The check-in (M7):** the order is field report, pay slip, memo, desk, then the next level. `Esc` on the report signs the slip as it stands (repair on, no coupons) and skips to the memo. Promotion is automatic: one Rank per level finished (Rank 2 after Level 1 ... Rank 5 after Level 4), never lower than you came with. The Wellness Break restores full HP at the new maximum and Standard Issue tops up as in A67. After Level 5 there is only the report, the slip and the review; no memo, no desk. |
| A72 | **Desk stock (M7):** four items rolled on `store/N` (the desk after Level N), the same for every player. Slot 1 is a bundle (Torch or Kit, even odds); the other three are distinct, drawn by my weights from the remaining eight (Sharpening 10, Waivers and Repair Plan 10 each, 8 for Hone & Balance, Reinforced Hard Hat, Wellness Seminar and Hazard Waiver, 6 for Armor Plating). Each slot sells once, is paid from the wallet on the spot, and the desk is closed to an account in debt. |
| A73 | **Purchases (M7):** a bundle is refused whole, and charged nothing, if the pack cannot take it. Sharpening (+1 damage, at most +3) and Hone & Balance (+1 ATK, at most +2) go on the weapon in hand and stay with that weapon. Armor Plating adds +4 max Dur (and +4 Dur now) and +1 DR, once per armor; broken armor loses the plate too. Wellness Seminar is +3 max HP for good. A Repair Plan, Property Damage Waiver or Hazard Waiver can be held one at a time, and applies to the next slip (a Repair Plan waits for a repair line). |
| A74 | **Memos (M7):** a sender, a subject ("RE: ..."), an opener, one policy line, a reminder, a notice and a sign-off, chosen on `store/N`. From the second memo on, half of them state the other side of the pair the memo before chose, so the company contradicts itself. The notice always says whether the next level is a graveyard and what the Hazard Premium is. |
| A75 | **Debug skip (M7):** `F5` signs the slip with its defaults, promotes you, skips the memo and desk, and starts the next level. |
| A76 | **The save file (M8):** `run.json`, JSON with `save_version` 1 (a forward migration chain, empty so far), the generator version, the seed, class, starting Rank, the level, the carry-over from the last check-in, the level in play (or none, when saved at a check-in), and the last 30 log lines. `layout_sha` is one hash over every generation stage of that level, so a change to loot or spawns stops a load just as a change to the map does: "This save was made with a different mine." |
| A77 | **When it saves (M8):** `Esc` opens a menu with Save & quit (any moment, mid-fight included); `S` on the Requisitions Desk saves and quits with your purchases made; and leaving the desk saves automatically before the next level begins. Loading does not delete the file. Quitting with `Q` leaves the last save as it was. |
| A78 | **Whose save it is (M8):** a run chosen from the title menu (New run, Continue) owns the slot. A run started from the command line (`--seed`, `--class`, `--level`, `--rank`) does not: it never autosaves over another run, and Save & quit asks before replacing one. With no save on disk it saves freely. Choosing New run over an existing save asks first. |
| A79 | **Endings (M8):** death and victory add an entry to `records.json` (the personnel file: share code, class, Rank, level reached, levels cleared, score, final title, cause of death, turns) and remove the save if it was this run's. Retry (`R`) restarts the level from its arrival with no save on disk until the next check-in; each death is its own record. A damaged `records.json` is reported and left alone. |
| A80 | **Where saves live (M8):** the portable EXE keeps `run.json` and `records.json` in `MineTooFarData\` beside itself; source runs use `%APPDATA%\MineTooFar\` on Windows, `$XDG_DATA_HOME/minetoofar/` (or `~/.local/share/minetoofar/`) on Linux, and `~/Library/Application Support/MineTooFar/` on macOS. `--save-dir` beats all of them. A folder that cannot be created or written stops the game with a message naming it; there is no fallback. |
| A81 | **What it will not load (M8):** a file that is not JSON, is truncated, or is full of zeros (damaged); JSON that is not ours; a newer `save_version`; a save whose generator version or `layout_sha` no longer matches; and state that names things this build does not have. Each says what is wrong, loads nothing, and starts no game. |
| A82 | **Atomic writes (M8):** the save is written to `run.json.tmp`, flushed to disk, then swapped in with an atomic replace, so a crash leaves the previous save. A lone `.tmp` file is not a saved run. |
| A83 | **Base Job Fee is 10g (M9):** retuned from 15g so the careful bot's median net per cleared level lands inside the 4-10g target (it was 13 to 15g). Debt stays under 15% of winning runs because the bot keeps a reserve at the desk (A85). The GDD 8.6 worked examples still use 15g. |
| A84 | **Boiler Suit repairs at rate 2 (M9):** the Fighter's heavy kit cost 6 to 9g a level to repair and put 21% of its winning runs into debt at the end; at rate 2 it is 8% and the Fighter's median net is in line with the other two classes. Other armor is unchanged. |
| A85 | **The competent player the simulator uses (M9):** `sim/bot.py` with the `CAREFUL` policy and `sim/autoplay.py`. It fights only what is already after it (waiting up to six turns for it to arrive), goes round sleepers and out of a Rogue Human's line of sight where a route exists, leaves finds that would wake someone, takes only armor, weapons and shields that beat what it wears and drops the spares, takes only gear from supply crates, heals at half HP (and to 80% before meeting a Rogue Human), drinks Overtime Fizz for a Human and Sanctified Detergent for the undead, and at the desk buys HP, kits, plating and edge in that order while keeping 8g back (14g before the last level). It never retreats, never closes a door or disarms a trap, and cannot sneak-attack, so it is a floor under a person's play, not an average of it. It wins about 41% of Fighter runs, 12% of Rogue runs and 26% of Ranger runs; Foreman Grimsby is its main killer (45 of 118 Fighter deaths, 79 of 176 Rogue, 86 of 149 Ranger). The `RECKLESS` policy (fight everything, take everything, no planning) is the sloppy player: its median slip is -17 to -22g. |
| A86 | **The generator is frozen at version 1 (M9):** `tools/regen_golden.py` refuses to change a hash already in the manifest unless `GEN_VERSION` is bumped first. Share codes name the same mine on every machine and every build of version 1. Economy and item numbers are not generator output, so the M9 retune left every golden hash alone. |
| A87 | **Help and history screens (M9):** `?` opens a one-screen list of the keys that exist and the rules of the job (no tutorial; GDD 12). The employment history is named for what it is, since "personnel file" is already the character sheet's title. Keys the first draft lists but the game does not have: `m` message log, `M` level overview, `C` close door, and `keys.toml` rebinding. |
| A88 | **The portable EXE (M10):** unsigned, so SmartScreen may warn on first run. The one-file build unpacks into `%TEMP%` for each launch (that is how PyInstaller works) and removes it on exit; everything the game itself writes goes in `MineTooFarData\` beside the EXE. A one-folder zip is offered because it starts about twice as fast. After a failure in a window it owns alone (a double-click), the EXE waits for Enter. `--autoplay` and `--save-selftest` exist so a build can be compared with the source; they are checks, not ways to play. |

---

## 14. Open questions

1. **Textual OK?** **Resolved (2026-10-09): yes.** Textual is the TUI library (Implementation Plan §1).
2. **Hazard Pay (A7):** deduction (as drafted) or bonus? **Resolved (2026-10-09): deduction.** Stubborn costs the Fighter 5g each time it fires.
3. **Rogue Humans (A11):** recurring named individuals with a "records error" gag, or a unique name per level generated from the seed? **Resolved (2026-10-09): recurring.** Grimsby and Vane keep their names across levels and runs.
4. **Free full heal at check-in (A5)** keeps each level self-contained. Do you prefer carry-over wounds, or a billed "Medical Services" line?
5. **Debt (A9):** is "debt that closes the desk and lowers the score" the right pressure? Alternatives: forgiven at a cost, or a hard cap that ends the run ("Collections").
6. **Flanking (A12):** rear-arc flanking is easy to implement and visible, but it triggers mainly against fleeing/slow/stunned/unaware foes. If you want classic "two attackers" flanking, we need allies or decoys; that is a larger scope.
7. **Length:** is a 75-100 minute full run the right target? It sets level size (80×40) and monster counts.
8. **Class balance:** the Ranger's early output is intentionally lower until Dual Strike (Rank 3). Acceptable, or give the Ranger a starter edge?
9. **Graveyard frequency (A10):** 30% per level gives no graveyards in about 1 run in 6. Should L1 be excluded?
10. **Naming:** the Python package is `minetoofar` in `src/`. Different name?
11. **Windows environment:** which Python and terminal do you use on the Windows side? **Resolved (2026-10-09): PowerShell or WSL; any Python 3.** `uv` installs and pins Python 3.12+ itself, so the installed version does not matter. Test targets are PowerShell (in Windows Terminal and in a standalone console window) and WSL.
12. **Git:** the folder is not a git repository yet. I will not run `git init` or commit; tell me when you want a repo and `.gitattributes` (needed to keep data files LF on Windows).
13. **Use-item key clash:** `u` was bound to both Use item and vi north-east. **Resolved (2026-10-09): Use item is `q`; `u` stays vi north-east; `Q` stays Quit.**
