#!/usr/bin/env python3
"""
Test how context fragments affect LLM reasoning.

This script validates that the smart context architecture improves LLM decision-making
by comparing responses with and without context injection.

Usage:
    # Run all tests against your LLM server
    ./venv/bin/python discord_bot/test_context_effectiveness.py

    # Run specific domain tests
    ./venv/bin/python discord_bot/test_context_effectiveness.py --domain skilling

    # Verbose output (show full responses)
    ./venv/bin/python discord_bot/test_context_effectiveness.py -v

    # Compare with/without context
    ./venv/bin/python discord_bot/test_context_effectiveness.py --compare

Environment:
    OLLAMA_HOST: Your LLM server (e.g., http://10.0.0.99:11434)
    OLLAMA_MODEL: Model to test (e.g., hermes3:8b)
"""

import asyncio
import json
import os
import sys
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import aiohttp

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from activity_classifier import classify_activity, get_context_fragment
from models import ActionDecision

# LLM Configuration
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://10.0.0.99:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "hermes3:8b")


@dataclass
class TestCase:
    """A single test case for context effectiveness."""
    message: str
    domain: str
    expected_tools: List[str]  # Tools that SHOULD be called
    bad_tools: List[str] = field(default_factory=list)  # Tools that should NOT be called
    expected_commands: List[str] = field(default_factory=list)  # Command patterns to find
    description: str = ""


@dataclass
class TestResult:
    """Result of running a test case."""
    test: TestCase
    with_context: bool
    response: str
    tools_called: List[str]
    commands_found: List[str]
    passed: bool
    issues: List[str]
    raw_response: dict = None


# Test cases organized by domain
TEST_CASES = [
    # === SKILLING ===
    TestCase(
        message="Start fishing raw shrimps",
        domain="skilling",
        expected_tools=["send_command", "query_nearby"],
        bad_tools=["scan_tile_objects"],  # Should NOT scan for fishing net
        expected_commands=["FISH", "INTERACT_NPC.*Fishing"],
        description="Should use FISH command or INTERACT_NPC on fishing spot, NOT scan for nets"
    ),
    TestCase(
        message="I want to fish some lobsters",
        domain="skilling",
        expected_tools=["send_command"],
        expected_commands=["FISH.*lobster", "INTERACT_NPC.*Fishing.*Cage"],
        description="Should know lobster fishing uses Cage action"
    ),
    TestCase(
        message="Pick up the fishing net on the ground",
        domain="interaction",
        expected_tools=["scan_tile_objects", "send_command"],
        expected_commands=["INTERACT_OBJECT.*fishing.*net.*Take", "PICK_UP"],
        description="Static spawns are GameObjects - use scan_tile_objects"
    ),

    # === COMBAT ===
    TestCase(
        message="Kill 100 giant frogs",
        domain="combat",
        expected_tools=["send_command"],
        expected_commands=["KILL_LOOP.*Giant_frog.*100", "KILL_LOOP.*frog"],
        description="Should use KILL_LOOP with underscore in name"
    ),
    TestCase(
        message="Attack the hill giants nearby",
        domain="combat",
        expected_tools=["send_command", "query_nearby"],
        expected_commands=["KILL_LOOP.*Hill_Giant", "ATTACK_NPC.*Hill"],
        description="Should use underscore for multi-word NPC names"
    ),
    TestCase(
        message="Switch to aggressive combat style",
        domain="combat",
        expected_tools=["send_command"],
        expected_commands=["SWITCH_COMBAT_STYLE.*aggressive", "SWITCH_COMBAT_STYLE.*1"],
        description="Should use SWITCH_COMBAT_STYLE command"
    ),

    # === NAVIGATION ===
    TestCase(
        message="Go to Draynor bank",
        domain="navigation",
        expected_tools=["send_command", "lookup_location"],
        expected_commands=["GOTO.*3092.*3245", "GOTO.*draynor"],
        description="Should use GOTO with coordinates or lookup_location"
    ),
    TestCase(
        message="Teleport home to Lumbridge",
        domain="navigation",
        expected_tools=["send_command", "teleport_home"],
        expected_commands=["HOME_TELEPORT", "TELEPORT"],
        description="Should use home teleport command"
    ),

    # === BANKING ===
    TestCase(
        message="Open the bank and deposit everything",
        domain="banking",
        expected_tools=["send_command"],
        expected_commands=["BANK_OPEN", "BANK_DEPOSIT_ALL", "DEPOSIT"],
        description="Should use BANK_OPEN then BANK_DEPOSIT_ALL"
    ),
    TestCase(
        message="Withdraw 100 lobsters from bank",
        domain="banking",
        expected_tools=["send_command"],
        expected_commands=["BANK_WITHDRAW.*lobster.*100", "BANK_WITHDRAW.*100.*lobster"],
        description="Should use BANK_WITHDRAW with item name and quantity"
    ),

    # === INTERACTION ===
    TestCase(
        message="Talk to the banker",
        domain="interaction",
        expected_tools=["send_command", "query_nearby"],
        expected_commands=["INTERACT_NPC.*Banker.*Talk", "TALK.*Banker"],
        description="Bankers are NPCs - use INTERACT_NPC"
    ),
    TestCase(
        message="Open the large door",
        domain="interaction",
        expected_tools=["send_command", "scan_tile_objects"],
        expected_commands=["INTERACT_OBJECT.*Large_door.*Open", "INTERACT_OBJECT.*door"],
        description="Doors are Objects - use underscore for multi-word names"
    ),
]


