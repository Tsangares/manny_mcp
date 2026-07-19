# Ban / Lock Detection at Login — Redesign

Date: 2026-07-19
Status: DESIGN ONLY (read-only investigation — no code written, no live login performed)
Scope: DEFENSIVE ban-DETECTION (know when WE'VE been banned so a run STOPS cleanly). Not evasion.

---

## 1. Problem recap and why the two prior approaches failed

The plugin must recognize, at login, that an account is BANNED / DISABLED / LOCKED and
STOP — instead of misreading the ban dialogue as "world busy" and hammering worlds
498/554/571/... 5 times before giving up.

Prior attempts (in `manny`):

| Commit | Approach | Result |
|--------|----------|--------|
| `6566fe9` DEFECT-22 | Scan login-screen **widget text** (`getWidgetRoots`) for ban phrases | FAILED. The ban dialogue is **rasterised to the canvas**, not backed by a text widget. `getWidgetRoots` returns nothing. |
| `a8a1020` DEFECT-22b | **Reflection** over the client's `String` / `String[]` fields for ban phrases | FAILED. Live gate (DEFECT-22c, deploy window #2) showed the reflection scan returns **len=0** — the ban phrase is in **no** scannable client `String` field. The scan only walks `client.getClass()`'s superclass chain; the rasterised text is never held as a live `String` on that object. |
| `70fac7a` DEFECT-22 | Provisional signal: hardcode the `getLoginIndex()` transition **10 → 14** | BRITTLE. `loginIndex` is undocumented above 4 and **drifted 10 → 14 between client versions**. A hardcoded number cannot be trusted; a false TERMINAL latch would brick a healthy login.

**Root cause of the whole difficulty:** RuneLite's public API exposes the login state
only as `Client.getLoginIndex()` — the login *screen* state index — and exposes
**no** login-response byte and **no** login-message string. Grep across the entire
runelite tree confirms: only `getLoginIndex()` exists; there is no `getLoginResponse`,
no `getLoginMessage`, no login-error event. The definitive ban signal that the game
server actually sends is consumed internally by the obfuscated client and never
surfaced as a stable API value or a readable `String`.

---

## 2. Login response codes vs. login-screen state indices (the two numbering systems)

There are **two different numbering systems** and they are routinely conflated. This is
the crux.

### 2a. OSRS network login-response codes (REFERENCE — NOT exposed by RuneLite)

The login server returns a single response byte. The client maps it to a screen. These
are stable in *meaning* across revisions, but **the plugin cannot read them** — no
RuneLite accessor exists. Listed here only so the classification of each outcome is
unambiguous:

| Code | Meaning | Class |
|------|---------|-------|
| 2 | Success — proceed into game | OK (→ GameState LOGGING_IN/LOADING/LOGGED_IN) |
| 3 | Invalid username or password | NON-terminal (bad creds; retry pointless but not a ban) |
| 4 | **Your account has been disabled** | **TERMINAL** (ban) |
| 5 | Account already logged in | Retryable-after-wait |
| 6 | Client out of date / game updated | TERMINAL for this jar (needs rebuild) |
| 7 | This world is full | RETRYABLE — world-hop is correct here |
| 8 | Login server offline / unable to connect | Retryable-after-wait |
| 9 | Login limit exceeded (too many from address) | RATE_LIMITED |
| 11 | Password suspected stolen — must change | **TERMINAL** |
| 12 | You need a members account (on a members world) | **TERMINAL** for that world |
| 13 | Could not complete login — try another world | RETRYABLE — world-hop |
| 14 | Server being updated | Retryable-after-wait |
| 16 | Too many login attempts | **RATE_LIMITED** (back off, then retry) |
| 18 | Account locked (hijack recovery) | **TERMINAL** |
| 20/23 | Invalid/again login server | Retryable-after-wait |
| 26 | Computer/IP address banned | **TERMINAL** |

TERMINAL = stop, do NOT world-hop. RETRYABLE / world-full (7, 13) = hopping is correct.
RATE_LIMITED (9, 16) = back off and retry, do not give up, do not hop aggressively.

### 2b. `Client.getLoginIndex()` screen-state indices (what the plugin CAN read)

`getLoginIndex()` returns the login **screen** state, a different value from §2a.
RuneLite documents only two, and treats the rest as opaque:

| Index | Meaning | Stability |
|-------|---------|-----------|
| 2 | Username / password entry form (resting LOGIN_SCREEN state) | **DOCUMENTED, stable** |
| 4 | Authenticator (OTP) form | **DOCUMENTED, stable** |
| (connecting) | "Connecting to server…" transient | undocumented, transient |
| (error/dialogue) | A response-error screen with a message + button (world-busy "Try again", **or** the ban "View Appeal Options / Back") | **UNDOCUMENTED, DRIFTS** — observed 10, then 14 |

Key consequence: **both** the transient "world busy" dialogue **and** the terminal ban
dialogue are non-`{2,4}` error-screen indices, and the specific number is version-unstable.
So `getLoginIndex()` alone can tell you "we are stuck on some login-error screen, not the
normal form", but **cannot by its number alone** distinguish world-busy (retry) from ban
(stop). That distinction is exactly what got rasterised away.

**Terminal-vs-not, by signal available to the plugin:**

| Observable (plugin-side) | Interpretation |
|--------------------------|----------------|
| GameState reaches LOGGING_IN → LOADING → LOGGED_IN | Success. Clear all latches. |
| loginIndex ∈ {2, 4}, GameState LOGIN_SCREEN | Normal resting form; not a failure. |
| loginIndex ∉ {2, 4}, **resolves within ≤1–2 attempts** (returns to form or logs in) | Transient (world-busy / rate-limit). Retry / hop is correct. |
| loginIndex ∉ {2, 4}, **persists across ≥2 attempts, never reaches LOGGED_IN** | **TERMINAL-SUSPECT.** Stop hopping. Confirm reason via vision (§3). |

---

## 3. Recommended PRIMARY signal + FALLBACK CHAIN

The insight driving the redesign: **the definitive ban text is rasterised, so no
in-JVM string/widget/index approach can read its *content* reliably.** The only reader
that is immune to obfuscation, field drift, and index drift is one that reads the
*pixels* — which manny already has as an MCP tool. And the only version-stable *plugin*
signal is *behavioural* (persistence), not a magic number.

### PRIMARY — MCP vision classification of the login screenshot (version-stable, definitive)

`manny_mcp` already ships `analyze_screenshot` (Gemini `gemini-2.5-flash-lite`, in
`mcptools/tools/screenshot.py`, on the **`manny-diort`** server). It reads whatever is on
the canvas — including the rasterised ban dialogue — as text, regardless of client
version. This is the **authoritative** ban signal.

- Immune to: obfuscation, `loginIndex` drift, field renames, rasterisation.
- Cost: one screenshot + one small-model call, only invoked on a *suspected* stuck login
  (not every tick), so negligible.
- Owner: the orchestrator / driver layer (Python), which is where "should this run keep
  going?" decisions already live.

### SECONDARY — plugin-side persistence heuristic (fast, in-process STOP)

Replace the brittle hardcoded `isBanSignatureTransition(10,14)` with a
**version-independent persistence rule** that relies only on the *stable* documented
indices {2, 4}:

> If `getLoginIndex()` is a non-`{2,4}` error-screen state that **persists across ≥2
> consecutive world-hop attempts** while GameState **never** reaches LOGGED_IN, latch
> TERMINAL and stop hopping.

This does not need to know the ban index number — it only needs to know the *normal* form
indices (2, 4), which are documented and stable. A genuine world-busy clears within an
attempt or two; a ban screen sits there forever. Pair it with the existing hard cap
(max 5 hops) as a backstop.

### TERTIARY — strict phrase match on widget text (belt-and-suspenders, cheap)

Keep the existing `classifyLoginFailure` / `classifyLoginResponseStrict` phrase scan for
the cases where the dialogue *is* text-backed (some rate-limit and members-required
prompts are real widgets). Never rely on it alone. Drop / de-emphasise the reflection
scan (`scanClientStringFields`) — the live gate proved it returns nothing for the ban
case; it adds risk (whole-field scan can false-positive) for no demonstrated benefit.

### BACKSTOP — bounded hops + latch (already present)

The existing "max 5 world switch attempts, then give up" cap stays as the final safety
net so a run always terminates even if every signal above misses. The difference after
this redesign: on give-up, the driver **classifies why** (vision) and records BANNED vs.
transient, instead of silently retrying the account on the next launch.

**Chain order at runtime:** persistence heuristic (SECONDARY) or phrase match (TERTIARY)
latches terminal in-plugin → world-hop loop aborts immediately → driver polls the latch /
GameState, and on any terminal-suspect OR hop-exhaustion calls `analyze_screenshot`
(PRIMARY) to get the definitive reason, then STOPS the run and marks the account.

### Version-stability reasoning (summary)

| Signal | Depends on | Breaks when |
|--------|-----------|-------------|
| Vision (`analyze_screenshot`) | pixels + English phrasing | Jagex rewords the ban copy (still human-readable; prompt is fuzzy) — very robust |
| Persistence heuristic | documented indices {2,4} + GameState enum | Jagex changes the *normal* form index (rare; 2/4 are long-stable and RuneLite-documented) |
| Phrase match on widgets | dialogue being a real text widget | ban dialogue rasterised (already the case) — so only a partial helper |
| Hardcoded index 10/14 | exact obfuscated screen number | every client revision (already broke once) — **do not use** |
| Reflection string scan | ban text living in a client String field | it doesn't (len=0 at live gate) — **remove** |

---

## 4. Concrete code plan (WHAT and WHERE — do NOT apply yet)

### 4a. `manny/login/LoginHandlers.java`

- **`WorldSelector.switchToF2PWorld()`** (the gateway every retry routes through,
  ~line 871): replace the `isBanSignatureTransition(prev,curr)` provisional block with the
  **persistence heuristic**. Track, in `LoginFailureState`, a counter of *consecutive*
  hop attempts observed with `loginIndex ∉ {2,4}` and GameState `LOGIN_SCREEN` (never
  LOGGED_IN). When that counter reaches 2, call `loginFailureState.latchTerminal(
  "persistent non-form login state N (idx=<x>) across M attempts")` and return false.
- **`LoginFailureState`** (~line 1256): add `int consecutiveErrorScreenAttempts` +
  `synchronized int noteErrorScreen(boolean isErrorScreen)` that increments when the
  current login state is a non-`{2,4}` error screen and resets to 0 otherwise (or on any
  LOGGED_IN observation). Keep `latchTerminal` / `isTerminal` / `getMessage` as-is.
- **Delete / neuter** `scanClientStringFields`, `readLoginResponseViaReflection`,
  `STRICT_*` reflection patterns, and the `BAN_SIGNATURE_PREV/CURR_INDEX` +
  `isBanSignatureTransition`. Keep `classifyLoginFailure` (widget phrase match) as the
  TERTIARY helper. Keep all the unconditional `[LOGIN] failure-check:` /
  `index-transition:` diagnostics — they are how the next live gate stays sighted.
- Keep the existing public surface: `isTerminalLoginFailure()`,
  `getLastLoginFailureMessage()`, `getLoginFailureState()`.

### 4b. `manny/utility/GameEngine.java` — export login diagnostics to `/tmp/manny_state.json`

The state file currently has **no** login section, so the driver is blind between
launches. Add one:

- In `MannyState` (~line 6556) add `public Object login;`.
- In `StateExporter.buildState()` (~line 5763) add `state.login = buildLoginState();`.
- Add `buildLoginState()` returning a map: `{ game_state: <client.getGameState()>,
  login_index: <safeLoginIndex>, terminal_login_failure: <loginHandlers.isTerminalLoginFailure()>,
  login_failure_message: <getLastLoginFailureMessage()>, world_switch_attempts: <n> }`.
  (StateExporter will need a `LoginHandlers` reference injected — it already receives
  several collaborators in its constructor at ~line 5561.)

This lets `get_game_state(fields=["login"])` see the ban latch directly.

### 4c. `manny_mcp/manny_driver/` — orchestrator uses vision + stops

- **`stuck_detector.py`**: add a login-stuck signal — GameState `LOGIN_SCREEN` /
  `LOGGING_IN` unchanged for > ~30s, or `login.terminal_login_failure == true` in the
  polled state. `get_recovery_hint()` for this signal must be "STOP, do not relaunch —
  classify with analyze_screenshot".
- The run monitor / watchdog (the loop that polls `get_game_state`): when the login-stuck
  signal fires, call `analyze_screenshot(prompt=<ban-classification prompt>)`, and if the
  answer indicates banned/disabled/locked, **STOP the run, mark the account BANNED in the
  run ledger, and do NOT world-hop or relaunch.** A transient answer (world full / rate
  limited) may retry within the existing bounded policy.
- Suggested prompt: *"This is an OSRS login screen. Does it show an account ban, disable,
  lock, appeal, or 'serious rule breaking' message? Answer strictly: BANNED, LOCKED,
  MEMBERS_REQUIRED, WORLD_FULL, RATE_LIMITED, NORMAL, or OTHER, then a one-line reason."*

---

## 5. ZERO-RISK live gate (exact steps for a future session)

Goal: capture the real login signal on a KNOWN-BANNED account, then STOP. No grinding, no
world-hop spam, no commands beyond login + one screenshot.

**Both `new` (GrimmsFairly, banned 2026-07-18) and `newbakshesh` (banned ~2026-07-19)
are confirmed BANNED** and are the intended fail-fast test cases. `main` is the user's
REAL account and is OFF-LIMITS. Live spare accounts (`blast`, `punitpun`) must NOT be used
for this test.

Steps (run on **`manny-diort`**, where the live client + `/tmp` IPC live):

1. **Pre-flight the account.** Read `~/.manny/credentials.yaml`; confirm the alias you'll
   use carries the `# BANNED` comment. Do NOT trust `default:` — it has twice been reset to
   a banned account; select the banned alias EXPLICITLY. Confirm you are not about to touch
   `main`.
2. **Bring up a display** and `start_runelite(account_id="new", display=":4")` (a display
   not used by any live lane). Send NO scenario, NO auto-play, NO grind commands.
3. **Immediately disable command processing** so nothing drives the account:
   `send_command("STOP_PROCESSOR")` (and ensure no routine/driver is attached).
4. **Let the login attempt land once.** The plugin will click Play and attempt login. Do
   NOT let it world-hop repeatedly — watch the logs and, the moment it reaches the error
   screen, capture signals (next step). If it starts hopping, `stop_runelite` after the
   first hop; one attempt is enough.
5. **Capture the definitive signal set** while the ban screen is up:
   - `get_logs(grep="[LOGIN]", since_seconds=60)` — record the `failure-check:`
     (reflection len, widget text, **loginIndex**) and `index-transition:` lines. This
     re-confirms the current ban `loginIndex` value (was 14) and that reflection len=0.
   - `get_game_state(fields=["login"])` (after 4b lands) — record `login_index`,
     `game_state`, `terminal_login_failure`.
   - **`analyze_screenshot`** with the §4c ban prompt — this is the PRIMARY validation:
     confirm the vision model reads the ban text and returns BANNED.
6. **STOP.** `stop_runelite(account_id="new")`. Record in the journal: the observed
   `loginIndex`, whether the persistence heuristic would have latched (index ∉ {2,4},
   persisted), and the exact `analyze_screenshot` verdict.
7. **Pass criteria:** (a) `analyze_screenshot` returns BANNED/serious-rule-breaking; (b)
   `loginIndex` is a stable non-`{2,4}` value that persists across the attempt; (c) the
   plugin latches `terminal_login_failure=true` WITHOUT 5 world hops. Any one of (a)/(b)
   satisfied with no hop-spam = the redesign works; (a) is the authoritative one.

Risk: zero. A banned account cannot log in; the test performs a single login attempt and a
screenshot, then stops. No gameplay, no bans-in-progress, no contact with live accounts.

---

## 6. One-line takeaways

- RuneLite exposes only `getLoginIndex()` (screen state, drifts) — no login response
  code, no login message string, no login-error event. Confirmed by full-tree grep.
- The ban text is rasterised: unreadable by widget scan, reflection (len=0 at live gate),
  or index number. **Only pixel-reading (`analyze_screenshot`) reads it reliably.**
- PRIMARY = MCP Gemini vision on the login screenshot (version-stable, definitive).
  SECONDARY = plugin persistence heuristic on non-`{2,4}` login states (no magic number).
  TERTIARY = widget phrase match. BACKSTOP = bounded hops + terminal latch.
- Remove the reflection scan and the hardcoded 10→14 signature; keep the diagnostics.
- Live gate is genuinely zero-risk on the already-banned `new` / `newbakshesh`.
</content>
</invoke>
