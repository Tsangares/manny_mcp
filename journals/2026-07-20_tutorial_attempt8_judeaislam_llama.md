# Tutorial attempt #8 — judeaislam/llama — MAINLAND (varp 1000)

**Date:** 2026-07-20 (UTC 02:07–02:45). **Host:** llama, display :8. **Account:** `judeaislam`.
**Result: TUTORIAL ISLAND COMPLETE.** varp-281 = **1000**, arrival at **Lumbridge (3221,3218,0)** at
02:45Z — the exact Driver-#5-confirmed spawn. Second account ever to finish (first: newbakshesh,
2026-07-19, since banned). Account **parked clean** (`mannyctl llama stop judeaislam`; process table
verified zero java/run_routine/watchdog for the account). Screenshot receipt:
`journals/images/2026-07-20_judeaislam_mainland_arrival.png`.

Start state: varp 525 (poll booth VISITED — attempt-#7 addendum probe), HEAD `736c5a8`
(bank-close settle + poll-booth varp gate). Runs this session: `20260720T020701Z` (master chain),
`20260720T021142Z` (s10 from step 3), `20260720T023314Z` (s10 from step 10, then step 26).

## Timeline (UTC, varp receipts)

| time | varp | event |
|---|---|---|
| 02:07 | 525 | WINDOW_GATE all 6 PASS first try; login 20s; chain gates skip s1–8 instantly |
| 02:07:12 | 525 | s09 re-ran (gate 550 > 525); step 2 "Ladder Climb-up" honest abort (see D1) |
| 02:10–02:11 | 525→530 | salvage: GOTO 3124,3124 + door open → Account Guide room |
| 02:11–02:19 | 530 | s10 (from step 3) Account-Guide talks OK, then wedged in walled-box antechamber (3123,3111) — python pair killed (see D2, D3) |
| 02:29–02:31 | 530 | diagnosis: east door tutorial-LOCKED; invisible chatbox modal found via screenshot (see D4) |
| 02:31:15 | 530→531 | re-talk Account Guide, 5-page drain |
| 02:32:06 | 531→532 | flashing Account-Management tab via canvas CLICK_AT 597,477 (Driver-#4 recipe; widget 35913777 does NOT exist on this jar — see D5) |
| 02:32–02:33 | 532→540 | final talk round, 16 pages drained |
| 02:33:10 | 540→550 | east door open + immediate plain through-walk (banking section COMPLETE) |
| 02:33:14 | 550 | run 023314Z launched at s10 step 10 |
| 02:33:42 | 570 | chapel (3125,3106), **Brother Brace dialogue OPEN — pacing-NPC blocker did NOT recur** |
| 02:33:52 | 610 | prayer phase complete (~10s of dialogue driving) |
| 02:34:00 | 620 | chapel exit door (3122,3102) |
| 02:34:35 | 650 | magic area (3140,3087); instructor talk + magic tab credited |
| 02:34–02:37 | 650 | Wind Strike FALSE-MARCH: routine cast failed silently, marched to Home Teleport, blocked by "You cannot teleport" modals; runner died honest (see D6) |
| 02:37:20 | 650→670 | hand-cast: CLICK_WIDGET 14286859 + CLICK_NPC Chicken — first try |
| 02:37:33 | 670→671 | run 023727Z (step 26): instructor talk, mainland menu answered |
| 02:39–02:43 | 671 | mainland/ironman menus: CLICK_CHILD_WIDGET no-op discovered (see D7); screenshot-guided CLICK_AT worked (Yes @263,400; decline @263,441) |
| 02:44:30 | 671→680 | post-decline info pages drained → "use your Home Teleport" |
| 02:45:0x | 680→**1000** | CLICK_WIDGET 35913798 + 14286854 → **Lumbridge (3221,3218)** |

## Defect harvest (the payload)

- **D1 — s09 resume re-runs the whole section, and its ladder interact is ambiguous.**
  `09_banking.yaml`'s chain gate is 550 (section END), so a resume at 525 re-runs from step 1.
  Step 2 `INTERACT_OBJECT Ladder Climb-up` matched 3 GameObjects named "Ladder", clicked the
  nearest at (3116,3126) — not the routine's documented ladder (3123,3128) — menu-verified
  "success", plane never flipped, `await plane:1` timed out, honest abort. Classic
  position-pin-before-ambiguous-name trap (ROUTINE_SCHEMA §i); fix = position-pin GOTO before the
  ladder interacts, or an idempotent-resume sub-gate (varp 525+ ⇒ skip straight to step 10).
- **D2 — plain-GOTO 3-tile slop + blind "Door Open" = wrong-door wander.** s10 step 8's GOTO
  (3129,3124) no-opped at (3128,3123) ("Already at…"); step 9's name-only `Door Open` then opened
  the SOUTH double doors (3121-3122,3119) instead of the east exit (3130,3124), and step 10's
  direct-walk south marched into the documented **walled-box antechamber** (3123,3111) where every
  GOTO fails (routine's own history comment describes this exact trap at these exact tiles).
- **D3 — the antechamber wedge loops forever.** run_routine retried the failing GOTO every ~60s
  with no escalation; supervisor applied the stall rule (killed python pair by pid, client kept).
- **D4 — chatbox modals are invisible AND click-eating (extends DEFECT-31).** "I can't reach
  that!" renders in chatbox group 162 children 39/40 — `dialogue.open:false` (DEFECT-31's fix
  covers groups 229/193/11, not 162) — and while queued, ALL other clicks (tab, door) register as
  menu "Cancel". Behind it a second queued modal held the actual truth: *"You need to talk to the
  Account Guide before you are allowed to proceed through this door."* (that one DID export as
  mesbox once the first was drained). Add group-162 message+continue to the modal-aware export.
- **D5 — Account-Management tab widget id 35913777 is STALE.** The widget does not exist on this
  jar (child gap …775→779 in a full scan); `CLICK_WIDGET 35913777` succeeds as a silent no-op —
  this alone stalled varp at 530 and kept the east door locked. The tutorial's flashing tab stone
  is only reachable by canvas click — Driver #4's (597,477) recipe worked, log-verified as menu
  option "Account Management". Needs a durable fix (resolve the flashing widget id live, or a
  TabOpen extension).
- **D6 — section 10 has ZERO varp gates → false-march class recurs.** The Wind Strike cast failed
  silently (varp stuck 650); steps 26–32 marched on and clicked Home Teleport into "You cannot
  teleport from Tutorial Island just yet!" modals until the runner died on step 32's honest
  timeout. Same class 736c5a8 just fixed in s09. Fix: wiki-varp WAIT gates after each s10 phase
  (540/550/560/570/600/610/620/630/650/670/680/1000 are all documented).
- **D7 — CLICK_CHILD_WIDGET 14352385 no longer registers in-game (regression vs newbakshesh).**
  Reported success; screen menu unchanged (screenshot receipts). Group-219 scan confirmed children
  [0]=title, [1]="Yes.", [2]="No." — the encoded index is right, the click doesn't land. Number-key
  (`KEY_PRESS 1`) also no-oped. What worked: screenshot-measured raw `CLICK_AT` on the option text
  (263,400 / 263,441). Java-side investigation needed (dynamic-child bounds? widget click path?).
- **Benign noted:** boot-time NPE crash ledger event fired again at STARTING (this time
  "Cannot read field am because xz.ch is null" — same boot-noise pattern as the known
  WidgetInspectorTool NPE); state stayed fresh, ignored per doctrine, correctly.

## What the fix (736c5a8) actually bought
The poll-booth WAIT gate never had to fire — varp was already 525 — but the honest-gate design
did exactly its job upstream: every failure this session **stopped at the real fault** (ladder
abort, teleport-block death) instead of cascading. The remaining sections falsified the "booth
steps are idempotent-skippable" assumption in one specific way: the chain-level gate (550) is too
coarse for intra-section resume. Section-level varp sub-gates are the general fix.

## Supervisor method notes
- Inline foreground polling held (30-45s cadence); one lapse into turn-ending wait was corrected
  by the coordinator — bounded foreground until-loops inside the turn are the workable shape.
- Screenshot-on-confusion (X11 `import` on :8) was decisive twice: found the invisible modal
  (D4) and the on-screen mainland menu (D7). Cheap, fast, canonical-transport-safe.
- All manual driving used `mannyctl llama cmd` / on-host transport scripts (rid-correlated,
  one driver at a time — python pair verified dead before every hand-drive block).
- Final-leg dialogue drains printed every page + varp (receipts in transcript); the two menu
  answers used the routine's own encoded choices (mainland Yes; ironman decline), only the click
  MECHANISM was substituted after the encoded one proved broken.

## Open items
1. File/fix D5 (stale tab widget) and D7 (CLICK_CHILD_WIDGET regression) — both Java-side.
2. Extend DEFECT-31 export to chatbox group-162 modals (D4).
3. Add varp WAIT gates through s10 (D6) + position-pin the s09 ladder (D1) + door-crossing
   discipline for s10 steps 8-9 (D2) — YAML, deployable next window.
4. judeaislam parked at Lumbridge spawn, clean. NO mainland activity started (per protocol).
