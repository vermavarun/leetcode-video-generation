# LeetCode Explanation Video Pipeline

Give it a LeetCode problem link plus your annotated solution file, and it produces a
narrated 1080p MP4 walkthrough — script, slides, voice-over, and final video.

Everything after a one-time model download runs **fully offline** on open-source models.

```
input.yaml + solution.cs
        │
        ├─ script   → output/script.json, output/script.md
        ├─ images   → output/images/*.png          (Pillow + Pygments)
        ├─ voice    → output/audio/*.wav           (Piper neural TTS, on-device)
        └─ video    → output/<slug>.mp4            (ffmpeg)
```

## Setup

```bash
brew install ffmpeg
./run.sh            # creates .venv, installs deps, downloads models, renders the video
```

Or manually:

```bash
python3.12 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/python scripts/setup_models.py          # ~63 MB Piper voice
./.venv/bin/python -m lcvideo.cli
```

## Models

| Role | Model | License | Size | Required |
|------|-------|---------|------|----------|
| Text-to-speech | Piper `en_US-lessac-medium` | MIT | 63 MB | yes |
| Script writing | Qwen2.5-3B-Instruct (GGUF, Q4_K_M) | Apache-2.0 | ~2 GB | optional |

Other voices: `--voice en_US-amy-medium`, `en_US-ryan-high`, `en_GB-alba-medium`.

### Optional LLM narration

Without the LLM the narration is generated deterministically from the problem statement
and the structured header in your solution file — which is already accurate and readable.
The LLM only rewrites those facts into smoother prose.

```bash
sudo xcodebuild -license accept          # macOS: needed to build llama-cpp
./.venv/bin/pip install llama-cpp-python
./.venv/bin/python scripts/setup_models.py --with-llm
./.venv/bin/python -m lcvideo.cli        # LLM is picked up automatically
```

## Input

`input.yaml`:

```yaml
Problem-link: https://leetcode.com/problems/reverse-degree-of-a-string/description/
Solution-link: solution.cs
Images-directory: output
Video-directory: output
voice: output
```

Optional extra keys: `voice-name` (Piper voice), `width`, `height`, `fps`, `llm-file`.

## Solution file format

The pipeline reads a structured header comment to build the approach and complexity
slides, and reads inline `//` comments to narrate the code walkthrough:

```csharp
/*
Title: 3498. Reverse Degree of a String
Difficulty: Easy
Approach: Character Position Mapping and Weighted Sum
Tags: String, Math
1) First step...
2) Second step...
Time Complexity: O(n)
Space Complexity: O(1)
Tip: ...
Similar Problems: ...
*/
public class Solution { ... }
```

C#, Python, Java, C/C++, JS/TS, Go, Rust, Kotlin, Ruby and Swift files are recognised.

## Network use

The **only** network call is fetching the problem statement from LeetCode's public
GraphQL API, and it is cached under `cache/problems/<slug>.json` on first run.

- `--offline` — never touch the network (falls back to cached statement, or to the
  metadata in your solution header).
- `--refresh` — re-fetch and overwrite the cached statement.

## Video sections

1. Title — problem number, difficulty, topic tags
2. The Problem — statement
3. Examples — input / output / explanation
4. Constraints
5. Approach — numbered steps
6. The Code — full listing, walked through part by part with the active lines highlighted
7. Complexity — time and space
8. Recap — tip and similar problems

## Running individual stages

```bash
./.venv/bin/python -m lcvideo.cli -s script          # regenerate the script only
./.venv/bin/python -m lcvideo.cli -s images -s video # re-render slides and re-encode
```

Edit `output/script.json` by hand between stages to tweak any narration or slide text.

## Flags

| Flag | Meaning |
|------|---------|
| `-i, --input` | path to the input YAML (default `input.yaml`) |
| `-s, --stage` | run only `script` / `images` / `voice` / `video`; repeatable |
| `--offline` | no network access at all |
| `--refresh` | re-fetch the problem statement |
| `--no-llm` | skip the local LLM polish step |
