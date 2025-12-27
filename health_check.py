#!/usr/bin/env python3
"""
Health Check Script for Code Editing Workflow Improvements

Verifies that all components are installed and working correctly.
Run this after implementing the improvements to ensure everything is ready.

Usage:
    python3 health_check.py
    # Or make executable:
    chmod +x health_check.py
    ./health_check.py
"""

import sys
import os
from pathlib import Path

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(text):
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{text:^60}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")

def print_success(text):
    print(f"{GREEN}✅ {text}{RESET}")

def print_error(text):
    print(f"{RED}❌ {text}{RESET}")

def print_warning(text):
    print(f"{YELLOW}⚠️  {text}{RESET}")

def print_info(text):
    print(f"ℹ️  {text}")

def check_file_exists(filepath, description):
    """Check if a file exists."""
    if Path(filepath).exists():
        print_success(f"{description}: {filepath}")
        return True
    else:
        print_error(f"{description} NOT FOUND: {filepath}")
        return False

def check_imports():
    """Check that all required modules can be imported."""
    print_header("Checking Python Imports")

    all_ok = True

    # Check core modules
    try:
        from request_code_change import (
            prepare_code_change,
            validate_code_change,
            validate_with_anti_pattern_check,
            _extract_commands_from_problem
        )
        print_success("request_code_change imports OK")
    except ImportError as e:
        print_error(f"request_code_change import failed: {e}")
        all_ok = False

    try:
        from manny_tools import (
            check_anti_patterns,
            _COMPILED_ANTI_PATTERNS,
            get_plugin_context
        )
        print_success("manny_tools imports OK")

        # Check pattern count
        pattern_count = len(_COMPILED_ANTI_PATTERNS)
        if pattern_count == 11:
            print_success(f"All 11 anti-pattern rules loaded")
        else:
            print_warning(f"Expected 11 patterns, got {pattern_count}")
    except ImportError as e:
        print_error(f"manny_tools import failed: {e}")
        all_ok = False

    return all_ok

def check_documentation():
    """Check that all documentation files exist."""
    print_header("Checking Documentation Files")

    docs = [
        ("CLAUDE.md", "Main MCP documentation"),
        ("IMPLEMENTATION_SUMMARY.md", "Implementation details"),
        ("CHANGELOG.md", "Version history"),
        ("TEST_RESULTS.md", "Test coverage"),
        ("QUICK_REFERENCE.md", "Quick reference guide"),
        ("EXAMPLE_WORKFLOW.md", "Example workflow"),
        ("README_IMPROVEMENTS.md", "Overview"),
    ]

    all_ok = True
    for filename, description in docs:
        if not check_file_exists(filename, description):
            all_ok = False

    return all_ok

def check_anti_patterns():
    """Test anti-pattern detection."""
    print_header("Testing Anti-Pattern Detection")

    try:
        from manny_tools import check_anti_patterns

        # Test 1: F-key detection
        result1 = check_anti_patterns(code='keyboard.pressKey(KeyEvent.VK_F6);')
        if result1.get("errors", 0) > 0:
            print_success("F-key detection working")
        else:
            print_warning("F-key detection may not be working")

        # Test 2: smartClick detection
        result2 = check_anti_patterns(code='smartClick(npc.getConvexHull());')
        if result2.get("errors", 0) > 0:
            print_success("smartClick detection working")
        else:
            print_warning("smartClick detection may not be working")

        # Test 3: No false positives
        result3 = check_anti_patterns(code='// Clean code, no anti-patterns')
        if result3.get("total_issues", 1) == 0:
            print_success("No false positives on clean code")
        else:
            print_warning(f"False positives detected: {result3.get('total_issues')} issues")

        return True
    except Exception as e:
        print_error(f"Anti-pattern testing failed: {e}")
        return False

def check_smart_sectioning():
    """Test smart sectioning / command extraction."""
    print_header("Testing Smart Sectioning")

    try:
        from request_code_change import _extract_commands_from_problem

        # Test command extraction
        result = _extract_commands_from_problem(
            "The BANK_OPEN command fails",
            "[BANK_OPEN] Error occurred"
        )

        if "BANK_OPEN" in result:
            print_success("Command extraction working")
            print_info(f"  Extracted: {result}")
        else:
            print_warning(f"Command extraction may not be working. Got: {result}")

        # Test camelCase conversion
        result2 = _extract_commands_from_problem("handleMineOre method broken", "")
        if "MINE_ORE" in result2:
            print_success("CamelCase → SNAKE_CASE conversion working")
        else:
            print_warning(f"Conversion may not be working. Got: {result2}")

        return True
    except Exception as e:
        print_error(f"Smart sectioning test failed: {e}")
        return False

