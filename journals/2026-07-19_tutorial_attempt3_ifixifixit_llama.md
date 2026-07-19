# 2026-07-19 — Tutorial Island attempt #3: `ifixifixit` on llama — the varp fix LANDED (gating works, 1→5 pass clean), but a NEW regression (blanket exact-mode GOTO) wall-traps the player at the cook→Quest-Guide leg BEFORE the ladder ever comes into play

**Author:** live supervisor agent (overseer-tutorial umbrella). **Account:** `ifixifixit`
(fresh, first automation run), display `:5` on llama. **Jar:** shaded sha `fa059e23…`
(sha-pinned; launch would refuse a mismatch — reaching the island proves the pin matched).
**Run:** `20260719T214839Z_ifixifixit`, T0 21:48:39Z, parked ~22:36Z. **Outcome:** mainland NOT
reached; ladder-descent question **UNTESTED** — blocked upstream by a navigation trap. No ban
signals at any point (LOGGED_IN throughout, `terminal_login_failure` false). Final parked
position **(3085,3097,0)**, tutorial.progress **130**.

## Headline verdicts

1. **FIX 1 (varp read) LANDED — this is the win.** `tutorial.progress` read **NONZERO and
   climbed** on-island: 1 → 20 → 30 → 80 → 130 across the first ~5 minutes. In attempt #2 it was
   permanently 0 (wrong `getVarbitValue(281)` namespace). Now `getVarpValue(281)` reads true.
   **Consequence proven live:** the master chain's stage-gate WORKED — Section 5 (cooking) was
   correctly **skipped** with `~ skipping (tutorial_progress 130 >= gate 120, section already
   complete)`. In attempt #2 the stuck-0 made the chain unsafe (would never skip); now it skips
   correctly. The #1 recommended fix from attempt #2 is confirmed end-to-end.

2. **Sections 1–5 PASS first-contact on a fresh account.** Character creation → experience
   selection → Gielinor Guide → Survival Expert (fishing/fire/cook shrimp) → Woodcutting/
   Firemaking → Cooking all cleared autonomously (progress 0→130). This is the clean early-corpus
   first-contact data: **5/5 sections PASS**. The premature "Client crash detected (attempt 1/3)"
   false-fire recurred at boot but was survived (single java process the whole run — kill-then-
   spawn held again).

3. **Section 5b+6 (cooking exit → Quest Guide → ladder) FAILS — but NOT at the ladder, and NOT
   from tutorial desync.** It fails EARLIER, at *navigation* from the cook building to the Quest
   Guide. The player never got within render range of the Quest Guide or the ladder. **Root cause
   (overseer offline diagnosis, accepted): the blanket exact-mode GOTO conversion is a
   regression.** Step-1 `GOTO 3073 3090 exact` (open cook-exit door approach) undershot to
   (3076,3088); in *plain* mode that 3-tile slop would have been accepted and self-corrected
   forward (attempt #1 passed this exact leg on a byte-identical nav jar). Instead `exact`
   hard-failed, the cooking-exit door re-closed, and the player got sealed and drifted into the
   walled pocket around **(3078,3097)** where no automated nav can move it. The client log line
   `A* path goes through uncached/blocked area — failing immediately` is a **RED HERRING**: it is
   `NavigationHelpers.java:2279`, the legacy minimap-follower's generic no-movement bail (zero
   `NAV-SHADOW` lines = stage-2 A* never even ran). Do not chase a collision-cache theory.

## The ladder question is still open — because we never reached the ladder

Attempt #3's headline question ("does the ladder descend on a fresh, correctly-synced account?")
**could not be answered**: the run was blocked ~2 sections upstream by the exact-mode nav trap.
Importantly, `ifixifixit` is **NOT desynced like the parked `punitpun`** — it is merely
**wall-trapped**, and varp gating now works — so once the YAML reverts the cook-exit leg to plain
GOTOs, a resumed/fresh attempt to reach the ladder is cheap.

## Live-supervisor lessons (reusable)

