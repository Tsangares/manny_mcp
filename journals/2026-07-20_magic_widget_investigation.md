# Why the "magic book widgets are different" — Tutorial Island spellbook/tab widget investigation

**Date:** 2026-07-20
**Trigger:** user report — *"the chicken and the magic button doesn't work normally, idk why the
magic book widgets are different — I would like you to figure that out"* (recorded in
`journals/2026-07-20_user_domain_answers.md` item 4).
**Type:** source archaeology + live-receipt synthesis. Read-only except one small, source-proven
Java fix (§7). No live run (jars in flight).

---

## TL;DR — the plain answer

The magic-book widgets are **not** a special Tutorial-Island interface. Tutorial Island uses the
**same** standard spellbook (widget group **218 = `MAGIC_SPELLBOOK`**) and the **same** tab stone
buttons as the mainland — proven from RuneLite source. They *look* "different" to us because our
**tooling hard-codes widget IDs that are frozen snapshots of a moving target**, and those snapshots
have drifted out of sync with the live client in three independent ways:

1. **The spell IDs are stale.** `SpellWidgetHelper`'s table maps `wind_strike → 14286856`, but
   `14286856` is group 218 **child 8 = `TELEPORT_MINIGAME_ANCIENT`**, not Wind Strike. The live
   Wind Strike is group 218 **child 11 = `14286859`**. The whole strike-spell block in our table is
   shifted ~one spell-slot too low (a 2026-01 capture that game updates invalidated). So
   `CAST_SPELL_NPC Wind_Strike` looks up a teleport button and fails.
2. **The "magic button" (magic tab) ID is layout-mode-specific.** The magic tab is
   `35913798` **only** in the client's **fixed** display mode (group 548 `TOPLEVEL`,
   `STONE6`). In **resizable** mode the same button is a *different ID in a different group*
   (`10551361` group 161, or `10747962` group 164) and group 548 is never even built —
   `client.getWidget(548, …)` returns `null`. manny hard-codes `548` in ≥5 places with no
   mode branch, so every tab click there silently returns null off fixed mode.
3. **The Account-Management tab ID `35913777` no longer resolves at all.** It decodes to group 548
   child 49 — which is **not** in the tab-stone block (the stones are children 64–77) and a live
   full-scan shows child 49 is absent (gap 775→779). It's a stale/mis-captured ID that maps to no
   live widget.

On top of the stale IDs, the click primitives **lie about success** — `CLICK_WIDGET`/`CLICK_AT`
report success as long as *something clickable* was there (or merely that the command was
dispatched), never verifying the click had any effect. So a stale ID "false-succeeds" and, with no
ground-truth gate, the routine marches on. That is exactly the Wind-Strike "false-march" of
attempt #8.

---

## 1. The real spellbook widget architecture (RuneLite source)

All widget IDs pack as `packedId = (group << 16) | child`.

Source of truth: `runelite/runelite-api/src/main/java/net/runelite/api/gameval/InterfaceID.java`
(auto-generated from the live game cache) and `.../api/widgets/WidgetInfo.java` /
`WidgetID.java` (legacy aliases).

- **Group 218 = `MAGIC_SPELLBOOK`** (`InterfaceID.java:225`). One **fixed, named STATIC child per
  spell** — `MagicSpellbook.WIND_STRIKE = 0x00da_000b`, `WATER_STRIKE = 0x00da_000e`,
  `EARTH_STRIKE = 0x00da_0011`, `FIRE_STRIKE = 0x00da_0013`, `TELEPORT_HOME_STANDARD = 0x00da_0006`,
  `TELEPORT_MINIGAME_STANDARD = 0x00da_0007`, `TELEPORT_MINIGAME_ANCIENT = 0x00da_0008`, etc.
  The clientscript that repaints the spellbook (`MagicSpellbookRedraw`, script id **2611**,
  `runelite-client/src/main/scripts/MagicSpellbookRedraw.rs2asm`) only `if_sethide` /
  `if_setposition` / `if_setsize`s these pre-existing static components and `cc_create`s decorative
  overlay children (level text, padlocks) on the layer container — **it never re-creates the spell
  buttons**. So a given spell's packed ID is **stable across filter/level state within a game
  revision**; it only moves when Jagex re-indexes the spellbook in a game update.

