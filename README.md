# LangGraph Starter

A tiny LangGraph project that fetches an official LeetCode question and a solution, then creates a casual teaching narration with Ollama. It is intentionally small so the graph structure is easy to extend.

## Setup

Using the existing virtual environment:

```bash
python -m pip install -e ".[dev]"
```

Install the browser runtime once on the host or deployment image:

```bash
python -m playwright install --with-deps chromium
```

Snapshots run in headless Chromium and use container-friendly launch flags. Set `SNAPSHOT_DIR` to change the output directory.

The solution source is configured in `.env`:

```bash
SOLUTIONS_WEB_APP=https://vermavarun.github.io/coding/
```

## Run

```bash
python -m src.main 0019
```

This prints the official question statement and examples from LeetCode, saves a rendered description snapshot under `artifacts/questions/`, fetches the structured solution from `solutions.json`, saves the Ollama narration under `artifacts/explanations/`, and creates video-ready PNG slides under `artifacts/demonstration/<problem>/`. The slides include an introduction, problem statement, examples, wrapped and highlighted code parts, and a conclusion. The current graph is:

```text
START -> fetch_question -> fetch_solution -> generate_explanation -> create_demonstration_images -> END
```

Print the graph as Mermaid text with:

```bash
python -m src.main --show-graph
```

## Test

```bash
pytest
```