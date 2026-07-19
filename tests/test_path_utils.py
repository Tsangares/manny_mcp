"""Unit tests for mcptools/path_utils.py :: normalize_path.

Pure path normalization: converts absolute / manny_src-symlink / relative inputs
into an absolute, resolved Path. Fully offline — no game client, no network.

Note on the module docstring's examples: they show ``manny_src/utility/File.java``
resolving to ``/home/wil/Desktop/manny/utility/File.java`` — i.e. the ``manny_src``
prefix is stripped and the remainder joined onto plugin_directory. The examples use
a non-existent tree, so ``.resolve()`` there is lexical; we assert the guaranteed
behavior and use tmp_path for the real symlink-resolution case.
"""
from pathlib import Path

import pytest

from mcptools.path_utils import normalize_path


PLUGIN = "/home/wil/Desktop/manny"


# ---------------------------------------------------------------------------
# Docstring examples (asserted against the module's own promises)
# ---------------------------------------------------------------------------
class TestDocstringExamples:
    def test_manny_src_prefix_stripped_and_joined(self):
        out = normalize_path("manny_src/utility/File.java", PLUGIN)
        assert out == Path("/home/wil/Desktop/manny/utility/File.java")

    def test_absolute_within_plugin_returned_resolved(self):
        out = normalize_path("/home/wil/Desktop/manny/CLAUDE.md", PLUGIN)
        assert out == Path("/home/wil/Desktop/manny/CLAUDE.md")

    def test_bare_relative_joined_to_plugin(self):
        out = normalize_path("utility/File.java", PLUGIN)
        assert out == Path("/home/wil/Desktop/manny/utility/File.java")


# ---------------------------------------------------------------------------
# General guarantees: always absolute, accepts str or Path
# ---------------------------------------------------------------------------
class TestGuarantees:
    def test_result_is_always_absolute(self):
        for p in ["utility/File.java", "manny_src/x.java", "/etc/hosts"]:
            assert normalize_path(p, PLUGIN).is_absolute()

    def test_accepts_path_objects_for_both_args(self):
        out = normalize_path(Path("utility/File.java"), Path(PLUGIN))
        assert out == Path("/home/wil/Desktop/manny/utility/File.java")

    def test_manny_src_alone_resolves_to_plugin_dir(self):
        # parts == ("manny_src",) -> relative_path becomes "." -> plugin_directory.
        out = normalize_path("manny_src", PLUGIN)
        assert out == Path(PLUGIN)

    def test_absolute_outside_plugin_returned_as_is(self):
        # Absolute paths are returned resolved even when outside the plugin dir
        # (the security gate lives in ensure_within_plugin, not here).
        out = normalize_path("/etc/hosts", PLUGIN)
        assert out == Path("/etc/hosts")


# ---------------------------------------------------------------------------
# Edge cases: dot segments, trailing slashes
# ---------------------------------------------------------------------------
class TestEdgeCases:
    def test_dotdot_segments_collapsed(self):
        # resolve() normalizes .. lexically once anchored under plugin_directory.
        out = normalize_path("utility/../CLAUDE.md", PLUGIN)
        assert out == Path("/home/wil/Desktop/manny/CLAUDE.md")

    def test_dotdot_can_escape_plugin_dir(self):
        # normalize_path does NOT clamp to the plugin dir; it only normalizes.
        out = normalize_path("../sibling/File.java", PLUGIN)
        assert out == Path("/home/wil/Desktop/sibling/File.java")

    def test_trailing_slash_ignored(self):
        assert normalize_path("utility/", PLUGIN) == Path("/home/wil/Desktop/manny/utility")

    def test_dot_current_dir(self):
        assert normalize_path(".", PLUGIN) == Path(PLUGIN)


# ---------------------------------------------------------------------------
# Real symlink resolution (uses tmp_path so .resolve() actually follows links)
# ---------------------------------------------------------------------------
class TestSymlinkResolution:
    def test_absolute_symlink_is_resolved_to_target(self, tmp_path):
        real = tmp_path / "real"
        real.mkdir()
        target = real / "File.java"
        target.write_text("x")
        link = tmp_path / "link"
        link.symlink_to(real)  # link -> real
        # An absolute path through the symlink resolves to the real location.
        out = normalize_path(str(link / "File.java"), str(tmp_path))
        assert out == target.resolve()
        assert "link" not in out.parts

    def test_relative_through_symlinked_plugin_dir_resolves(self, tmp_path):
        real = tmp_path / "manny_real"
        real.mkdir()
        (real / "utility").mkdir()
        f = real / "utility" / "File.java"
        f.write_text("x")
        plugin_link = tmp_path / "manny"
        plugin_link.symlink_to(real)  # plugin_directory is itself a symlink
        out = normalize_path("utility/File.java", str(plugin_link))
        # resolve() follows the plugin-dir symlink to the real tree.
        assert out == f.resolve()
