# Refactor Wave 3 + Display Isolation & Thermals — 2026-07-17 (evening)

Continuation of the manny refactor campaign (see `architecture_review_2026-07-17.md` for the
"why" and `REFACTOR_CAMPAIGN_HANDOFF.md` for live status). This entry covers Wave 3b landing,
the decision on the MCP server's future, and moving the game client onto an isolated virtual
display without cooking the laptop.

## Wave 3b: 23 inline handlers → command classes (committed `2f916a9`)

An opus subagent (fanning out to 8 sub-subagents for file creation, single writer on
`PlayerHelpers.java`) migrated 23 "simple" inline command handlers out of the old 212-case
switch into `utility/commands/*Command.java` classes registered in the Wave-3a registry:

- 23 new command classes + 2 shared helpers it factored out on its own initiative:
  `SpellWidgetHelper` (5 spell commands) and `GeWidgetSupport` (7 GE commands).
- 23 switch cases removed; 17 inline methods deleted. 6 inline methods **kept** because
  retained legacy handlers still call them internally (e.g. `handleTeleport` →
  `handleCastSpell`); dispatch still flows through the new classes, so behavior is identical
  on both paths. These duplicates evaporate in Wave 4 when the callers migrate.
- Build gate caught exactly one compile error: `mouse.move(new Point(x,y))` — Mouse has
  `move(int,int)` and `move(net.runelite.api.Point)` but not `move(java.awt.Point)`. One-line fix.

Two bonus fixes while gating live:

1. **DUMP_COLLISION crashed with "must be called on client thread"** — `player.getWorldLocation()`
   called from the background executor. Verified via `git diff` that the bug was copied verbatim
   from the old inline handler (bug-for-bug preservation working as specified); it was latent all
   along. Fixed by wrapping the read in `helper.readFromClient(...)`. Command now succeeds.
2. **MannyPlugin startup log lied about paths** — hardcoded "monitoring /tmp/manny_command.txt"
   while the real processor watches the account-suffixed `/tmp/manny_new_command.txt`. Now logs
   `MannyPaths.commandFile()` truthfully.

Gates: compileJava + shadowJar green, relaunch, dispatch-checks (GET_GAME_STATE, DUMP_COLLISION,
CLICK_DIALOGUE all correct), smoke 5/5. Committed + pushed as Wave 3b.

**Wave 3c dispatched** (opus, in flight at time of writing): `checkInterrupt()`/`sleepChecked()`
in CommandBase wired to the processor's `shouldInterrupt` at register time; `Mouse.replay()`
swallowed-InterruptedException + hz=0 division fixes; interrupt adoption in ~17 sleep-loop
command classes; migration of the 5 skilling-loop handlers (DROP_ALL, POWER_MINE, MINE_ORE,
FISH_DROP, POWER_CHOP).

## Decision: the MCP server stays, but demoted to optional

Question raised: is the MCP server layer still needed, since last touching it a year ago?
Honest audit: this entire campaign has been driven over **direct file IPC via Bash** — the MCP
server hasn't even been running. For Claude Code sessions the tool layer is pure overhead; the
real value of `manny_mcp` is the Python library (transport.py, credentials, launcher, routines).

**Decision (user-confirmed): keep the MCP server but prune hard in Wave 5** (~105 → 25-40 thin
tools over transport.py), purely as optionality for non-terminal clients (claude.ai phone/desktop).
Direct IPC is the documented primary interface; no session needs to start in `manny_mcp/` anymore.

Also discussed transport design philosophically: the file mailbox looks primitive but fits the
two constraints that matter — the primary client is an LLM with a shell (echo/cat IS the killer
feature), and OSRS runs a 600ms tick so file-latency is irrelevant. Real gaps identified: the
single-slot command file, and no push channel (response.json holds only the latest response).
Proposed fix, staying file-native: an append-only `manny_<acct>_events.jsonl` the plugin writes
command-lifecycle + game events to (tail -f-able). Penciled in for Wave 6.

## Display isolation: game moved to Xvfb :2

Problem: the client on `:0` interferes with the user's real keyboard/mouse (Wayland desktop).
Root cause turned out narrower than expected: manny's `Mouse`/`Keyboard` never touch the OS
pointer — they dispatch **synthetic AWT events straight to the RuneLite canvas**. The
interference was the window *living on the desktop*: focus stealing, plus the user's real
cursor crossing the window feeding real events into the canvas that fight the synthetic hover.

Because input is canvas-dispatch (no `java.awt.Robot`, no XTEST), *any* X server works — so no
gamescope, no container, no second seat. `xorg-server-xvfb 21.1.22-2` was already installed
(the old rig's `display: ":2"` config finally explained):

```
setsid Xvfb :2 -screen 0 1600x1000x24 > /tmp/xvfb2.log 2>&1 < /dev/null &
# then launch RuneLite with DISPLAY=:2
```

Verified end-to-end headless: client boot, **auto-login** (LOGGED_IN in 12s), smoke 5/5,
screenshots via `DISPLAY=:2 import -window root out.png`.

Gotcha of the day (again): `pgrep -af "Xvfb :2" || setsid Xvfb...` never launched Xvfb —
pgrep matched *its own bash wrapper* and short-circuited the `||`. Same family as the earlier
pkill/exit-144 trap. Rule: match with `ps -eo pid,comm,args | awk '$2=="..."'`, never
pgrep/pkill -f, and keep kill/launch in separate tool calls.

## Thermal fix: GPU plugin off, 374% → 46% CPU

On Xvfb there's no GPU, so RuneLite's **GPU plugin** fell back to llvmpipe (Mesa software GL):
`Using device: llvmpipe (LLVM 22.1.5, 256 bits)` — 374% CPU, hot laptop. Fix, in
`~/.runelite/profiles2/default-*.properties` (client stopped first; backup `.bak-gpu`):

```
runelite.gpuplugin=false
fpscontrol.limitFps=true
fpscontrol.maxFps=30
fpscontrol.drawFps=false
```

CPU renderer + 30fps cap → **~46% CPU**, fan off, smoke still 5/5. The classic software
rasterizer is far cheaper than software-emulated OpenGL. Do not re-enable the GPU plugin while
on Xvfb. Escalation path if GPU-accelerated isolation is ever needed: rootful Xwayland window
or VirtualGL's EGL backend.

## Viewing the game (in flight)

Xvfb is invisible by design, so an opus agent is researching viewing options (report to land at
`docs/GAME_VIEWING_OPTIONS.md`): x11vnc/TigerVNC (+ noVNC + `tailscale serve` for
browser/phone viewing over the tailnet — taxi is 100.83.247.91), ffmpeg streaming, and local
nested-X options. It's also building a zero-install stdlib-python MJPEG streamer
(`scripts/mjpeg_viewer.py`, port 8787, ~1.5fps, view-only by construction) as an immediate
solution.

## Open items

- W3c agent (interrupts + 5 skilling loops) → gate: KILL must stop a sleep-loop mid-flight;
  then commit "Wave 3c", Wave 3 done.
- Viewing agent → prototype URL + report; user may then install x11vnc/TigerVNC (needs sudo).
- Waves 4-7 per plan; Wave 4 absorbs the 12 stateful handlers; Wave 5 = MCP pruning per the
  decision above; Wave 6 += events.jsonl (proposed); Wave 7 regenerates both CLAUDE.md.
- GrimmsFairly is parked at the Tutorial Island character creator — the testing phase drives
  from there.
