# Routine Corpus Study — 2026-07-18

*Read-only analysis of all 42 routine YAMLs under `routines/`, cross-referenced
against the executor (`mcptools/tools/routine.py`), the await/condition parser
(`mcptools/tools/monitoring.py`, `mcptools/tools/commands.py`), and the prior
journals `ROUTINE_VALIDATION_SWEEP_2026-07-17.md`, `ROUTINE_ENGINE_HARDENING_2026-07-17.md`,
`ROUTINE_STRATEGY_2026-07-17.md`, and `TUTORIAL_TEST_DEFECTS_2026-07-17.md`.
No files edited, no client touched, no writes to `/tmp/manny_new_command.txt`.*

Maturity legend: **complete** = has `steps:`, real command vocab, usually carries
`validated: true` / `status: VALIDATED`. **stub** = no executable `steps:` (config
sidecar / design doc / reference / `manual_steps:`). **scaffold** = test/placeholder.

---

## 1. Inventory

| Path | Category | Purpose (one line) | Maturity | Needs specific start state? |
|---|---|---|---|---|
| combat/chicken_killer_loop.yaml | combat | `KILL_LOOP Chicken 100`, 50 auto-loops (5000 kills) | complete | Yes — must already be near Lumbridge chickens; step 1 has no GOTO |
| combat/chicken_killer_training.yaml | combat | GOTO coop → `KILL_LOOP Chicken 200`, single run | complete | Self-travels from Lumbridge; needs a weapon |
| combat/cow_killer_no_bones.yaml | combat | Cow-kill *config sidecar* (loot/eating keys, no steps) | stub | n/a (not executable) |
| combat/cow_killer_training.yaml | combat | Bank→`EQUIP_BEST_MELEE`→GOTO cow pen→kill | complete | Self-travels; needs melee gear banked at Lumbridge |
| combat/hill_giants.yaml | combat | Hill Giant *design doc* (loot/eating config, no steps) | stub (superseded) | n/a |
| combat/hill_giants_loot.yaml | combat | Attack Hill Giant, loot runes/bones, bury, 100-loop | complete | Yes — start inside Edgeville Dungeon w/ gear+food |
| combat/hill_giants_restock.yaml | combat | Bank loot, restock food/runes, return | complete | Yes — mid-Hill-Giants trip |
| combat/hill_giants_resupply.yaml | combat | Bank at GE and restock for Hill Giants | complete | Yes — start at GE |
| combat/hill_giants_travel.yaml | combat | Travel GE→Hill Giants via brass-key shortcut | complete | Yes — start at GE, brass key |
| common_actions.yaml | library | Reusable snippets (stairs/banking) under named keys | stub (reference) | n/a |
| generated/test_scorpion_attack_1769492259.yaml | generated | Auto-generated 1-event sample (attack scorpion) | scaffold | Yes — wherever scorpions are |
| quests/cooks_assistant.yaml | quest | Cook's Assistant, gather milk/flour/egg in Lumbridge | complete | Yes — Lumbridge; one-shot |
| quests/imp_catcher.yaml | quest | Imp Catcher, 4 beads → Wizard Mizgog | complete | Yes — start Wizard's Tower; needs 4 beads; one-shot |
| quests/restless_ghost.yaml | quest | The Restless Ghost, skull from tower basement | complete | Yes — Lumbridge Church; multi-area; one-shot |
| quests/romeo_and_juliet.yaml | quest | Romeo & Juliet, cross-Varrock, 38 steps | complete | Yes — Varrock Square; one-shot |
| quests/sheep_shearer.yaml | quest | Sheep Shearer, shear 20 wool, spin, deliver | complete | Yes — Fred's house north Lumbridge; one-shot |
| skilling/cooking_lumbridge.yaml | skilling | Cook raw fish at Lumbridge range, bank top floor, loop | complete | Needs 28 raw food banked; self-navigates in castle |
| skilling/fishing_draynor.yaml | skilling | Fish shrimp at Draynor, bank Lumbridge (no loop block) | complete (single pass) | Needs small net; self-travels |
| skilling/fishing_karamja_harpoon.yaml | skilling | Harpoon tuna/swordfish Musa Point, ferry, deposit box | complete | Yes — fishing 35+, harpoon, coins, ferry hops |
| skilling/fishing_karamja_lobster.yaml | skilling | Lobster cage Musa Point, ferry, 50-loop | complete | Yes — fishing 40+, lobster pot, coins, ferry |
| skilling/flour_milling.yaml | skilling | Mill grain→flour at Lumbridge windmill (no loop) | complete (single pass) | Needs grain+pot; start at windmill |
| skilling/mine_iron_ore.yaml | skilling | Mine iron in Mining Guild, bank Falador E, inner/outer loop | complete | Yes — **mining 60**, pickaxe, start Falador E bank |
| skilling/mining_falador_iron.yaml | skilling | `POWER_MINE` iron (drops ore), internal loop | complete | mining 15, pickaxe, start Falador Dwarven Mine |
| skilling/superheat_mining_guild.yaml | skilling | Mine iron + Superheat → iron bars, loop | complete | Yes — **mining 60 / magic 43 / smith 15**, runes |
| skilling/superheat_steel_bars.yaml | skilling | Mine coal+iron + Superheat → steel bars, inner/outer loop | complete | Yes — **mining 60 / magic 43 / smith 30**, staff+natures |
| skilling/woodcutting_lumbridge.yaml | skilling | Bank→chop trees near Lumbridge (no loop block) | complete (single pass) | Needs any axe; self-travels |
| test/basic_test_routine.yaml | test | 5-step system smoke test (PING/state) | scaffold | No |
| tutorial_island/01_character_creation.yaml | tutorial | Randomize + confirm character | complete | Yes — must be at tutorial start |
| tutorial_island/01_experience_selection.yaml | tutorial | Single-step experience-mode pick | complete (1 step) | Yes — tutorial start |
| tutorial_island/02_gielinor_guide.yaml | tutorial | Gielinor Guide dialogue/settings | complete | Yes — tutorial stage 2 |
| tutorial_island/03_survival_expert.yaml | tutorial | Survival: fishing/fire/cooking shrimp | complete | Yes — tutorial stage 3 |
| tutorial_island/04_woodcutting_firemaking.yaml | tutorial | Woodcutting + firemaking section | complete | Yes — tutorial stage 4 |
| tutorial_island/05_cooking.yaml | tutorial | Cooking section | complete | Yes — tutorial stage 5 |
| tutorial_island/05_cooking_to_quest_guide.yaml | tutorial | Cooking→Quest Guide bridge (5 locations miss `plane`) | complete (data gap) | Yes — tutorial stage 5 |
| tutorial_island/06_quest_guide.yaml | tutorial | Quest Guide + quest journal | complete | Yes — tutorial stage 6 |
| tutorial_island/07_mining_smithing.yaml | tutorial | Mining + smithing (bronze dagger) | complete | Yes — tutorial stage 7 |
| tutorial_island/08_combat.yaml | tutorial | Combat rats; `mcp_tool:` equip/widget + `await:dialogue` | complete | Yes — tutorial stage 8 |
| tutorial_island/09_banking.yaml | tutorial | Banking tutorial section | complete | Yes — tutorial stage 9 |
| tutorial_island/10_prayer_magic.yaml | tutorial | Prayer + magic; heavy `await:dialogue` + `mcp_tool:` | complete | Yes — tutorial stage 10 |
| tutorial_island/widget_reference.yaml | tutorial | Widget-ID reference doc (no steps) | stub (reference) | n/a |
| utility/death_escape.yaml | utility | Escape Death's Domain after first death | complete | Yes — only valid inside Death's Domain |
| utility/gravestone_retrieval.yaml | utility | Retrieve items from gravestone (`manual_steps:`) | stub (manual runbook) | Yes — post-death, 15-min timer |

