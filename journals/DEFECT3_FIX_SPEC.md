# DEFECT-3 FIX SPEC — SCAN_TILEOBJECTS off-thread crash

**Date:** 2026-07-18
**Status:** SPEC ONLY — deployment freeze in effect, DO NOT apply, DO NOT rebuild.
**Jar in question:** 2fcb602
**Defect class:** Same as DEFECT-1 (CameraSystem) — client-thread-only RuneLite accessor
invoked from `manny-background` thread.

---

## 1. Root cause (CONFIRMED)

`ScanTileObjectsCommand.executeCommand()` (file:
`/home/wil/Desktop/manny/utility/commands/ScanTileObjectsCommand.java`) does its
**lookups** on the client thread — `gameHelpers.findTileObjectsByName()` and
`gameHelpers.findGroundItemsByName()` both wrap their work in
`helper.readFromClient(...)` internally (see `GameEngine.java:2685`+) — and those return fine.

The bug is the **result-building loop that runs on the calling thread** (`manny-background`,
per the stack trace: `PlayerHelpers$CommandProcessor.executeCommand` →
`CommandBase.execute:138` → `ScanTileObjectsCommand.executeCommand:119`). That loop calls
client-thread-only accessors on the live `TileObject` / `Player` handles, throwing
`IllegalStateException: must be called on client thread` at `du.getWorldLocation`.

### Every off-client-thread accessor in the result-building path

**TileObject loop (lines 106–143) — ALL UNSAFE off-thread:**

| Line | Call | Why unsafe |
|------|------|-----------|
| 103  | `client.getLocalPlayer()` | client-thread read (move into lambda) |
| 111  | `obj.getId()` | live `TileObject` accessor |
| 112  | `obj.getWorldLocation().toString()` | `getWorldLocation()` is client-thread-only |
| 113  | `obj.getWorldLocation().getX()` | same |
| 114  | `obj.getWorldLocation().getY()` | same |
| 115  | `obj.getWorldLocation().getPlane()` | same |
| 119  | `player.getWorldLocation()` | **the crash point** (`du.java:36862`) |
| 119  | `.distanceTo(obj.getWorldLocation())` | `distanceTo` is safe WorldPoint math, but the `obj.getWorldLocation()` arg is unsafe |
| 124  | `getObjectComposition(obj)` → internally `obj.getId()` (224), `client.getObjectDefinition(id)` (225), `comp.getImpostorIds()` / `comp.getImpostor()` (226–228) | all client-thread-only |
| 127  | `comp.getActions()` | `ObjectComposition` read, client-thread-only |

`getObjectTypeName(obj)` (line 110 → 199–218) uses only `instanceof` — **SAFE**, no accessor.

**GroundItem loop (lines 146–164) — SAFE, needs NO wrapping:**
`GroundItemInfo` (`GameEngine.java:2659`) holds already-extracted primitives
(`itemId`, `name`, `quantity`, `distance`) plus an immutable `WorldPoint location`.
These were all computed on the client thread inside `findGroundItemsByName`. `WorldPoint`
is an immutable coords value object; `getX()/getY()/getPlane()/toString()` are pure int/string
reads with no client-thread requirement. This loop can safely run on any thread.

**Sort (lines 167–171)** operates on the built `Map` primitives — SAFE.

---

## 2. Chosen fix primitive

**`helper.readFromClientSafe(Supplier<List<Map<String,Object>>>)`** — wrap the entire
results-building block so it executes on the client thread and returns the finished list.

**Why `readFromClientSafe` (not `readFromClient` / `readBatchFromClient` / `executeOnClient`):**

- `readFromClientSafe` (`ClientThreadHelper.java:308`) returns **null on timeout instead of
  throwing**. The command **already has a null-timeout branch** (lines 94–99) that writes a
  clean `"Client thread timeout - game may be loading or busy"` failure. Reusing that path
  keeps messaging consistent and avoids a generic stack-trace failure.
