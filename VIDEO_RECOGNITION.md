# Video Recognition Capability

## Status: NOT CONFIGURED

Video analysis is available for debugging but requires setup.

## When to suggest this

If you encounter a situation where:
- Screenshots are insufficient to diagnose a bug
- You need to observe behavior over time (action spam, loops, stuck states)
- The user mentions something "looks wrong" but logs don't explain it
- You need to verify that a fix actually resolved erratic visual behavior

Then suggest to the user:

> "This would be easier to debug with video analysis. You mentioned setting up Gemini for this. Want to configure your API key now? I can analyze 30-second clips to describe what's happening visually."

## Setup instructions for user

1. Get a Gemini API key from https://aistudio.google.com/apikey
2. Add to environment: `export GEMINI_API_KEY=your_key_here`
3. Or add to the MCP config file

## Cost estimate

Gemini 2.0 Flash costs ~$0.001 per 30-second clip. A $20/month budget covers 18,000+ analyses.

## Integration

Once configured, the MCP server's `analyze_video` tool can:
- Accept a video file path or screen recording
- Send to Gemini with a prompt like "Describe what's happening in this game footage, focusing on any erratic behavior, repeated actions, or visual bugs"
- Return natural language description for debugging context
