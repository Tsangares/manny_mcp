# Model Comparison for Discord Bot Reasoning

**Date:** 2026-01-23
**Hardware:** RTX 3060 + 3060 Ti (20GB combined VRAM)
**Purpose:** Find the best local LLM for agentic game control reasoning

## Summary

**Winner: `qwen2.5:14b`** - Best balance of reasoning ability and reliability.

## Test Methodology

Used the test harness (`discord_bot/test_harness.py`) with mock MCP tools to evaluate:
1. Prerequisite checking (does it notice missing items?)
2. Emergency handling (does it stop when health is critical?)
3. Multi-step task planning
4. Command accuracy

## Models Tested

| Model | Size | VRAM | Speed |
|-------|------|------|-------|
| hermes3:8b | 8B | ~5GB | ~10s |
| qwen2.5:14b | 14B | ~9GB | ~15s |
| qwen3:14b | 14B | ~9GB | ~20s |
| mistral-nemo:12b | 12B | ~7GB | ~12s |
| llama3.1:8b | 8B | ~5GB | ~12s |
| llama3-groq-tool-use:8b | 8B | ~5GB | ~10s |
| qwen2.5-coder:14b | 14B | ~9GB | ~15s |
| Salesforce xLAM:8b | 8B | ~5GB | ~12s |

## Critical Test Results

### Test 1: Prerequisite Checking
**Message:** "Start cutting trees, you will need to find an axe"
**Scenario:** Default (inventory has Bronze sword, shield, coins, bread, logs - NO AXE)

| Model | Result | Behavior |
|-------|--------|----------|
| **qwen2.5:14b** | **PASS** | "You don't have an axe. Please equip one." (0 commands) |
| qwen3:14b | PARTIAL | Tried to BANK_WITHDRAW Bronze axe (assumes bank has one) |
| mistral-nemo:12b | PARTIAL | Tried lookup_location("axe shop"), got confused |
| hermes3:8b | FAIL | "Started chopping with Bronze axe" (hallucinated) |
| llama3.1:8b | PARTIAL | Tried to BUY AXE (good intent, wrong command) |
| llama3-groq-tool-use:8b | FAIL | Started chopping immediately |

**Key Insight:** Only qwen2.5:14b correctly identified the missing prerequisite and informed the user instead of proceeding blindly.

### Test 2: Emergency Handling
**Message:** "I'm dying!"
**Scenario:** low_health (5 HP, in combat with frogs)

| Model | Result | Behavior |
|-------|--------|----------|
| **qwen2.5:14b** | **PASS** | Sent STOP, advised to flee/heal |
| qwen3:14b | FAIL | Chinese output (?!), tried to bank for food |
| mistral-nemo:12b | UNCLEAR | 0 commands (too cautious?) |
| hermes3:8b | FAIL | Started KILL_LOOP (kept fighting at 5 HP!) |

**Key Insight:** qwen2.5:14b recognized the emergency and took defensive action. Others either continued dangerous activity or froze.

### Test 3: Batch Task Tests

#### Train Combat
**Message:** "Go kill chickens to get your stats up to 15 in att, str, def"

| Model | Commands | Notes |
|-------|----------|-------|
| qwen2.5:14b | KILL_LOOP Chicken none 100 | Correct |
| qwen3:14b | KILL_LOOP Chicken none 100 | Correct |
| mistral-nemo:12b | (none) | Failed to act |

#### Bank Deposit
**Message:** "Can you go deposit all your items in the bank"

| Model | Commands | Notes |
|-------|----------|-------|
| qwen2.5:14b | GOTO bank, BANK_OPEN, BANK_DEPOSIT_ALL | Complete sequence |
| qwen3:14b | BANK_DEPOSIT_ALL | Skipped travel (assumed at bank?) |
| mistral-nemo:12b | BANK_OPEN, BANK_DEPOSIT_ALL | Good |

#### Fish Shrimp (has net)
**Message:** "Can you fish shrimp; you have a net already."