- `readFromClient` (`:105`) throws `RuntimeException` on 5s timeout → caught by
  `CommandBase.execute` → generic `writeFailure(e)`. Works, but less graceful than the
  existing timeout message. Not chosen.
- `readBatchFromClient` (`:187`) is just an alias for `readFromClient` — same throw behavior.
- `executeOnClient` (`:212`) is fire-and-forget void (`clientThread.invoke`) — cannot return
  the built list. Wrong tool.
- `readFromClientWithRetry` — heavier (retries + `Thread.sleep`); unnecessary for a one-shot
  read. Not chosen.

The supplier does pure reads only (builds Maps), satisfying the ClientThreadHelper
"reads only, no blocking" contract.

---

## 3. Accessing the ClientThreadHelper — CORRECTION to the task brief

> The brief states "the enclosing command already has a ClientThreadHelper reference." **This is
> not the case.** `ScanTileObjectsCommand` has only two fields — `client` and `gameHelpers`
> (lines 32–33) — and `CommandBase` exposes **no** ClientThreadHelper. `GameHelpers` holds a
> `ClientThreadHelper helper` but it is **private with no getter**, so it is not reachable via
> `gameHelpers`.

**The command must be given a ClientThreadHelper.** Recommended: add it as a constructor
parameter (mirrors the sibling `SwitchCombatStyleCommand`, which already takes `helper` as its
last ctor arg at `PlayerHelpers.java:7194`). The construction site
(`PlayerHelpers.java:7207`) sits in the `CommandProcessor` scope where a
`ClientThreadHelper helper` field is in scope (`PlayerHelpers.java:6916`), so the value is
available with no extra wiring.

---

## 4. Exact patch (before/after, content-anchored — line numbers will drift)

### Change A — add the field + constructor param
**File:** `utility/commands/ScanTileObjectsCommand.java`

BEFORE (imports block, ~lines 3–7):
```java
import net.runelite.client.plugins.manny.utility.GameEngine.GameHelpers;
import net.runelite.client.plugins.manny.utility.GameEngine.GameHelpers.GroundItemInfo;
import net.runelite.client.plugins.manny.utility.ResponseWriter;
```
AFTER (add one import):
```java
import net.runelite.client.plugins.manny.utility.ClientThreadHelper;
import net.runelite.client.plugins.manny.utility.GameEngine.GameHelpers;
import net.runelite.client.plugins.manny.utility.GameEngine.GameHelpers.GroundItemInfo;
import net.runelite.client.plugins.manny.utility.ResponseWriter;
```

BEFORE (fields + ctor, ~lines 32–42):
```java
	private final Client client;
	private final GameHelpers gameHelpers;

	public ScanTileObjectsCommand(ResponseWriter responseWriter,
	                              Client client,
	                              GameHelpers gameHelpers)
	{
		super("SCAN_TILEOBJECTS", responseWriter);
		this.client = client;
		this.gameHelpers = gameHelpers;
	}
```
AFTER:
```java
	private final Client client;
	private final GameHelpers gameHelpers;
	private final ClientThreadHelper helper;

	public ScanTileObjectsCommand(ResponseWriter responseWriter,
	                              Client client,
	                              GameHelpers gameHelpers,
	                              ClientThreadHelper helper)
	{
		super("SCAN_TILEOBJECTS", responseWriter);
		this.client = client;
		this.gameHelpers = gameHelpers;
		this.helper = helper;
	}
```

### Change B — wrap the results-building loop on the client thread (with isClientThread guard)
**File:** `utility/commands/ScanTileObjectsCommand.java`

