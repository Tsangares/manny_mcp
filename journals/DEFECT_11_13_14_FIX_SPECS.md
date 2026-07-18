# Fix Specs — DEFECT-11, DEFECT-13, DEFECT-14

READ-ONLY design pass. No code was edited, nothing rebuilt. These are ready-to-apply
specs so a later batch can apply them fast in one rebuild (alongside the DEFECT-3 fix).

All paths are relative to `/home/wil/Desktop/manny/` (the plugin, `manny_src` symlink).

Constraint honored: **`MannyPlugin.java` is LOCKED.** None of the three fixes edit it.
Anything that would have needed it is called out as a manifest note instead.

Anchor edits by content (the `switch`/comment context), not raw line numbers — line
numbers below are as-observed on 2026-07-18 and will drift.

---

## DEFECT-11 — `TILE` command NPE (`this.tileMarkerManager is null`)

### Root cause (CONFIRMED)

`TileMarkerManager` is a `@Singleton @Slf4j public static class` nested in
`PlayerHelpers` (`utility/PlayerHelpers.java`, class decl ~line 15557). During the J2-2
latch conversion its constructor gained a third `@Inject` param:

```java
@Inject
public TileMarkerManager(Client client, ClientThread clientThread, ClientThreadHelper helper)
{
    ...
    instance = this;   // static singleton handle set ONLY here
    load();
}

public static TileMarkerManager getInstance() { return instance; }   // no lazy init
```

`getInstance()` just returns the static `instance`, which is assigned **only inside the
constructor**. So `instance` is non-null only after Guice has actually constructed the
singleton.

The `CommandProcessor` constructor (`utility/PlayerHelpers.java`, `@Inject` ctor ~line
7114) wires the two capture-at-construction tile commands using `getInstance()`:

- `~7209`: `this.tileClearCommand = new TileClearCommand(responseWriter, TileMarkerManager.getInstance());`
- `~7243`: `this.tileCommand = new TileCommand(responseWriter, TileMarkerManager.getInstance());`

`TileMarkerManager` is **not** a constructor param of `CommandProcessor`, so constructing
`CommandProcessor` does **not** trigger construction of the `TileMarkerManager` singleton.
In `MannyPlugin` the two are independent `@Inject` fields — `CommandProcessor`
(`MannyPlugin.java:225`) is declared *before* `TileMarkerManager` (`MannyPlugin.java:228`),
so Guice injects/constructs `CommandProcessor` first. At that moment the
`TileMarkerManager` singleton has not been built yet → `instance == null` →
`getInstance()` returns `null` → `TileCommand`/`TileClearCommand` capture a null manager
in their final field forever. Every later `TILE`/`TILE_CLEAR` throws
`NullPointerException: this.tileMarkerManager is null`.

(The other tile commands — `TileExportCommand`, `TileListCommand`, `TileClearAllCommand`
— call `getInstance()` at **execute** time, by which point the singleton exists, which is
why only `TILE` / `TILE_CLEAR` are broken.)

### Fix — force the singleton to be constructed before `CommandProcessor`

Make `TileMarkerManager` a declared dependency of the `CommandProcessor` `@Inject`
constructor. Guice fully resolves every constructor argument (constructing the
`@Singleton`, which sets `instance`) **before** invoking the constructor body, so by the
time the wiring lines run the manager is live. Because it is `@Singleton`, the injected
reference is the exact same object `MannyPlugin` and `getInstance()` see — no split-brain.

This touches only `utility/PlayerHelpers.java`. `MannyPlugin` is unaffected (Guice injects
the new constructor arg transparently).

**Change 1 — add the constructor parameter.** In the `CommandProcessor` `@Inject`
constructor parameter list, anchor on the final param and append one:

Before:
```java
			InteractionSystem interactionSystem,
			WidgetClickHelper widgetClickHelper,
			LoginHandlers loginHandlers)
	{
```
After:
```java
			InteractionSystem interactionSystem,
			WidgetClickHelper widgetClickHelper,
			LoginHandlers loginHandlers,
			TileMarkerManager tileMarkerManager)
	{
```
(`TileMarkerManager` resolves unqualified here — it is a sibling nested class of
`CommandProcessor` in `PlayerHelpers`. If the compiler complains about scope, qualify as
`PlayerHelpers.TileMarkerManager tileMarkerManager`.)

