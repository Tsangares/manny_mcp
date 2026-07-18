# Manny Refactor Campaign — Orchestrator Playbook (LIVE DOC)

**Purpose:** Working state + forward instructions for the multi-wave refactor of `~/Desktop/manny` (Java RuneLite plugin) + `~/Desktop/manny_mcp` (Python MCP server). Written for the orchestrating Claude session to re-read after context compaction. The approved wave plan is at `/home/wil/.claude/plans/can-you-search-around-giggly-globe.md`; the architecture review that drives it is `journals/architecture_review_2026-07-17.md`. Update this file at every wave boundary.

## Status (update me!)

- ✅ Wave 0 (hygiene) — committed+pushed both repos
- ✅ Wave 1 (9 Phase-0 bug fixes) — committed+pushed; live smoke 5/5
- ✅ Wave 2 (MannyPaths + transport.py + read-only lane) — committed+pushed; non-preemption proven live
- ✅ Wave 3 DONE + pushed: 3a registry; 3b `2f916a9` (23 handlers → classes); 3c `1e747c5` (CommandBase interrupt system, Mouse fixes, 5 skilling loops migrated, KILL/STOP/EMERGENCY_STOP now preserve shouldInterrupt past their own finally — detached cmdlog loops abort within 200ms; live-gated)
- 🔶 Wave 4 IN PROGRESS: Phase A = 3 parallel sonnet agents (GE dedup, GameEngine self-copies, Keyboard/Mouse/login) — none touch PlayerHelpers. Phase B (opus, sequential) = InteractionSystem click authority + banking-helper extraction + 12 stateful handler migration + ListCommandsCommand from registry. Detail: REFACTOR_CAMPAIGN_HANDOFF.md.
- ENV CHANGES 2026-07-17: client on **Xvfb :2** (input isolation); **GPU plugin disabled + fps 30** (llvmpipe heat, 374%→46% CPU); MJPEG live view http://100.83.247.91:8787/ ; MCP layer decision: keep server, prune to ~25-40 tools in Wave 5, direct file IPC is primary.
- ⬜ Waves 5-7: see plan file.

## Scope decision made mid-flight (differs from plan file)

Wave 3's "migrate all 39/40 inline handlers" was split by risk:
- 23 simple ones → 3b (in flight)
- 5 skilling loops using `shouldInterrupt` (#14 DROP_ALL, #22 POWER_MINE, #23 MINE_ORE, #25 FISH_DROP, #26 POWER_CHOP) → do WITH the interrupt system in 3c
- 12 stateful/cross-calling (#11 TELEPORT, #12 TELEGRAB_WINE_LOOP, #15 BURY_ALL, #17 KILL_LOOP, #18 KILL_LOOP_CONFIG, #19 KILL_COW, #20 KILL_COW_GET_HIDES, #21 IMP_HUNT, #24 COLLECT_LUMBRIDGE_TIN_COPPER, #29 SMELT_BRONZE_BARS, #30 SMELT_BAR, #31 BUY_GE) → **moved to Wave 4**, because they depend on shared private helpers (handleBankOpen/Close/Deposit/Withdraw, handleGotoCommand, handleSmeltBar, handleBuryItem) that Wave 4 extracts anyway (GEInterfaceHelper/banking consolidation). Also deferred to Wave 4: feed `ListCommandsCommand` from `commandRegistry.keySet()`.

## 3c spec (next after 3b's compile gate)

One opus agent, owns PlayerHelpers.java + CommandBase.java + Mouse.java + the 5 skilling handlers:
1. Add `checkInterrupt()` to `CommandBase` wired to a `BooleanSupplier` (the processor's `shouldInterrupt`); constructor-inject the supplier (or a static hook) without breaking the ~114 existing command classes — prefer an optional setter/registry-time wiring.
2. Fix `Mouse.replay()` swallowed `InterruptedException` (~line 486: catches and prints instead of propagating) + `hz=0` division guard (~line 464, `gauss(40