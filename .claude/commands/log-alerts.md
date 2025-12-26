# Log Alerts

Summarize recent logs and extract only actionable issues using Haiku.

## Instructions

1. Call `get_logs(level="ALL", since_seconds=60, max_lines=100)` MCP tool
2. Spawn a Haiku subagent to filter noise:

```
Task(
    prompt=f"""Analyze these OSRS bot logs. Extract ONLY actionable issues:
- Errors and exceptions (ERROR level or stack traces)
- Stuck/failed patterns ("stuck", "failed", "timeout", "not found")
- Unexpected states or crashes

IGNORE: INFO messages, routine progress, expected retries (2/3, 3/3), normal fishing/banking

Return JSON:
{{
  "alerts": [
    {{"severity": "error", "summary": "brief description"}},
    {{"severity": "warn", "summary": "brief description"}}
  ],
  "summary": "one line overall status"
}}

If no issues: {{"alerts": [], "summary": "Operating normally"}}

Logs:
{logs}""",
    subagent_type="general-purpose",
    model="haiku"
)
```

3. Report alerts to the user (or "Operating normally" if no issues)
