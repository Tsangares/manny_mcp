# Tutorial Island Test Run — Defect Log (2026-07-17)

Run context: agent-first drive of account `new` (GrimmsFairly) on jar `5bd303e` (Wave 5 Java +
Wave 6a), Xvfb :2. Driver #1 relaunched fresh post-crash ~20:12, terminated ~22:0x by session
limit RIGHT AFTER root-causing DEFECT-1 (its write-up was lost with the transcript; root cause
re-derived from /tmp/runelite.log by orchestrator). This file is the durable defect log —
driver agents APPEND here as they find defects.

---

## DEFECT-1 (CONFIRMED, root-caused): INTERACT_OBJECT dies off-client-thread in camera orient

**Severity:** HIGH — breaks every INTERACT_OBJECT on TileObjects that triggers camera
orientation (doors, ranges, etc.). 5 occurrences in /tmp/runelite.log (first 20:13:54 PDT).

**Symptom:** `INTERACT_OBJECT Door Open` → command fails with
`java.lang.IllegalStateException: must be called on client thread`.

**Stack (deployed jar 5bd303e):**
```
at du.getWorldLocation(du.java:36862)
at manny.utility.CameraSystem.getYawToPoint(CameraSystem.java:1064)
at manny.utility.CameraSystem.pointCameraAt(CameraSystem.java:1141)
at manny.utility.InteractionSystem.clickTileObjectSafe(InteractionSystem.java:766)
at manny.utility.InteractionSystem.interactWithGameObject(InteractionSystem.java:379)
at manny.utility.InteractionSystem.interactWithGameObject(InteractionSystem.java:550)
at manny.utility.commands.InteractObjectCommand.executeCommand(InteractObjectCommand.java:45)
... executed on [manny-background-N] thread pool
```

**Root cause:** `CameraSystem.getYawToPoint` calls `TileObject.getWorldLocation()` (a
client-thread-only RuneLite API) directly on the manny-background executor. Log shows
"[INTERACT-TILEOBJECT] Orienting camera toward 'Door'" immediately before each throw.
Likely a Wave 5 (7a651c8) latch→direct conversion or Wave 6a call-context change — the
camera-orient path used to run under a client-thread wrap. Fix direction: capture the
target's WorldPoint on the client thread (ClientThreadHelper.readFromClient) before/inside
pointCameraAt, or take a pre-fetched WorldPoint parameter instead of the live TileObject.

**Driver workaround (validated):** route THROUGH doors with GOTO to a tile on the far side —
pathfinding opens the door implicitly; avoids the broken camera-orient path entirely.

**Status:** fix in progress compile-only (deployment freeze); deploy with the Wave 6 relaunch.

---

## Progress notes (driver #1, salvaged)

- Character creator + early guide dialogue: PASSED (routines used as map).
- Gielinor Guide dialogue, options/settings step: PASSED.
- Survival section: fishing net obtained + dialogue continuations handled (one stale-instruction
  wrinkle worked through).
- Skills tab open + Survival Expert talk: PASSED.
- Cooking-range building (chef section): DEFECT-1 struck on the building door; driver was
  navigating via walk-through-door workaround (GOTO 3072 3094 0) when terminated.
- Driver #1's final claim before termination: found DEFECT-1 root cause; was about to "stamp
  validated routines" — no routine YAML edits were made (git clean at termination).

---

## Driver #2 resume log (23:12 PT, post session-limit)

- Client had been DISCONNECTED to the red login screen during the ~70min idle gap.
  Recovery: CLICK_AT 383 301 dismissed the "You were disconnected" Ok dialog (LOGIN command
  alone did NOT — its click coords miss that dialog; note for LoginHandlers: no disconnect-Ok
  handling), then LOGIN clicked Play Now → logged in, camera setup ran (~20s).
