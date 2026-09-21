from __future__ import annotations

import argparse
import html
import json
import os
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import TypedDict
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph
from playwright.sync_api import sync_playwright


load_dotenv()
SOLUTIONS_WEB_APP = os.getenv("SOLUTIONS_WEB_APP")


class GraphState(TypedDict):
    problem_number: str
    question_url: str
    question: str
    question_snapshot: str
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


def capture_question_snapshot(
    description_html: str,
    problem_number: str,
    title: str,
) -> str:
    snapshot_dir = os.getenv("SNAPSHOT_DIR", "artifacts/questions")
    output_path = Path(snapshot_dir) / f"{int(problem_number):04d}.png"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            page = browser.new_page(
                viewport={"width": 1440, "height": 1200},
                device_scale_factor=1,
            )
            page.set_content(
                f"""
                <style>
                    body {{ margin: 0; background: #262626; color: #f5f5f5;
                            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
                    #description {{ box-sizing: border-box; width: 900px; padding: 12px 8px 32px;
                                    font-size: 16px; line-height: 1.55; }}
                    h1 {{ margin: 0 0 16px; font-size: 25px; line-height: 1.25; }}
                    .badge {{ display: inline-block; border-radius: 14px; padding: 4px 10px;
                              background: #3a3a3a; color: #f5c542; font-size: 13px; }}
                    .content p {{ margin: 16px 0; }}
                    .content li {{ margin: 10px 0; }}
                    .content pre {{ border-left: 3px solid #505050; padding-left: 16px;
                                    overflow-wrap: anywhere; white-space: pre-wrap; }}
                    .content code {{ background: #3a3a3a; padding: 2px 4px; border-radius: 3px; }}
                    .content img {{ display: block; max-width: 100%; height: auto; margin: 12px 0; }}
                </style>
                <main id="description">
                    <h1>{int(problem_number)}. {html.escape(title)}</h1>
                    <span class="badge">LeetCode</span>
                    <section class="content"></section>
                </main>
                """
            )
            page.locator(".content").evaluate(
                "(element, content) => element.innerHTML = content", description_html
            )
            page.wait_for_function(
                "() => Array.from(document.images).every(image => image.complete)",
                timeout=30_000,
            )
            page.locator("#description").screenshot(path=str(output_path), type="png")
        finally:
            browser.close()

    return str(output_path)


def fetch_question(problem_number: str) -> tuple[str, str, str]:
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
    question_url = f"https://leetcode.com/problems/{slug}/"
    snapshot_path = capture_question_snapshot(
        question.get("content", ""),
        problem_number,
        question["title"],
    )
    return question_url, question_text, snapshot_path


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
    question_url, question, snapshot_path = fetch_question(state["problem_number"])
    return {
        "question_url": question_url,
        "question": question,
        "question_snapshot": snapshot_path,
    }


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
            "question_snapshot": "",
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
        f"Question URL: {result['question_url']}\n"
        f"Question snapshot: {result['question_snapshot']}\n\n"
        f"{result['question']}\n\n"
        f"Solution URL: {result['solution_url']}\n\n{result['solution']}"
    )


if __name__ == "__main__":
    main()