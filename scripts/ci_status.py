"""Read public GitHub Actions state without credentials; HTML is a read-only fallback."""

from __future__ import annotations

import argparse
import json
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPOSITORY = "cheshmakzanoon-ops/python-projects"


class EmbeddedJSON(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.active = False
        self.parts: list[str] = []
        self.values: list[Any] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script" and dict(attrs).get("type") == "application/json":
            self.active, self.parts = True, []

    def handle_data(self, data: str) -> None:
        if self.active:
            self.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self.active:
            self.active = False
            try:
                self.values.append(json.loads("".join(self.parts)))
            except json.JSONDecodeError:
                pass


def from_html(page: str) -> list[dict[str, Any]]:
    parser = EmbeddedJSON()
    parser.feed(page)
    result = []
    for value in parser.values:
        if not isinstance(value, dict):
            continue
        runs = value.get("payload", {}).get("allWorkflowRunsRoute", {}).get("workflowRuns", [])
        for run in runs:
            result.append(
                {
                    "id": str(run["id"]),
                    "commit": run["description"]["linkUrl"].rsplit("/", 1)[-1],
                    "state": run["state"],
                    "url": run["runUrl"],
                    "title": run["title"],
                }
            )
    return result


def fetch(url: str) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": "python-portfolio-verification",
            "Accept": "application/vnd.github+json" if "api.github.com" in url else "text/html",
        },
    )
    with urlopen(request, timeout=20) as response:
        body = response.read(4_000_001)
    if len(body) > 4_000_000:
        raise ValueError("GitHub response exceeds supported bound")
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit")
    args = parser.parse_args()
    try:
        data = json.loads(
            fetch(
                f"https://api.github.com/repos/{REPOSITORY}/actions/runs?branch=main&per_page=100"
            )
        )
        runs = [
            {
                "id": str(r["id"]),
                "commit": r["head_sha"],
                "state": {"status": r["status"], "conclusion": r["conclusion"]},
                "url": r["html_url"],
                "title": r["display_title"],
            }
            for r in data["workflow_runs"]
        ]
        source = "GitHub REST API"
    except (HTTPError, URLError):
        runs = from_html(
            fetch(f"https://github.com/{REPOSITORY}/actions?query=branch%3Amain").decode()
        )
        source = "GitHub Actions public page"
    chosen = [r for r in runs if not args.commit or r["commit"] == args.commit]
    print(json.dumps({"source": source, "runs": chosen}, indent=2))
    return 0 if chosen else 2


if __name__ == "__main__":
    raise SystemExit(main())