- NEW FINDING: chef section had COMPLETED before the disconnect ("Moving on — Well done!
  You've baked your first loaf of bread" instruction showing; bread visible in inventory).
  Driver #1's door workaround (GOTO through) + chef dialogue + dough + range all PASSED.
- Resuming at: exit chef building via next door → emotes/run step → Quest Guide.

## Driver #2 checkpoint (~23:30 PT) — cooking exit → Quest Guide

**Sections PASSED since resume:** cooking exit door opened + exited; run-orb step (Toggle Run
clicked; "Fancy a run?" instruction persists by design until next section); navigation
cooking→Quest Guide via routine waypoints (3072,3100 → 3072,3110 → ~3080,3120); Quest Guide
building door opened + entered (3086,3125); Quest Guide first dialogue completed via
INTERACT_NPC Quest_Guide Talk-to + CLICK_CONTINUE xN. INTERACT_NPC and dialogue commands work
fine on this jar — only TileObject interaction is broken.

**Validated DOOR METHOD (replaces INTERACT_OBJECT until DEFECT-1 fix deploys):**
approach to adjacent tile (GOTO) → hover-sweep MOUSE_MOVE over candidate pixels reading
top-left action text until "Open Door" (door renders ~17px/tile from viewport center ~(273,168),
window offset +804,+496 on :2) → MOUSE_CLICK left → GOTO through. Applied twice successfully
(cooking exit 3072,3090; quest guide 3086,3126).

**NEW DEFECTS:**
- DEFECT-2: CLICK_AT coordinate space mismatch vs MOUSE_MOVE. CLICK_AT 248 168 dispatched
  "Walk here" while MOUSE_MOVE 248 168 hover showed "Open Door" (and MOUSE_MOVE+MOUSE_CLICK
  left dispatched "Open"). Menu-debug log shows canvas=765x503 vs 796x504 window — CLICK_AT
  appears to evaluate at unstretched coords. HIGH for click_widget/CLICK_AT users in stretched
  mode; MOUSE_MOVE+MOUSE_CLICK pair is the reliable primitive.
- DEFECT-3: SCAN_TILEOBJECTS Door → same IllegalStateException "must be called on client
  thread" (DEFECT-1 class; another off-thread TileObject read in the scan path).
- DEFECT-4: LIST_OBJECTS omits WallObjects entirely — doors invisible to it (39-148 objects
  returned, zero doors at distance 1). QUERY_TRANSITIONS is the correct discovery tool
  (works, client-thread-safe, gives state+actions).
- DEFECT-5 (minor): QUERY_TRANSITIONS kept reporting door state 'closed' even after the door
  was opened and walked through (state lag or wrong open/closed detection); also a radius-3
  call returned a malformed result (doors=None). Don't trust `state` for gating; verify by
  walking.
- DEFECT-1 addendum: fails even at distance 1 with door fully visible top-down — camera
  orient is unconditional in clickTileObjectSafe.

**Routine repair state:** 05_cooking_to_quest_guide.yaml is directionally correct (waypoints
validated) but steps 2/7 (INTERACT_OBJECT door Open) unusable until DEFECT-1 fix deploys —
will annotate rather than rewrite (fix is queued). No YAML edits committed yet.

**Next:** quest journal tab (CLICK_WIDGET 35913794 — may hit DEFECT-2; fallback hover/click
the flashing tab), second Quest Guide talk, ladder down to mining (3088,3119).

## Driver #2 — Quest Guide section PASSED (~23:35 PT)

Quest journal tab (CLICK_WIDGET 35913794 — widget clicks work fine), second guide talk,
all continues, ladder Climb-down via hover-sweep method at (295,262) → underground
(3088,9520). NOTE: dialogue state in /tmp/manny_new_state.json intermittently reports
open:false while a "Click here to continue" is still on screen (state lag) — screenshot
verify before assuming dialogue done (defect-6, minor). 06 routine section: dialogue/widget
steps validated as-is; both INTERACT_OBJECT steps (door, ladder) need the DEFECT-1 fix or
hover-sweep fallback.

## Driver #2 — Mining & Smithing section PASSED (~23:50 PT)

Full section via hover-sweep primitive (all TileObject interactions): instructor talks +
pickaxe/hammer handouts (INTERACT_NPC + CLICK_CONTINUE, solid), Mine Tin rocks (205,170),
Mine Copper rocks (415,220), Use Furnace (155,268) → Bronze bar, Smith Anvil (326,253) →
smithing menu → Dagger widget click (45,75) → Bronze dagger. NOTE: this tutorial variant
does NOT require Prospect (07 routine steps for prospecting are dead — instruction goes
straight to "try mining some tin"); routine's estimated object coords all confirmed ±1 tile.
07 routine: INTERACT_NPC/dialogue steps validated; INTERACT_OBJECT steps blocked by DEFECT-1
same as before. Screen-position math validated: screen = (273+dx*17, 168-dy*17) from player,
window offset (+804,+496), at default post-login zoom (zoomed-out-5 changes scale ~10px/tile
— re-derive if GOTO zoomed).

Next: combat section (gate → combat instructor, equip dagger, kill rats).

- DEFECT-7: GOTO arrival tolerance masks unreachable targets. At (3105,9511) with Combat
  Instructor at ~(3104,9508) behind the rat-cage fence, GOTO 3104 9509 returns success
  "Already at - distance: 2 tiles" WITHOUT moving; INTERACT_NPC then fails "I can't reach
  that!" x3. Tolerance should be 0-1 for tutorial-precision moves, or GOTO needs an
  exact:true arg. Workaround: GOTO to a farther tile (>tolerance) to force real pathing.

## Driver #2 checkpoint (~00:15 PT) — COMBAT SECTION, mid-struggle

**Done:** instructor talks 1-2 (dagger auto-given earlier + sword/shield handed over),
equipment tab + equip-stats panel + dagger equip (via panel), sword+shield equipped via
inventory clicks after re-opening backpack tab (equip switches panel back to worn view —
must re-click backpack tab between equips), combat-options tab opened, rat-cage gate opened
(hover-sweep at 259,161), Giant rat KILLED (melee) — "Well done, you've made your first kill!"

**Current blocker:** post-kill return to Combat Instructor. Player parked at (3105,9511),
instructor ~(3104,9508)ish, ~3-10 tiles S depending on his wander. Tried: INTERACT_NPC x5 →
"I can't reach that!" x4; GOTO 3104 9509 (tolerance no-op, DEFECT-7), GOTO 3103/3104/3106 9506
→ pathfail (A* refuses south), minimap click south (no move — was blocked by modal at the time).
KEY FINDINGS: (a) the "I can't reach that!" chat message is MODAL and blocks ALL movement until
dismissed; CLICK_CONTINUE **fails** on it (unknown widget group — DEFECT-8); KEY_PRESS space
dismisses it. Several "failed" GOTOs were actually modal-blocked, muddying diagnosis.
(b) INTERACT_NPC computed the instructor's click rect at canvas (177,349) — BELOW the 512x334
viewport (offset 4,4) — clicked into the chatbox → menu shows only Cancel → fail. INTERACT_NPC
has no camera-rotate/pitch recovery for off-viewport NPCs (DEFECT-9). Viewport is 512x334@4,4
(fixed-mode classic), NOT full window width — hover math should center on (260,171).
(c) There appears to be a wall/cliff between the (3105,9511) pocket and the instructor; correct
route unknown, tutorial minimap arrow (red triangle) points NW of player.

**Next attempt:** click minimap at the red tutorial arrow (~641,80 window coords) to let native
pathing route us; then INTERACT_NPC once in viewport range. Then: ranged rat kill → banking.

## Driver #2 — COMBAT SECTION PASSED (~00:40 PT)

Resolution of the pathing saga: the (3105,9511) pocket + rat pen are ONE enclosure; exit is
the double gate on the x=3111 N-S fence. "Open Gate" hotspot found at (282,110-134) after
walking to (3109,9515) — earlier sweeps missed because (a) INTERACT_NPC's retry zoom-ins
changed px/tile so my offsets were stale, (b) gate WallObject models render on tile EDGES,
not centers. CAMERA_POINT_AT x y z works (needs all 3 args) and is useful for re-centering.
Then: GOTO 3106 9505 pathed out+south+west (reported "failed" but moved — GOTO failure
reporting unreliable when target tile occupied, DEFECT-10 minor), instructor dialogue OK,
Shortbow + 50 Bronze arrows received and equipped (backpack-tab reclick between equips),
INTERACT_NPC Giant_rat Attack from (3104,9509) → ranged kill → "Moving on: click the
indicated ladder."

Combat section retro: the ONLY reliable primitives all section were INTERACT_NPC (when NPC
in-viewport + reachable), CLICK_CONTINUE/KEY_PRESS space, MOUSE_MOVE+MOUSE_CLICK, and
QUERY_TRANSITIONS. GOTO tolerance (DEFECT-7) + modal blocking (DEFECT-8) compounded into a
40-minute loop — priority fix order for tutorial driving: DEFECT-8 (CLICK_CONTINUE on
plain-message modals) > DEFECT-7 (GOTO exact mode) > DEFECT-1 (TileObject client-thread).

Next: exit ladder (~3111,9526) → banking section (09).

## Driver #3 (new jar 2fcb602) — started ~01:24 PT, killed ~01:30, re-dispatched as Driver #4

Ladder climbed, player at (3124,3125) — tutorial bank area (section 09). Confirmed on the NEW
jar: INTERACT_OBJECT Door Open succeeded (DEFECT-1 fix holds in the interact path).

**NEW FINDING — DEFECT-3 confirmed NOT covered by the DEFECT-1 fix.** SCAN_TILEOBJECTS still
throws off-thread on jar 2fcb602 (2 repros, 01:26:17 + 01:26:28 PT):

```
java.lang.IllegalStateException: must be called on client thread
  at du.getWorldLocation(du.java:36862)
  at ...utility.commands.ScanTileObjectsCommand.executeCommand(ScanTileObjectsCommand.java:119)
  at ...utility.commands.CommandBase.execute(CommandBase.java:138)
  at ...PlayerHelpers$CommandProcessor.executeCommand(PlayerHelpers.java:7752)   [manny-background]
```

Note the GameEngine find itself logs on [Client] thread and succeeds ("Found 1 TileObjects
matching 'Poll booth'"); the crash is the FOLLOW-UP `getWorldLocation()` on the returned
TileObject at ScanTileObjectsCommand.java:119, executed on manny-background. Same class of bug
as DEFECT-1 but in the scan command, not CameraSystem. Fix (post-freeze queue): wrap the
result-processing read in ClientThreadHelper, or capture locations inside the client-thread
scan closure before returning.

Driver workaround: skip SCAN_TILEOBJECTS entirely; QUERY_TRANSITIONS for doors/stairs,
LIST_OBJECTS/state file otherwise. (INTERACT_OBJECT's own lookup path is fine.)

## Driver #4 (new jar 2fcb602) — BANK + ACCOUNT SECTIONS PASSED (~01:55 PT)

Route: Bank booth used (bank opened, 25gp) → poll credit auto → east door (3125,3124) →
Account Guide talks (2 rounds, ~12 CLICK_CONTINUEs) → Account Management tab via flashing
icon click (canvas ~(597,477)) → east exit door (3130,3124). Next: path to chapel, Brother Brace.

**Defect re-tests on new jar:**
- DEFECT-7 WORSE than documented: GOTO tolerance no-ops at distance 2 AND 3 ("Already at
  (x,y) - distance: 3 tiles" without moving). Must target ≥4 tiles away to force movement.
- DEFECT-8 confirmed: "I can't reach that!" modals dismissed by KEY_PRESS space (2 instances).
  NOTE: the persistent tutorial INSTRUCTION panel looks similar but does NOT block movement
  and is NOT dismissible — don't confuse them (space no-ops harmlessly).
- DEFECT-2 quantified: MOUSE_MOVE/CLICK use canvas coords (765x503); screenshots are the
  stretched window (796x504). window_x = canvas_x * 796/765 (~+4%): a click aimed from
  screenshot pixels lands ~25px east at x≈630 (minimap!). Convert or use cursor-dot feedback.
- **NEW DEFECT-11**: INTERACT_OBJECT has no action-aware candidate filtering. With an OPEN
  door at d=2 and the target CLOSED door at d=3, `INTERACT_OBJECT Door Open` locks onto the
  open one (menu has no 'Open') and fails 3 attempts. Blocked bank re-entry ×3. Fix: filter
  candidates by requested action in menu, or add coordinate-targeted variant.
- **NEW DEFECT-12 (J2 REGRESSION)**: TILE command NPEs — `tileMarkerManager` null in
  TileCommand.executeCommand:60. The J2-2/J2-3 TileMarkerManager ctor change broke command
  wiring. Post-freeze fix required.
- **NEW: CAMERA_STABILIZE crashes off-thread** — getVisibleTiles (CameraSystem:674) via
  logViewportDiagnostics via stabilizeCamera:2197: `must be called on client thread`. This is
  the flagged-but-unfixed DEFECT-1 audit site, now confirmed live. (Partial effect applied:
  zoom happens, then diagnostics crash → command reports failed.)
- Doors AUTO-CLOSE behind you (north bank door shut itself); native walk-clicks won't path
  through closed doors → "stuck" GOTOs. Always QUERY_TRANSITIONS to re-check door state.
- GOTO zooms out 5 scrolls every call (GotoCommand PATHFINDING_ZOOM_OUT_SCROLLS=5) — after a
  few GOTOs the camera is fully zoomed out and all px/tile math breaks. CAMERA_STABILIZE
  400 NORMAL partially restores (zoom applies despite the crash above).

**WINNING PATTERN for tutorial driving** (worked 4/4 since adopted): screenshot → zoom crop
around the yellow arrow → MOUSE_MOVE to candidate → re-screenshot 400x30 strip at (0,0) →
read hover tooltip text → MOUSE_CLICK only when tooltip names the right verb+target. The
white dot in screenshots = synthetic cursor position (good feedback). Native click auto-walk
handles doors/pathing that GOTO/NAV-DIRECT cannot.

## Driver #4 — CHAPEL/PRAYER SECTION PASSED (~02:00 PT)

GOTO 3128 3110 crossed 13 tiles of outdoor path fine (reported "failed" at 1-off — DEFECT-10
again; treat GOTO result as advisory, verify via state file). Brother Brace talks ×2 with
TAB_OPEN prayer between (TAB_OPEN works for standard tabs; account_management is NOT in
TabOpenCommand's list — clicked the flashing icon manually via canvas coords instead).
Friends-list steps apparently auto-credited during dialogue continues. Next: chapel exit door
→ path → Magic Instructor (final).
