"""Pipeline configuration: input.yaml parsing and shared paths."""

from __future__ import annotations

import os
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


@dataclass
class Config:
    problem_link: str
    solution_path: Path
    images_dir: Path
    video_dir: Path
    audio_dir: Path
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
    # name a Piper voice. Treat a known-voice-looking value as the voice name.
    voice_value = str(norm.get("voice", "")).strip()
    voice = voice_value if voice_value.count("-") >= 2 else DEFAULT_VOICE
    if voice_value and voice_value.count("-") < 2:
        audio_dir = _resolve(base, voice_value)

    return Config(
        problem_link=problem_link,
        solution_path=_resolve(base, solution),
        images_dir=images_dir / "images",
        video_dir=video_dir,
        audio_dir=audio_dir / "audio",
        voice=str(norm.get("voice_name", voice)),
        llm_file=str(norm.get("llm_file", DEFAULT_LLM_FILE)),
        width=int(norm.get("width", 1920)),
        height=int(norm.get("height", 1080)),
        fps=int(norm.get("fps", 30)),
        extra=norm,
    )
