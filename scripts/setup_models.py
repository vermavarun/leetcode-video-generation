#!/usr/bin/env python3
"""One-time model download. After this runs, the pipeline needs no network.

Downloads:
  * Piper neural TTS voice (MIT, ~60 MB) - required for narration
  * Argos Translate en->xx package (MIT, ~100 MB) - required for non-English
  * Noto Sans Devanagari (OFL) - required for Hindi slides
  * Qwen2.5-3B-Instruct GGUF (Apache-2.0, ~2 GB) - optional script polisher
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lcvideo.config import DEFAULT_LLM_FILE, MODELS_DIR, default_voice, normalize_language  # noqa: E402

PIPER_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
PIPER_VOICES = {
    # voice name -> path under the piper-voices repo
    "en_US-lessac-medium": "en/en_US/lessac/medium/en_US-lessac-medium",
    "en_US-amy-medium": "en/en_US/amy/medium/en_US-amy-medium",
    "en_US-ryan-high": "en/en_US/ryan/high/en_US-ryan-high",
    "en_GB-alba-medium": "en/en_GB/alba/medium/en_GB-alba-medium",
    "hi_IN-pratham-medium": "hi/hi_IN/pratham/medium/hi_IN-pratham-medium",
    "hi_IN-priyamvada-medium": "hi/hi_IN/priyamvada/medium/hi_IN-priyamvada-medium",
}

DEVANAGARI_FONT_URL = (
    "https://github.com/google/fonts/raw/main/ofl/notosansdevanagari/"
    "NotoSansDevanagari%5Bwdth%2Cwght%5D.ttf"
)

LLM_URL = (
    "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf"
)


def download(url: str, dest: Path) -> Path:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  = {dest.name} (already present)")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  + {dest.name}  <-  {url}")
    tmp = dest.with_suffix(dest.suffix + ".part")

    def progress(block: int, block_size: int, total: int) -> None:
        if total > 0:
            done = min(block * block_size, total)
            print(f"\r    {done / 1e6:7.1f} / {total / 1e6:.1f} MB", end="", flush=True)

    urllib.request.urlretrieve(url, tmp, reporthook=progress)  # noqa: S310 - fixed HTTPS hosts
    print()
    tmp.replace(dest)
    return dest


def fetch_voice(voice: str) -> None:
    if voice not in PIPER_VOICES:
        raise SystemExit(f"Unknown voice '{voice}'. Options: {', '.join(PIPER_VOICES)}")
    stem = PIPER_VOICES[voice]
    out = MODELS_DIR / "piper"
    download(f"{PIPER_BASE}/{stem}.onnx?download=true", out / f"{voice}.onnx")
    download(f"{PIPER_BASE}/{stem}.onnx.json?download=true", out / f"{voice}.onnx.json")


def fetch_translation(target: str) -> None:
    """Install the Argos Translate en -> target model."""
    import argostranslate.package as package
    import argostranslate.translate as translate

    installed = {lang.code for lang in translate.get_installed_languages()}
    if target in installed:
        print(f"  = en -> {target} translation package (already installed)")
        return

    package.update_package_index()
    match = next(
        (p for p in package.get_available_packages() if p.from_code == "en" and p.to_code == target),
        None,
    )
    if match is None:
        raise SystemExit(f"No Argos Translate package available for en -> {target}")
    print(f"  + en -> {target} translation package")
    package.install_from_path(match.download())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-l", "--language", default="en", choices=["en", "english", "hi", "hindi"])
    parser.add_argument("--voice", help="Piper voice (defaults to the language's voice)")
    parser.add_argument("--with-llm", action="store_true", help="also download the ~2 GB instruct model")
    args = parser.parse_args()

    language = normalize_language(args.language)
    voice = args.voice or default_voice(language)
    print(f"Models directory: {MODELS_DIR}")
    print("Piper TTS voice:")
    fetch_voice(voice)

    if language != "en":
        print("Translation model:")
        fetch_translation(language)
        print("Devanagari font:")
        download(DEVANAGARI_FONT_URL, MODELS_DIR / "fonts" / "NotoSansDevanagari.ttf")

    if args.with_llm:
        print("Instruct model (optional):")
        download(LLM_URL, MODELS_DIR / "llm" / DEFAULT_LLM_FILE)
        print("\nEnable it with: pip install llama-cpp-python")

    print("\nDone. The pipeline can now run fully offline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
