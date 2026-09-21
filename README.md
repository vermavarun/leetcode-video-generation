# LangGraph Starter

A tiny LangGraph project that fetches a LeetCode solution from the configured web app. It is intentionally small so the graph structure is easy to extend with Ollama-backed nodes.

## Setup

Using the existing virtual environment:

```bash
python -m pip install -e ".[dev]"
```

The solution source is configured in `.env`:

```bash
SOLUTIONS_WEB_APP=https://vermavarun.github.io/coding/
```

## Run

```bash
python -m src.main 0019
```

This prints the solution source URL and the structured solution fetched from `solutions.json`. The current graph is:

```text
START -> fetch_solution -> END
```

Print the graph as Mermaid text with:

```bash
python -m src.main --show-graph
```

## Test

```bash
pytest
```