Counts: 42 YAML total → ~31 executable-complete, 5 stubs (`cow_killer_no_bones`,
`hill_giants`, `common_actions`, `widget_reference`, `gravestone_retrieval`),
2 scaffolds (`basic_test_routine`, `generated/…`), plus `01_experience_selection`
(1-step) and `05_cooking_to_quest_guide` (data gap) flagged.

---

## 2. Inferred user intent

The corpus is a **fresh-account-to-self-sufficiency F2P automation pipeline**, built
in the order a real F2P account progresses, and the density of files tracks where
the most engineering time went.

- **Get an account through Tutorial Island reliably** is the single most-invested
  area: 13 files, 01→10 in stage order, each carrying validated widget IDs and hard-won
  pitfalls (`08_combat.yaml`, `10_prayer_magic.yaml` even pre-adopt `mcp_tool:` steps
  and `await_condition: "dialogue"`). `ROUTINE_STRATEGY_2026-07-17.md` calls this "the
  best-documented code in the repo," and `TUTORIAL_TEST_DEFECTS_2026-07-17.md` shows an
  active acceptance test being run against it *today*. Direction: **finish tutorial
  automation first** — it's the gate to everything else.
- **Early F2P novice quests for quest points / unlocks**: all 5 quests are the classic
  low-req starters — `cooks_assistant`, `sheep_shearer`, `restless_ghost`, `imp_catcher`,
  `romeo_and_juliet` — every one `difficulty: novice`, requirements "None (F2P)". This is
  a deliberate "clear the free QP starters" set.
