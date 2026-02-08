"""Tests for mcptools.utils - utility functions."""
import json
import pytest
from pathlib import Path

from mcptools.utils import (
    parse_gradle_errors,
    parse_gradle_warnings,
    maybe_truncate_response,
    resolve_plugin_path,
    extract_category_from_description,
    group_tools_by_category,
)


class TestParseGradleErrors:
    def test_parse_javac_error(self):
        output = "/home/wil/src/File.java:42: error: cannot find symbol"
        errors = parse_gradle_errors(output)
        assert len(errors) == 1
        assert errors[0]["file"] == "/home/wil/src/File.java"
        assert errors[0]["line"] == 42
        assert "cannot find symbol" in errors[0]["message"]

    def test_parse_multiple_errors(self):
        output = """/home/wil/A.java:10: error: missing return
/home/wil/B.java:20: error: incompatible types"""
        errors = parse_gradle_errors(output)
        assert len(errors) == 2

    def test_parse_no_errors(self):
        output = "BUILD SUCCESSFUL in 5s\n3 actionable tasks: 3 executed"
        errors = parse_gradle_errors(output)
        assert errors == []

    def test_parse_gradle_failure_block(self):
        output = """* What went wrong:
Execution failed for task ':compileJava'.
> Compilation failed; see the compiler error output for details.

* Try:
Run with --stacktrace"""
        errors = parse_gradle_errors(output)
        assert len(errors) >= 1
        assert "Execution failed" in errors[0]["message"]


class TestParseGradleWarnings:
    def test_parse_javac_warning(self):
        output = "/home/wil/Foo.java:5: warning: unchecked cast"
        warnings = parse_gradle_warnings(output)
        assert len(warnings) == 1
        assert "unchecked cast" in warnings[0]

    def test_no_warnings(self):
        output = "BUILD SUCCESSFUL"
        warnings = parse_gradle_warnings(output)
        assert warnings == []


class TestMaybeTruncateResponse:
    def test_small_response_unchanged(self):
        data = {"success": True, "message": "ok"}
        result = maybe_truncate_response(data, threshold=10000)
        assert result == data

    def test_large_response_truncated(self, tmp_path):
        data = {"success": True, "errors": [], "output": "x" * 10000}
        result = maybe_truncate_response(data, threshold=100)
        assert result["truncated"] is True
        assert "full_output_path" in result
        assert result["success"] is True  # Key fields preserved

    def test_preserves_error_preview(self, tmp_path):
        errors = [f"error {i}" for i in range(10)]
        data = {"success": False, "errors": errors, "output": "x" * 10000}
        result = maybe_truncate_response(data, threshold=100)
        assert result["error_count"] == 10
        assert len(result["errors_preview"]) == 3


class TestResolvePluginPath:
    def test_absolute_path_returned_as_is(self, tmp_path):
        result = resolve_plugin_path("/absolute/path/File.java", "/some/dir")
        assert result == Path("/absolute/path/File.java")

    def test_relative_path_resolved(self, tmp_path):
        # Create the file
        plugin_dir = tmp_path / "plugin"
        plugin_dir.mkdir()
        (plugin_dir / "File.java").touch()

        result = resolve_plugin_path("File.java", plugin_dir)
        assert result == plugin_dir / "File.java"

    def test_recursive_search(self, tmp_path):
        plugin_dir = tmp_path / "plugin"
        sub_dir = plugin_dir / "src" / "main"
        sub_dir.mkdir(parents=True)
        (sub_dir / "Deep.java").touch()

        result = resolve_plugin_path("Deep.java", plugin_dir)
        assert result == sub_dir / "Deep.java"


class TestExtractCategory:
    def test_extract_bracketed_category(self):
        assert extract_category_from_description("[RuneLite] Start client") == "RuneLite"

    def test_extract_multi_word_category(self):
        assert extract_category_from_description("[Code Change] Validate") == "Code Change"

    def test_no_category_returns_general(self):
        assert extract_category_from_description("Some generic tool") == "general"


class TestGroupToolsByCategory:
    def test_groups_correctly(self):
        tools = [
            {"name": "build_plugin", "description": "[RuneLite] Build"},
            {"name": "get_logs", "description": "[RuneLite] Get logs"},
            {"name": "prepare_code_change", "description": "[Code Change] Prepare"},
        ]
        grouped = group_tools_by_category(tools)
        assert len(grouped["RuneLite"]) == 2
        assert len(grouped["Code Change"]) == 1