- **BAD: blanket-converting tutorial GOTOs to `exact`.** `exact` hard-fails on a 1–3-tile
  undershoot with no self-correction; plain GOTO's tolerance is a *feature* on approach legs
  (it lets the player settle-and-retry into doorways). Reserve `exact` for tile-critical pins
  (e.g. the ladder seat 12d), NOT for door-approach walks. This regression converted 26 GOTOs;
  the cook-exit approach is one that must be plain.
- **A manual salvage could not free the player.** After stopping the runner (killed the two
  python procs — `run_routine.py` + `watchdog.py` — leaving the single java client alive; NOT
  `pkill java`), I drove with `mannyctl llama cmd`. Plain short GOTOs *do* move the player a few
  tiles at a time, but every route out of the pocket dead-ends: from (3085,3097) every SW nudge
  toward the cook building failed to move the player at all. **The walled pocket is a true nav
  sink under the current jar.**
- **My east detour made recovery harder (documented for the resume plan).** Trying to escape,
  I routed the player EAST through the survival-area **Gate (3089,3092)** to the exterior
  (3090,3092), which put the wall *between* the player and the cook west door. Entry path into
  the final trap: `(3076,3088) → GOTO-north → (3078,3097) pocket → GOTO-east → (3087,3095) →
  open Gate(3089,3092) → (3090,3092) exterior → settles (3085,3097)`. **Resume escape is likely
  to RETRACE this: from (3085,3097)/(3090,3091) go back out the SE gate and around the building
  exterior, rather than trying to punch west through the pocket.**
- **`mannyctl llama cmd <acct> <CMD>` is the manual-drive lever on llama; `stop <acct>` kills the
  client (SIGTERM), `cmd` does not.** `QUERY_TRANSITIONS` / `SCAN_TILEOBJECTS <name>` /
  `QUERY_NPCS` all work via `cmd` for live diagnosis. DISPLAY resolved to `:5` from
  `/proc/<javapid>/environ` (matches hosts.yaml this run, but always resolve it — attempt #2 got
  `:4`).
- **GOTO "timeout"/"Navigation failed" ≠ no movement.** Repeatedly the command returned
  `failed`/`No response within 10000ms` while the player HAD advanced several tiles — always
  re-read state after, never trust the command verdict alone.

## What went RIGHT (do not lose)

- Varp read + gate-skip (verdict #1) — attempt #2's top ask, confirmed live.
- Sections 1–5 first-contact PASS on a fresh account.
- Jar sha gate held (fa059e23…); credentials guard ran clean (default→punitpun, banned guards,
  byte-identical rsync to llama); residual `~/.runelite/credentials.properties` removed pre-launch
  so nothing hijacked the client.
- Single java client all run; account-scoped clean stop; no ban signals, no thermal issues.

## Ranked next fixes

1. **Revert the cook-exit / door-approach GOTOs from `exact` to plain** (fix agent already doing
   this offline). Keep `exact` ONLY on tile-critical pins (ladder 12d/12e).
2. **Resume `ifixifixit` after the revert** — it is wall-trapped, not desynced; varp gating works,
   so re-running the chain (or resuming at 5b) should finally reach the Quest Guide and let us
   answer the ladder-descent question + section-08 DEFECT-29 equip, which remain unmeasured.
3. **Audit the other 25 exact-converted GOTOs** for the same approach-leg hazard before the next
   full run.

## Artifacts

Supervisor scratchpad `attempt3/`: `hv_ledger.json`, `hv_runner.log`, `hv_client_tail.log`
(400 lines incl. the exact-GOTO fail + minimap bail + door re-close), `hv_state.json`
(parked (3085,3097), progress 130), `hv_lochist.json`, `hv_trapped.png` (screenshot of the
wall-trapped player). Metrics rows appended to `journals/metrics_first_contact.csv`
(01–04 = P; 05_cooking = P gate-skipped; 05b_06_quest_guide_ladder = F
exact-mode-regression/nav-trap; 07–10 = NR not-reached-nav-trap).
</content>
</invoke>
