# TOOL_RENAME_MAP — Wave 5 MCP tool-surface consolidation

Date: 2026-07-17. The MCP tool surface was pruned from ~105 defined tools (78
registered at boot + 27 in unimported modules) to **39 registered tools**.
Principle: ONE canonical tool per capability — the most general/robust variant
survives, the others' parameters were folded in as optional args.

Migration examples for every old name are below. Python handler functions that
external code imported (`handle_scan_tile_objects`, `handle_click_text`,
`handle_execute_routine`, `handle_equip_item`, `_capture_gif`,
`handle_get_action_log`) remain importable even where the MCP tool was removed.

## Widget clicking (5 variants → 1)

| Old tool | New |
|---|---|
| `click_widget` | **`click_widget`** (canonical, new params) — `click_widget(widget_id=...)` unchanged; bounds click now uses atomic `CLICK_AT` instead of the racy MOUSE_MOVE+MOUSE_CLICK pair |
| `find_and_click_widget(text=, action=)` | REMOVED → `click_widget(text=..., action=...)` |
| `click_widget_by_action(action=, container_id=)` | REMOVED → `click_widget(action=..., container_id=...)` |
| `click_text(text=)` | REMOVED → `click_widget(dialogue_option=...)` (dialogue) or `click_widget(text=...)` (UI) |
| `click_continue()` | REMOVED → `click_widget(continue_dialogue=True)` |

Routine YAML compatibility: `mcp_tool: find_and_click_widget` and
`mcp_tool: equip_item` steps still execute (mapped to the canonical handlers in
`mcptools/tools/routine.py::_execute_mcp_tool_step`); `mcp_tool: click_widget`
is the new canonical spelling.

## Widget inspection (3 → 1)

| Old tool | New |
|---|---|
| `find_widget(text=)` | **`find_widget`** (canonical; `text` now optional) |
| `scan_widgets(filter_text=, group=)` | REMOVED → `find_widget(text=..., group=..., full=True for raw)` ; bare `find_widget()` = old summary mode |
| `debug_widget_children(container_id=)` | REMOVED → `find_widget(container_id=...)` |

## Routine-from-recording (trio → 1)

| Old tool | New |
|---|---|
| `session_to_routine(session_path=)` | REMOVED → **`recording_to_routine(source="session", session_path=...)`** |
| `action_log_to_routine(since_seconds=)` | REMOVED → `recording_to_routine(source="action_log", since_seconds=...)` |
| `generate_routine(routine_name=)` (was never wired into server.py) | REMOVED → `recording_to_routine(source="location_history", routine_name=...)` |

## Command discovery (trio+1 → 1)

| Old tool | New |
|---|---|
| `list_plugin_commands(category=)` | REMOVED → **`list_commands(category=...)`** (live query; auto-falls back to static index when client is down) |
| `list_available_commands(search=, category=)` (unwired) | REMOVED → `list_commands(search=..., category=...)` |
| `generate_command_reference` | REMOVED → `list_commands` (or `manny_tools.generate_command_reference` for scripts) |
| `get_command_examples(command=)` | REMOVED → `list_commands(command=...)` |

## Anti-pattern duo (2 → 1 + flag)

| Old tool | New |
|---|---|
| `check_anti_patterns` | **`check_anti_patterns`** (unchanged) |
| `validate_with_anti_pattern_check(modified_files=)` | REMOVED → `validate_code_change(modified_files=..., check_anti_patterns=True)` |

## Session / sessions domain unification

Recording domain (was `session.py`, none wired into server.py before; now 2 registered tools):

| Old tool | New |
|---|---|
| `start_session_recording(goal=)` | REMOVED → **`record_session(action="start", goal=...)`** |
| `stop_session_recording()` | REMOVED → `record_session(action="stop")` |
| `is_session_recording()` | REMOVED → `record_session(action="status")` |
| `add_session_marker(label=, note=)` | REMOVED → `record_session(action="marker", label=...)` |
| `get_session_events(last_n=)` | REMOVED → `record_session(action="events", last_n=...)` |
| `get_command_history` | REMOVED — read `/tmp/manny_sessions/commands_YYYY-MM-DD.yaml` directly |
| `get_action_log` | REMOVED — read `/tmp/manny_<account>_actions.json` directly (`handle_get_action_log` still importable) |
| `clear_action_log` | REMOVED — delete `/tmp/manny_*_actions.json` directly |

Client-session domain (was `sessions.py`, unwired before; now 2 registered tools):

| Old tool | New |
|---|---|
| `get_session_status(account_id=)` | REMOVED → **`session_status(account_id=...)`** |
| `get_available_accounts()` | REMOVED → `session_status()` (includes per-account availability) |
| `get_playtime(account_id=)` | REMOVED → `session_status(account_id=...)` (playtime block) |
| `get_display_status()` | REMOVED → `session_status(include_displays=True)` |
| `end_session(account_id=)` | REMOVED → **`manage_session(action="end", account_id=...)`** |
| `cleanup_stale_sessions()` | REMOVED → `manage_session(action="cleanup")` |
| `reset_account_display(account_id=)` | REMOVED → `manage_session(action="reset_display", account_id=...)` |
| `reassign_account_display(account_id=, display=)` | REMOVED → `manage_session(action="reassign_display", account_id=..., display=...)` |

## Credentials (6 → 2)

| Old tool | New |
|---|---|
| `list_accounts` | **`list_accounts`** (unchanged) |
| `add_account(alias=, display_name=, ...)` | REMOVED → **`manage_account(action="add", alias=..., display_name=..., ...)`** |
| `import_credentials(alias=, display_name=)` | REMOVED → `manage_account(action="import", ...)` |
| `remove_account(alias=)` | REMOVED → `manage_account(action="remove", alias=...)` |
| `set_account_proxy(alias=, proxy=)` | REMOVED → `manage_account(action="set_proxy", alias=..., proxy=...)` |
| `set_default_account(alias=)` | REMOVED → `manage_account(action="set_default", alias=...)` |

