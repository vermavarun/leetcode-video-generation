from __future__ import annotations

import argparse
import html
import json
import os
import re
from html.parser import HTMLParser
from typing import TypedDict
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph


load_dotenv()
SOLUTIONS_WEB_APP = os.getenv("SOLUTIONS_WEB_APP")


class GraphState(TypedDict):
    problem_number: str
    question_url: str
    question: str
    solution_url: str
    solution: str


def fetch_page(url: str) -> str:
    request = Request(url, headers={"User-Agent": "langgraph-starter/0.1"})
    with urlopen(request, timeout=15) as response:
        return response.read().decode("utf-8")


def post_json(url: str, payload: dict[str, str]) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "langgraph-starter/0.1",
        },
        method="POST",
    )
    with urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


class HtmlTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = html.unescape(data).strip()
        if text:
            self.parts.append(text)


def html_to_text(content: str) -> str:
    parser = HtmlTextParser()
    parser.feed(content)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(parser.parts))


def fetch_question(problem_number: str) -> tuple[str, str]:
    if not problem_number.isdigit() or int(problem_number) < 1:
        raise ValueError("Problem number must be a positive integer, such as 0019.")

    index = json.loads(fetch_page("https://leetcode.com/api/problems/all/"))
    problem = next(
        (
            item["stat"]
            for item in index.get("stat_status_pairs", [])
            if int(item["stat"].get("frontend_question_id", 0)) == int(problem_number)
        ),
        None,
    )
    if problem is None:
        raise LookupError(f"LeetCode problem {problem_number} was not found.")

    slug = problem["question__title_slug"]
    query = """
    query QuestionDetails($titleSlug: String!) {
      question(titleSlug: $titleSlug) {
        questionFrontendId
        title
        content
      }
    }
    """
    response = post_json(
        "https://leetcode.com/graphql",
        {"query": query, "variables": json.dumps({"titleSlug": slug})},
    )
    question = response.get("data", {}).get("question")
    if not question:
        raise LookupError(f"Details for LeetCode problem {problem_number} were not found.")

    question_text = "\n".join(
        [
            f"{question['questionFrontendId']}. {question['title']}",
            html_to_text(question.get("content", "")),
        ]
    )
    return f"https://leetcode.com/problems/{slug}/", question_text


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


def fetch_question_node(state: GraphState) -> GraphState:
    question_url, question = fetch_question(state["problem_number"])
    return {"question_url": question_url, "question": question}


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("fetch_question", fetch_question_node)
    graph.add_node("fetch_solution", fetch_solution_node)
    graph.add_edge(START, "fetch_question")
    graph.add_edge("fetch_question", "fetch_solution")
    graph.add_edge("fetch_solution", END)
    return graph.compile()


def run_graph(problem_number: str) -> GraphState:
    return build_graph().invoke(
        {
            "problem_number": problem_number,
            "question_url": "",
            "question": "",
            "solution_url": "",
            "solution": "",
        }
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
    print(
        f"Question URL: {result['question_url']}\n\n{result['question']}\n\n"
        f"Solution URL: {result['solution_url']}\n\n{result['solution']}"
    )


if __name__ == "__main__":
    main()