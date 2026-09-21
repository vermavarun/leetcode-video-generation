from __future__ import annotations

import argparse
import json
import os
from typing import TypedDict
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph


load_dotenv()
SOLUTIONS_WEB_APP = os.getenv("SOLUTIONS_WEB_APP")


class GraphState(TypedDict):
    problem_number: str
    solution_url: str
    solution: str


def fetch_page(url: str) -> str:
    request = Request(url, headers={"User-Agent": "langgraph-starter/0.1"})
    with urlopen(request, timeout=15) as response:
        return response.read().decode("utf-8")


def fetch_solution(problem_number: str, base_url: str | None = SOLUTIONS_WEB_APP) -> tuple[str, str]:
    if not problem_number.isdigit() or int(problem_number) < 1:
        raise ValueError("Problem number must be a positive integer, such as 0019.")
    if not base_url:
        raise RuntimeError("SOLUTIONS_WEB_APP is not configured in .env.")

    base_url = base_url.rstrip("/") + "/"
    source_url = f"{base_url}solutions.json"
    data = json.loads(fetch_page(source_url))
    solution = next(
        (
            item
            for item in data.get("solutions", [])
            if str(item.get("problemNumber", "")).isdigit()
            and int(item["problemNumber"]) == int(problem_number)
        ),
        None,
    )
    if solution is None:
        raise LookupError(f"No solution found for problem {problem_number}.")

    steps = "\n".join(solution.get("steps", []))
    solution_text = "\n".join(
        [
            f"{solution.get('problemNumber')}. {solution.get('title', '')}",
            f"Language: {solution.get('language', 'Unknown')}",
            f"Difficulty: {solution.get('difficulty', 'Unknown')}",
            f"Approach: {solution.get('approach', '')}",
            f"Tags: {', '.join(solution.get('tags', []))}",
            "Algorithm:",
            steps,
            f"Time: {solution.get('timeComplexity', '')}",
            f"Space: {solution.get('spaceComplexity', '')}",
            "Code:",
            solution.get("code", ""),
        ]
    )
    return solution.get("solutionLink") or solution.get("githubUrl") or source_url, solution_text


def fetch_solution_node(state: GraphState) -> GraphState:
    solution_url, solution = fetch_solution(state["problem_number"])
    return {"solution_url": solution_url, "solution": solution}


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("fetch_solution", fetch_solution_node)
    graph.add_edge(START, "fetch_solution")
    graph.add_edge("fetch_solution", END)
    return graph.compile()


def run_graph(problem_number: str) -> GraphState:
    return build_graph().invoke(
        {"problem_number": problem_number, "solution_url": "", "solution": ""}
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch a LeetCode solution with LangGraph.")
    parser.add_argument("problem_number", nargs="?", default="0019")
    parser.add_argument(
        "--show-graph",
        action="store_true",
        help="Print the graph as Mermaid text.",
    )
    args = parser.parse_args()
    if args.show_graph:
        print(build_graph().get_graph().draw_mermaid())
        return
    result = run_graph(args.problem_number)
    print(f"Solution URL: {result['solution_url']}\n\n{result['solution']}")


if __name__ == "__main__":
    main()