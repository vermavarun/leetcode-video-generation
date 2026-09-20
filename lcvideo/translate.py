"""Offline English -> target-language translation via Argos Translate.

Argos runs a local CTranslate2 model; once the language package is installed by
scripts/setup_models.py, translation needs no network.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .config import CACHE_DIR, LANGUAGES


class Translator:
    def __init__(self, target: str):
        self.target = target
        self._cache_file = CACHE_DIR / "translations" / f"en-{target}.json"
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

    def __call__(self, text: str) -> str:
        text = str(text).strip()
        if not text:
            return text
        if text in self._cache:
            return self._cache[text]
        try:
            result = self._translation.translate(text).strip()
        except Exception:
            return text
        self._cache[text] = result
        return result

    def flush(self) -> None:
        self._cache_file.parent.mkdir(parents=True, exist_ok=True)
        self._cache_file.write_text(
            json.dumps(self._cache, ensure_ascii=False, indent=1), encoding="utf-8"
        )


def get_translator(language: str) -> Translator | None:
    """None for English (no translation needed)."""
    if language == "en":
        return None
    if language not in LANGUAGES:
        raise ValueError(f"Unsupported language '{language}'. Options: {', '.join(LANGUAGES)}")
    return Translator(language)