- **The tab stones live in whichever TOP-LEVEL group is loaded, and there are three:**
  - `TOPLEVEL = 548` — **fixed** mode (`InterfaceID.java:554`; `WidgetID.FIXED_VIEWPORT_GROUP_ID`).
  - `TOPLEVEL_OSRS_STRETCH = 161` — **resizable modern/stretch**.
  - `TOPLEVEL_PRE_EOC = 164` — **resizable classic/bottom-line**.
  `WidgetInfo.java` enumerates the *same logical tabs three times*, once per group. The magic tab
  (`STONE6`) is:
  - fixed `Toplevel.STONE6 = 0x0224_0046` → **548/70 = 35913798**
  - resizable-stretch `ToplevelOsrsStretch.STONE6 = 0x00a1_0041` → **161/65 = 10551361**
  - resizable-classic `ToplevelPreEoc.STONE6 = 0x00a4_003a` → **164/58 = 10747962**
  Both the group *and* the child index differ between modes (fixed STONE0 = child 64, stretch
  STONE0 = child 59, pre-eoc STONE0 = child 52), so you cannot even reuse the child across modes.
  The canonical RuneLite handling is `OverlayOrigin.getComponent()` (`OverlayOrigin.java:82-95`),
  which branches on `client.isResized()` + `client.getTopLevelInterfaceId()` to pick 548/161/164.

- **Tutorial Island is the same interface.** VARP **281 = `VarPlayerID.TUTORIAL`**
  (`VarPlayerID.java:130`). The tutorial hides/locks and *flashes* the same STONE tab components and
  the same group-218 spellbook, keyed off VARP 281 — there is no separate "tutorial spellbook"
  group. The tutorial's own overlay (`InterfaceID.TutorialOverlay`) is a different interface, but
  the spellbook and tabs the player clicks are the ordinary 218 / 548-161-164 components.

### Decoding the four IDs that bit us
| ID our tooling used | group/child | what it *actually* is now (InterfaceID) |
|---|---|---|
| `35913777` (Account-Mgmt tab) | 548 / 49 | **not a tab stone** (stones are children 64–77); no live widget (scan gap 775→779) |
| `35913798` (magic tab) | 548 / 70 | `Toplevel.STONE6` = `FIXED_VIEWPORT_MAGIC_TAB` ✓ (fixed mode only) |
| `35913797` (prayer tab) | 548 / 69 | `Toplevel.STONE5` = `FIXED_VIEWPORT_PRAYER_TAB` ✓ (fixed mode only) |
| `14286856` (our "Wind Strike") | 218 / 8 | `TELEPORT_MINIGAME_ANCIENT` — **wrong**; live Wind Strike is 218/11 = `14286859` |

---

## 2. What actually failed — PROVEN

- **P1 — the strike-spell table is systematically wrong.** manny hard-codes
  `wind_strike=14286856, water_strike=14286859, earth_strike=14286862, fire_strike=14286864`
  (`utility/commands/SpellWidgetHelper.java:30-33`, duplicated verbatim in
  `utility/SpellCombatSupport.java:636-639`). RuneLite's generated constants say
  `WIND_STRIKE=14286859, WATER_STRIKE=14286862, EARTH_STRIKE=14286865, FIRE_STRIKE=14286867`.
  Every entry is ~3 children (one spell-slot) too low; our "wind_strike" is really the ancient
  minigame-teleport button. So `CAST_SPELL_NPC Wind_Strike` resolves a teleport widget and the
  hover-verify fails ("Spell widget 14286856 not found"). The routine's live-verified value
  (`14286859`) and RuneLite's own `MagicSpellbook.WIND_STRIKE` agree. *Receipts:* live cast
  `CLICK_WIDGET 14286859 + CLICK_NPC Chicken` 650→670 first try
  (`2026-07-20_tutorial_attempt8_judeaislam_llama.md:33`); id drift 14286856→14286859 across the
  Jan→Jul jars (`journals/quests/spell_casting_on_npcs_2026-01-20.md:155` vs
  `journals/OVERSEER_HANDOFF.md:92`).

