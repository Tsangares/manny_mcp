# Tool Registry Migration - Lessons Learned
**Date:** 2026-02-06

## The Problem

The MCP server had tool definitions split across 3 locations: a `ToolRegistry` pattern (72 tools), manual `Tool()` construction in `server.py` (26 more), and raw handler functions in `request_code_change.py` / `manny_tools.py`. This meant `server.py` was ~668 lines of boilerplate dispatch code, and adding a tool required edits in 3 places.

## Root Cause

The registry pattern was introduced mid-project but the migration was never completed. The 26 legacy tools in `request_code_change.py` and `manny_tools.py` each defined their schema as a `*_TOOL = {...}` dict constant AND a separate handler function. `server.py` imported both, manually constructed `Tool()` objects in `list_tools()`, and had a 200-line `if/elif` dispatch chain in `call_tool()`.

## Key Lessons

### 1. Wrapper modules beat moving code

**What happened:** Instead of moving ~3000 lines of implementation code into `mcptools/tools/`, we created thin wrapper modules that import from the original files and register via `@registry.register()`.

**Why:** Moving the code would have been a massive diff with high breakage risk. The original files have internal cross-references (e.g., `request_code_change.py` imports from `manny_tools.py` for smart sectioning).

**Solution:**
```python
# BAD - move all code into mcptools/tools/ (huge diff, breaks imports)
# manny_tools.py functions reference each other internally

# GOOD - thin wrapper that reuses existing schema constants
from manny_tools import _get_section as impl, GET_SECTION_TOOL

@registry.register(GET_SECTION_TOOL)  # Reuse the existing dict!
async def handle_get_section(arguments: dict) -> dict:
    return impl(plugin_dir=config.plugin_directory, ...)
```

The `*_TOOL` dict constants already have the exact schema the registry needs - just pass them directly to `@registry.register()`.

### 2. Config injection is the main glue

**What happened:** Most legacy handlers needed `config.plugin_directory` or `config.runelite_root` injected. The original `server.py` dispatch had access to the global `config`, but wrapper modules don't.

**Why:** The registry pattern uses `set_dependencies()` for dependency injection (same pattern as `core.py`, `commands.py`, etc.).

**Solution:**
```python
# In the wrapper module
config = None

def set_dependencies(server_config):
    global config
    config = server_config

# In server.py initialization section
code_changes.set_dependencies(config)
manny_navigation.set_dependencies(config)
```

### 3. Special formatting handlers need to return MCP content lists

**What happened:** `get_manny_guidelines` had custom formatting logic in `server.py` that built markdown text instead of returning raw JSON. The registry's `call_tool()` auto-wraps dict returns in `TextContent(json.dumps(...))`, which would lose the formatting.

**Why:** The registry normalizes responses - dicts become JSON, lists pass through. If a handler needs custom formatting, it must return `[TextContent(...)]` directly.

**Solution:**
```python
# Handler returns list -> registry passes it through unchanged
@registry.register(GET_MANNY_GUIDELINES_TOOL)
async def handle_get_manny_guidelines(arguments: dict) -> list:
    result = _get_manny_guidelines(...)
    if result.get("success"):
        content_text = f"# Manny Plugin Guidelines ({result['mode']} mode)\n\n"
        content_text += result["content"]
        return [TextContent(type="text", text=content_text)]
    # ...
```

### 4. Clean up unused imports after migration

**What happened:** After removing the 200-line dispatch chain, `server.py` no longer used `Tool`, `TextContent`, `signal`, or `Path` imports. Left uncleaned, these would confuse future readers.

**Why:** Removing dead code prevents confusion about what's actually used.

## Anti-Patterns

1. **Don't move implementation code during a registry migration** - Wrap it. Moving creates merge conflicts and breaks internal references.
2. **Don't forget `set_dependencies()` call in server.py** - The wrapper module will have `config = None` and crash on first tool call.
3. **Don't assume all handlers return dicts** - Some return `list[TextContent]` for custom formatting. Check `server.py` dispatch for special cases before migrating.

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `python -c "import server; from mcptools.registry import registry; print(registry.get_tool_count())"` | Verify all tools register after changes |
| `python -c "import py_compile; py_compile.compile('file.py', doraise=True)"` | Quick syntax check without full import |
| `pytest tests/ -v` | Run test suite (62 tests, <1s) |

## Files Modified

| File | Change |
|------|--------|
| `mcptools/tools/code_changes.py` | NEW - Registry wrappers for 8 tools from request_code_change.py |
| `mcptools/tools/manny_navigation.py` | NEW - Registry wrappers for 18 tools from manny_tools.py |
| `server.py` | Removed 60 lines of imports, 130 lines of Tool() construction, 200 lines of if/elif dispatch. Down from ~668 to ~248 lines. |
