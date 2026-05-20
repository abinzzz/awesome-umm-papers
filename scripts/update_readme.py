#!/usr/bin/env python3
"""Generate README.md and refresh citation counts from Semantic Scholar."""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAPERS_PATH = ROOT / "data" / "papers.json"
README_PATH = ROOT / "README.md"


def read_json_url(url: str) -> dict | None:
    request = urllib.request.Request(url, headers={"User-Agent": "awesome-umm-papers/1.0"})

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        print(f"warning: failed to fetch {url}: {exc}", file=sys.stderr)
        return None


def fetch_semantic_scholar_count(arxiv_id: str) -> int | None:
    if not arxiv_id:
        return None

    paper_id = f"ARXIV:{arxiv_id}"
    url = (
        "https://api.semanticscholar.org/graph/v1/paper/"
        + urllib.parse.quote(paper_id, safe=":")
        + "?fields=citationCount"
    )
    payload = read_json_url(url)
    if not payload:
        return None

    count = payload.get("citationCount")
    return count if isinstance(count, int) else None


def normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def fetch_openalex_count(title: str) -> int | None:
    query = urllib.parse.urlencode({"search": title, "per-page": "5"})
    url = f"https://api.openalex.org/works?{query}"
    payload = read_json_url(url)
    if not payload:
        return None

    results = payload.get("results") or []
    wanted = normalize_title(title)
    best: tuple[float, dict] | None = None
    for result in results:
        candidate = normalize_title(result.get("title") or "")
        score = SequenceMatcher(None, wanted, candidate).ratio()
        if best is None or score > best[0]:
            best = (score, result)

    if best is None or best[0] < 0.92:
        print(f"warning: no reliable OpenAlex match for {title}", file=sys.stderr)
        return None

    count = best[1].get("cited_by_count")
    return count if isinstance(count, int) else None


def fetch_citation_count(paper: dict[str, str]) -> int | None:
    count = fetch_semantic_scholar_count(paper.get("arxiv", ""))
    if count is not None:
        return count
    return fetch_openalex_count(paper["title"])


def github_stars_badge(repo: str) -> str:
    return f"![GitHub stars](https://img.shields.io/github/stars/{repo}?style=social)"


def paper_link(arxiv_id: str) -> str:
    if not arxiv_id:
        return "TBA"
    return f"[arXiv:{arxiv_id}](https://arxiv.org/abs/{arxiv_id})"


def render_paper(paper: dict[str, str], citation_count: int | None) -> str:
    repo = paper["github"]
    citations = "N/A" if citation_count is None else str(citation_count)

    return "\n".join(
        [
            f"**Title:** {paper['title']}  ",
            f"**Acceptance:** {paper['acceptance']}  ",
            f"**GitHub:** {github_stars_badge(repo)} [{repo}](https://github.com/{repo})  ",
            f"**Citations:** {citations}  ",
            f"**Paper:** {paper_link(paper.get('arxiv', ''))}  ",
            f"**Authors:** {paper['authors']}  ",
            f"**Affiliations:** {paper['affiliations']}",
        ]
    )


def render_readme(papers: list[dict[str, str]]) -> str:
    citation_counts: dict[str, int | None] = {}
    for index, paper in enumerate(papers):
        arxiv_id = paper.get("arxiv", "")
        citation_counts[arxiv_id] = fetch_citation_count(paper)
        if index != len(papers) - 1:
            time.sleep(1)

    entries = [
        render_paper(paper, citation_counts.get(paper.get("arxiv", "")))
        for paper in papers
    ]

    return (
        "# Awesome UMM Papers\n\n"
        "A curated list of papers on unified multimodal models, agents, and native multimodal pretraining.\n\n"
        "Citation counts are refreshed by GitHub Actions from Semantic Scholar, with OpenAlex as a fallback. GitHub stars are live Shields.io badges.\n\n"
        "## Papers\n\n"
        + "\n\n---\n\n".join(entries)
        + "\n"
    )


def main() -> int:
    papers = json.loads(PAPERS_PATH.read_text(encoding="utf-8"))
    README_PATH.write_text(render_readme(papers), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
