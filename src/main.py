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
from langchain_ollama import ChatOllama
from langgraph.graph import END, START, StateGraph
from playwright.sync_api import sync_playwright


load_dotenv()
SOLUTIONS_WEB_APP = os.getenv("SOLUTIONS_WEB_APP")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")


class GraphState(TypedDict):
    problem_number: str
    question_url: str
    question: str
    question_snapshot: str
    solution_url: str
    solution: str
    explanation: str
    explanation_path: str
    demonstration_images: list[str]


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


def generate_explanation(
    problem_number: str,
    question: str,
    solution: str,
    model: str = DEFAULT_MODEL,
) -> tuple[str, str]:
    prompt = f"""You are a friendly coding teacher writing a narration for a short video.

Explain LeetCode problem {problem_number} using the source material below.
Write in a casual, clear teaching tone, as if speaking directly to a learner.
Cover these sections:
1. What the problem is asking, including the important constraints and examples.
2. The key insight behind the solution.
3. A step-by-step walkthrough of the provided code.
4. Time and space complexity.
5. A short closing takeaway.

Do not invent requirements, examples, or behavior that are not present in the source.
Use Markdown headings and paragraphs. Keep the explanation focused and understandable.

QUESTION:
{question}

SOLUTION:
{solution}
"""
    response = ChatOllama(model=model, temperature=0.2).invoke(prompt)
    explanation = str(response.content).strip()
    output_dir = Path(os.getenv("EXPLANATION_DIR", "artifacts/explanations"))
    output_path = output_dir / f"{int(problem_number):04d}.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(explanation + "\n", encoding="utf-8")
    return str(output_path), explanation


def generate_explanation_node(state: GraphState, model: str) -> GraphState:
    explanation_path, explanation = generate_explanation(
        state["problem_number"], state["question"], state["solution"], model
    )
    return {"explanation_path": explanation_path, "explanation": explanation}


def _slide_paragraphs(text: str, limit: int = 5) -> str:
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    return "".join(f"<p>{html.escape(paragraph)}</p>" for paragraph in paragraphs[:limit])


def _render_slide(page, output_path: Path, title: str, body: str, code: bool = False) -> None:
    page.set_content(
        f"""
        <style>
            * {{ box-sizing: border-box; }}
            body {{ margin: 0; width: 1280px; height: 720px; background: #16181d;
                    color: #f5f7fa; font-family: -apple-system, BlinkMacSystemFont,
                    "Segoe UI", sans-serif; }}
            main {{ width: 100%; height: 100%; padding: 58px 72px; display: flex;
                    flex-direction: column; justify-content: center; }}
            .eyebrow {{ color: #f0b429; text-transform: uppercase; letter-spacing: 1px;
                        font-size: 16px; font-weight: 700; margin-bottom: 18px; }}
            h1 {{ max-width: 1100px; margin: 0 0 30px; font-size: 46px; line-height: 1.1; }}
            .body {{ max-width: 1100px; font-size: 27px; line-height: 1.42; }}
            .body p {{ margin: 0 0 20px; }}
            .body code {{ background: #30343c; border-radius: 5px; padding: 2px 7px;
                          font-family: "SFMono-Regular", Consolas, monospace; font-size: .82em; }}
            .body pre {{ margin: 0; color: #e8edf2; font-family: "SFMono-Regular", Consolas,
                         monospace; font-size: 20px; line-height: 1.38; white-space: pre-wrap;
                         overflow-wrap: anywhere; }}
            .code {{ justify-content: flex-start; padding-top: 46px; }}
            .code h1 {{ font-size: 34px; margin-bottom: 22px; }}
            .line {{ display: block; padding: 1px 12px; }}
            .active {{ background: #5a4518; border-left: 4px solid #f0b429; }}
            .footer {{ margin-top: auto; color: #8f98a8; font-size: 15px; }}
        </style>
        <main class="{'code' if code else ''}">
            <div class="eyebrow">LeetCode video</div>
            <h1>{html.escape(title)}</h1>
            <section class="body">{body}</section>
            <div class="footer">Local learning narration</div>
        </main>
        """
    )
    page.screenshot(path=str(output_path), type="png")


def _extract_solution_code(solution: str) -> str:
    code = solution.split("Code:\n", 1)[1] if "Code:\n" in solution else solution
    code = code.strip()
    while code.startswith("/*") and "*/" in code:
        code = code.split("*/", 1)[1].lstrip()
    return code


