# Smart Widget Scan

Scan the game UI and extract structured information using Haiku.

## Instructions

1. Call the `scan_widgets` MCP tool to get raw widget data
2. Spawn a Haiku subagent to parse the results:

```
Task(
    prompt=f"""Analyze these OSRS UI widgets. Extract:

1. **Dialogue options** - clickable text choices (not "Click here to continue")
2. **Continue button** - is "Click here to continue" present?
3. **NPC/Speaker text** - what is being said in dialogue
4. **Bank interface** - is bank open? any visible buttons?
5. **Notable UI elements** - quest text, warnings, important buttons

Return JSON:
{{
  "dialogue_options": ["option1", "option2"] or [],
  "has_continue": true/false,
  "speaker_text": "what NPC is saying" or null,
  "bank_open": true/false,
  "notable": ["any other important UI elements"]
}}

Widget data:
{widgets}""",
    subagent_type="general-purpose",
    model="haiku"
)
```

3. Report the structured result to the user