## Routine execution

| Old tool | New |
|---|---|
| `execute_routine(routine_path=)` | REMOVED as MCP tool → run `./run_routine.py <path> --loops N --account ID` (the script path is unchanged and still calls `routine.handle_execute_routine` directly) |
| `execute_combat_routine` | **`execute_combat_routine`** (unchanged — combat YAML has a different schema handled by `KILL_LOOP_CONFIG`) |

## Trivial-wrapper command tools (removed; use the canonical command path)

| Old tool | Replacement |
|---|---|
| `deposit_item(item_name="X")` | `send_and_await("BANK_DEPOSIT_ITEM X_with_underscores", "no_item:X")` |
| `teleport_home()` | `send_and_await("TELEPORT_HOME", "location:3222,3218")` |
| `stabilize_camera(pitch=, zoom_in_scrolls=)` | `send_command("CAMERA_STABILIZE <pitch> <zoom>")` (defaults 350 15) |
| `equip_item(item_name="X")` | `click_widget(text="X", action="Wear"/"Wield")` (handler kept for routine YAML steps) |
| `get_command_response()` | read `/tmp/manny_<account>_response.json` directly, or prefer `send_and_await` |
| `clear_widget_overlay()` | truncate `/tmp/manny_widget_select.txt` |
| `kill_command` | **`kill_command`** (unchanged) |

## Spatial / quests

| Old tool | New |
|---|---|
| `scan_environment` | **`scan_environment`** (canonical; new `transitions_only` param) |
| `get_transitions(radius=)` | REMOVED → `scan_environment(transitions_only=True, radius=...)` |
| `get_location_info(area=)` | **`get_location_info`** (`area` now optional; no args lists all known locations) |
| `list_known_locations()` | REMOVED → `get_location_info()` |
| `scan_tile_objects(object_name=, max_distance=)` | REMOVED → `query_nearby(object_name=..., max_distance=...)` |
| `list_quests(filter=)` | **`list_quests`** (canonical; new `quest_name` param) |
| `quest_summary(f2p_only=)` | REMOVED → `list_quests(filter="f2p")` |
| `check_quest(quest_name=)` | REMOVED → `list_quests(quest_name=...)` |

## Monitoring / core

| Old tool | New |
|---|---|
| `get_logs, get_game_state, check_health, is_alive, await_state_change, auto_reconnect, restart_if_frozen` | unchanged (mcptools/tools/monitoring.py untouched this wave) |
| `runelite_status()` | REMOVED → `session_status()` for listing, `is_alive()` for a fast per-account check |
| `build_plugin, start_runelite, stop_runelite` | unchanged |
| `capture_gif` | REMOVED → MJPEG live view (`scripts/mjpeg_viewer.py`, http://100.83.247.91:8787/); `_capture_gif` still importable (Discord /gif uses it) |
| `get_screenshot, analyze_screenshot` | unchanged |

## Code-change / plugin-navigation surface (pruned)

| Old tool | New |
|---|---|
| `prepare_code_change, validate_code_change, deploy_code_change` | unchanged (validate gained `check_anti_patterns`) |
| `find_relevant_files` | REMOVED → grep/Glob or `request_code_change.find_relevant_files` for scripts |
| `backup_files` / `rollback_code_change` | REMOVED → use git |
| `diagnose_issues` | REMOVED → `get_logs` + reasoning (`request_code_change.diagnose_issues` still importable) |
| `get_section, find_command, check_anti_patterns, validate_routine_deep` | unchanged |
| `get_manny_guidelines` | REMOVED → read `manny_src/CLAUDE.md`; auto-included by `prepare_code_change` |
| `get_plugin_context, find_pattern, generate_command_template, get_class_summary, find_similar_fix, get_threading_patterns, find_blocking_patterns, generate_debug_instrumentation, get_blocking_trace, get_teleport_info` | REMOVED from MCP (all remain plain functions in `manny_tools.py`) |

## Never-wired dead modules (defined but never imported by server.py, before or after)

`mcptools/tools/code_intelligence.py` (`find_usages`, `find_definition`,
`get_call_graph`), `mcptools/tools/location_history.py` (`get_location_history`,
`visualize_trail`, `detect_movement_patterns`, `get_event_history`),
`mcptools/tools/testing.py` (`run_tests`). These were never on the running tool
surface; the files remain on disk, unregistered.

## Internal (non-MCP) names intentionally kept

- discord_bot keeps its bot-internal capability names `scan_tile_objects`,
  `run_routine`, `lookup_location`, `get_command_help` etc. — they are the
  bot↔LLM contract, dispatched to internal handlers, not MCP tool names.
- `manny-cli` and direct file IPC (`/tmp/manny_<account>_command.txt` /
  `_response.json`) are unaffected.

## Final registered surface (39)

analyze_screenshot, auto_reconnect, await_state_change, build_plugin,
check_anti_patterns, check_health, click_widget, deploy_code_change,
execute_combat_routine, find_command, find_widget, get_chat_messages,
get_dialogue, get_game_state, get_location_info, get_logs, get_screenshot,
get_section, is_alive, kill_command, list_accounts, list_commands, list_quests,
manage_account, manage_session, prepare_code_change, query_nearby,
record_session, recording_to_routine, restart_if_frozen, scan_environment,
send_and_await, send_command, send_input, session_status, start_runelite,
stop_runelite, validate_code_change, validate_routine_deep
