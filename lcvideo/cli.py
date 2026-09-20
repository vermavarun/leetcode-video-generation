"""End-to-end pipeline CLI: problem link + source code -> narrated MP4."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import LANGUAGES, default_voice, load_config, normalize_language
from .llm import load_llm
from .problem import get_problem
from .script_gen import build_script, load_script, localize, save_script
from .slides import render_all
from .solution import identifiers_in, parse_solution
from .tts import duration, synthesize_script
from .translate import get_translator
from .video import build_video

STAGES = ["script", "images", "voice", "video"]


def _step(message: str) -> None:
    print(f"==> {message}", flush=True)


def run(args: argparse.Namespace) -> int:
    cfg = load_config(args.input)
    if args.language:
        cfg.language = normalize_language(args.language)
        cfg.voice = default_voice(cfg.language)
    if args.slide_language:
        cfg.slide_language = normalize_language(args.slide_language)
    if args.tone:
        cfg.tone = args.tone
    if args.voice:
        cfg.voice = args.voice
    # Keep per-language renders side by side rather than overwriting each other.
    cfg.images_dir = cfg.images_dir / cfg.slide_language
    cfg.audio_dir = cfg.audio_dir / cfg.language
    cfg.ensure_dirs()
    stages = set(args.stages or STAGES)

    print(
        f"Narration: {LANGUAGES[cfg.language]['name']} ({cfg.voice})  "
        f"Slides: {LANGUAGES[cfg.slide_language]['name']}"
    )
    script_path = cfg.script_dir / f"script.{cfg.language}.json"

    if "script" in stages:
        _step("Parsing solution source")
        sol = parse_solution(cfg.solution_path)
        print(f"    {sol.title} [{sol.language}] - {len(sol.steps)} approach steps")

        _step("Loading problem statement")
        problem = get_problem(cfg.problem_link, offline=args.offline, refresh=args.refresh)
        print(f"    source: {problem.source}, {len(problem.examples)} example(s)")

        llm = None
        if not args.no_llm:
            _step("Loading local LLM (optional)")
            llm = load_llm(cfg.llm_file)
            print(f"    {'loaded ' + cfg.llm_file if llm else 'not available - using template narration'}")

        _step("Writing narration script")
        script = build_script(problem, sol, llm=llm)
        if cfg.language != "en":
            what = "narration and slides" if cfg.slide_language != "en" else "narration"
            _step(f"Translating {what} to {LANGUAGES[cfg.language]['name']} ({cfg.tone})")
            script = localize(
                script,
                get_translator(
                    cfg.language,
                    casual=cfg.tone != "formal",
                    code_terms=identifiers_in(sol),
                ),
                translate_slides=cfg.slide_language == cfg.language,
            )
        json_path, md_path = save_script(script, cfg.script_dir)
        print(f"    {json_path}\n    {md_path}")
    else:
        if not script_path.exists():
            print(f"error: {script_path} not found; run the 'script' stage first", file=sys.stderr)
            return 1
        script = load_script(script_path)

    images: list[Path] = []
    if "images" in stages:
        _step("Rendering slides")
        images = render_all(script, cfg.images_dir, cfg.width, cfg.height)
        print(f"    {len(images)} images -> {cfg.images_dir}")
    else:
        images = [cfg.images_dir / f"{s.id}.png" for s in script.sections]

    audio: list[tuple[Path, float]] = []
    if "voice" in stages:
        _step("Synthesizing narration")
        audio = synthesize_script(script, cfg.audio_dir, cfg.voice)
        print(f"    {len(audio)} clips, {sum(d for _, d in audio):.1f}s total -> {cfg.audio_dir}")
    else:
        for section in script.sections:
            path = cfg.audio_dir / f"{section.id}.wav"
            audio.append((path, duration(path) if path.exists() else 5.0))

    if "video" in stages:
        _step("Encoding video")
        missing = [p for p in images if not p.exists()] + [p for p, _ in audio if not p.exists()]
        if missing:
            print(f"error: missing assets: {missing[:3]}", file=sys.stderr)
            return 1
        out_path = cfg.video_dir / f"{cfg.problem_link.rstrip('/').split('/')[-1] or 'solution'}.mp4"
        if out_path.name in {"description.mp4", ".mp4"}:
            out_path = cfg.video_dir / "solution.mp4"
        out_path = out_path.with_name(f"{out_path.stem}-{cfg.language}.mp4")
        pairs = [(img, aud, dur) for img, (aud, dur) in zip(images, audio)]
        build_video(pairs, out_path, fps=cfg.fps, width=cfg.width, height=cfg.height)
        total = sum(d for _, d in audio)
        _step(f"Done: {out_path}  (~{total / 60:.1f} min)")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lcvideo", description=__doc__)
    parser.add_argument("-i", "--input", default="input.yaml", help="pipeline input file")
    parser.add_argument(
        "-l", "--language",
        choices=["en", "english", "hi", "hindi"],
        help="narration language (default: from input.yaml)",
    )
    parser.add_argument(
        "--slide-language",
        choices=["en", "english", "hi", "hindi"],
        help="language for on-slide text (default: English)",
    )
    parser.add_argument(
        "--tone", choices=["casual", "formal"],
        help="Hindi wording style (default: casual, conversational Hinglish)",
    )
    parser.add_argument("--voice", help="override the Piper voice name")
    parser.add_argument(
        "-s", "--stage", dest="stages", action="append", choices=STAGES,
        help="run only the given stage(s); repeatable",
    )
    parser.add_argument("--offline", action="store_true", help="never touch the network")
    parser.add_argument("--refresh", action="store_true", help="re-fetch the problem statement")
    parser.add_argument("--no-llm", action="store_true", help="skip the local LLM polish step")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