- **Skill grinds that scale from a fresh account to mid-level money**: woodcutting/fishing/
  cooking/mining at Lumbridge/Draynor for low levels (`woodcutting_lumbridge.yaml`,
  `fishing_draynor.yaml`), escalating to **mining-60 gated** Mining-Guild content
  (`mine_iron_ore.yaml`, `superheat_steel_bars.yaml`) and cross-continent Karamja fishing
  (`fishing_karamja_lobster.yaml`). The superheat pair (iron *and* steel) plus the
  Falador power-mining variant show the mining/magic/smithing triangle is the current
  money-maker focus (steel bars called out as ~480gp vs 175gp iron in
  `superheat_steel_bars.yaml:13`).
- **Combat training ladder**: chickens (lvl 1) → cows (lvl 2, with/without hides) → Hill
  Giants (the most elaborate, split into `loot/restock/resupply/travel` — a full
  bank-and-return combat cycle). Direction: melee training from zero toward sustainable
  Hill Giant profit.
- **Death recovery** (`death_escape.yaml`, `gravestone_retrieval.yaml`) exists as a safety
  net — consistent with the memory note that "routines ARE the product" and runs are meant
  to be long and unattended.

Net: the user is building an **unattended F2P leveling/money bot library**, currently
bottlenecked on getting tutorial + early quests fully hands-off so the skill/combat grind
loops can run for hours without a driver.

---

## 3. Gap analysis

**Quests — the biggest content gap.** Only 5 of the ~15 F2P quests are covered, and the
natural next-step F2P quests that these very routines set up are missing:

- **`Rune Mysteries`** — explicitly listed as "easy to create next" in `ROUTINE_CATALOG.md`
  but never written; it's the gateway to Runecrafting and is a standard fresh-account quest.
- **`Doric's Anvil`, `Witch's Potion`, `Goblin Diplomacy`, `The Knight's Sword`,
  `Vampyre Slayer`, `Dwarf Cannon`(members), `Prince Ali Rescue`, `Ernest the Chicken`,
  `Pirate's Treasure`** — none present. Several are trivial and would round out the
  free-QP set the corpus clearly targets.

