# 2026-07-20 — User domain answers (verbatim intent, for future agents)

Six questions were put to the user (the campaign's cheapest oracle); answers below with
the action each one seeded. Treat these as domain priors, not verified facts — receipts
still required where they drive fixes.

1. **Bank close / Esc.** User believes Esc normally closes the bank and doesn't know why it
   didn't here; directive: *"Click the X widget then."* → Matches DEFECT-33 fix `dbefcea`
   (close-button action-scan click, Esc fallback, honest failure). Movement-close (1f91a80)
   separately validated live in attempt #15.
2. **Level-up detection.** *"Just check the widget container for text that is
   congratulations."* → Detection primitive for gathering-routine loops: scan
   dialogue/widget export for "Congratulations" and drain/continue, then re-click the
   resource. Await empirical interrupt data from mainland session 1 before wiring in.
3. **Cook's Assistant dialogue.** *"Check the wikipedia."* → Wiki quest transcript is the
   authority for exact option text (CLICK_DIALOGUE is exact-match, silent no-op on miss).
4. **Tutorial magic section.** *"There are a ton of doors… also the chicken and the magic
   button doesn't work normally, idk why the magic book widgets are different — I would
   like you to figure that out."* → Standing investigation: why spellbook-tab / spell
   widget clicks misbehave (matches attempt #8: stale widget 35913777, wind-strike
   false-march, CLICK_AT fallbacks in e3c51c5). Goal: replace raw CLICK_ATs with honest
   widget clicks once the widget layout is actually understood.
5. **Firemaking.** *"Sometimes you can't light a fire — check my old code."* → Prior-art
   dig: the old code already handled can't-light-here (likely walk-a-tile-and-retry).
   Fold into woodcutting routine before its first live run.
6. **Account factory.** *"Yeah it needs emails and stuff."* → Fresh accounts require email
   verification: the factory cannot be fully autonomous without an email supply (candidate:
   catch-all addresses on the user's domains, hosted on mat). Design item for factory
   kickoff, parked.
