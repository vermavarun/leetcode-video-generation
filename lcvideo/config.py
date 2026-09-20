"""Pipeline configuration: input.yaml parsing and shared paths."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = Path(os.environ.get("LCVIDEO_MODELS_DIR", REPO_ROOT / "models"))
CACHE_DIR = Path(os.environ.get("LCVIDEO_CACHE_DIR", REPO_ROOT / "cache"))

# Piper voice used for narration. Downloaded once by scripts/setup_models.py.
DEFAULT_VOICE = "en_US-lessac-medium"
# Instruct model used to write the narration script. Optional: the pipeline
# falls back to deterministic templates when the weights are absent.
DEFAULT_LLM_FILE = "Qwen2.5-3B-Instruct-Q4_K_M.gguf"

LANGUAGES = {
    "en": {"name": "English", "voice": DEFAULT_VOICE},
    "hi": {"name": "Hindi", "voice": "hi_IN-pratham-medium"},
}
LANGUAGE_ALIASES = {"english": "en", "en_us": "en", "hindi": "hi", "hi_in": "hi"}


def normalize_language(value: str) -> str:
    code = str(value).strip().lower().replace("-", "_")
    code = LANGUAGE_ALIASES.get(code, code)
    if code not in LANGUAGES:
        raise ValueError(
            f"Unsupported language '{value}'. Use one of: "
            + ", ".join(f"{c} ({LANGUAGES[c]['name'].lower()})" for c in LANGUAGES)
        )
    return code


def default_voice(language: str) -> str:
    return LANGUAGES[normalize_language(language)]["voice"]


@dataclass
class Config:
    problem_link: str
    solution_path: Path
    images_dir: Path
    video_dir: Path
    audio_dir: Path
    language: str = "en"
    voice: str = DEFAULT_VOICE
    llm_file: str = DEFAULT_LLM_FILE
    width: int = 1920
    height: int = 1080
    fps: int = 30
    extra: dict = field(default_factory=dict)

    @property
    def script_dir(self) -> Path:
        return self.video_dir

    def ensure_dirs(self) -> None:
        for path in (self.images_dir, self.video_dir, self.audio_dir):
            path.mkdir(parents=True, exist_ok=True)


def _resolve(base: Path, value: str) -> Path:
    path = Path(str(value)).expanduser()
    return path if path.is_absolute() else (base / path)


def load_config(input_file: str | os.PathLike[str]) -> Config:
    """Read the user-facing input.yaml into a Config."""
    input_path = Path(input_file).expanduser().resolve()
    base = input_path.parent
    raw = yaml.safe_load(input_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{input_path} must contain a YAML mapping")

    # Keys are matched case-insensitively and hyphen/underscore-insensitively.
    norm = {str(k).strip().lower().replace("-", "_"): v for k, v in raw.items()}

    try:
        problem_link = str(norm["problem_link"]).strip()
        solution = str(norm["solution_link"]).strip()
    except KeyError as exc:
        raise ValueError(f"input.yaml is missing required key: {exc}") from exc

    images_dir = _resolve(base, norm.get("images_directory", "output"))
    video_dir = _resolve(base, norm.get("video_directory", "output"))
    audio_dir = _resolve(base, norm.get("audio_directory", norm.get("voice_directory", "output")))

    # `voice:` in the sample input.yaml is an output directory, but it may also
    # name a Piper voice (e.g. hi_IN-pratham-medium). Disambiguate on shape.
    voice_value = str(norm.get("voice", "")).strip()
    is_voice_name = bool(re.fullmatch(r"[a-z]{2}_[A-Z]{2}-[a-z_]+-[a-z]+", voice_value))
    if voice_value and not is_voice_name:
        audio_dir = _resolve(base, voice_value)

    language = normalize_language(norm.get("language", "en"))
    voice = norm.get("voice_name") or (voice_value if is_voice_name else default_voice(language))

    return Config(
        problem_link=problem_link,
        solution_path=_resolve(base, solution),
        images_dir=images_dir / "images",
        video_dir=video_dir,
        audio_dir=audio_dir / "audio",
        language=language,
        voice=str(voice),
        llm_file=str(norm.get("llm_file", DEFAULT_LLM_FILE)),
        width=int(norm.get("width", 1920)),
        height=int(norm.get("height", 1080)),
        fps=int(norm.get("fps", 30)),
        extra=norm,
    )