**Change 2 — use the injected param at the two wiring sites** (drop `getInstance()`):

Before:
```java
		this.tileClearCommand = new TileClearCommand(responseWriter, TileMarkerManager.getInstance());
```
After:
```java
		this.tileClearCommand = new TileClearCommand(responseWriter, tileMarkerManager);
```

Before:
```java
		this.tileCommand = new TileCommand(responseWriter, TileMarkerManager.getInstance());
```
After:
```java
		this.tileCommand = new TileCommand(responseWriter, tileMarkerManager);
```

No new field is required — both wiring lines are inside the same constructor body, so the
parameter is in scope directly.

### Risk / regression notes

- Very low risk. `TileMarkerManager` is already `@Singleton`, so adding it as a
  constructor dependency cannot create a second instance; it only reorders construction.
- The two `getInstance()` execute-time callers (export/list/clearAll) are unaffected and
  now guaranteed to see the same, earlier-constructed singleton.
- No `MannyPlugin` edit needed. **Manifest note:** none — the fix is fully contained in
  `PlayerHelpers.java`.

### Validation (post-rebuild live gate)

1. `send_command("TILE Copper_rock yellow")` near a mining spot → expect
   `success` + "Marked N tiles", no NPE in `get_logs(grep="TILE")`.
2. `send_command("TILE_LIST")` → returns the group just marked (proves same singleton).
3. `send_command("TILE_CLEAR Copper_rock")` → success, no NPE.

---

## DEFECT-13 — `TELEPORT_HOME` wrong widget (Minigame Teleport, not Home Teleport)

### Root cause (CONFIRMED)

The spell-name → widget map returns `14286855` for `home_teleport`, which is the
**Minigame Teleport** button. The correct standard-spellbook **Lumbridge Home Teleport**
button is `14286854` (group 218 child 6; `14286848 = 218<<16`, so child 6 = `...854`).
The existing `// child 7` comment is also wrong — home teleport is child 6.

The map is **duplicated** in two places:

1. **LIVE path** — `utility/commands/SpellWidgetHelper.java:64`:
   ```java
   case "home_teleport":
   case "lumbridge_home_teleport": return 14286855;  // Standard spellbook home teleport (child 7)
   ```
   This is what `TELEPORT_HOME` actually runs today: `register("TELEPORT_HOME",
   teleportHomeCommand)` → `TeleportHomeCommand.executeCommand()` calls
   `SpellWidgetHelper.getSpellWidgetId("home_teleport")`. `CAST_SPELL` (`CastSpellCommand`)
   uses the same helper, so `CAST_SPELL Home_Teleport` is wrong too.

2. **DEAD duplicate** — `utility/PlayerHelpers.java:9090` (inside the legacy inline
   `getSpellWidgetId(...)` used by the orphaned `handleTeleportHome()` / `handleCastSpell()`
   methods that are no longer registered). Same wrong value, same wrong comment.

### Recommended fix — simple constant correction (NOT spell-driven)

The command is **already** spell-name-driven — it resolves `"home_teleport"` through the
map. The map *value* is simply wrong. So the lowest-risk fix is a one-value correction, no
control-flow change. Making it "more" spell-driven would add risk for zero benefit.

