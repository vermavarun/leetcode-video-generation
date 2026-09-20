"""Assemble slides + narration into an MP4 with ffmpeg."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

MIN_SEGMENT_SECONDS = 2.0


def _require_ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required. Install it with: brew install ffmpeg")
    return ffmpeg


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def build_segment(image: Path, audio: Path, out: Path, seconds: float, fps: int, width: int, height: int) -> Path:
    ffmpeg = _require_ffmpeg()
    seconds = max(seconds, MIN_SEGMENT_SECONDS)
    _run(
        [
            ffmpeg, "-y", "-loglevel", "error",
            "-loop", "1", "-framerate", str(fps), "-i", str(image),
            "-i", str(audio),
            "-filter_complex",
            f"[0:v]scale={width}:{height},format=yuv420p,fade=t=in:st=0:d=0.3[v];"
            f"[1:a]apad=pad_dur=0.2,aresample=44100[a]",
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2",
            "-t", f"{seconds + 0.2:.3f}",
            "-shortest", "-movflags", "+faststart",
            str(out),
        ]
    )
    return out


def concat(segments: list[Path], out: Path) -> Path:
    ffmpeg = _require_ffmpeg()
    list_file = out.parent / "segments.txt"
    list_file.write_text(
        "\n".join(f"file '{segment.resolve()}'" for segment in segments) + "\n", encoding="utf-8"
    )
    _run(
        [
            ffmpeg, "-y", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(list_file),
            "-c", "copy", "-movflags", "+faststart",
            str(out),
        ]
    )
    list_file.unlink(missing_ok=True)
    return out


def build_video(
    pairs: list[tuple[Path, Path, float]],
    out_path: Path,
    *,
    fps: int = 30,
    width: int = 1920,
    height: int = 1080,
) -> Path:
    """pairs: (image, audio, duration) in playback order."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    work = out_path.parent / "segments"
    work.mkdir(parents=True, exist_ok=True)

    segments = []
    for i, (image, audio, seconds) in enumerate(pairs):
        segment = work / f"seg-{i:02d}.mp4"
        build_segment(image, audio, segment, seconds, fps, width, height)
        segments.append(segment)

    concat(segments, out_path)
    shutil.rmtree(work, ignore_errors=True)
    return out_path
