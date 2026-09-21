from src.main import build_graph


def test_graph_fetches_solution(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.main.fetch_solution",
        lambda problem_number: (
            "https://example.test/solutions/0019-remove.html",
            "Remove Nth Node From End of List",
        ),
    )

    result = build_graph().invoke(
        {"problem_number": "0019", "solution_url": "", "solution": ""}
    )

    assert result["solution_url"].endswith("0019-remove.html")
    assert result["solution"] == "Remove Nth Node From End of List"