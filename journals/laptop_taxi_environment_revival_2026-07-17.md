# Reviving the Manny Dev Environment on a New Machine (taxi) - Lessons Learned
**Date:** 2026-07-17

## Context

Restored the manny plugin + MCP server from backup onto laptop `taxi` (Arch, GNOME Wayland).
Plugin and MCP repos survived at `~/Desktop/manny` and `~/Desktop/manny_mcp`, but the
RuneLite checkout, `.env`, `~/.manny/credentials.yaml`, and `~/.gradle` did not.
GitHub remotes: `Tsangares/manny` (private), `Tsangares/manny_mcp` (public).

## Root Causes & Fixes (in order hit)

1. **Stale absolute paths from the old machine.** `.mcp.json`, `config.yaml`
   (`session_file`), and the `manny_mcp/manny` symlink all pointed at
   `/home/wil/manny-mcp` (old layout, hyphen, under `$HOME`). New canonical layout is
   `/home/wil/Desktop/manny_mcp` (underscore). Grep for `manny-mcp` after any restore.

2. **Gradle 8.8 cannot run on the system JDK 26.** Arch's default `jdk-openjdk` is too
   new. Fix: install `jdk21-openjdk` and pin per-user, NOT system-wide:
   - `~/.gradle/gradle.properties` → `org.gradle.java.home=/usr/lib/jvm/java-21-openjdk`
   - `config.yaml` → `java_path: /usr/lib/jvm/java-21-openjdk/bin/java`

3. **Plugin needs snakeyaml, upstream runelite-client doesn't ship it.**
   `ScenarioEngine.java` imports `org.yaml.snakeyaml`. Fix in
   `runelite-client/build.gradle.kts`: `implementation("org.yaml:snakeyaml:2.2")`.
   Then RuneLite's **dependency verification** rejects the new artifact — run
   `./gradlew --write-verification-metadata sha256 help` once to register checksums.

4. **One API drift vs current master (1.12.34-SNAPSHOT):** `Client.getMapAngle()` was
   removed. Replacement: `Client.getCameraYawTarget()` (same 0–2047 jau). Only compile
   error in ~200 plugin files.

5. **`world_map.png` must live in classpath resources, not the plugin source dir.**
   `WorldMapData` does `getResourceAsStream("/world_map.png")`. The Gradle build (unlike
   whatever the old setup did) only bundles `src/main/resources`. Fix:
   `cp manny/world_map.png runelite-client/src/main/resources/world_map.png`.
   Symptom if missing: "global pathfinding will not be available" + repeated IOException.

6. **PMD/Checkstyle fail `./gradlew build` on plugin code (794 + 4284 violations).**
   Not a real failure — the shaded jar is still produced. `build_plugin` in core.py
   already excludes them: `-x checkstyleMain -x pmdMain` (plus `-x test -x javadoc
   -x javadocJar`). Use the same flags for manual builds.

## Working Setup (verified)

- RuneLite master cloned at `~/Desktop/runelite`; plugin symlinked:
  `runelite-client/src/main/java/net/runelite/client/plugins/manny -> ~/Desktop/manny`
- Build: `./gradlew build -x test -x javadoc -x javadocJar -x checkstyleMain -x pmdMain`
  → `runelite-client/build/libs/client-*-shaded.jar`
- Launch: `DISPLAY=:0 _JAVA_OPTIONS="-Xmx1536m -XX:MaxMetaspaceSize=192m" java -jar <shaded.jar>`
  → "Manny plugin started!", world map 8712x4912 loaded, 7 locations loaded.
- `display` in config.yaml temporarily `:0` — **gamescope is not installed** on taxi yet
  (`sudo pacman -S gamescope` to restore the `:2`-`:5` multi-display setup).

## Still Missing After Restore

- `.env` (JX_* Jagex session creds) — manual login required until re-provisioned.
- `~/.manny/credentials.yaml` — multi-account store empty.
- Benign startup NPE: `UITools$WidgetInspectorTool` refreshWidgetTree throws while
  logged out (widget tree null). Pre-existing; harmless at login screen.