**Skilling — common methods absent.** `ROUTINE_CATALOG.md` advertises `firemaking_draynor`,
`power_chopping`, `mining_lumbridge` (tin/copper), and money-makers `TELEGRAB_WINE_LOOP`,
`flax_picker`, `air_rune_crafter`, `COLLECT_LUMBRIDGE_TIN_COPPER` — **none of these exist as
YAML**. Notable holes for a fresh account: **no firemaking, no low-level mining (copper/tin
for <15), no smithing-from-bars, no crafting/runecrafting, no thieving, no fletching**. The
skill coverage is strong in the middle (iron/superheat) but thin at the very bottom and top.

**Combat — coverage holes.** No **ranged or magic** training routine anywhere (all melee).
No **Al-Kharid warriors / guards / minotaurs** mid-tier bridge between cows and Hill Giants.
`cow_killer_no_bones.yaml` and `hill_giants.yaml` are **half-finished config sidecars with
no `steps:`** — superseded by the split Hill Giants chain but left in place (validation sweep
§4a judgment item 2 flags them for archive/delete).

**Dangling / half-finished references:**

- `combat/hill_giants_loot.yaml:79` documents that `EAT_FOOD` was removed and `EAT` has no
  HP-threshold arg, so the loop **eats unconditionally every iteration** — a known
  food-waste half-fix awaiting a `CHECK_HP_THRESHOLD`-gated flow (or the proposed
  `only_if: hp_pct:<50` guard).
- `quests/sheep_shearer.yaml:86` uses `skip_if:` which the engine **does not implement**
  (validation sweep judgment item 1) — inert dead key.
- `tutorial_island/08_combat.yaml` and `10_prayer_magic.yaml` use
  `await_condition: "dialogue"` (10 steps total) — an atom the parser **does not support**
  (see §5); it is only a *proposed* atom in `ROUTINE_ENGINE_HARDENING_2026-07-17.md`.
- `tutorial_island/05_cooking_to_quest_guide.yaml` — 5 location entries missing `plane`
  (validation sweep judgment item 3).
- Only **2 of 4 authoring/recording pipelines** produced any output: a single
  `generated/` sample exists; `session_to_routine` and the Java scenario recorder left
  nothing (`ROUTINE_STRATEGY_2026-07-17.md` §2). Not a routine gap per se, but the
  "record→routine" funnel the user intended is barely populated.

---

## 4. Testability ranking — prioritized queue for a 10-hour unattended run

Ranked easiest→hardest by *setup cost* and *robustness when left alone*. The dominant
constraint tonight is **we do not know the current level/location/inventory of the cached
accounts (main / new / newbakshesh)** — so anything gated on a high skill level or a
specific banked loadout is a gamble until verified with `get_game_state(fields=["skills",
"location","inventory"])`. Grind loops (designed to run for hours) beat one-shot quests for
a 10-hour window; quests are one-shot and, per strategy doc, better agent-driven.

**Tier 1 — run these first (lowest requirements, self-recovering loops):**

1. **`combat/chicken_killer_training.yaml`** — self-travels (GOTO coop, step 1) then
   `KILL_LOOP Chicken 200`. Level-1 NPCs, **no food, no banking, no death risk**, only
   needs *any weapon equipped* and a character reasonably near Lumbridge. Lowest-setup
   routine in the corpus. (For continuous overnight running switch to
   `combat/chicken_killer_loop.yaml` — same kill loop wrapped in a 50×100 auto-loop — but
   note its step 1 has **no GOTO**, so position the character at the coop first.)
2. **`skilling/mining_falador_iron.yaml`** — `POWER_MINE` loops *internally* and **drops
   ore** (never fills inventory, never needs a bank), so it's genuinely set-and-forget.
   Needs only a pickaxe + **mining 15** and to start at the Falador Dwarven Mine entrance
   (`3061,3374`). Verify the pickaxe/level before queueing.
3. **`skilling/woodcutting_lumbridge.yaml`** — simple bank-then-chop, needs *any axe*,
   self-travels. Caveat: **no `loop:` block** (single pass), so it won't fill 10 hours
   alone — good as a low-risk validation run, or wrap externally with `--loops`.

