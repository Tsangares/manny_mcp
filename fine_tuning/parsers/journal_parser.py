"""
Journal Parser - Extract structured training data from lesson journals.

Journals capture reasoning patterns, anti-patterns, and debugging knowledge
that are invaluable for fine-tuning. This parser extracts:

1. Problem → Root Cause → Fix patterns (reasoning chains)
2. BAD vs GOOD code examples (negative/positive training pairs)
3. Anti-patterns (what NOT to do)
4. Command usage patterns (tool usage examples)
5. Convention tables (naming rules, coordinate systems)

Output: Structured JSON suitable for fine-tuning data synthesis.
"""

import re
import json
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional, Generator
from datetime import datetime


@dataclass
class CodeExample:
    """A code example with annotation (BAD/GOOD)."""
    code: str
    annotation: str  # "bad", "good", "example", "neutral"
    explanation: Optional[str] = None
    language: str = "python"


@dataclass
class LessonPattern:
    """A lesson with what happened, why, and solution."""
    title: str
    what_happened: Optional[str] = None
    why: Optional[str] = None
    solution: Optional[str] = None
    code_examples: List[CodeExample] = field(default_factory=list)


@dataclass
class AntiPattern:
    """An anti-pattern to avoid."""
    pattern: str
    reason: Optional[str] = None


@dataclass
class CommandUsage:
    """A command/tool usage example."""
    command: str
    purpose: str
    example: Optional[str] = None


@dataclass
class ConventionRule:
    """A naming or formatting convention."""
    context: str  # e.g., "objects", "items", "coordinates"
    rule: str
    examples: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class ParsedJournal:
    """Complete parsed journal with all extracted patterns."""
    filepath: str
    title: str
    date: Optional[str] = None
    context: Optional[str] = None

    # Core content
    problem: Optional[str] = None
    root_cause: Optional[str] = None

    # Extracted patterns
    lessons: List[LessonPattern] = field(default_factory=list)
    anti_patterns: List[AntiPattern] = field(default_factory=list)
    code_examples: List[CodeExample] = field(default_factory=list)
    command_usages: List[CommandUsage] = field(default_factory=list)
    conventions: List[ConventionRule] = field(default_factory=list)

    # Files and metadata
    files_modified: List[Dict[str, str]] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


