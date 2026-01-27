# File Corruption During Edits - Lessons Learned
**Date:** 2026-01-26

## The Problem

While making simple edits to `UIOverlays.java` (adding a single method call), the entire file was corrupted and reduced to 1 empty line. The build failed with "file does not contain class" errors, and git restore was required to recover.

## Root Cause

Unknown - the Edit tool appeared to work correctly (showed snippet of edited file), but subsequent reads revealed the file was empty. Possible causes:
1. Race condition during file write
2. Edit tool failure mode when file is large (~3000+ lines)
3. Concurrent file access issue

The file `manny_src/ui/UIOverlays.java` is a large file with multiple overlay classes. The corruption occurred after a seemingly successful edit.

## Key Lessons

### 1. Verify File Integrity After Edits to Large Files

**What happened:** Edit showed success with correct snippet, but file was actually empty
**Why:** Unknown - Edit tool failure mode on large files
**Solution:**
```python
# BAD - Trust edit result, immediately build
Edit(file_path="UIOverlays.java", old_string="...", new_string="...")
build_plugin()  # Fails with cryptic "file does not contain class" error

# GOOD - Verify file after edit, especially for large files
Edit(file_path="UIOverlays.java", old_string="...", new_string="...")
Read(file_path="UIOverlays.java", limit=10)  # Quick sanity check
# If file appears truncated/empty, restore before building
```

### 2. "File Does Not Contain Class" = Empty/Corrupted File

**What happened:** Build error "bad source file... file does not contain class X"
**Why:** Java compiler found file but it was empty or truncated
**Solution:**
```bash
# When you see this error, check file length first
wc -l path/to/File.java  # Should show hundreds of lines, not 1

# If corrupted, restore from git
git checkout path/to/File.java
```

### 3. Multiple Empty Files Can Cascade

**What happened:** Both `UIOverlays.java` and `GotoCommand.java` were empty in the same build
**Why:** Unknown if related or coincidental. May indicate broader file system issue.
**Solution:** When one file is corrupt, check other recently-edited files too.

## Anti-Patterns

1. **Don't** assume Edit success means file is intact - Always verify large file edits
2. **Don't** debug build errors without checking file integrity first - "cannot find symbol" may just mean empty file
3. **Don't** make multiple edits to the same large file in quick succession - May increase corruption risk

## Debugging Commands

| Command | Purpose |
|---------|---------|
| `Read(file_path, limit=10)` | Quick check if file has content |
| `wc -l file.java` | Verify line count matches expected |
| `git checkout file.java` | Restore corrupted file from git |
| `git status` | See which files have been modified |

## Interface Gaps Identified

- [ ] Edit tool needs: Better error detection when file write fails
- [ ] Edit tool needs: File integrity verification after write
- [ ] CLAUDE.md needs: Warning about large file edit risks

## Files Modified (if applicable)

| File | Change |
|------|--------|
| `manny_src/MannyPlugin.java` | IP tracker: 60s -> 10min interval, refresh on game state change |
| `manny_src/ui/UIOverlays.java` | Mouse overlay: Always render (corrupted, had to restore and re-edit) |

## Recovery Steps

When this happens again:
1. `git status` to see modified files
2. `git diff file.java` to see if file is empty/truncated
3. `git checkout file.java` to restore
4. Re-apply edits more carefully, verifying after each one