async def query_llm(
    message: str,
    system_prompt: str,
    tools: List[dict] = None
) -> Tuple[str, List[str], dict]:
    """
    Send a message to the LLM and get response with tool calls.

    Returns: (response_text, tools_called, raw_response)
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message}
    ]

    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.1}  # Low temp for consistency
    }

    if tools:
        payload["tools"] = tools

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{OLLAMA_HOST}/api/chat",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                if resp.status != 200:
                    return f"ERROR: {resp.status}", [], {}

                result = await resp.json()

                response_text = result.get("message", {}).get("content", "")
                tool_calls = result.get("message", {}).get("tool_calls", [])

                tools_called = []
                for tc in tool_calls:
                    func = tc.get("function", {})
                    name = func.get("name", "unknown")
                    args = func.get("arguments", {})
                    tools_called.append(f"{name}({json.dumps(args)})")

                return response_text, tools_called, result

    except Exception as e:
        return f"ERROR: {e}", [], {}


def get_base_system_prompt() -> str:
    """Get the base CONTEXT.md without any fragments."""
    context_path = Path(__file__).parent / "CONTEXT.md"
    if context_path.exists():
        return context_path.read_text()
    return "You are an OSRS bot assistant. Help the user with their request."


def get_system_prompt_with_context(message: str) -> str:
    """Get system prompt with appropriate context fragment injected."""
    base = get_base_system_prompt()

    domain = classify_activity(message)
    if domain:
        fragment = get_context_fragment(domain)
        if fragment:
            return f"{base}\n\n## {domain.title()} Context\n{fragment}"

    return base


def get_mock_tools() -> List[dict]:
    """Get simplified tool definitions for testing."""
    return [
        {
            "type": "function",
            "function": {
                "name": "send_command",
                "description": "Send a command to the game plugin",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string", "description": "The command to send"}
                    },
                    "required": ["command"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "query_nearby",
                "description": "Query nearby NPCs, objects, and ground items",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "include_npcs": {"type": "boolean"},
                        "include_objects": {"type": "boolean"},
                        "include_ground_items": {"type": "boolean"},
                        "name_filter": {"type": "string"}
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "scan_tile_objects",
                "description": "Scan for tile objects by name (for static spawns)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "object_name": {"type": "string"}
                    },
                    "required": ["object_name"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_game_state",
                "description": "Get current game state",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "fields": {"type": "array", "items": {"type": "string"}}
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "lookup_location",
                "description": "Look up coordinates for a named location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"}
                    },
                    "required": ["location"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "teleport_home",
                "description": "Cast home teleport spell",
                "parameters": {"type": "object", "properties": {}}
            }
        }
    ]


import re

def evaluate_result(
    test: TestCase,
    response: str,
    tools_called: List[str],
    with_context: bool
) -> TestResult:
    """Evaluate if the LLM response meets expectations."""
    issues = []

    # Extract commands from tool calls
    commands_found = []
    for tool_call in tools_called:
        if "send_command" in tool_call:
            # Extract command from send_command({"command": "..."})
            match = re.search(r'"command":\s*"([^"]+)"', tool_call)
            if match:
                commands_found.append(match.group(1))

    # Also check response text for commands (LLM might describe them)
    for cmd_pattern in test.expected_commands:
        if re.search(cmd_pattern, response, re.IGNORECASE):
            commands_found.append(f"(in text: {cmd_pattern})")

    # Check for expected tools
    tools_used = [t.split("(")[0] for t in tools_called]
    for expected in test.expected_tools:
        if not any(expected in t for t in tools_used):
            # Not a hard failure - might be in response text
            pass

    # Check for bad tools (should NOT be used)
    for bad in test.bad_tools:
        if any(bad in t for t in tools_used):
            issues.append(f"Used bad tool: {bad}")

    # Check for expected commands
    found_expected_cmd = False
    for cmd_pattern in test.expected_commands:
        for cmd in commands_found:
            if re.search(cmd_pattern, cmd, re.IGNORECASE):
                found_expected_cmd = True
                break
        if found_expected_cmd:
            break

    if not found_expected_cmd and test.expected_commands:
        issues.append(f"Missing expected command pattern: {test.expected_commands}")

    passed = len(issues) == 0

    return TestResult(
        test=test,
        with_context=with_context,
        response=response,
        tools_called=tools_called,
        commands_found=commands_found,
        passed=passed,
        issues=issues
    )


async def run_test(test: TestCase, with_context: bool, tools: List[dict]) -> TestResult:
    """Run a single test case."""
    if with_context:
        system_prompt = get_system_prompt_with_context(test.message)
    else:
        system_prompt = get_base_system_prompt()

    response, tools_called, raw = await query_llm(test.message, system_prompt, tools)

    result = evaluate_result(test, response, tools_called, with_context)
    result.raw_response = raw

    return result


async def run_all_tests(
    domain_filter: str = None,
    compare_mode: bool = False,
    verbose: bool = False
) -> Dict[str, List[TestResult]]:
    """Run all tests and return results."""
    tools = get_mock_tools()
    results = {"with_context": [], "without_context": []}

    # Filter tests by domain if specified
    tests = TEST_CASES
    if domain_filter:
        tests = [t for t in tests if t.domain == domain_filter]

    print(f"\n{'='*60}")
    print(f"Context Effectiveness Test Suite")
    print(f"LLM: {OLLAMA_HOST} / {OLLAMA_MODEL}")
    print(f"Tests: {len(tests)}")
    print(f"{'='*60}\n")

    for test in tests:
        print(f"\n--- Test: {test.message[:50]}... ---")
        print(f"Domain: {test.domain} | {test.description}")

        # Test WITH context
        result_with = await run_test(test, with_context=True, tools=tools)
        results["with_context"].append(result_with)

        status = "✅ PASS" if result_with.passed else "❌ FAIL"
        print(f"  With context:    {status}")
        if verbose or not result_with.passed:
            print(f"    Tools: {result_with.tools_called[:3]}")
            print(f"    Commands: {result_with.commands_found}")
            if result_with.issues:
                print(f"    Issues: {result_with.issues}")

        # Test WITHOUT context (comparison mode)
        if compare_mode:
            result_without = await run_test(test, with_context=False, tools=tools)
            results["without_context"].append(result_without)

            status = "✅ PASS" if result_without.passed else "❌ FAIL"
            print(f"  Without context: {status}")
            if verbose or not result_without.passed:
                print(f"    Tools: {result_without.tools_called[:3]}")
                if result_without.issues:
                    print(f"    Issues: {result_without.issues}")

    return results


def print_summary(results: Dict[str, List[TestResult]], compare_mode: bool):
    """Print test summary."""
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")

    with_ctx = results["with_context"]
    passed_with = sum(1 for r in with_ctx if r.passed)

    print(f"\nWith Context: {passed_with}/{len(with_ctx)} passed ({100*passed_with/len(with_ctx):.0f}%)")

    if compare_mode and results["without_context"]:
        without_ctx = results["without_context"]
        passed_without = sum(1 for r in without_ctx if r.passed)
        print(f"Without Context: {passed_without}/{len(without_ctx)} passed ({100*passed_without/len(without_ctx):.0f}%)")

        improvement = passed_with - passed_without
        print(f"\nContext Improvement: {'+' if improvement >= 0 else ''}{improvement} tests")

    # Show failures
    failures = [r for r in with_ctx if not r.passed]
    if failures:
        print(f"\n--- Failures ({len(failures)}) ---")
        for f in failures:
            print(f"  • {f.test.message[:40]}...")
            print(f"    Expected: {f.test.expected_commands}")
            print(f"    Got: {f.commands_found}")
            print(f"    Issues: {f.issues}")


async def main():
    parser = argparse.ArgumentParser(description="Test context fragment effectiveness")
    parser.add_argument("--domain", "-d", help="Test only specific domain (skilling, combat, etc.)")
    parser.add_argument("--compare", "-c", action="store_true", help="Compare with/without context")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    parser.add_argument("--list", "-l", action="store_true", help="List all test cases")

    args = parser.parse_args()

    if args.list:
        print("Available test cases:")
        for t in TEST_CASES:
            print(f"  [{t.domain}] {t.message}")
        return

    results = await run_all_tests(
        domain_filter=args.domain,
        compare_mode=args.compare,
        verbose=args.verbose
    )

    print_summary(results, args.compare)


if __name__ == "__main__":
    asyncio.run(main())
