# The `judeaislam: *` chat-asterisk investigation — INNOCENT (no leak, no detection surface)

**Run:** `20260720T053755Z_judeaislam` (host diort, display :6, client pid 2765180).
**Anomaly (from `journals/2026-07-20_mainland_session1_judeaislam_diort.md`, §"Anomaly log"):**
the screenshot chatbox shows `judeaislam: *` although zero TYPE/chat commands were sent the whole
session; the only keyboard activity was the login-phase camera-rotation `KEY_PRESSED` bursts.

## Verdict (plain language)

**Nothing made the character "say" `*`. The account never sent a public-chat message — or any
chat message of any type.** `judeaislam: *` is the **standard OSRS empty chat-input prompt line**:
OSRS always renders your name followed by the text-entry caret at the bottom of the chat panel as
`<name>: <typed-text>*`. With an empty input buffer it reads exactly `judeaislam: *`, where the
trailing `*` is the flashing cursor, not a typed character. It is drawn client-side from the local
input buffer (VarClientStr) and is **never transmitted to the server** until Enter is pressed with
real content. No other player ever saw judeaislam say anything. This is baseline UI, present in
every OSRS client whenever the chat is in its standard/public view — it is not anomalous and is
**not a detection surface at all.**

The anomaly note was an honest misread of a screenshot: the `*` caret was mistaken for a spoken
message. There is no input-path leak to fix.

## Evidence (receipts)

### 1. The screenshot proves it is the input line, not a message
`journals/images/2026-07-20_judeaislam_mainland_s1b_draynor_bankopen_fail.png`:
- `judeaislam: *` sits on **its own line at the very bottom** of the chat panel, **directly above
  the chat-filter tab bar** (`All / Game / Public / Private / Channel / Clan / Trade`). That is the
  fixed location of the OSRS chat *input prompt*, not the scrollable message area.
- The scrollable message area **above** it (with its own scrollbar) contains **only** Game/Broadcast
  content: "Welcome to Old School RuneScape.", a "Did you know?" tip, a Broadcast line, and three
  "You have unlocked a new music track:" lines. **There is no public-chat message from judeaislam
  anywhere in the message area.**
- If judeaislam had actually *said* `*` in public chat, it would appear as a cyan message line
  **inside** the message area (e.g. `judeaislam: *`), not on the input-prompt line below the divider.

### 2. Which chat type was it? — **none.** It is not a ChatMessage at all.
Task question #4 answered definitively: the line is the client's chatbox **input buffer render**
(`<name>: <input>*`), drawn continuously whenever the chat is in standard view. It is not
`PUBLICCHAT`, not `FRIENDSCHAT`/clan, not console/game — it is not a message of any RuneLite
`ChatMessageType`. It is the local "type here" prompt with an empty buffer. Nothing was broadcast.

### 3. No chat/TYPE command was ever issued for this account
`/tmp/manny_sessions/commands_2026-07-19.yaml` on diort: the string `judeaislam` appears **0 times**;
the only `TYPE` lines in that shared session log are three `TYPE tovahkline` entries belonging to a
**different account's** name-entry session (not chat, not judeaislam). So no TYPE/chat/SAY command
touched judeaislam's run.

### 4. The only keyboard activity was VK_UP, dispatched with CHAR_UNDEFINED (cannot enter text)
`/tmp/runelite_judeaislam.log` `[KEYBOARD-DEBUG]` lines: every rotation logs
`direction=UP (look up)` — i.e. `MannyPlugin.java:752 keyboard.rotate('^', duration)` (the one-time
post-login camera pitch-up). In `human/Keyboard.java` `rotate(char,long)` builds each event as:
```java
new KeyEvent(canvas, KeyEvent.KEY_PRESSED, now, 0, VK_UP, KeyEvent.CHAR_UNDEFINED)
```
plus one trailing `KEY_RELEASED`. **No `KEY_TYPED` is ever dispatched by `rotate()`**, and the
keyChar is `CHAR_UNDEFINED`. Per project doctrine, OSRS chat/text fields consume `KEY_TYPED` only;
`KEY_PRESSED` arrow keys move the camera and cannot enter a character. So the camera keys could not
put anything (least of all `*`) into the chat input.

### 5. No Enter was ever dispatched this session
`grep -i 'ENTER|KEY_TYPED|Key Typed'` over the client log returns 6 hits, **all false substring
matches** ("Button **center**", "**Clicking** … tab", "Dynamic **center**") — zero real
`VK_ENTER`/`KEY_TYPED` events. In the source, `VK_ENTER` is dispatched only by GE/Bank
quantity/price entry (`GEInputPriceCommand`, `GEInputQuantityCommand`, `BankWithdrawCommand:312`,
`BankingSupport:1174`) — **none of which ran**: the chain aborted at `BANK_OPEN` (candidate
DEFECT-34, client-thread crash) before any withdraw/GE path. So even if text had somehow entered the
buffer, nothing submitted it.

## Hypotheses tested and killed

- **Held arrow key producing a typed char / stray Enter submitting it** — killed by §4 + §5: arrow
  events carry `CHAR_UNDEFINED` and emit no `KEY_TYPED`; no Enter was dispatched.
- **VK_MULTIPLY / shift+8 / a hardcoded `*` in a dispatched KeyEvent** — killed:
  `grep VK_MULTIPLY|'(char) 42'` across the whole plugin returns nothing. `Keyboard.type()` *does*
  map `'*'`→`VK_8`+shift, but `type()` is only reachable via `TYPE`/GE/Bank commands, none of which
  ran (§3).
- **X-level injection (Xvfb/xdotool)** — not in this path: all input is AWT `canvas.dispatchEvent`
  in-JVM; no xdotool/X keystroke injection is used by the run flow.
- **OSRS masking some input as `*`** — moot: the buffer was empty; `*` is the caret glyph, present
  with zero input.

## Latent (unrelated) bug noted, NOT the cause, NOT fixed

`Keyboard.rotate()` (the **no-argument** overload, line 55) is buggy:
`rotate((char)(random.nextInt(4) + 37))` yields chars 37–40 (`% & ' (`), none of which match the
`< > ^ v` cases in `rotate(char)` — so `keyCode` stays `-1` (the author clearly meant the VK codes
37–40 = LEFT/UP/RIGHT/DOWN, per the `//37`… comments, but switched on symbols instead). It would
dispatch a `keyCode=-1, CHAR_UNDEFINED` no-op event. **This is harmless (no character, no
`KEY_TYPED`) and has ZERO callers** (`grep 'rotate()'` finds no invocation) — every live caller uses
the `rotate('^'/'>'/'v', …)` overloads. It is dead-code cosmetics, unrelated to the `*`, and left
untouched per the brief (a Java fix is authorized only for a *proven* leak path; the leak is
disproven).

## Recommendation

- **No code change.** No leak exists; no detection surface. Close anomaly item #4 from the session
  journal as INNOCENT — the `*` is the normal empty chat-input caret.
- **Doc hygiene:** future overseers reading a screenshot should treat a bottom-of-panel
  `<name>: *` (above the filter tabs) as the standard input prompt, not a sent message. A real
  public message renders as a cyan line *inside* the scrollable message area.
- Optional tidy (non-safety): fix or delete the unused no-arg `Keyboard.rotate()` overload so it
  can't mislead a future reader — but it changes no behavior and is out of scope here.

## Bookkeeping
- Read-only investigation. Nothing started/stopped on diort or llama; only `grep`/`ls`/screenshot
  reads over ssh. No live client touched.
- No manny (Java) commit — no fix made (leak disproven).