def create_demonstration_images(
    problem_number: str,
    question: str,
    solution: str,
    explanation: str,
) -> list[str]:
    output_dir = Path(os.getenv("DEMONSTRATION_DIR", "artifacts/demonstration"))
    problem_dir = output_dir / f"{int(problem_number):04d}"
    problem_dir.mkdir(parents=True, exist_ok=True)
    for old_image in problem_dir.glob("*.png"):
        old_image.unlink()

    question_lines = question.splitlines()
    question_title = question_lines[0] if question_lines else f"Problem {problem_number}"
    question_body = "\n".join(question_lines[1:])
    example_match = re.search(r"(?im)^Example 1:", question_body)
    statement = question_body[: example_match.start()] if example_match else question_body
    examples = question_body[example_match.start() :] if example_match else "Examples are included in the problem statement."
    code = _extract_solution_code(solution)
    code_lines = code.strip().splitlines() or ["No solution code was provided."]
    code_chunks = [code_lines[index : index + 24] for index in range(0, len(code_lines), 24)]

    image_paths: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            page = browser.new_page(viewport={"width": 1280, "height": 720}, device_scale_factor=1)

            slides = [
                ("001-introduction.png", question_title, _slide_paragraphs(explanation, 2), False),
                ("002-problem-statement.png", "What are we being asked to do?", _slide_paragraphs(statement, 4), False),
                ("003-examples.png", "Examples", _slide_paragraphs(examples, 5), False),
            ]
            for filename, title, body, is_code in slides:
                path = problem_dir / filename
                _render_slide(page, path, title, body, is_code)
                image_paths.append(str(path))

            for part_number, chunk in enumerate(code_chunks, start=1):
                lines = "".join(
                    f'<span class="line active">{html.escape(line) or " "}</span>\n'
                    for line in chunk
                )
                path = problem_dir / f"004-solution-code-part-{part_number:02d}.png"
                _render_slide(
                    page,
                    path,
                    f"Solution code | Part {part_number} of {len(code_chunks)}",
                    f"<pre>{lines}</pre>",
                    True,
                )
                image_paths.append(str(path))

            conclusion = explanation.split("Closing Takeaway", 1)[-1]
            conclusion_number = 4 + len(code_chunks)
            path = problem_dir / f"{conclusion_number:03d}-conclusion.png"
            _render_slide(page, path, "The takeaway", _slide_paragraphs(conclusion, 3), False)
            image_paths.append(str(path))
        finally:
            browser.close()

    return image_paths


def create_demonstration_images_node(state: GraphState) -> GraphState:
    images = create_demonstration_images(
        state["problem_number"],
        state["question"],
        state["solution"],
        state["explanation"],
    )
    return {"demonstration_images": images}


def build_graph(model: str = DEFAULT_MODEL):
    graph = StateGraph(GraphState)
    graph.add_node("fetch_question", fetch_question_node)
    graph.add_node("fetch_solution", fetch_solution_node)
    graph.add_node(
        "generate_explanation",
        lambda state: generate_explanation_node(state, model),
    )
    graph.add_node("create_demonstration_images", create_demonstration_images_node)
    graph.add_edge(START, "fetch_question")
    graph.add_edge("fetch_question", "fetch_solution")
    graph.add_edge("fetch_solution", "generate_explanation")
    graph.add_edge("generate_explanation", "create_demonstration_images")
    graph.add_edge("create_demonstration_images", END)
    return graph.compile()


def run_graph(problem_number: str, model: str = DEFAULT_MODEL) -> GraphState:
    return build_graph(model).invoke(
        {
            "problem_number": problem_number,
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch a LeetCode solution with LangGraph.")
    parser.add_argument("problem_number", nargs="?", default="0019")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama model to use.")
    parser.add_argument(
        "--show-graph",
        action="store_true",
        help="Print the graph as Mermaid text.",
    )
    args = parser.parse_args()
    if args.show_graph:
        print(build_graph(args.model).get_graph().draw_mermaid())
        return
    result = run_graph(args.problem_number, args.model)
    print(
        f"Question URL: {result['question_url']}\n"
        f"Question snapshot: {result['question_snapshot']}\n\n"
        f"{result['question']}\n\n"
        f"Solution URL: {result['solution_url']}\n\n{result['solution']}\n\n"
        f"Explanation: {result['explanation_path']}\n\n{result['explanation']}"
        f"\n\nDemonstration images:\n" + "\n".join(result["demonstration_images"])
    )


if __name__ == "__main__":
    main()