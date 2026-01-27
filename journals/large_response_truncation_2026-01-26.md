# Large MCP Response Truncation - Lessons Learned
**Date:** 2026-01-26

## The Problem

MCP tools like `build_plugin` return responses that fill context quickly (~16k tokens for a failed build). Claude Code warns: "Large MCP response (~16.4k tokens), this can fill up context quickly." This wastes context on data Claude may not need to fully read.

## Root Cause

MCP tools return complete data structures (all errors, full logs, all widgets) even when a summary would suffice. The MCP protocol doesn't have built-in pagination or streaming - each tool call returns everything at once.

Tools affected:
- `build_plugin` - Full Maven error output (10-50KB)
- `get_logs` - Up to 100 log lines at 200+ chars each (5-20KB)
- `query_nearby` - Aggregates NPCs + objects + ground items (5-20KB)
- `find_usages` - All code matches for popular symbols (5-30KB)
- `scan_tile_objects` - Many objects in dense areas (2-10KB)

## Key Lessons

### 1. Write Large Responses to File, Return Summary with Path

**What happened:** `build_plugin` returned all 127 compilation errors inline, consuming 16k tokens.
**Why:** No truncation logic - just dumped the entire error list.
**Solution:**
```python
# BAD - returns everything inline
return {
    "success": False,
    "errors": all_127_errors,  # 16k tokens!
    "warnings": warnings
}

# GOOD - write to file, return summary
from ..utils import maybe_truncate_response

response = {
    "success": False,
    "errors": all_127_errors,
    "warnings": warnings
}
return maybe_truncate_response(response, prefix="build_output")
# Returns: {
#   "truncated": True,
#   "full_output_path": "/tmp/manny_mcp/build_output_1706000000.json",
#   "success": False,
#   "error_count": 127,
#   "errors_preview": [first_3_errors]
# }
```

### 2. Threshold Should Be ~4000 Characters (~1k Tokens)

**What happened:** Initial threshold was too high, still wasting context.
**Why:** 4000 chars is roughly 1000 tokens - enough for summaries, low enough to catch bloat.
**Solution:**
```python
LARGE_RESPONSE_THRESHOLD = 4000  # ~1k tokens

def maybe_truncate_response(data: dict, threshold: int = LARGE_RESPONSE_THRESHOLD, prefix: str = "mcp_response") -> dict:
    serialized = json.dumps(data, indent=2)
    if len(serialized) <= threshold:
        return data  # Small enough, return as-is

    # Write full response to file
    result = large_response_to_file(data, prefix)
    # Add preview fields...
    return result
```

### 3. Preserve Key Summary Fields in Truncated Response

**What happened:** First truncation attempt lost critical info like `success` and `error_count`.
**Why:** Claude needs to know if build failed without reading the full file.
**Solution:**
```python
# Include key summary fields if they exist
if isinstance(data, dict):
    for key in ["success", "return_code", "build_time_seconds"]:
        if key in data:
            result[key] = data[key]

    # Include error count + preview (first few)
    if "errors" in data and isinstance(data["errors"], list):
        result["error_count"] = len(data["errors"])
        result["errors_preview"] = data["errors"][:3]
```

## Anti-Patterns

1. **Don't** return full data inline expecting Claude to "skim" - Claude reads everything, wasting context
2. **Don't** truncate without providing file path - Claude needs access to full data when needed
3. **Don't** forget preview fields - Claude needs enough info to decide if it needs the full file

## Files Modified

| File | Change |
|------|--------|
| `mcptools/utils.py` | Added `large_response_to_file()` and `maybe_truncate_response()` |
| `mcptools/tools/core.py` | `build_plugin` uses truncation |
| `mcptools/tools/monitoring.py` | `get_logs` uses truncation |
| `mcptools/tools/routine.py` | `query_nearby`, `scan_tile_objects` use truncation |
| `mcptools/tools/code_intelligence.py` | `find_usages` uses truncation |
| `mcptools/tools/testing.py` | `run_tests` uses truncation |

## Interface Pattern Established

```
┌─────────────────┐     Small response     ┌─────────────────┐
│   MCP Tool      │ ───────────────────── │   Claude        │
│                 │     (<4k chars)        │                 │
└─────────────────┘                        └─────────────────┘

┌─────────────────┐     Truncated summary  ┌─────────────────┐
│   MCP Tool      │ ───────────────────── │   Claude        │
│                 │     + file path        │                 │
└────────┬────────┘                        └────────┬────────┘
         │                                          │
         │ Write full data                          │ Read if needed
         ▼                                          ▼
┌─────────────────────────────────────────────────────────────┐
│              /tmp/manny_mcp/<prefix>_<timestamp>.json       │
└─────────────────────────────────────────────────────────────┘
```

## Related Discovery: Discord Bot Tool Subset

While investigating, discovered the Discord bot (`discord_bot/llm_client.py`) uses a separate curated **20-tool subset** (was 16, added 4), not the full 71-tool MCP server. This is intentional for smaller LLMs like Qwen 2.5 14B.

Added missing tools that improve reliability:
- `send_and_await` - Verified command execution (waits for condition)
- `query_nearby` - Discovery without hardcoded knowledge
- `get_dialogue` - Quest/NPC conversation handling
- `click_text` - Dialogue option clicking
