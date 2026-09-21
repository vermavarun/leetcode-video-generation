from src.main import build_graph


class FakeResponse:
    content = "# Friendly explanation\n\nHere is the key idea."


class FakeModel:
    def __init__(self, model: str, temperature: float) -> None:
        assert model == "test-model"
        assert temperature == 0.2

    def invoke(self, prompt: str) -> FakeResponse:
        assert "QUESTION:" in prompt
        assert "SOLUTION:" in prompt
        return FakeResponse()


def test_graph_fetches_solution(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.main.fetch_question",
        lambda problem_number: (
            "https://leetcode.com/problems/example/",
            "19. Example question\nExample 1: input -> output",
            "artifacts/questions/0019.png",
        ),
    )
    monkeypatch.setattr(
        "src.main.fetch_solution",
        lambda problem_number: (
            "https://example.test/solutions/0019-remove.html",
            "Remove Nth Node From End of List",
        ),
    )

    result = build_graph().invoke(
        {
            "problem_number": "0019",
            "question_url": "",
            "question": "",
            "question_snapshot": "",
            "solution_url": "",
            "solution": "",
            "explanation": "",
            "explanation_path": "",
            "demonstration_images": [],
        }
    )

    assert result["question_url"].endswith("/example/")
    assert "Example 1" in result["question"]
    assert result["question_snapshot"].endswith("0019.png")
    assert result["solution_url"].endswith("0019-remove.html")
    assert result["solution"] == "Remove Nth Node From End of List"


def test_graph_generates_explanation(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("src.main.ChatOllama", FakeModel)
    monkeypatch.setenv("EXPLANATION_DIR", str(tmp_path))
    monkeypatch.setattr(
        "src.main.fetch_question",
        lambda problem_number: ("https://example.test/question", "Question text", "snapshot.png"),
    )
    monkeypatch.setattr(
        "src.main.fetch_solution",
        lambda problem_number: ("https://example.test/solution", "Solution code"),
    )

    result = build_graph("test-model").invoke(
        {
            "problem_number": "0019",
            "question_url": "",
            "question": "",
            "question_snapshot": "",
            "solution_url": "",
            "solution": "",
            "explanation": "",
            "explanation_path": "",
        }
    )

    assert result["explanation_path"].endswith("0019.md")
    assert result["explanation"] == FakeResponse.content
    assert (tmp_path / "0019.md").read_text(encoding="utf-8").strip() == FakeResponse.content