- **P2 — the click primitives false-succeed on effect.** `WidgetClickHelper.clickWidget()` PHASE 3
  (`utility/WidgetClickHelper.java:143-154`) returns `true` whenever the widget merely resolved and
  was clickable — literally *"assume success if we managed to click it"* — and never checks the
  click did anything. `ClickAtCommand` (`utility/commands/ClickAtCommand.java:55`) writes success
  **unconditionally** after dispatching the mouse event. And at the routine layer a bare
  `action: CLICK_WIDGET` step with no `await_condition` counts as success on dispatch (the plugin's
  boolean return isn't surfaced) — the incident note itself says *"CLICK_WIDGET reports 'sent'
  regardless"* (`10_prayer_magic.yaml:48-51`). The honest counter-model already exists:
  `ClickChildWidgetCommand` (git `7f42b54`) re-snapshots after clicking and fails if the widget
  didn't change (`utility/commands/ClickChildWidgetCommand.java:139-164`).

- **P3 — the Wind-Strike "false-march."** Because s10 had **zero VARP gates** past the magic
  instructor, a missed cast (chicken paces; a miss clicks ground and *deselects* the spell) went
  undetected: steps marched on and clicked Home Teleport into repeated *"You cannot teleport from
  Tutorial Island just yet!"* until the runner died on an honest timeout. *Receipt:* attempt #8 D6
  (`2026-07-20_tutorial_attempt8_judeaislam_llama.md:67-71`) + `metrics_first_contact.csv:77`.
  (Already mitigated in the YAML with retry-then-abort VARP gates.)

- **P4 — the Account-Management tab ID `35913777` maps to no live widget.** Decodes to 548/49,
  outside the tab-stone block; a live full scan shows child 49 absent (gap 775→779). `CLICK_WIDGET
  35913777` was a silent no-op that stalled VARP at 530. *Receipt:* attempt #8 D5
  (`...attempt8...:61-66`). Origin: a 2026-01-18 capture
  (`journals/quests/tutorial_island_automation_lessons_2026-01-18.md:76`).

- **P5 — the fixed-vs-resizable landmine is real in code.** The magic/prayer tab IDs the routine
  uses (`35913798`/`35913797`) are the **fixed-mode** STONE constants; manny hard-codes group
  `548` in `utility/UiHelpers.java:36`, `utility/GameEngine.java:7114`,
  `utility/commands/SwitchCombatStyleCommand.java:40`, `utility/InteractionSystem.java:2856`,
  `utility/PlayerHelpers.java:259`, none guarded by `isResized()`. In resizable mode all of these
  return null (proven from `OverlayOrigin.java` + the three `WidgetInfo` alias sets).

## 3. What is HYPOTHESIZED (not proven)

- **The current tutorial client is in fixed mode.** *Inferred*, not receipted: `runelite.gameSize`
  is `765x503` (the exact fixed-mode canvas) and the fixed-mode prayer/magic STONE IDs
  (548/69,70) demonstrably work in-run. No journal states the display mode, so P5 is a **latent**
  landmine, not the proven cause of the account-tab failure. If any account ever runs resizable
  (or a fresh account defaults to it), every hard-coded 548 tab click breaks at once.
- **uiScale is NOT a factor in the widget-click path.** Confirmed *absent* from code: the whole
  plugin click pipeline is logical pixels end to end (`Widget.getBounds()` → `Mouse.click(x,y)` →
  `canvas.dispatchEvent`, `human/Mouse.java:105-131`; no `getScalingFactor`/DPI conversion). The
  "divide by 2" note in `manny_mcp/CLAUDE.md` only applies to **physical screenshot** coordinates
  fed to `CLICK_AT` (e.g. the D7 `CLICK_AT 263,400` dialogue-option workaround) — not to
  widget-ID clicks. So uiScale is a red herring for the magic-tab/spell failures.
- **Exact current child index of the Account-Management stone.** Not receipted; the honest fix
  (action-based live scan) makes it moot.

---

## 4. Why the "magic button" and "chicken" feel different to the user, specifically

- The **magic button** = magic tab stone. It works when hard-coded (fixed mode) but is the single
  most layout-fragile primitive we have: its ID is valid only in one of three display modes and
  only until Jagex re-indexes the top-level interface. The Account-Management sibling tab already
  fell off that cliff (`35913777`).
- The **chicken cast** = `CAST_SPELL_NPC Wind_Strike`, which fails because the spell-ID table
  points at a teleport button, and the manual fallback (`CLICK_WIDGET 14286859 + CLICK_NPC`) can
  physically miss a pacing chicken with no way to notice. Nothing about the chicken/spellbook is
  special — it's a stale hard-coded ID plus a lying success signal.

---

## 5. The HONEST fix

Ordered by leverage. All retire a failure class rather than patch a symptom.

1. **Spell IDs → RuneLite's cache-synced constants (DONE, §7).** Resolve spell widgets from
   `net.runelite.api.gameval.InterfaceID.MagicSpellbook.*` (the generated single source of truth)
   instead of hand-copied literals. Immediately fixes `CAST_SPELL_NPC Wind_Strike` and the whole
   strike block; retires the manual `CLICK_WIDGET 14286859 + CLICK_NPC` workaround in future
   mainland magic routines. **Compile-only, source-proven. Cost: trivial.**
   - *Even more robust (future):* resolve the spell by **name via live scan** — `SCAN_WIDGETS
     "<spell>"` over group 218 already matches on widget `text`/`name`/`actions`
     (`ScanWidgetsCommand.java:443-505`; spell text is `<col=00ff00>Wind Strike</col>`), take the
     first non-hidden `hasListener` hit's live ID. Immune to *any* future re-index.

2. **Tab resolution → mode-aware, or action-scan.** Replace the hard-coded `548` literals with the
   `OverlayOrigin` pattern (branch on `client.isResized()` / `getTopLevelInterfaceId()` → 548/161/164)
   or the `WidgetInfo` `FIXED_/RESIZABLE_` alias trio. For the Tutorial-Island *flashing* tabs
   (Account Management especially), resolve live by action via `mcp_tool: click_widget`
   `{action: "..."}` — which the YAML already does (`10_prayer_magic.yaml:248-286`). **Cost:
   moderate (≈5 files, mechanical) but retires the resizable landmine for every tab.**

3. **Make the click primitives honest.** Give `WidgetClickHelper.clickWidget` PHASE 3 the same
   effect-verification `ClickChildWidgetCommand` already has (re-snapshot; require the widget to
   hide/change or a state delta), and have the routine layer surface the plugin's boolean instead
   of treating dispatch as success. **Cost: moderate + needs live validation** (risk of
   false-negatives on legitimately-inert widgets), so *not* compile-only — deferred.

4. **Ground-truth gates stay.** The VARP-281 WAIT gates now in s10 are the honest backstop that
   converts any residual false-success into an honest abort. Keep the pattern for all mainland
   magic.

## 6. Cost to retire the `CLICK_AT` fallbacks

- **The magic-tab / spell `CLICK_AT`s** are retired by fixes #1 + #2 above (resolve IDs live /
  mode-aware). No screenshot coordinates needed.
