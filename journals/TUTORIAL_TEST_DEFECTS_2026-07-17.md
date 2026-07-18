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
