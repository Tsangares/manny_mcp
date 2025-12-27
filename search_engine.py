#!/home/wil/manny-mcp/venv/bin/python
"""
Unified Search Engine for Manny Plugin Code Navigation (Phase 3)

Builds an inverted index at server startup for O(1) code lookups instead of
O(n) file scans. Dramatically speeds up find_command, find_pattern, and
find_relevant_files operations.

Index structure:
- command:BANK_OPEN → [(file, line, context)]
- class:CombatSystem → [(file, line)]
- method:handleBankOpen → [(file, line)]
- section:SECTION_4_SKILLING → [(file, line_start, line_end)]
"""

import re
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import hashlib


class CodeSearchIndex:
    """
    Inverted index for fast code navigation.

    Builds once at startup, provides O(1) lookups for:
    - Commands (case "BANK_OPEN":)
    - Classes (class CombatSystem)
    - Methods (private void handleBankOpen())
    - Section markers (// ===== SECTION X =====)
    """

    def __init__(self, plugin_dir: str):
        self.plugin_dir = Path(plugin_dir)
        self.index: Dict[str, List[Tuple]] = defaultdict(list)
        self.file_hashes: Dict[str, str] = {}
        self.last_build_time = 0
        self._build_index()

    def _build_index(self):
        """Build inverted index by scanning all Java files."""
        start_time = time.time()
        files_indexed = 0

        for java_file in self.plugin_dir.rglob("*.java"):
            try:
                content = java_file.read_text()
                lines = content.split('\n')

                # Track file hash for incremental rebuilds
                file_hash = hashlib.md5(content.encode()).hexdigest()
                self.file_hashes[str(java_file)] = file_hash

                # Index commands (case "COMMAND_NAME":)
                for i, line in enumerate(lines, 1):
                    # Command case statements
                    match = re.search(r'case\s+"([A-Z_]+)":', line)
                    if match:
                        cmd = match.group(1)
                        self.index[f"command:{cmd}"].append({
                            "file": str(java_file),
                            "line": i,
                            "context": line.strip(),
                            "type": "case_statement"
                        })

                    # Class definitions
                    match = re.search(r'class\s+(\w+)', line)
                    if match:
                        cls = match.group(1)
                        self.index[f"class:{cls}"].append({
                            "file": str(java_file),
                            "line": i,
                            "context": line.strip(),
                            "type": "class_definition"
                        })

                    # Method definitions
                    match = re.search(r'(public|private|protected)\s+\w+\s+(\w+)\s*\(', line)
                    if match:
                        method = match.group(2)
                        self.index[f"method:{method}"].append({
                            "file": str(java_file),
                            "line": i,
                            "context": line.strip(),
                            "type": "method_definition"
                        })

                    # Section markers (// ===== SECTION X =====)
                    match = re.search(r'//\s*=+\s*SECTION\s+(\d+):\s*(.+?)\s*=+', line)
                    if match:
                        section_num = match.group(1)
                        section_name = match.group(2).strip()
                        self.index[f"section:{section_num}"].append({
                            "file": str(java_file),
                            "line": i,
                            "name": section_name,
                            "context": line.strip(),
                            "type": "section_marker"
                        })
                        self.index[f"section:{section_name.lower()}"].append({
                            "file": str(java_file),
                            "line": i,
                            "name": section_name,
                            "context": line.strip(),
                            "type": "section_marker"
                        })

                files_indexed += 1
            except Exception as e:
                print(f"Warning: Failed to index {java_file}: {e}")

        self.last_build_time = time.time() - start_time
        print(f"[SearchIndex] Indexed {files_indexed} files in {self.last_build_time:.2f}s")
        print(f"[SearchIndex] Index size: {len(self.index)} keys")

    def find_command(self, command: str) -> List[Dict]:
        """
        Find all occurrences of a command (case statements and handler methods).

        Returns:
            List of locations with file, line, context
        """
        results = []

        # Find case statement
        case_key = f"command:{command.upper()}"
        results.extend(self.index.get(case_key, []))

        # Find handler method (handleBankOpen from BANK_OPEN)
        # Convert BANK_OPEN → BankOpen → handleBankOpen
        parts = command.split('_')
        camel = ''.join(word.capitalize() for word in parts)
        handler_name = f"handle{camel}"

        method_key = f"method:{handler_name}"
        results.extend(self.index.get(method_key, []))

        return results

    def find_class(self, class_name: str) -> List[Dict]:
        """Find class definition."""
        return self.index.get(f"class:{class_name}", [])

    def find_method(self, method_name: str) -> List[Dict]:
        """Find method definition."""
        return self.index.get(f"method:{method_name}", [])

    def find_section(self, section: str) -> List[Dict]:
        """Find section marker by number or name."""
        # Try by number first
        if section.isdigit():
            return self.index.get(f"section:{section}", [])

        # Try by name (case-insensitive)
        return self.index.get(f"section:{section.lower()}", [])

    def search(self, query: str, search_type: str = "any") -> List[Dict]:
        """
        Unified search across all indices.

        Args:
            query: Search term
            search_type: "command", "class", "method", "section", or "any"

        Returns:
            List of matching locations
        """
        if search_type == "command":
            return self.find_command(query)
        elif search_type == "class":
            return self.find_class(query)
        elif search_type == "method":
            return self.find_method(query)
        elif search_type == "section":
            return self.find_section(query)
        else:
            # "any" - search all types
            results = []
            results.extend(self.find_command(query))
            results.extend(self.find_class(query))
            results.extend(self.find_method(query))
            results.extend(self.find_section(query))
            return results

    def get_stats(self) -> Dict:
        """Get index statistics."""
        return {
            "total_keys": len(self.index),
            "commands": len([k for k in self.index if k.startswith("command:")]),
            "classes": len([k for k in self.index if k.startswith("class:")]),
            "methods": len([k for k in self.index if k.startswith("method:")]),
            "sections": len([k for k in self.index if k.startswith("section:")]),
            "files_indexed": len(self.file_hashes),
            "build_time_sec": round(self.last_build_time, 2)
        }


# Global search index (initialized lazily)
_search_index: Optional[CodeSearchIndex] = None


def get_search_index(plugin_dir: str = None) -> CodeSearchIndex:
    """
    Get or create the global search index.

    Singleton pattern - builds index once at first access.
    """
    global _search_index

    if _search_index is None:
        if plugin_dir is None:
            # Default to manny plugin directory
            plugin_dir = "/home/wil/Desktop/manny"

        print(f"[SearchIndex] Building index for {plugin_dir}...")
        _search_index = CodeSearchIndex(plugin_dir)

    return _search_index
