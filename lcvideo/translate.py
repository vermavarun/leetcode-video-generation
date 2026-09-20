"""Offline English -> target-language translation via Argos Translate.

Argos runs a local CTranslate2 model; once the language package is installed by
scripts/setup_models.py, translation needs no network.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .config import CACHE_DIR, LANGUAGES
from .hindi import Masker, casualize

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
MAX_CHUNK_CHARS = 220


def _sentences(text: str) -> list[str]:
    """Short chunks keep the model from looping on long repetitive input."""
    chunks: list[str] = []
    current = ""
    for sentence in _SENTENCE_END.split(text):
        if current and len(current) + len(sentence) + 1 > MAX_CHUNK_CHARS:
            chunks.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current)
    return chunks


class Translator:
    def __init__(self, target: str, *, casual: bool = True, code_terms: set[str] | None = None):
        self.target = target
        self.casual = casual and target == "hi"
        self._masker = Masker(code_terms) if target == "hi" else None
        tone = "casual" if self.casual else "formal"
        self._cache_file = CACHE_DIR / "translations" / f"en-{target}-{tone}.json"
        self._cache: dict[str, str] = {}
        if self._cache_file.exists():
            self._cache = json.loads(self._cache_file.read_text(encoding="utf-8"))
        self._translation = self._load(target)

    @staticmethod
    def _load(target: str):
        import argostranslate.translate as translate

        installed = {lang.code: lang for lang in translate.get_installed_languages()}
        if "en" not in installed or target not in installed:
            raise RuntimeError(
                f"Argos language package en -> {target} is not installed.\n"
                f"Run: python scripts/setup_models.py --language {target}"
            )
        return installed["en"].get_translation(installed[target])

    def __call__(self, text: str, *, speech: bool = False) -> str:
        text = str(text).strip()
        if not text:
            return text
        key = ("s:" if speech else "t:") + text
        if key in self._cache:
            return self._cache[key]

        try:
            result = " ".join(self._translate_one(part, speech) for part in _sentences(text))
        except Exception:
            return text

        if self.casual:
            result = casualize(result)
        self._cache[key] = result
        return result

    def _translate_one(self, text: str, speech: bool) -> str:
        if self._masker is None:
            return self._translation.translate(text).strip()
        masked, mapping = self._masker.mask(text)
        translated = self._translation.translate(masked).strip()
        return self._masker.unmask(translated, mapping, speech=speech)

    def flush(self) -> None:
        self._cache_file.parent.mkdir(parents=True, exist_ok=True)
        self._cache_file.write_text(
            json.dumps(self._cache, ensure_ascii=False, indent=1), encoding="utf-8"
        )


def get_translator(
    language: str, *, casual: bool = True, code_terms: set[str] | None = None
) -> Translator | None:
    """None for English (no translation needed)."""
    if language == "en":
        return None
    if language not in LANGUAGES:
        raise ValueError(f"Unsupported language '{language}'. Options: {', '.join(LANGUAGES)}")
    return Translator(language, casual=casual, code_terms=code_terms)
