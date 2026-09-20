# LeetCode Explanation Video Pipeline

Give it a LeetCode problem link plus your annotated solution file, and it produces a
narrated 1080p MP4 walkthrough — script, slides, voice-over, and final video, in
**English or Hindi**.

Everything after a one-time model download runs **fully offline** on open-source models.

```
input.yaml + solution.cs
        │
        ├─ script   → output/script.<lang>.json, output/script.<lang>.md
        ├─ images   → output/images/<lang>/*.png   (Pillow + Pygments)
        ├─ voice    → output/audio/<lang>/*.wav    (Piper neural TTS, on-device)
        └─ video    → output/<slug>-<lang>.mp4     (ffmpeg)
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
./.venv/bin/python scripts/setup_models.py                    # English assets (~63 MB)
./.venv/bin/python scripts/setup_models.py --language hindi   # Hindi assets (~200 MB)
./.venv/bin/python -m lcvideo.cli
```

## Language: English and Hindi

### 1. Download the assets for the language (once)

```bash
./.venv/bin/python scripts/setup_models.py --language english
./.venv/bin/python scripts/setup_models.py --language hindi
```

The Hindi run additionally pulls the Argos `en → hi` translation model, the
`hi_IN-pratham-medium` Piper voice, and Noto Sans Devanagari for the slides.

### 2a. Pick the language in `input.yaml`

```yaml
language: english         # narration / voice: english | hindi (or en | hi)
slide-language: english   # text drawn on the slides: english | hindi
```

```bash
./.venv/bin/python -m lcvideo.cli
```

### 2b. Or override per run from the command line

```bash
./.venv/bin/python -m lcvideo.cli --language english
./.venv/bin/python -m lcvideo.cli --language hindi                          # Hindi voice, English slides
./.venv/bin/python -m lcvideo.cli --language hindi --slide-language hindi   # Hindi voice and slides
```

### Narration language vs slide language

These are independent. `slide-language` defaults to **english** even when the narration is
Hindi, because code, identifiers and complexity notation read better in English.

| `language` | `slide-language` | Result |
|---|---|---|
| english | english | English voice, English slides |
| hindi | english | **Hindi voice-over, English slides** (default for Hindi) |
| hindi | hindi | Hindi voice-over, Devanagari slides |

### Generate both from one source file

```bash
./.venv/bin/python -m lcvideo.cli -l english   # -> output/fancy-sequence-en.mp4
./.venv/bin/python -m lcvideo.cli -l hindi     # -> output/fancy-sequence-hi.mp4
```

Audio is kept per narration language (`output/audio/<lang>/`) and slides per slide language
(`output/images/<lang>/`), so runs never overwrite each other.

### What gets translated

| Translated | Kept in English |
|---|---|
| Narration (voice-over) | Source code on the code slides |
| Slide text — only when `slide-language: hindi` | Example inputs and outputs |
| Headings, bullets, section labels | Problem title and complexity formulas |

Translation happens locally with Argos Translate (CTranslate2), and results are cached
in `cache/translations/en-hi.json`. Edit that file to correct any wording — the
corrections are reused on the next run.

### Picking a different voice

| Language | Voices |
|---|---|
| English | `en_US-lessac-medium` (default), `en_US-amy-medium`, `en_US-ryan-high`, `en_GB-alba-medium` |
| Hindi | `hi_IN-pratham-medium` (default), `hi_IN-priyamvada-medium` |

```bash
./.venv/bin/python scripts/setup_models.py --language hindi --voice hi_IN-priyamvada-medium
./.venv/bin/python -m lcvideo.cli -l hindi --voice hi_IN-priyamvada-medium
```

You can also set it permanently in `input.yaml` with `voice-name: hi_IN-priyamvada-medium`.

## Models

| Role | Model | License | Size | Required |
|------|-------|---------|------|----------|
| Text-to-speech (English) | Piper `en_US-lessac-medium` | MIT | 63 MB | yes |
| Text-to-speech (Hindi) | Piper `hi_IN-pratham-medium` | MIT | 64 MB | for Hindi |
| Translation | Argos Translate `en → hi` | MIT | ~130 MB | for Hindi |
| Devanagari font | Noto Sans Devanagari | OFL | 0.6 MB | for Hindi |
| Script writing | Qwen2.5-3B-Instruct (GGUF, Q4_K_M) | Apache-2.0 | ~2 GB | optional |

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
language: english          # narration: english | hindi
slide-language: english    # slide text: english | hindi
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

Edit `output/script.<lang>.json` by hand between stages to tweak any narration or slide
text — useful for polishing machine-translated Hindi before rendering:

```bash
./.venv/bin/python -m lcvideo.cli -l hindi -s script     # produce output/script.hi.json
#  ... edit output/script.hi.json ...
./.venv/bin/python -m lcvideo.cli -l hindi -s images -s voice -s video
```

## Flags

| Flag | Meaning |
|------|---------|
| `-i, --input` | path to the input YAML (default `input.yaml`) |
| `-l, --language` | narration language: `english` / `en` or `hindi` / `hi` |
| `--slide-language` | on-slide text language (default English) |
| `--voice` | override the Piper voice name |
| `-s, --stage` | run only `script` / `images` / `voice` / `video`; repeatable |
| `--offline` | no network access at all |
| `--refresh` | re-fetch the problem statement |
| `--no-llm` | skip the local LLM polish step |