| Model | Commands | Notes |
|-------|----------|-------|
| qwen2.5:14b | FISH | Simple and correct |
| qwen3:14b | FISH_DRAYNOR_LOOP | Used loop variant (also correct) |
| mistral-nemo:12b | GOTO wrong coords | Typo in coordinates |

#### Woodcutting + Firemaking
**Message:** "Can you start cutting trees and lighting fires"

| Model | Commands | Notes |
|-------|----------|-------|
| qwen2.5:14b | CHOP_TREE, INTERACT_OBJECT Fire | Didn't check for axe! |
| qwen3:14b | BANK_WITHDRAW Axe Tinderbox, CHOP_TREE | Tried to get prereqs |
| mistral-nemo:12b | (none) | Failed to act |

#### Multi-Step Quest
**Message:** "Go kill goblins for coins then buy a tinderbox"

| Model | Commands | Notes |
|-------|----------|-------|
| qwen2.5:14b | KILL_LOOP Goblin, BANK_WITHDRAW Tinderbox | Wrong (bank != shop) |
| qwen3:14b | GOTO goblins, KILL_LOOP, GOTO store, INTERACT_NPC Shopkeeper Buy | Better planning |
| mistral-nemo:12b | (none) | Failed to act |

## Final Rankings

| Rank | Model | Reasoning | Reliability | Multi-Step | Overall |
|------|-------|-----------|-------------|------------|---------|
| **1** | **qwen2.5:14b** | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | Best overall |
| 2 | qwen3:14b | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | Better at complex tasks |
| 3 | mistral-nemo:12b | ⭐⭐ | ⭐ | ⭐ | Too cautious, often fails to act |
| 4 | llama3.1:8b | ⭐⭐ | ⭐ | ⭐ | Good intent, bad execution |
| 5 | hermes3:8b | ⭐ | ⭐⭐ | ⭐ | Fast but hallucinates |
| 6+ | Others | ⭐ | ⭐ | ⭐ | Not recommended |

## Key Findings

### 1. Model Size > Tool-Use Fine-Tuning
The tool-use fine-tuned models (llama3-groq-tool-use, Salesforce xLAM) performed poorly. They're optimized for *calling* tools correctly, not *reasoning about when* to call them.

### 2. 14B is the Sweet Spot
- 8B models lack reasoning depth
- 14B models fit in 20GB VRAM with room to spare
- 32B models are too slow for interactive Discord use

### 3. qwen2.5:14b vs qwen3:14b Trade-off
- **qwen2.5:14b**: Better at recognizing when NOT to act (prerequisites, emergencies)
- **qwen3:14b**: Better at complex multi-step planning, but sometimes over-assumes

### 4. Speed vs Quality
| Model | Speed | Quality |
|-------|-------|---------|
| hermes3:8b | ~10s | Low |
| qwen2.5:14b | ~15s | High |
| qwen3:14b | ~20s | Medium-High |

The 5-second difference between qwen2.5:14b and hermes3:8b is worth it for correct behavior.

## Recommendations

1. **Set `qwen2.5:14b` as default** - best reasoning, acceptable speed
2. **Keep `qwen3:14b` available** for complex multi-step tasks that need planning
3. **Improve system prompt** for edge cases (woodcutting test 4 - qwen2.5 didn't check for axe when not explicitly mentioned)
4. **Add prerequisite hints to commands** - help models reason about requirements

## Test Cases for Regression

Saved in `discord_bot/test_cases.yaml`:
- `woodcutting_no_axe` - prerequisite checking
- `low_health_emergency` - emergency handling
- `train_combat` - basic combat loop
- `bank_deposit` - multi-step banking
- `fish_shrimp` - action with prerequisites met
- `woodcutting_firemaking` - implicit prerequisites
- `multi_step_quest` - complex planning

## Next Steps

1. Update default model in `.env` and `llm_client.py`
2. Consider queryable skill contexts for prerequisite info
3. Add more test cases as issues are discovered
4. Fine-tune on successful interactions (training data being collected)