BEFORE (lines 101–171 — the whole build+sort block):
```java
		// Build combined results
		List<Map<String, Object>> results = new ArrayList<>();
		Player player = client.getLocalPlayer();

		// Add TileObjects
		for (TileObject obj : foundObjects)
		{
			Map<String, Object> objectInfo = new HashMap<>();
			objectInfo.put("name", objectName);
			objectInfo.put("type", getObjectTypeName(obj));
			objectInfo.put("id", obj.getId());
			objectInfo.put("location", obj.getWorldLocation().toString());
			objectInfo.put("x", obj.getWorldLocation().getX());
			objectInfo.put("y", obj.getWorldLocation().getY());
			objectInfo.put("plane", obj.getWorldLocation().getPlane());

			if (player != null)
			{
				int distance = player.getWorldLocation().distanceTo(obj.getWorldLocation());
				objectInfo.put("distance", distance);
			}

			// Get actions if possible
			ObjectComposition comp = getObjectComposition(obj);
			if (comp != null)
			{
				String[] actions = comp.getActions();
				if (actions != null)
				{
					List<String> validActions = new ArrayList<>();
					for (String action : actions)
					{
						if (action != null && !action.isEmpty())
						{
							validActions.add(action);
						}
					}
					objectInfo.put("actions", validActions);
				}
			}

			results.add(objectInfo);
		}

		// Add GroundItems (TileItems)
		for (GroundItemInfo item : foundItems)
		{
			... (unchanged ground-item loop) ...
			results.add(itemInfo);
		}

		// Sort combined results by distance
		results.sort((a, b) -> { ... });
```

AFTER — extract the build into a client-thread-safe helper call. Replace only the two
`for` loops' data-gathering; the sort stays after (it is thread-safe). The whole builder is
run under `readFromClientSafe`, with an `isClientThread()` fast-path guard mirroring
DEFECT-1's `CameraSystem.readPlayerWorldLocation()` (`CameraSystem.java:292`):

```java
		final String objName = objectName;
		final List<TileObject> objs = foundObjects;
		final List<GroundItemInfo> items = foundItems;

		// Build the result maps on the CLIENT THREAD — obj.getWorldLocation(), obj.getId(),
		// client.getObjectDefinition(), comp.getActions() and player.getWorldLocation() are all
		// client-thread-only (DEFECT-3, same class as DEFECT-1). isClientThread() guard mirrors
		// CameraSystem.readPlayerWorldLocation() to avoid a self-invoke deadlock if this path is
		// ever reached while already on the client thread.
		List<Map<String, Object>> results = client.isClientThread()
			? buildResults(objName, objs, items)
			: helper.readFromClientSafe(() -> buildResults(objName, objs, items));

		// null == client-thread timeout (readFromClientSafe). Reuse the existing timeout branch.
		if (results == null)
		{
			logError("Client thread timeout while building scan results");
			writeFailure("Client thread timeout - game may be loading or busy");
			return false;
		}

		// Sort combined results by distance (thread-safe: operates on built map primitives)
		results.sort((a, b) -> {
			int distA = (Integer) a.getOrDefault("distance", Integer.MAX_VALUE);
			int distB = (Integer) b.getOrDefault("distance", Integer.MAX_VALUE);
			return Integer.compare(distA, distB);
		});
```

And add a new private method holding the (unchanged) body of the two loops, so it can run
either inline (client thread) or inside the supplier:

```java
	/**
	 * Build the combined TileObject + GroundItem result maps. MUST run on the client thread
	 * (calls obj.getWorldLocation(), obj.getId(), client.getObjectDefinition(),
	 * comp.getActions(), player.getWorldLocation()).
	 */
	private List<Map<String, Object>> buildResults(String objectName,
	                                                List<TileObject> foundObjects,
	                                                List<GroundItemInfo> foundItems)
	{
		List<Map<String, Object>> results = new ArrayList<>();
		Player player = client.getLocalPlayer();

		for (TileObject obj : foundObjects)
		{
			// ... EXACT existing TileObject-loop body, lines 108–142, unchanged ...
		}
		for (GroundItemInfo item : foundItems)
		{
			// ... EXACT existing GroundItem-loop body, lines 148–163, unchanged ...
		}
		return results;
	}
```

> Note: the `GroundItemInfo` loop is technically thread-safe on its own (precomputed
> primitives + immutable `WorldPoint`), so it may be left outside the supplier. Keeping it
> inside `buildResults` is harmless and keeps the diff/logic in one place — recommended.