- **The D7 dialogue-option `CLICK_AT 263,400 / 263,441`** (mainland/ironman menus, group 219) were
  a workaround for `CLICK_CHILD_WIDGET` reporting success-but-no-op. That command has since been
  **hardened to verify effect** (`ClickChildWidgetCommand.java:139-164`, git `7f42b54`, jar
  `7f42b54`). Once that jar is the live jar, s10 can revert steps 34/36 to the
  resolution-independent `CLICK_CHILD_WIDGET 14352385 <child#>` and drop the uiScale-fragile
  coordinates. That revert is a **YAML-only** change (owned by the s10 editor), gated on the
  hardened jar going live — not on any new Java.

Net: the durable end state is **no hard-coded spell/tab IDs and no raw coordinates** — spells and
flashing tabs resolved live by name/action, persistent tabs resolved mode-aware, dialogue options
via effect-verified `CLICK_CHILD_WIDGET`, everything backstopped by VARP gates.

---

## 7. Java fix applied (small, source-proven, compile-checked)

Pointed the four strike spells at RuneLite's authoritative constants in **both** copies of the
spell table:

- `manny/utility/commands/SpellWidgetHelper.java` (strike block)
- `manny/utility/SpellCombatSupport.java` (duplicate strike block)

```java
case "wind_strike": return net.runelite.api.gameval.InterfaceID.MagicSpellbook.WIND_STRIKE;   // 218/11 = 14286859
case "water_strike": return net.runelite.api.gameval.InterfaceID.MagicSpellbook.WATER_STRIKE; // 218/14 = 14286862
case "earth_strike": return net.runelite.api.gameval.InterfaceID.MagicSpellbook.EARTH_STRIKE; // 218/17 = 14286865
case "fire_strike": return net.runelite.api.gameval.InterfaceID.MagicSpellbook.FIRE_STRIKE;   // 218/19 = 14286867
```

