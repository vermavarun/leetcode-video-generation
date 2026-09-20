"""Offline narration synthesis with Piper (neural TTS, runs fully on-device)."""

from __future__ import annotations

import shutil
import subprocess
import wave
from pathlib import Path

from .config import MODELS_DIR
from .script_gen import VideoScript

LEAD_SILENCE = 0.35
TAIL_SILENCE = 0.75


def voice_paths(voice: str) -> tuple[Path, Path]:
    base = MODELS_DIR / "piper"
    return base / f"{voice}.onnx", base / f"{voice}.onnx.json"


class PiperNarrator:
    def __init__(self, voice: str):
        from piper import PiperVoice

        model, config = voice_paths(voice)
        if not model.exists():
            raise FileNotFoundError(
                f"Piper voice not found: {model}\nRun: python scripts/setup_models.py"
            )
        self.voice = PiperVoice.load(str(model), str(config) if config.exists() else None)

    def synthesize(self, text: str, out_path: Path) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(out_path), "wb") as wav_file:
            self.voice.synthesize_wav(text, wav_file)
        _pad(out_path, LEAD_SILENCE, TAIL_SILENCE)


class SayNarrator:
    """macOS `say` fallback. Fully offline, but not an open-source model."""

    def __init__(self, voice: str = "Samantha"):
        if not shutil.which("say"):
            raise RuntimeError("macOS `say` is unavailable")
        self.voice = voice

    def synthesize(self, text: str, out_path: Path) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        aiff = out_path.with_suffix(".aiff")
        subprocess.run(["say", "-v", self.voice, "-o", str(aiff), text], check=True)
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(aiff), "-ar", "22050", "-ac", "1", str(out_path)],
            check=True,
        )
        aiff.unlink(missing_ok=True)
        _pad(out_path, LEAD_SILENCE, TAIL_SILENCE)


def _pad(path: Path, lead: float, tail: float) -> None:
    with wave.open(str(path), "rb") as src:
        params = src.getparams()
        frames = src.readframes(src.getnframes())
    silence = b"\x00" * (params.sampwidth * params.nchannels)
    with wave.open(str(path), "wb") as dst:
        dst.setparams(params)
        dst.writeframes(silence * int(params.framerate * lead))
        dst.writeframes(frames)
        dst.writeframes(silence * int(params.framerate * tail))


def duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wav_file:
        return wav_file.getnframes() / float(wav_file.getframerate())


def make_narrator(voice: str, allow_fallback: bool = True):
    try:
        return PiperNarrator(voice)
    except Exception as exc:
        if not allow_fallback:
            raise
        print(f"  ! Piper unavailable ({exc}); falling back to system TTS")
        return SayNarrator()


def synthesize_script(script: VideoScript, out_dir: Path, voice: str) -> list[tuple[Path, float]]:
    narrator = make_narrator(voice)
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for section in script.sections:
        path = out_dir / f"{section.id}.wav"
        narrator.synthesize(section.narration, path)
        results.append((path, duration(path)))
    return results
