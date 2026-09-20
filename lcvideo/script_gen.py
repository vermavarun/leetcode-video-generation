"""Turn problem + solution facts into a narrated, slide-by-slide video script."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .problem import Problem
from .solution import Solution

MAX_CODE_CHUNKS = 4
MIN_CHUNK_LINES = 3
# A 1080p bullet slide stays legible up to roughly this much text.
MAX_BULLETS_PER_SLIDE = 5
MAX_BULLET_CHARS_PER_SLIDE = 440


@dataclass
class Section:
    id: str
    kind: str  # slide renderer type: title | bullets | example | code | kv | outro
    heading: str
    narration: str
    subheading: str = ""
    bullets: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    code: str = ""
    language: str = "text"
    highlight: list[int] = field(default_factory=list)
    footer: str = ""


@dataclass
class VideoScript:
    title: str
    subtitle: str
    sections: list[Section]
    language: str = "en"
    slide_language: str = "en"

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "subtitle": self.subtitle,
            "language": self.language,
            "slide_language": self.slide_language,
            "sections": [asdict(s) for s in self.sections],
        }


# --------------------------------------------------------------------------
# Speech normalisation
# --------------------------------------------------------------------------

_SPEECH_REPLACEMENTS = [
    (r"O\(1\)", "O of one"),
    (r"O\(n\s*\*\s*m\)", "O of n times m"),
    (r"O\(n\s*log\s*n\)", "O of n log n"),
    (r"O\(n\^?2\)", "O of n squared"),
    (r"O\(([^)]+)\)", r"O of \1"),
    (r"\bi\.e\.", "that is"),
    (r"\be\.g\.", "for example"),
    (r"<=", " less than or equal to "),
    (r">=", " greater than or equal to "),
    (r"!=", " not equal to "),
    (r"==", " equals "),
    (r"(?<=\S)\s=\s(?=\S)", " equals "),
    (r"\+\+", " plus plus "),
    (r"\s*\|\s*", " "),
    (r"[`*_#>\[\]{}]", " "),
    (r"\^", " to the power "),
]


def to_speech(text: str) -> str:
    """Make a line of technical text sound natural when spoken."""
    out = str(text)
    for pattern, repl in _SPEECH_REPLACEMENTS:
        out = re.sub(pattern, repl, out)
    out = re.sub(r"\bs\.length\b", "the length of s", out)
    out = re.sub(r"\b1-based\b", "one based", out)
    out = re.sub(r"\b0-based\b", "zero based", out)
    out = re.sub(r"\s+", " ", out).strip()
    if out and out[-1] not in ".!?:":
        out += "."
    return out


def join_speech(parts: list[str]) -> str:
    return " ".join(p for p in (to_speech(x) for x in parts if str(x).strip()) if p)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _comments_in(lines: list[str]) -> list[str]:
    found = []
    for line in lines:
        match = re.search(r"(?://|#)\s*(.+)$", line)
        if match:
            comment = match.group(1).strip()
            if len(comment) > 3:
                found.append(comment)
    return found


def _chunk_code(code: str, max_chunks: int = MAX_CODE_CHUNKS) -> list[tuple[int, int]]:
    """Split code into 1-based inclusive (start, end) line ranges."""
    lines = code.splitlines()
    groups: list[list[int]] = []
    current: list[int] = []
    for idx, line in enumerate(lines, start=1):
        if line.strip():
            current.append(idx)
        elif current:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    if not groups:
        return []

    # Merge neighbouring groups until we are within the chunk budget, and fold
    # away slivers (a lone brace or class declaration makes a poor slide).
    def merge_smallest() -> None:
        sizes = [len(a) + len(b) for a, b in zip(groups, groups[1:])]
        i = sizes.index(min(sizes))
        groups[i : i + 2] = [groups[i] + groups[i + 1]]

    while len(groups) > max_chunks:
        merge_smallest()
    while len(groups) > 1 and min(len(g) for g in groups) < MIN_CHUNK_LINES:
        merge_smallest()

    return [(g[0], g[-1]) for g in groups]


def _chunk_budget(code: str) -> int:
    """Longer files need more walkthrough slides so each highlight stays readable."""
    dense = sum(1 for line in code.splitlines() if line.strip())
    return max(MAX_CODE_CHUNKS, min(10, -(-dense // 16)))


def _wrap_paragraphs(paragraphs: list[str], limit: int = 5) -> list[str]:
    cleaned = [re.sub(r"\s+", " ", p).strip() for p in paragraphs if p and p.strip()]
    return cleaned[:limit]


def _paginate(bullets: list[str]) -> list[list[str]]:
    pages: list[list[str]] = []
    current: list[str] = []
    chars = 0
    for bullet in bullets:
        length = len(str(bullet))
        if current and (len(current) >= MAX_BULLETS_PER_SLIDE or chars + length > MAX_BULLET_CHARS_PER_SLIDE):
            pages.append(current)
            current, chars = [], 0
        current.append(bullet)
        chars += length
    if current:
        pages.append(current)
    return pages or [[]]


def _bullet_sections(
    section_id: str,
    heading: str,
    bullets: list[str],
    footer: str,
    *,
    subheading: str = "",
    lead: str = "",
) -> list[Section]:
    """One bullets section, split across slides when the text is too long."""
    pages = _paginate(bullets)
    sections = []
    for i, page in enumerate(pages, start=1):
        suffix = "" if len(pages) == 1 else f" ({i}/{len(pages)})"
        sections.append(
            Section(
                id=section_id if len(pages) == 1 else f"{section_id}-{i}",
                kind="bullets",
                heading=heading,
                subheading=(subheading + suffix).strip(),
                bullets=page,
                narration=join_speech([lead if i == 1 else "", *page]),
                footer=footer,
            )
        )
    return sections


# --------------------------------------------------------------------------
# Script builder
# --------------------------------------------------------------------------


def build_script(problem: Problem, sol: Solution, llm=None) -> VideoScript:
    number = problem.number or sol.number
    title = problem.title or sol.clean_title
    difficulty = problem.difficulty or sol.difficulty or "Unknown"
    topics = problem.topics or sol.tags
    display_title = f"{number}. {title}" if number else title
    # The approach field often carries a trailing explanation; slides only need the name.
    approach_name = re.split(r"\s[-\u2013:]\s", sol.approach or "", maxsplit=1)[0].strip()

    sections: list[Section] = []

    def polish(default: str, facts: str, max_tokens: int = 220) -> str:
        if llm is None:
            return default
        try:
            text = llm.narrate(facts, max_tokens=max_tokens)
        except Exception:
            return default
        return text if len(text) > 40 else default

    # 1. Title -------------------------------------------------------------
    sections.append(
        Section(
            id="00-title",
            kind="title",
            heading=display_title,
            subheading=approach_name or "Solution walkthrough",
            bullets=[difficulty, *topics[:5]],
            narration=polish(
                join_speech(
                    [
                        f"Welcome. In this video we solve LeetCode problem {number} {title}"
                        if number
                        else f"Welcome. In this video we solve {title}",
                        f"This is rated {difficulty}",
                        f"We will use the {sol.approach} approach" if sol.approach else "",
                    ]
                ),
                f"Intro for a LeetCode video. Problem: {display_title}. Difficulty: {difficulty}. "
                f"Approach: {sol.approach}. Topics: {', '.join(topics)}.",
                160,
            ),
            footer="Problem Introduction",
        )
    )

    # 2. Problem statement -------------------------------------------------
    paragraphs = _wrap_paragraphs(problem.paragraphs, limit=8)
    if paragraphs:
        problem_sections = _bullet_sections(
            "01-problem", "The Problem", paragraphs, "Problem Introduction"
        )
        if len(problem_sections) == 1:
            problem_sections[0].narration = polish(
                problem_sections[0].narration,
                "Read this LeetCode problem statement out loud as narration: " + " ".join(paragraphs),
                260,
            )
        sections.extend(problem_sections)

    # 3. Examples ----------------------------------------------------------
    for i, example in enumerate(problem.examples[:2], start=1):
        rows = [
            ["Input", example.get("input", "")],
            ["Output", example.get("output", "")],
        ]
        if example.get("explanation"):
            rows.append(["Why", example["explanation"]])
        sections.append(
            Section(
                id=f"02-example-{i}",
                kind="kv",
                heading=example.get("label") or f"Example {i}",
                rows=rows,
                narration=join_speech(
                    [
                        f"For the input {example.get('input', '')}, the answer is {example.get('output', '')}",
                        example.get("explanation", ""),
                    ]
                ),
                footer="Problem Introduction",
            )
        )

    # 4. Constraints -------------------------------------------------------
    if problem.constraints:
        sections.extend(
            _bullet_sections(
                "03-constraints",
                "Constraints",
                problem.constraints[:8],
                "Problem Introduction",
                lead="Now the constraints.",
            )
        )

    # 5. Approach ----------------------------------------------------------
    if sol.steps:
        approach_sections = _bullet_sections(
            "04-approach",
            approach_name or "Approach",
            sol.steps,
            "Solution",
            subheading="Step by step",
            lead=(
                f"Here is the idea behind the {sol.approach} approach."
                if sol.approach
                else "Here is the idea."
            ),
        )
        if len(approach_sections) == 1:
            approach_sections[0].narration = polish(
                approach_sections[0].narration,
                f"Explain this algorithm as narration. Approach name: {sol.approach}. Steps: "
                + " ".join(f"{i}. {s}" for i, s in enumerate(sol.steps, 1)),
                280,
            )
        sections.extend(approach_sections)

    # 6. Code walkthrough --------------------------------------------------
    code_lines = sol.code.splitlines()
    chunks = _chunk_code(sol.code, _chunk_budget(sol.code))
    for i, (start, end) in enumerate(chunks, start=1):
        window = code_lines[start - 1 : end]
        comments = _comments_in(window)
        step_hint = sol.steps[i - 1] if i - 1 < len(sol.steps) else ""
        lead = "Let's walk through the code." if i == 1 else ""
        narration_parts = comments or ([step_hint] if step_hint else ["Next part of the implementation."])
        if lead:
            narration_parts = [lead, *narration_parts]
        sections.append(
            Section(
                id=f"05-code-{i}",
                kind="code",
                heading="The Code",
                subheading=f"Part {i} of {len(chunks)}",
                code=sol.code,
                language=sol.language,
                highlight=list(range(start, end + 1)),
                narration=polish(
                    join_speech(narration_parts),
                    "Narrate this part of the code walkthrough. Highlighted code:\n"
                    + "\n".join(window)
                    + "\nKey points: "
                    + "; ".join(narration_parts),
                    220,
                ),
                footer="Solution",
            )
        )

    # 7. Complexity --------------------------------------------------------
    if sol.time_complexity or sol.space_complexity:
        rows = []
        if sol.time_complexity:
            rows.append(["Time", sol.time_complexity])
        if sol.space_complexity:
            rows.append(["Space", sol.space_complexity])
        sections.append(
            Section(
                id="06-complexity",
                kind="kv",
                heading="Complexity",
                rows=rows,
                narration=join_speech(
                    [
                        f"Time complexity is {sol.time_complexity}" if sol.time_complexity else "",
                        f"Space complexity is {sol.space_complexity}" if sol.space_complexity else "",
                    ]
                ),
                footer="Solution",
            )
        )

    # 8. Outro -------------------------------------------------------------
    outro_bullets = []
    if sol.tip:
        outro_bullets.append(f"Tip: {sol.tip}")
    if sol.similar_problems:
        outro_bullets.append("Practice next: " + ", ".join(sol.similar_problems))
    outro_bullets.append("Thanks for watching!")
    sections.append(
        Section(
            id="07-outro",
            kind="outro",
            heading="Recap",
            subheading=display_title,
            bullets=outro_bullets,
            narration=join_speech(
                [
                    f"To recap, we solved {title} using the {sol.approach} approach."
                    if sol.approach
                    else f"To recap, we solved {title}.",
                    sol.tip,
                    "Practice these similar problems: " + ", ".join(sol.similar_problems)
                    if sol.similar_problems
                    else "",
                    "Thanks for watching",
                ]
            ),
            footer="Solution",
        )
    )

    return VideoScript(title=display_title, subtitle=difficulty, sections=sections)


def localize(script: VideoScript, translator, *, translate_slides: bool = False) -> VideoScript:
    """Translate the narration, and optionally the on-slide prose too.

    Code and example input/output always stay verbatim.
    """
    if translator is None:
        return script

    for section in script.sections:
        section.narration = translator(section.narration)
        if not translate_slides:
            continue
        section.bullets = [translator(b) for b in section.bullets]
        section.footer = translator(section.footer)
        if section.kind != "title":
            section.heading = translator(section.heading)
        if section.subheading and section.kind not in {"title", "outro"}:
            section.subheading = translator(section.subheading)
        # Only the row label is prose; the value is input/output or a formula.
        section.rows = [[translator(label), value] for label, value in section.rows]

    script.language = translator.target
    if translate_slides:
        script.subtitle = translator(script.subtitle)
        script.slide_language = translator.target
    translator.flush()
    return script


def save_script(script: VideoScript, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"script.{script.language}.json"
    json_path.write_text(json.dumps(script.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    md_lines = [f"# {script.title}", f"_{script.subtitle}_", ""]
    for section in script.sections:
        md_lines += [f"## {section.heading}", "", section.narration, ""]
    md_path = out_dir / f"script.{script.language}.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    return json_path, md_path


def load_script(path: Path) -> VideoScript:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return VideoScript(
        title=data["title"],
        subtitle=data["subtitle"],
        language=data.get("language", "en"),
        slide_language=data.get("slide_language", "en"),
        sections=[Section(**s) for s in data["sections"]],
    )