class JournalParser:
    """Parse journal markdown files into structured training data."""

    # Section header patterns
    PROBLEM_HEADERS = [
        r"##\s*The Problem",
        r"##\s*The Disaster",
        r"##\s*Problem",
        r"##\s*Issue",
    ]

    ROOT_CAUSE_HEADERS = [
        r"##\s*Root Cause[s]?",
        r"##\s*Why",
        r"##\s*Cause",
    ]

    LESSONS_HEADERS = [
        r"##\s*Key Lessons",
        r"##\s*Lessons",
        r"##\s*What I Learned",
        r"###\s*\d+\.\s*",  # Numbered lessons like "### 1. Lesson Title"
    ]

    ANTI_PATTERN_HEADERS = [
        r"##\s*Anti-?[Pp]atterns?",
        r"##\s*What NOT to do",
        r"##\s*Avoid",
    ]

    def __init__(self, journals_dir: str = None):
        self.journals_dir = Path(journals_dir or "journals")

    def list_journals(self) -> List[Path]:
        """List all journal files, excluding template. Searches subdirectories."""
        # Search both root and subdirectories
        journals = sorted(self.journals_dir.glob("**/*.md"))
        return [j for j in journals if "TEMPLATE" not in j.name.upper() and "README" not in j.name.upper()]

    def parse_journal(self, filepath: Path) -> ParsedJournal:
        """Parse a single journal file."""
        content = filepath.read_text()
        lines = content.split("\n")

        journal = ParsedJournal(
            filepath=str(filepath),
            title=self._extract_title(lines),
            date=self._extract_date(lines),
            context=self._extract_context(lines),
        )

        # Extract main sections
        journal.problem = self._extract_section(content, self.PROBLEM_HEADERS)
        journal.root_cause = self._extract_section(content, self.ROOT_CAUSE_HEADERS)

        # Extract structured patterns
        journal.lessons = self._extract_lessons(content)
        journal.anti_patterns = self._extract_anti_patterns(content)
        journal.code_examples = self._extract_code_examples(content)
        journal.command_usages = self._extract_command_usages(content)
        journal.conventions = self._extract_conventions(content)
        journal.files_modified = self._extract_files_modified(content)
        journal.tags = self._infer_tags(journal)

        return journal

    def _extract_title(self, lines: List[str]) -> str:
        """Extract title from first H1."""
        for line in lines:
            if line.startswith("# "):
                return line[2:].strip()
        return "Unknown"

    def _extract_date(self, lines: List[str]) -> Optional[str]:
        """Extract date from metadata line."""
        for line in lines:
            match = re.search(r"\*\*Date:\*\*\s*(\d{4}-\d{2}-\d{2})", line)
            if match:
                return match.group(1)
        return None

    def _extract_context(self, lines: List[str]) -> Optional[str]:
        """Extract context from metadata line."""
        for line in lines:
            match = re.search(r"\*\*Context:\*\*\s*(.+)", line)
            if match:
                return match.group(1).strip()
        return None

    def _extract_section(self, content: str, headers: List[str]) -> Optional[str]:
        """Extract content under any of the given headers."""
        for header_pattern in headers:
            pattern = f"({header_pattern})\n(.*?)(?=\n##|\n#[^#]|$)"
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                text = match.group(2).strip()
                # Clean up: remove sub-headers, keep just the prose
                text = re.sub(r"###.+\n", "", text)
                return text[:1000] if text else None
        return None

    def _extract_lessons(self, content: str) -> List[LessonPattern]:
        """Extract numbered lessons with their patterns."""
        lessons = []

        # Pattern for numbered lesson headers like "### 1. Lesson Title"
        lesson_pattern = r"###\s*\d+\.\s*(.+?)\n(.*?)(?=###\s*\d+\.|\n##[^#]|$)"
        matches = re.findall(lesson_pattern, content, re.DOTALL)

        for title, body in matches:
            lesson = LessonPattern(title=title.strip())

            # Extract "What happened" / "What happened:"
            what_match = re.search(
                r"\*\*What happened:?\*\*:?\s*(.+?)(?=\*\*|\n\n|```|$)",
                body, re.DOTALL
            )
            if what_match:
                lesson.what_happened = what_match.group(1).strip()

            # Extract "Why" / "Should have done"
            why_match = re.search(
                r"\*\*(?:Why|Should have done):?\*\*:?\s*(.+?)(?=\*\*|\n\n|```|$)",
                body, re.DOTALL
            )
            if why_match:
                lesson.why = why_match.group(1).strip()

            # Extract "Solution"
            solution_match = re.search(
                r"\*\*Solution:?\*\*:?\s*(.+?)(?=\*\*|\n\n|```|$)",
                body, re.DOTALL
            )
            if solution_match:
                lesson.solution = solution_match.group(1).strip()

            # Extract code examples from this lesson
            lesson.code_examples = self._extract_code_examples(body)

            lessons.append(lesson)

        return lessons

    def _extract_anti_patterns(self, content: str) -> List[AntiPattern]:
        """Extract anti-patterns (things NOT to do)."""
        anti_patterns = []

        # Find anti-pattern section
        section_match = re.search(
            r"##\s*Anti-?[Pp]atterns?[^\n]*\n(.*?)(?=\n##[^#]|$)",
            content, re.DOTALL | re.IGNORECASE
        )

        if section_match:
            section = section_match.group(1)

            # Pattern 1: Numbered list with bold "Don't"
            # e.g., "1. **Don't** assume object names - always scan"
            pattern1 = r"\d+\.\s*\*\*(?:Don't|DON'T|Never|Avoid)\*\*\s*(.+?)(?:\s*[-–—]\s*(.+))?(?=\n\d+\.|\n[^0-9]|$)"
            for match in re.finditer(pattern1, section):
                pattern_text = match.group(1).strip()
                reason = match.group(2).strip() if match.group(2) else None
                anti_patterns.append(AntiPattern(pattern=pattern_text, reason=reason))

            # Pattern 2: Bullet list with "Don't"
            pattern2 = r"[-*]\s*\*\*(?:Don't|DON'T|Never|Avoid)\*\*\s*(.+?)(?:\s*[-–—]\s*(.+))?(?=\n[-*]|\n\n|$)"
            for match in re.finditer(pattern2, section):
                pattern_text = match.group(1).strip()
                reason = match.group(2).strip() if match.group(2) else None
                anti_patterns.append(AntiPattern(pattern=pattern_text, reason=reason))

        return anti_patterns

    def _extract_code_examples(self, content: str) -> List[CodeExample]:
        """Extract code blocks with BAD/GOOD annotations."""
        examples = []

        # Find all code blocks
        code_pattern = r"```(\w*)\n(.*?)```"

        for match in re.finditer(code_pattern, content, re.DOTALL):
            language = match.group(1) or "python"
            code = match.group(2).strip()

            # Check for BAD/GOOD annotations in the code
            annotation = "neutral"
            explanation = None

            # Check lines before the code block for context
            start_pos = match.start()
            context_before = content[max(0, start_pos-200):start_pos]

            if re.search(r"#\s*(?:BAD|WRONG|INCORRECT)", code, re.IGNORECASE):
                annotation = "bad"
            elif re.search(r"#\s*(?:GOOD|CORRECT|FIXED)", code, re.IGNORECASE):
                annotation = "good"
            elif "BAD" in context_before.upper()[-100:]:
                annotation = "bad"
            elif "GOOD" in context_before.upper()[-100:]:
                annotation = "good"

            # Extract explanation comments
            explanation_matches = re.findall(r"#\s*(.+?)\n", code)
            if explanation_matches:
                explanation = "; ".join(explanation_matches[:3])

            examples.append(CodeExample(
                code=code,
                annotation=annotation,
                explanation=explanation,
                language=language
            ))

        return examples

    def _extract_command_usages(self, content: str) -> List[CommandUsage]:
        """Extract command/tool usage patterns from tables and examples."""
        usages = []

        # Pattern 1: Markdown tables with Command/Purpose columns
        table_pattern = r"\|\s*Command\s*\|\s*Purpose\s*\|.*?\n\|[-|\s]+\|(.*?)(?=\n\n|\n##|$)"
        for table_match in re.finditer(table_pattern, content, re.DOTALL | re.IGNORECASE):
            rows = table_match.group(1).strip().split("\n")
            for row in rows:
                cells = [c.strip() for c in row.split("|") if c.strip()]
                if len(cells) >= 2:
                    cmd = cells[0].strip("`")
                    purpose = cells[1]
                    example = cells[2] if len(cells) > 2 else None
                    usages.append(CommandUsage(
                        command=cmd,
                        purpose=purpose,
                        example=example
                    ))

        # Pattern 2: Inline command mentions like `send_command("KILL_LOOP ...")`
        inline_pattern = r"`(send_command|get_game_state|click_text|scan_\w+|query_\w+|get_\w+)\(([^)]+)\)`"
        for match in re.finditer(inline_pattern, content):
            cmd = match.group(1)
            args = match.group(2)
            # Find surrounding context for purpose
            pos = match.start()
            context = content[max(0, pos-100):pos]
            purpose_match = re.search(r"(?:to|for|should|use)\s+(.{10,50})", context, re.IGNORECASE)
            purpose = purpose_match.group(1) if purpose_match else "Execute command"

            usages.append(CommandUsage(
                command=cmd,
                purpose=purpose,
                example=f"{cmd}({args})"
            ))

        return usages

    def _extract_conventions(self, content: str) -> List[ConventionRule]:
        """Extract naming conventions and rules from tables."""
        conventions = []

        # Look for convention/naming tables
        # Pattern: | Type/Context | Convention | Example |
        table_headers = [
            r"\|\s*(?:Type|Command|Context)\s*\|\s*(?:Convention|Name Format|Rule|Format)\s*\|",
            r"\|\s*(?:Tried|BAD|Wrong)\s*\|\s*(?:Actual|GOOD|Correct)\s*\|",
        ]

        for header_pattern in table_headers:
            table_match = re.search(
                f"({header_pattern}.*?\n\\|[-|\\s]+\\|)(.*?)(?=\\n\\n|\\n##|$)",
                content, re.DOTALL | re.IGNORECASE
            )
            if table_match:
                rows = table_match.group(2).strip().split("\n")
                for row in rows:
                    cells = [c.strip() for c in row.split("|") if c.strip()]
                    if len(cells) >= 2:
                        conventions.append(ConventionRule(
                            context=cells[0],
                            rule=cells[1],
                            examples=[{"value": cells[i]} for i in range(2, len(cells))]
                        ))

        return conventions

    def _extract_files_modified(self, content: str) -> List[Dict[str, str]]:
        """Extract files modified section."""
        files = []

        section_match = re.search(
            r"##\s*Files Modified[^\n]*\n.*?\|[-|\s]+\|(.*?)(?=\n\n|\n##|$)",
            content, re.DOTALL | re.IGNORECASE
        )

        if section_match:
            rows = section_match.group(1).strip().split("\n")
            for row in rows:
                cells = [c.strip() for c in row.split("|") if c.strip()]
                if len(cells) >= 2:
                    files.append({
                        "file": cells[0].strip("`"),
                        "change": cells[1]
                    })

        return files

    def _infer_tags(self, journal: ParsedJournal) -> List[str]:
        """Infer topic tags from content."""
        tags = set()

        content = f"{journal.title} {journal.problem or ''} {journal.root_cause or ''}"
        content = content.lower()

        tag_keywords = {
            "navigation": ["navigation", "indoor", "door", "goto", "walk", "path"],
            "combat": ["combat", "kill", "attack", "npc", "fight"],
            "banking": ["bank", "deposit", "withdraw"],
            "widgets": ["widget", "click", "ui", "interface", "button"],
            "threading": ["thread", "timeout", "latch", "freeze", "block"],
            "quests": ["quest", "dialogue", "npc"],
            "fishing": ["fish", "fishing", "lobster", "shrimp"],
            "cooking": ["cook", "cooking", "range"],
            "camera": ["camera", "zoom", "pitch"],
            "naming": ["naming", "underscore", "convention", "object name"],
        }

        for tag, keywords in tag_keywords.items():
            if any(kw in content for kw in keywords):
                tags.add(tag)

        return sorted(tags)

    def parse_all(self) -> List[ParsedJournal]:
        """Parse all journals."""
        journals = []
        for filepath in self.list_journals():
            try:
                journal = self.parse_journal(filepath)
                journals.append(journal)
            except Exception as e:
                print(f"Error parsing {filepath}: {e}")
        return journals

    def export_to_jsonl(self, output_path: str) -> int:
        """Export all parsed journals to JSONL."""
        journals = self.parse_all()

        with open(output_path, "w") as f:
            for journal in journals:
                f.write(json.dumps(asdict(journal), default=str) + "\n")

        return len(journals)

    def generate_training_examples(self, journal: ParsedJournal) -> Generator[Dict, None, None]:
        """Generate training examples from a parsed journal."""

        # Type 1: Problem → Solution reasoning
        if journal.problem and journal.root_cause:
            yield {
                "type": "reasoning",
                "source": journal.filepath,
                "input": f"Problem: {journal.problem[:500]}",
                "reasoning": f"Root cause: {journal.root_cause[:500]}",
                "tags": journal.tags,
            }

        # Type 2: BAD → GOOD code transformations
        bad_examples = [e for e in journal.code_examples if e.annotation == "bad"]
        good_examples = [e for e in journal.code_examples if e.annotation == "good"]

        # Pair up bad/good examples when possible
        for i, bad in enumerate(bad_examples):
            good = good_examples[i] if i < len(good_examples) else None
            yield {
                "type": "code_correction",
                "source": journal.filepath,
                "bad_code": bad.code,
                "bad_explanation": bad.explanation,
                "good_code": good.code if good else None,
                "good_explanation": good.explanation if good else None,
                "tags": journal.tags,
            }

        # Type 3: Anti-patterns as negative examples
        for ap in journal.anti_patterns:
            yield {
                "type": "anti_pattern",
                "source": journal.filepath,
                "pattern": ap.pattern,
                "reason": ap.reason,
                "tags": journal.tags,
            }

        # Type 4: Command usage examples
        for usage in journal.command_usages:
            yield {
                "type": "command_usage",
                "source": journal.filepath,
                "command": usage.command,
                "purpose": usage.purpose,
                "example": usage.example,
                "tags": journal.tags,
            }

        # Type 5: Lessons as instructional examples
        for lesson in journal.lessons:
            if lesson.what_happened and lesson.solution:
                yield {
                    "type": "lesson",
                    "source": journal.filepath,
                    "title": lesson.title,
                    "problem": lesson.what_happened,
                    "solution": lesson.solution,
                    "why": lesson.why,
                    "tags": journal.tags,
                }

    def export_training_examples(self, output_path: str) -> int:
        """Export all training examples to JSONL."""
        count = 0

        with open(output_path, "w") as f:
            for journal in self.parse_all():
                for example in self.generate_training_examples(journal):
                    f.write(json.dumps(example) + "\n")
                    count += 1

        return count


