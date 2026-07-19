# TICKET: Expose `Keyboard.type()` as a `TYPE` command (unblocks in-game display-name automation)

**Filed:** 2026-07-19 · **For:** the larger game-editing (manny_src / plugin) project queue
**Status:** spec only — do NOT implement from the account-automation side; queued for the plugin project.
**Related:** plan `~/.claude/plans/idk-what-are-you-lexical-sutton.md` (Phase E), Bolt CDP work this session.

## Problem

Automating the OSRS **"Set display name"** screen (which appears at *first login* of a
fresh character — NOT post-tutorial, corrected this session) requires typing text into
the name field. The plugin currently has **no command that can type free text into a
game text field.**

- `KEY_PRESS` (→ `Keyboard.pressKey`, `manny_src/human/Keyboard.java:174/195`) dispatches
  only `KEY_PRESSED` + `KEY_RELEASED` with `CHAR_UNDEFINED`.
- **Verified live (char `tovahkline` / 369475846, 2026-07-19):** clicking the field
  (`CLICK_WIDGET 36569095 "Enter name"`) then `KEY_PRESS t` → plugin logs
  `[KEY_PRESS] Pressed: t` / succeeded, but the field (`36569095`) stays empty and the
  masked child (`36569100`) still shows `*`. **The character does not enter the field.**
- Root cause: OSRS text inputs consume the **`KEY_TYPED`** char event, which `pressKey`
  never sends.

## What's needed

Expose the EXISTING, correct primitive as a command. `Keyboard.type(String word)`
(`manny_src/human/Keyboard.java:266`) already dispatches the full, human-paced
`KEY_PRESSED → KEY_TYPED(char) → KEY_RELEASED` sequence with shift handling
(`KEY_TYPED` at line 375) — exactly what text fields need. It just has no command wrapper.

**Deliverable:** a new command `TYPE "<text>"` that calls `Keyboard.type(text)`.

- Mirror the existing command pattern: new `manny_src/utility/commands/TypeCommand.java`
  (see `KeyPressCommand.java` for the template — `super("TYPE", responseWriter)`,
  ResponseWriter usage), register it in `PlayerHelpers.java` (alongside
  `register("KEY_PRESS", keyPressCommand)` ~line 1410), and add a `meta(...)` entry in
  `ListCommandsCommand.java` (~line 143) e.g.
  `meta("TYPE", "ui_control", "<text>", "Type free text into the focused field")`.
- Arg parsing: accept the full remainder as the string (supports spaces); trust
  `type()`'s existing handling of case/shift/punctuation.
- No new interrupt/threading concerns beyond what `KEY_PRESS` already does.

Optional (nice-to-have, lower priority): a higher-level `SET_DISPLAY_NAME "<name>"`
command that scripts the whole dialog. Not required — with `TYPE`, the flow is fully
composable from existing commands (see below), so `TYPE` alone unblocks everything.

## The naming flow this unblocks (widget IDs captured live, group 558)

1. `CLICK_WIDGET 36569095 "Enter name"`   — focus the display-name field
2. `TYPE <name>`                          — NEW command (the missing piece)
3. `CLICK_WIDGET 36569106 "Look up name"` — availability check
4. read status widget `36569101` ("Please look up a name…" → availability result)
5. click the **Set/Confirm** button that appears only after an available look-up
   — **CAPTURED (2026-07-19):** widget id **`36569107`**, action **`"Set name"`**
   (`CLICK_WIDGET 36569107 "Set name"`). TYPE acceptance PASSED end-to-end 2026-07-19.
   NOTE: this button (like `36569095`/`36569106`) reports (-1,-1)/null bounds and an
   empty widget name, which exposed the CLICK_WIDGET null-bounds menu-fallback defect
   fixed this window (InteractionSystem.matchesMenuEntry association-fallback).

Other refs: dialog title `36569091` ("Set display name"), masked field child
`36569100`, group `263` = tutorial-progress gate overlaid on the same screen.

## Acceptance criteria

- `CLICK_WIDGET 36569095 "Enter name"` then `TYPE tovahkline` results in the field
  (`36569095` / masked `36569100`) showing the typed name.
- `CLICK_WIDGET 36569106 "Look up name"` updates status widget `36569101` with the
  availability result.
- End-to-end: a fresh unnamed character can be named entirely via commands (no OS input).

## Test setup (reproduce the screen)

A fresh char lands on this screen at first login. Reproduce:
`start_runelite(account_id=<fresh unnamed char>, display=":0")` → auto-login →
`find_widget(group=558)` shows the dialog. (Char `tovahkline`/369475846 is currently
unnamed and parked on this exact screen.)

## Notes

- Build/deploy is laptop-local (`build_plugin` → shaded jar → restart client). Restarting
  drops the current screen but it reappears on relogin (char stays unnamed until set).
- This is the ONLY plugin change needed for the naming half of the account pipeline; the
  Bolt-side (create + launch + creds) is already automated via CDP (`mcptools/bolt_cdp.py`,
  `mcptools/tools/bolt.py`).
