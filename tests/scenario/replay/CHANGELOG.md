# Replay logs

A committed log is evidence that rules and dice did not drift. Re-record only when a rule
change makes the old evidence wrong on purpose, and say why here.

- M3: first logs (Fighter): fights, a death, a Rank jump with the torch lit.
- M4: re-recorded the three Fighter logs because actors now have a facing and flanking adds +2 to
  hit; added a Rogue log (Poison Blades, Backstab) and a Ranger log (dual wield, Dual Strike).
- M5: re-recorded all five logs. The monster roster, spawn budget, hidden traps, Rogue Humans and
  level themes changed every level's contents, so the old logs described levels that no longer
  exist. Same seeds, levels, classes, ranks and opening commands as before; the bot is now
  hazard-aware, so some logs end in a death and some in a standing fight.
- M6: re-recorded all five logs. The state hash now covers the pack, floor items, purse and ledger,
  and levels hold loot; the bot picks things up, reads documents and drinks a Patch-Up Kit when
  badly hurt. Same seeds, levels, classes, ranks and opening commands as before.
- M6 fix: re-recorded all five logs again. Traps are no longer placed where they would be the only
  way on, so every level's traps (and the loot that avoids them) moved. Same seeds, levels,
  classes, ranks and opening commands.
- M7: re-recorded all five logs (supply crates now land, so the state hash and the levels' play
  changed) and added `fighter-GOLD0016-L1-rank5-supply.json`, in which the bot walks to a
  landed crate and takes its lines. Same seeds, levels, classes, ranks and opening commands.
- M8: re-recorded all six logs. The state hash now covers the turns spent on earlier levels (the
  personnel file needs them). Same seeds, levels, classes, ranks and opening commands.