### Change C — pass the helper at the construction site
**File:** `utility/PlayerHelpers.java`, line ~7207

BEFORE:
```java
		this.scanTileObjectsCommand = new ScanTileObjectsCommand(responseWriter, client, gameHelpers);
```
AFTER:
```java
		this.scanTileObjectsCommand = new ScanTileObjectsCommand(responseWriter, client, gameHelpers, helper);
```
(`helper` is the `ClientThreadHelper` field in scope at `PlayerHelpers.java:6916`; the sibling
`SwitchCombatStyleCommand` at line 7194 already receives it the same way.)

---

## 5. Deadlock risk assessment

- **Current reachability:** The command runs on `manny-background`
  (`PlayerHelpers$CommandProcessor.executeCommand`), never on the client thread. So today the
  `readFromClientSafe` branch is always taken and there is **no deadlock risk** in the live path.
- **Why the guard anyway:** `readFromClientSafe` → `readFromClient` uses
  `clientThread.invokeLater(...)` + `latch.await(5s)`. If this code were ever invoked **while
  already on the client thread** (e.g. a future overlay/tick caller), the client thread would
  block in `await` waiting for a task only it can run → guaranteed 5s timeout (null result), a
  soft self-deadlock. The `client.isClientThread()` fast-path (Change B) builds inline in that
  case and skips the hop entirely. This exactly mirrors the established DEFECT-1 fix in
  `CameraSystem.readPlayerWorldLocation()` (`CameraSystem.java:292–303`) and its
  `InteractionSystem` counterpart.
- **No lock inversion:** `buildResults` acquires no monitors and does pure reads, so running it
  on the client thread cannot deadlock against background locks.

---

## 6. Build + smoke validation checklist (run AFTER freeze lifts)

1. **Compile:**
   `mvn compile -pl runelite-client -T 1C -DskipTests` (from runelite root).
2. **Format:** `mvn spotless:apply -pl runelite-client`.
3. **Restart RuneLite** with the test profile:
   `--config=/home/wil/Desktop/runelite/manny_test`.
4. **Positive smoke (multi-result):** log in, stand near scenery, send
   `SCAN_TILEOBJECTS Door 15` (or a locally present object). Expect a success response with
   `count`/`objects`, each entry having `id`, `x`, `y`, `plane`, `distance`, `actions` — and
   **no** `IllegalStateException: must be called on client thread` in
   `~/.runelite/logs/client.log`.
5. **Single-result path:** scan a name with exactly one match → response is the single flat map
   (not wrapped in `count`/`objects`).
6. **GroundItem path:** drop an item, `SCAN_TILEOBJECTS <item> 15` → entry with
   `type: GroundItem`, `quantity`, `actions:[Take]`.
7. **Not-found path:** `SCAN_TILEOBJECTS Nonexistentxyz 15` → clean "not found" failure, no crash.
8. **Log grep:** `grep "must be called on client thread\|SCAN_TILEOBJECTS" ~/.runelite/logs/client.log`
   — the crash string must be absent; only normal `[SCAN_TILEOBJECTS]` info lines present.
9. **Blocking log check:** confirm no new 5s timeout entries for `ScanTileObjectsCommand` in the
   ClientThreadHelper blocking log (`MannyPaths.blockingLog()`), which would indicate the guard
   or supplier misbehaving.

---

## 7. Summary

- Root cause confirmed: result-building loop calls client-thread-only accessors off-thread.
- Fix: wrap the builder in `helper.readFromClientSafe(...)` with an `isClientThread()` guard;
  ground-item loop is already safe; sort stays outside.
- The command has **no** existing ClientThreadHelper — it must be added via constructor param
  and passed from `PlayerHelpers` (Changes A + C). This is the one deviation from the brief.
- Deadlock risk: none in the current background-only path; guard added defensively to match
  DEFECT-1.