def main():
    """CLI for journal parsing."""
    import argparse

    parser = argparse.ArgumentParser(description="Parse journals for training data")
    parser.add_argument("--journals-dir", "-d", default="journals",
                        help="Journals directory")
    parser.add_argument("--output", "-o", default="fine_tuning/data/extracted/journals.jsonl",
                        help="Output file path")
    parser.add_argument("--training", "-t", action="store_true",
                        help="Export training examples instead of raw parsed data")
    parser.add_argument("--stats", action="store_true",
                        help="Show statistics only")

    args = parser.parse_args()

    jp = JournalParser(args.journals_dir)

    if args.stats:
        journals = jp.parse_all()
        print(f"Total journals: {len(journals)}")
        print(f"\nBy tag:")
        tag_counts = {}
        for j in journals:
            for tag in j.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1]):
            print(f"  {tag}: {count}")

        print(f"\nContent counts:")
        print(f"  Lessons: {sum(len(j.lessons) for j in journals)}")
        print(f"  Anti-patterns: {sum(len(j.anti_patterns) for j in journals)}")
        print(f"  Code examples: {sum(len(j.code_examples) for j in journals)}")
        print(f"  Command usages: {sum(len(j.command_usages) for j in journals)}")
        print(f"  Conventions: {sum(len(j.conventions) for j in journals)}")

        # Count training examples
        total_examples = 0
        for j in journals:
            total_examples += len(list(jp.generate_training_examples(j)))
        print(f"\nTotal training examples: {total_examples}")

    elif args.training:
        count = jp.export_training_examples(args.output)
        print(f"Exported {count} training examples to {args.output}")

    else:
        count = jp.export_to_jsonl(args.output)
        print(f"Exported {count} parsed journals to {args.output}")


if __name__ == "__main__":
    main()
