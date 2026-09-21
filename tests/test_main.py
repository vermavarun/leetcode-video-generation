from src.main import build_graph


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
        }
    )

    assert result["question_url"].endswith("/example/")
    assert "Example 1" in result["question"]
    assert result["question_snapshot"].endswith("0019.png")
    assert result["solution_url"].endswith("0019-remove.html")
    assert result["solution"] == "Remove Nth Node From End of List"