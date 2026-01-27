"""
Testing tools for manny plugin development.

Provides test execution, coverage analysis, and test generation.
"""

import subprocess
import re
from pathlib import Path
from typing import Optional
from mcp.types import Tool, TextContent

from ..config import ServerConfig
from ..registry import registry
from ..path_utils import normalize_path, to_symlink_path
from ..utils import maybe_truncate_response


# =============================================================================
# RUN_TESTS
# =============================================================================

def run_tests_impl(pattern: Optional[str] = None, timeout: int = 60, plugin_dir: str = None) -> dict:
    """
    Execute Maven tests for the manny plugin.

    Args:
        pattern: Test class pattern (e.g., "**/PathingTest.java", "PathingManagerTest")
        timeout: Test timeout in seconds (default: 60)
        plugin_dir: Path to manny plugin directory

    Returns:
        {
            "success": bool,
            "tests_run": int,
            "failures": int,
            "errors": int,
            "skipped": int,
            "time": float,
            "output": str,
            "failed_tests": [{"test": str, "error": str}]
        }
    """
    if plugin_dir is None:
        config = ServerConfig.load()
        plugin_dir = str(config.plugin_directory)
        runelite_root = str(config.runelite_root)
    else:
        plugin_dir = str(plugin_dir)
        # Assume runelite_root is parent of plugin_dir
        runelite_root = str(Path(plugin_dir).parent.parent)

    # Build Maven command
    cmd = ["mvn", "test", "-pl", "runelite-client"]

    if pattern:
        # Convert pattern to Maven test format
        if pattern.endswith(".java"):
            pattern = pattern.replace(".java", "")
        if "/" in pattern or "\\" in pattern:
            # Extract class name from path
            pattern = Path(pattern).stem

        cmd.extend(["-Dtest=" + pattern])

    # Run tests
    try:
        result = subprocess.run(
            cmd,
            cwd=runelite_root,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        output = result.stdout + "\n" + result.stderr

        # Parse Maven output
        tests_run = 0
        failures = 0
        errors = 0
        skipped = 0
        time_taken = 0.0

        # Look for test summary line
        # Example: Tests run: 5, Failures: 1, Errors: 0, Skipped: 0, Time elapsed: 2.345 s
        summary_match = re.search(
            r'Tests run: (\d+), Failures: (\d+), Errors: (\d+), Skipped: (\d+)(?:, Time elapsed: ([\d.]+))?',
            output
        )

        if summary_match:
            tests_run = int(summary_match.group(1))
            failures = int(summary_match.group(2))
            errors = int(summary_match.group(3))
            skipped = int(summary_match.group(4))
            if summary_match.group(5):
                time_taken = float(summary_match.group(5))

        # Extract failed test details
        failed_tests = []
        failure_pattern = r'(\w+)\s+Time elapsed.*FAILURE!'
        for match in re.finditer(failure_pattern, output):
            test_name = match.group(1)

            # Try to extract error message (next few lines after FAILURE!)
            error_start = match.end()
            error_end = output.find('\n\n', error_start)
            error_msg = output[error_start:error_end].strip() if error_end > error_start else "See output"

            failed_tests.append({
                "test": test_name,
                "error": error_msg[:500]  # Limit error message length
            })

        success = (failures == 0 and errors == 0 and result.returncode == 0)

        return {
            "success": success,
            "tests_run": tests_run,
            "failures": failures,
            "errors": errors,
            "skipped": skipped,
            "time": time_taken,
            "output": output[-5000:],  # Last 5000 chars
            "failed_tests": failed_tests,
            "pattern": pattern
        }

    except subprocess.TimeoutExpired:
        return {
            "error": f"Test execution timed out after {timeout} seconds",
            "pattern": pattern,
            "success": False
        }

    except Exception as e:
        return {
            "error": f"Test execution failed: {e}",
            "pattern": pattern,
            "success": False
        }


@registry.tool(
    name="run_tests",
    description=(
        "Execute Maven tests for the manny plugin.\n\n"
        "Examples:\n"
        "- run_tests() - Run all tests\n"
        "- run_tests(pattern='PathingManagerTest') - Run specific test class\n"
        "- run_tests(pattern='**/Pathing*.java', timeout=120) - Run all pathing tests with longer timeout"
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Test class pattern (e.g., 'PathingTest', '**/PathingManagerTest.java')"
            },
            "timeout": {
                "type": "integer",
                "description": "Test timeout in seconds (default: 60)",
                "default": 60
            }
        },
        "required": []
    }
)
async def run_tests(pattern: Optional[str] = None, timeout: int = 60) -> list[TextContent]:
    """MCP tool: Execute Maven tests"""
    result = run_tests_impl(pattern=pattern, timeout=timeout)

    if "error" in result:
        return [TextContent(type="text", text=f"Error: {result['error']}")]

    # Truncate large results (writes to file, returns summary)
    truncated = maybe_truncate_response(result, prefix="test_output")

    if truncated.get("truncated"):
        # Return summary with file path
        output = "# Test Results\n\n"
        if result.get('pattern'):
            output += f"**Pattern:** {result['pattern']}\n\n"
        output += f"**Summary:**\n"
        output += f"- Tests run: {result['tests_run']}\n"
        output += f"- Failures: {result['failures']}\n"
        output += f"- Errors: {result['errors']}\n"
        output += f"- Skipped: {result['skipped']}\n"
        output += f"- Time: {result['time']:.2f}s\n"
        output += f"- Status: {'✅ PASSED' if result['success'] else '❌ FAILED'}\n\n"
        output += f"**Full output truncated** - see: `{truncated['full_output_path']}`\n"
        if result['failed_tests']:
            output += "\n## Failed Tests Preview (first 3):\n\n"
            for failed in result['failed_tests'][:3]:
                output += f"- {failed['test']}\n"
        return [TextContent(type="text", text=output)]

    # Normal output for small results
    output = "# Test Results\n\n"

    if result.get('pattern'):
        output += f"**Pattern:** {result['pattern']}\n\n"

    output += f"**Summary:**\n"
    output += f"- Tests run: {result['tests_run']}\n"
    output += f"- Failures: {result['failures']}\n"
    output += f"- Errors: {result['errors']}\n"
    output += f"- Skipped: {result['skipped']}\n"
    output += f"- Time: {result['time']:.2f}s\n"
    output += f"- Status: {'✅ PASSED' if result['success'] else '❌ FAILED'}\n\n"

    if result['failed_tests']:
        output += "## Failed Tests\n\n"
        for failed in result['failed_tests']:
            output += f"### {failed['test']}\n"
            output += f"```\n{failed['error']}\n```\n\n"

    output += "## Maven Output\n\n"
    output += f"```\n{result['output']}\n```\n"

    return [TextContent(type="text", text=output)]