**Tier 2 — robust loops but need a verified character loadout:**

4. **`skilling/cooking_lumbridge.yaml`** — self-loops in Lumbridge castle, very low death
   risk, but requires **28 raw fish banked** and its stop condition is a stub (see §5), so
   it runs until food/loops exhaust (benign).
5. **`combat/cow_killer_training.yaml`** — self-travels, `EQUIP_BEST_MELEE` from bank,
   then kills. Needs melee gear banked at Lumbridge; cows can deal chip damage (no food
   management) — moderate unattended risk.
6. **`skilling/fishing_draynor.yaml`** — needs a small net; single pass (no loop block).

**Tier 3 — high character-state requirements we likely don't have:**

7. **`skilling/mine_iron_ore.yaml`** — **mining 60** + start at Falador East bank.
8. **`skilling/superheat_mining_guild.yaml` / `superheat_steel_bars.yaml`** — **mining 60 /
   magic 43 / smithing 15–30**, specific banked runes + equipped fire staff. Highest setup.
9. **`skilling/fishing_karamja_lobster.yaml` / `fishing_karamja_harpoon.yaml`** — level 40/35,
   coins, **cross-continent ferry hops** (many failure points; poor unattended candidate).

**Tier 4 — do not queue unattended tonight:**

- **All 5 quests** — one-shot, dialogue-heavy, multi-area; strategy doc recommends
  agent-driven. If any single one is attempted, `quests/cooks_assistant.yaml` is the most
  self-contained (all in Lumbridge).
- **Hill Giants chain** — Edgeville Dungeon, brass key, combat gear + food, and it **eats
  unconditionally** (`hill_giants_loot.yaml:79`); high wipe risk unattended.
- **Tutorial Island 01–10** — require the exact tutorial stage as start state and are the
  subject of the *live* driver test right now.
- **Stubs/scaffolds** (`cow_killer_no_bones`, `hill_giants`, `common_actions`,
  `widget_reference`, `gravestone_retrieval`, `basic_test_routine` except as a smoke test,
  `generated/…`) — not runnable end-to-end.

**Recommended 10-hour queue:** verify account skills/inventory first, then run
`chicken_killer_training` (or `_loop` once positioned) as the anchor, with
`mining_falador_iron` as the second job if a pickaxe + mining 15 is confirmed, and
`woodcutting_lumbridge`/`cooking_lumbridge` as validation fillers.

---

## 5. Schema / consistency notes

*Known validator false-positives from `ROUTINE_VALIDATION_SWEEP_2026-07-17.md` (the
`Missing 'steps'` fire on reference files §4a, and `Missing 'action'` on `mcp_tool:` steps
§4b) and the fixed `restless_ghost` step 9 are NOT re-reported here.* New/engine-level items:

1. **Two divergent condition vocabularies that don't overlap.** Per-step `await_condition`
   is parsed by `monitoring._parse_condition` via `commands.handle_send_and_await`
   (routine.py:1403-1410, commands.py:353-373) and supports **only** `plane:N`, `has_item:`,
   `no_item:`, `inventory_count:<op>N`, `location:X,Y`, `idle`. Loop `stop_conditions` /
   `exit_conditions` are parsed by a *different* function, `routine.check_stop_condition`
   (routine.py:1485-1545), which supports `inventory_full`, `no_item:`, `has_item:`,
   `no_item_in_bank:`, `<skill>_level:N` — and **not** `plane`/`location`/`inventory_count`/
   `idle`. So `inventory_full` and `<skill>_level:` work only as loop stops, while
   `plane`/`location` work only as awaits; putting one in the other's slot silently
   misbehaves. (Documented as the split table in `ROUTINE_ENGINE_HARDENING_2026-07-17.md:32`.)