Apply in **both** copies (fix the live one; fix the dead one too so the two maps stay in
sync and a future re-wire can't resurrect the bug):

`utility/commands/SpellWidgetHelper.java` — before:
```java
		case "home_teleport":
		case "lumbridge_home_teleport": return 14286855;  // Standard spellbook home teleport (child 7)
```
after:
```java
		case "home_teleport":
		case "lumbridge_home_teleport": return 14286854;  // Lumbridge Home Teleport (group 218 child 6)
```

`utility/PlayerHelpers.java` (inline `getSpellWidgetId`, ~line 9090) — same before/after
edit (change `14286855` → `14286854` and correct the comment).

### Other nearby hardcoded spell widgets — caveat (do NOT change without verification)

The same maps contain several **colliding** IDs that look suspect but are OUT OF SCOPE for
this fix (they are not what DEFECT-13 reported and were not re-verified with a live widget
inspector):

- `ardougne_teleport` `14286889` == `fire_blast` `14286889`
- `watchtower_teleport` `14286895` == `water_wave` `14286895`
- `teleother_lumbridge` `14286910` == `earth_surge` `14286910`
- `teleother_falador` `14286913` == `fire_surge` `14286913`

Flagging only. Correcting `home_teleport` to `14286854` is the confirmed, isolated change.
If home teleport ever proves to be off-by-one for a systemic reason, re-scan the whole map
with `scan_widgets(group=218)` — but current evidence is a single wrong entry.

### Risk / regression notes

- Trivial risk: one integer literal, name-keyed, no branching change.
- Fixing both copies avoids a latent trap if the inline path is ever re-registered.
- No `MannyPlugin` edit. **Manifest note:** none.

### Validation (post-rebuild live gate)

1. Stand anywhere non-Lumbridge, `send_command("TELEPORT_HOME")`.
2. `get_logs(grep="TELEPORT_HOME")` shows it targeting the Home Teleport spell; screenshot
   the magic tab hover to confirm the cursor is on **Home Teleport**, not Minigame Teleport.
3. After ~10s, `get_game_state(fields=["location"])` shows Lumbridge (~3222,3218,0).

---

## DEFECT-14 — `MOUSE_MOVE` rejects sidebar coordinates ("Invalid coordinates")

### Root cause (PARTIALLY confirmed — see note; the journal's "viewport clamp" is NOT in current source)

Coordinate-space intel (from `manny_mcp/journals/TUTORIAL_TEST_DEFECTS_2026-07-17.md`,
DEFECT-2/-14): **canvas is 765x503**; the **3D game viewport is 512x334 at offset (4,4)**.
The sidebar / tabs / spellbook live to the right of the viewport but well inside the
canvas (e.g. `552,324` → x<765, y<503 → a valid canvas target).

The observed failure string is verbatim `MouseMoveCommand.getFailureMessage()`:
`"Failed to move mouse: Invalid coordinates"`. In `CommandBase.execute()` that message is
emitted **only** when `executeCommand(...)` returns `false`. In the current registered
handler (`utility/commands/MouseMoveCommand.java`) the **only** false path is:

```java
String[] parts = args.split("\\s+");
if (parts.length < 2) { ... return false; }   // <-- the ONLY thing that yields "Invalid coordinates"
int x = Integer.parseInt(parts[0]);
int y = Integer.parseInt(parts[1]);
mouse.movePrecisely(x, y);                      // no bounds check anywhere
return true;
```

Findings:
- **There is NO viewport (512x334) clamp anywhere** — not in `MouseMoveCommand`, not in
  `Mouse.movePrecisely()` / `move()`, not in the movement layer. The journal's
  "bounds check appears limited to the 3D viewport region" is an **inference that does not
  match current source.** So a space-separated in-canvas move (`MOUSE_MOVE 552 324`) would
  currently **succeed**, not fail.
- The reproducible trigger for the exact error string is a **single-token arg** —
  `split("\\s+")` on `"552,324"` (the comma form recorded in the journal) yields one token
  → `parts.length < 2` → the "Invalid coordinates" failure. The MCP `move` tool formats
  `f"MOUSE_MOVE {x} {y}"` (space-separated, `mcptools/tools/commands.py:293`), but a
  hand-typed / comma-formatted coordinate hits this path.
- Secondary gap: with no bounds check, genuinely out-of-window coords (negative, or
  beyond the canvas) are silently accepted and dispatched off-canvas.

So the fix must (a) tolerate comma-or-space separators (kills the actual "Invalid
coordinates" repro), and (b) add a proper **full-canvas** bounds check that allows the
sidebar but rejects genuinely out-of-window coords (closes the silent-accept gap and
guarantees no viewport-only rejection can ever regress in).

### Fix — normalize separators + full-canvas validation

`Mouse` already holds a `public Client client;` (`human/Mouse.java:29`) whose
`getCanvasWidth()/getCanvasHeight()` give the live full-canvas size — reuse it so no
constructor/wiring change is needed. Edit only `utility/commands/MouseMoveCommand.java`.

Before:
```java
	@Override
	protected boolean executeCommand(String args) throws Exception
	{
		String[] parts = args.split("\\s+");
		if (parts.length < 2)
		{
			logError("requires x y coordinates");
			writeFailure("requires x y coordinates");
			return false;
		}

		int x = Integer.parseInt(parts[0]);
		int y = Integer.parseInt(parts[1]);

		logInfo("Moving mouse to ({}, {})", x, y);
		mouse.movePrecisely(x, y);
		return true;
	}
```
After:
```java
	@Override
	protected boolean executeCommand(String args) throws Exception
	{
		// Accept either whitespace- or comma-separated coordinates ("552 324" or "552,324").
		String[] parts = args == null ? new String[0] : args.trim().split("[\\s,]+");
		if (parts.length < 2)
		{
			logError("requires x y coordinates");
			writeFailure("requires x y coordinates");
			return false;
		}

		int x;
		int y;
		try
		{
			x = Integer.parseInt(parts[0]);
			y = Integer.parseInt(parts[1]);
		}
		catch (NumberFormatException e)
		{
			logError("non-numeric coordinates: {}", args);
			writeFailure("Invalid coordinates: " + args);
			return false;
		}

		// Validate against the FULL canvas (765x503-class), NOT the 512x334 game viewport.
		// The sidebar, tabs and spellbook are valid click targets outside the 3D viewport
		// but inside the canvas. Reject only genuinely out-of-window coordinates.
		int canvasW = mouse.client.getCanvasWidth();
		int canvasH = mouse.client.getCanvasHeight();
		if (canvasW <= 0 || canvasH <= 0)
		{
			// Canvas not ready (pre-login); skip the bounds gate rather than false-reject.
			logWarn("canvas size unavailable ({}x{}), skipping bounds check", canvasW, canvasH);
		}
		else if (x < 0 || y < 0 || x >= canvasW || y >= canvasH)
		{
			logError("({}, {}) outside canvas {}x{}", x, y, canvasW, canvasH);
			writeFailure(String.format("Coordinates (%d, %d) outside canvas %dx%d", x, y, canvasW, canvasH));
			return false;
		}

		logInfo("Moving mouse to ({}, {})", x, y);
		mouse.movePrecisely(x, y);
		return true;
	}
```

Notes:
- Uses `mouse.client.getCanvasWidth()/getCanvasHeight()` (both public) — no constructor or
  registry-wiring change, so the `new MouseMoveCommand(responseWriter, mouse)` site
  (`PlayerHelpers.java:7181`) is untouched.
- Bounds are the **live full canvas**, not the hardcoded 512x334 viewport, so `552,324`
  and any sidebar/tab coordinate now pass while negatives / beyond-canvas fail with a clear,
  distinct message.
- If you prefer stricter typing than the public field, an alternative is to add a `Client`
  constructor param and update the one wiring site in the same file's registrar; the
  `mouse.client` route was chosen to keep the change to a single file.

### Risk / regression notes

- Low risk, single file. Separator normalization is backward-compatible (space input still
  splits identically).
- The added bounds check is strictly more permissive than any (nonexistent) viewport clamp
  for legitimate targets, and only rejects off-window coords that would have produced a
  no-op/garbage event anyway.
- Pre-login guard prevents false rejections when `getCanvasWidth()` returns 0.
- No `MannyPlugin` edit. **Manifest note:** none.

### Validation (post-rebuild live gate)

1. `send_command("MOUSE_MOVE 552 324")` (sidebar) → success; screenshot shows cursor over
   the spellbook/tab region, no "Invalid coordinates".
2. `send_command("MOUSE_MOVE 552,324")` (comma form) → also success (separator fix).
3. `send_command("MOUSE_MOVE 5000 5000")` → failure with "outside canvas 765x503"-style
   message (genuine out-of-window still rejected).
4. `send_command("MOUSE_MOVE 250 168")` (in-viewport) → still success (no regression).

---

## Batch assessment

All three are **low-risk and localized**, and safe to batch into one rebuild with the
DEFECT-3 fix:

| Defect | Files touched | MannyPlugin? |
|--------|---------------|--------------|
| 11 | `utility/PlayerHelpers.java` (CommandProcessor ctor: +1 param, 2 wiring lines) | No |
| 13 | `utility/commands/SpellWidgetHelper.java` (+ dead dup in `PlayerHelpers.java`) | No |
| 14 | `utility/commands/MouseMoveCommand.java` (single method) | No |

No overlapping edit regions, no `MannyPlugin.java` changes, no shared-signature churn — they
compose cleanly in a single `build_plugin` + restart.
