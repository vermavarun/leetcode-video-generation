"""Fetch (once) and cache the LeetCode problem statement.

The pipeline is offline-first: the statement is cached on disk after the first
fetch, and everything downstream (script, slides, audio, video) runs with no
network access. If the statement cannot be fetched, the pipeline degrades
gracefully to the metadata embedded in the solution file header.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

from .config import CACHE_DIR

GRAPHQL_URL = "https://leetcode.com/graphql"
_QUERY = """
query questionData($titleSlug: String!) {
  question(titleSlug: $titleSlug) {
    questionFrontendId
    title
    titleSlug
    difficulty
    content
    topicTags { name }
  }
}
"""


@dataclass
class Problem:
    slug: str
    number: str = ""
    title: str = ""
    difficulty: str = ""
    url: str = ""
    paragraphs: list[str] = field(default_factory=list)
    examples: list[dict] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    source: str = "cache"


def slug_from_url(url: str) -> str:
    match = re.search(r"/problems/([a-z0-9\-]+)", url)
    if not match:
        raise ValueError(f"Could not extract a problem slug from: {url}")
    return match.group(1)


class _TextExtractor(HTMLParser):
    """Flatten LeetCode's HTML statement into blocks of plain text."""

    BLOCK_TAGS = {"p", "div", "li", "pre", "ul", "ol", "br", "h1", "h2", "h3"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[str] = []
        self._buf: list[str] = []
        self._in_pre = False

    def _flush(self) -> None:
        text = "".join(self._buf)
        self._buf.clear()
        if not self._in_pre:
            text = re.sub(r"[ \t]+", " ", text)
        text = text.strip()
        if text:
            self.blocks.append(text)

    def handle_starttag(self, tag, attrs):
        if tag in self.BLOCK_TAGS:
            self._flush()
        if tag == "pre":
            self._in_pre = True
        if tag == "li":
            self._buf.append("• ")

    def handle_endtag(self, tag):
        if tag in self.BLOCK_TAGS:
            self._flush()
        if tag == "pre":
            self._in_pre = False

    def handle_data(self, data):
        self._buf.append(data)

    def close(self):
        super().close()
        self._flush()


def _parse_content(html: str) -> tuple[list[str], list[dict], list[str]]:
    parser = _TextExtractor()
    parser.feed(unescape(html))
    parser.close()

    paragraphs: list[str] = []
    examples: list[dict] = []
    constraints: list[str] = []
    mode = "description"
    pending_example: dict | None = None

    for block in parser.blocks:
        lowered = block.lower().lstrip("• ").strip()
        if lowered.startswith("example"):
            mode = "example"
            pending_example = {"label": block.strip(":"), "input": "", "output": "", "explanation": ""}
            examples.append(pending_example)
            continue
        if lowered.startswith("constraints"):
            mode = "constraints"
            continue
        if lowered.startswith("follow up") or lowered.startswith("follow-up"):
            mode = "followup"
            continue

        if mode == "example" and pending_example is not None:
            for line in block.splitlines():
                line = line.strip()
                low = line.lower()
                if low.startswith("input:"):
                    pending_example["input"] = line.split(":", 1)[1].strip()
                elif low.startswith("output:"):
                    pending_example["output"] = line.split(":", 1)[1].strip()
                elif low.startswith("explanation:"):
                    pending_example["explanation"] = line.split(":", 1)[1].strip()
                elif pending_example["explanation"]:
                    pending_example["explanation"] += " " + line
        elif mode == "constraints":
            constraints.append(block.lstrip("• ").strip())
        elif mode == "description":
            paragraphs.append(block)

    return paragraphs, examples, constraints


def _cache_path(slug: str) -> Path:
    return CACHE_DIR / "problems" / f"{slug}.json"


def _fetch(slug: str) -> dict | None:
    try:
        import requests
    except ImportError:
        return None
    try:
        response = requests.post(
            GRAPHQL_URL,
            json={"query": _QUERY, "operationName": "questionData", "variables": {"titleSlug": slug}},
            headers={
                "Content-Type": "application/json",
                "Referer": f"https://leetcode.com/problems/{slug}/",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
            },
            timeout=20,
        )
        response.raise_for_status()
        return (response.json().get("data") or {}).get("question")
    except Exception:
        return None


def get_problem(url: str, *, offline: bool = False, refresh: bool = False) -> Problem:
    slug = slug_from_url(url)
    cache_file = _cache_path(slug)

    if cache_file.exists() and not refresh:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        return Problem(**data)

    question = None if offline else _fetch(slug)
    if not question or not question.get("content"):
        return Problem(slug=slug, url=url, source="unavailable")

    paragraphs, examples, constraints = _parse_content(question["content"])
    problem = Problem(
        slug=slug,
        number=str(question.get("questionFrontendId") or ""),
        title=question.get("title") or "",
        difficulty=question.get("difficulty") or "",
        url=url,
        paragraphs=paragraphs,
        examples=examples,
        constraints=constraints,
        topics=[t["name"] for t in (question.get("topicTags") or [])],
        source="leetcode",
    )
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(asdict(problem), indent=2), encoding="utf-8")
    return problem
