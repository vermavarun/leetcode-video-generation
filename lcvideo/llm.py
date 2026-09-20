"""Optional local LLM narration polisher.

Runs a GGUF instruct model through llama-cpp-python entirely on-device. When
the runtime or the weights are missing the pipeline silently falls back to the
deterministic template narration in script_gen.py.
"""

from __future__ import annotations

from pathlib import Path

from .config import MODELS_DIR

SYSTEM_PROMPT = (
    "You are a concise technical narrator for a LeetCode explainer video. "
    "Rewrite the given facts as spoken narration. Rules: plain spoken English, "
    "no markdown, no bullet characters, no emoji, no headings, expand symbols "
    "into words (say 'O of n' for O(n)), 2 to 4 sentences, and never invent "
    "facts that are not in the input."
)


class LocalLLM:
    def __init__(self, model_path: Path, n_ctx: int = 4096, threads: int | None = None):
        from llama_cpp import Llama  # imported lazily: optional dependency

        self._llama = Llama(
            model_path=str(model_path),
            n_ctx=n_ctx,
            n_threads=threads,
            verbose=False,
        )

    def narrate(self, facts: str, max_tokens: int = 220) -> str:
        result = self._llama.create_chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": facts},
            ],
            temperature=0.3,
            max_tokens=max_tokens,
        )
        text = result["choices"][0]["message"]["content"].strip()
        return " ".join(text.split())


def load_llm(model_file: str) -> LocalLLM | None:
    """Return a LocalLLM, or None when the optional runtime/weights are absent."""
    path = Path(model_file)
    if not path.is_absolute():
        path = MODELS_DIR / "llm" / model_file
    if not path.exists():
        return None
    try:
        return LocalLLM(path)
    except Exception:
        return None
