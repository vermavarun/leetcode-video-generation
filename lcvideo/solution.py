"""Parse the annotated solution source file into structured facts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

LANG_BY_SUFFIX = {
    ".cs": "csharp",
    ".py": "python",
    ".java": "java",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".c": "c",
    ".js": "javascript",
    ".ts": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".kt": "kotlin",
    ".rb": "ruby",
    ".swift": "swift",
}

_BLOCK_COMMENT = re.compile(r"/\*(.*?)\*/", re.DOTALL)
_HASH_HEADER = re.compile(r'^\s*(?:"""|\'\'\')(.*?)(?:"""|\'\'\')', re.DOTALL)
_STEP = re.compile(r"^\s*(\d+)\)\s*(.+)$")
_FIELD = re.compile(r"^\s*([A-Za-z][A-Za-z ]*?)\s*:\s*(.*)$")

KNOWN_FIELDS = {
    "title",
    "solution",
    "difficulty",
    "approach",
    "tags",
    "time complexity",
    "space complexity",
    "tip",
    "similar problems",
}


@dataclass
class Solution:
    path: Path
    language: str
    code: str
    title: str = ""
    difficulty: str = ""
    approach: str = ""
    tags: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    time_complexity: str = ""
    space_complexity: str = ""
    tip: str = ""
    similar_problems: list[str] = field(default_factory=list)

    @property
    def number(self) -> str:
        match = re.match(r"\s*(\d+)\s*\.", self.title)
        return match.group(1) if match else ""

    @property
    def clean_title(self) -> str:
        return re.sub(r"^\s*\d+\s*\.\s*", "", self.title).strip()


def _extract_header(text: str, suffix: str) -> tuple[str, str]:
    """Return (header_text, code_body)."""
    if suffix == ".py":
        match = _HASH_HEADER.match(text)
    else:
        match = _BLOCK_COMMENT.search(text[: text.find("\n\n") + 4000] or text)
    if match and match.start() < 200:
        return match.group(1), text[match.end() :].lstrip("\n")
    return "", text


def parse_solution(path: str | Path) -> Solution:
    path = Path(path).expanduser().resolve()
    text = path.read_text(encoding="utf-8")
    language = LANG_BY_SUFFIX.get(path.suffix.lower(), "text")
    header, code = _extract_header(text, path.suffix.lower())

    sol = Solution(path=path, language=language, code=code.strip("\n"))
    current: str | None = None

    for line in header.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        step = _STEP.match(stripped)
        if step:
            sol.steps.append(step.group(2).strip())
            current = None
            continue

        field_match = _FIELD.match(stripped)
        key = field_match.group(1).strip().lower() if field_match else None
        if key in KNOWN_FIELDS:
            value = field_match.group(2).strip()
            current = key
            if key == "title":
                sol.title = value
            elif key == "difficulty":
                sol.difficulty = value
            elif key == "approach":
                sol.approach = value
            elif key == "tags":
                sol.tags = [t.strip() for t in value.split(",") if t.strip()]
            elif key == "time complexity":
                sol.time_complexity = value
            elif key == "space complexity":
                sol.space_complexity = value
            elif key == "tip":
                sol.tip = value
            elif key == "similar problems":
                sol.similar_problems = [t.strip() for t in value.split(",") if t.strip()]
            continue

        # Continuation line of the previous field.
        if current == "tip":
            sol.tip = f"{sol.tip} {stripped}".strip()
        elif current == "approach":
            sol.approach = f"{sol.approach} {stripped}".strip()

    if not sol.title:
        sol.title = path.stem.replace("_", " ").title()
    return sol


def code_lines(sol: Solution) -> list[str]:
    return sol.code.splitlines()


_IDENTIFIER = re.compile(r"\b[A-Za-z_]\w*\b")
# Words that are both code identifiers and ordinary English; translating them is fine.
_COMMON_WORDS = {
    "if", "else", "for", "while", "return", "class", "public", "private", "static",
    "void", "int", "new", "this", "true", "false", "null", "string", "var", "let",
    "const", "def", "self", "in", "is", "and", "or", "not", "the", "to", "of",
}


def identifiers_in(sol: Solution) -> set[str]:
    """Names from the source that must survive translation verbatim."""
    found = {n for n in _IDENTIFIER.findall(sol.code) if 3 <= len(n) <= 12}
    return found - _COMMON_WORDS