Proof: `InterfaceID.java:8708-8721` (`WIND_STRIKE=0x00da_000b`, …) + the live-verified `14286859`
from attempt #8. Scope deliberately limited to the four strike spells that are *proven* wrong and
*proven* correct against RuneLite's constants — the bolt/blast/wave/teleport entries are left
untouched (not individually re-verified; `home_teleport=14286854` is already correct). No collision
risk (wind no longer aliases the old water value). Compile-check only:
`./gradlew :client:compileJava -x checkstyleMain -x pmdMain` → **BUILD SUCCESSFUL**. No shadowJar,
no jar deployed (live runs in flight; jar queue managed separately). Humanization files untouched.

---

## Key source references
- `runelite/runelite-api/.../gameval/InterfaceID.java` — groups 218/548/161/164, MagicSpellbook + Toplevel/ToplevelOsrsStretch/ToplevelPreEoc STONE constants
- `runelite/runelite-api/.../widgets/WidgetInfo.java`, `WidgetID.java` — fixed/resizable tab aliases
- `runelite/.../ui/overlay/OverlayOrigin.java:82-95` — the canonical mode-aware widget accessor
- `runelite/.../scripts/MagicSpellbookRedraw.rs2asm` (script 2611) — spells are static children
- `manny/utility/WidgetClickHelper.java:143-154`, `commands/ClickAtCommand.java:55` — false-success
- `manny/utility/commands/ClickChildWidgetCommand.java:139-164` — the honest, effect-verifying model
- `manny/utility/commands/SpellWidgetHelper.java`, `utility/SpellCombatSupport.java` — the spell tables (fixed here)
- `manny/utility/commands/ScanWidgetsCommand.java:145-167,443-505` — live action/name scan (honest resolver)
- `manny_mcp/journals/2026-07-20_tutorial_attempt8_judeaislam_llama.md` (D5/D6/D7) + `metrics_first_contact.csv:76-77` — live receipts