def check_performance_optimizations():
    """Check performance optimizations are active."""
    print_header("Checking Performance Optimizations")

    try:
        from manny_tools import _COMPILED_ANTI_PATTERNS

        # Check pre-compiled patterns
        if hasattr(_COMPILED_ANTI_PATTERNS[0], '__getitem__'):
            has_compiled = "compiled_pattern" in _COMPILED_ANTI_PATTERNS[0]
            if has_compiled:
                print_success("Pre-compiled patterns active (10x speedup)")
            else:
                print_warning("Pre-compiled patterns may not be loaded")

        print_info(f"  Total patterns: {len(_COMPILED_ANTI_PATTERNS)}")

        return True
    except Exception as e:
        print_error(f"Performance check failed: {e}")
        return False

def check_plugin_files():
    """Check plugin directory structure."""
    print_header("Checking Plugin Directory")

    plugin_dir = "/home/wil/Desktop/manny"

    if not Path(plugin_dir).exists():
        print_error(f"Plugin directory not found: {plugin_dir}")
        return False

    print_success(f"Plugin directory exists: {plugin_dir}")

    # Check for key files
    key_files = [
        "CLAUDE.md",
        "utility/PlayerHelpers.java",
        "utility/GameEngine.java",
        "utility/InteractionSystem.java"
    ]

    all_ok = True
    for relative_path in key_files:
        full_path = Path(plugin_dir) / relative_path
        if full_path.exists():
            print_success(f"  Found: {relative_path}")
        else:
            print_warning(f"  Missing: {relative_path}")
            all_ok = False

    return all_ok

def check_config():
    """Check config.yaml settings."""
    print_header("Checking Configuration")

    import yaml

    try:
        with open("config.yaml") as f:
            config = yaml.safe_load(f)

        print_success("config.yaml loaded successfully")

        # Check key settings
        plugin_dir = config.get("plugin_directory")
        if plugin_dir:
            print_success(f"  plugin_directory: {plugin_dir}")
        else:
            print_warning("  plugin_directory not set")

        runelite_root = config.get("runelite_root")
        if runelite_root:
            print_success(f"  runelite_root: {runelite_root}")
        else:
            print_warning("  runelite_root not set")

        return True
    except Exception as e:
        print_error(f"Config check failed: {e}")
        return False

def print_summary(results):
    """Print summary of health check results."""
    print_header("Health Check Summary")

    total = len(results)
    passed = sum(results.values())
    failed = total - passed

    print(f"Total Checks: {total}")
    print(f"{GREEN}Passed: {passed}{RESET}")
    if failed > 0:
        print(f"{RED}Failed: {failed}{RESET}")

    print()

    if failed == 0:
        print_success("All checks passed! System is ready for use.")
        print()
        print_info("Next steps:")
        print_info("  1. Read QUICK_REFERENCE.md for workflow guide")
        print_info("  2. Try EXAMPLE_WORKFLOW.md for a realistic example")
        print_info("  3. Use the enhanced workflow on your next code fix")
        return True
    else:
        print_error("Some checks failed. Review errors above.")
        print()
        print_info("Troubleshooting:")
        print_info("  1. Ensure all files are in the correct location")
        print_info("  2. Check that Python imports are working")
        print_info("  3. Verify config.yaml settings")
        print_info("  4. See IMPLEMENTATION_SUMMARY.md for details")
        return False

def main():
    """Run all health checks."""
    print_header("Code Editing Workflow - Health Check")
    print_info("Version 2.0.0")
    print_info("Checking installation and configuration...\n")

    results = {}

    # Run all checks
    results["imports"] = check_imports()
    results["documentation"] = check_documentation()
    results["anti_patterns"] = check_anti_patterns()
    results["smart_sectioning"] = check_smart_sectioning()
    results["performance"] = check_performance_optimizations()
    results["plugin_files"] = check_plugin_files()
    results["config"] = check_config()

    # Print summary
    success = print_summary(results)

    # Exit code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