2. **`await_condition: "dialogue"` fails fast and the command is never sent.** `_parse_condition`
   has no `dialogue` case; with no `:` and not equal to `idle` it raises `ValueError`
   (monitoring.py:533-536), and `handle_send_and_await` parses the condition *before*
   writing the command (commands.py:364-373) — so the step returns
   `success:false, error:"Invalid condition"` **without ever issuing the action**, then the
   executor's single retry (routine.py:1417-1428) fails identically. Affected steps:
   `tutorial_island/08_combat.yaml:64,97,148` and
   `tutorial_island/10_prayer_magic.yaml:62,85,120,142,170,194,242` (10 steps). `dialogue`
   is only a *proposed* atom (`ROUTINE_ENGINE_HARDENING_2026-07-17.md:279`), so this is a
   live pre-adoption of an unbuilt feature — those two routines will not run clean under
   `run_routine.py` even though they carry `status: VALIDATED` (they were validated
   agent-driven, not through the executor's await path).

3. **`no_item_in_bank:` is a stub that always returns False** (routine.py:1531-1534, bank
   contents aren't in the state file). `skilling/cooking_lumbridge.yaml:246` lists
   `no_item_in_bank:${raw_food}` as a stop condition — it never fires, so the loop only ever
   stops on `cooking_level:99` (line 247, essentially never) or the `--loops` count. Benign
   but the intended "stop when out of fish" guard is dead. (Known: hardening journal line 61.)

4. **`skip_if:` is inert** — `sheep_shearer.yaml:86` uses it, but the engine implements no
   `skip_if`/`only_if`/`on_fail` (grep: zero matches; proposed in hardening §1c). The step
   runs unconditionally. (Known judgment item, sweep §judgment-1.)

5. **`mcp_tool:` step shape is real but only two tools are wired.** `_execute_mcp_tool_step`
   (routine.py:1446-1482) dispatches only `equip_item`, `click_widget`, and
   `find_and_click_widget`; any other `mcp_tool:` returns "Unknown mcp_tool". Current corpus
   uses only `equip_item` (×2) and `key` (×1 — **`mcp_tool: key` is NOT in the dispatch
   list**, so that step would fail with "Unknown mcp_tool: key"). Worth grepping the exact
   file before a run. `args:` for an `mcp_tool` step must be a **dict** — a bare string is
   silently dropped to `{}` (routine.py:1450-1451).

6. **`threshold_percent` / `eating:` / `loot:` config blocks are never read by the engine.**
   They appear in the no-`steps:` sidecars `combat/cow_killer_no_bones.yaml:14` and
   `combat/hill_giants.yaml:23` — dead config for a "configurable loot" feature that was
   never built. The `EAT` command takes no HP arg (hill_giants_loot.yaml:79), so no routine
   actually gates eating on HP today. `hp:`/`hp_pct:` conditions appear **nowhere** in the
   corpus (they're proposed atoms, hardening lines 97-98) — the task's mention of them is
   forward-looking, not a current inconsistency.

7. **Minor structural inconsistencies:**
   - **Step-ID gaps**: `combat/hill_giants_loot.yaml` uses ids `1,3,4,5,6…` (no id 2). IDs
     are labels, not indices, and loops key on `start_step`, so it's cosmetic — but any
     future `goto_step:`/`on_fail: goto:` targeting id 2 would silently mis-resolve.
   - **Filename ordering collisions**: two `01_*` (`01_character_creation`,
     `01_experience_selection`) and two `05_*` (`05_cooking`, `05_cooking_to_quest_guide`)
     under `tutorial_island/` — ambiguous run order for anything that globs the directory.
   - **`skill:` field inconsistency**: some are single (`skill: fishing`), some
     comma-joined (`skill: mining, magic, smithing`) — harmless but not machine-parseable
     uniformly.
   - **`loop:` presence is uneven**: `woodcutting_lumbridge`, `fishing_draynor`,
     `flour_milling`, `cow_killer_training` have **no loop block** (single pass), while peer
     skilling routines loop — a caller expecting "runs for hours" will get one pass from
     these. Relevant to the testability queue above.
