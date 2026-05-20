#!/usr/bin/env python3
"""Generate README.md from structured paper metadata.

Citation counts use the values stored in data/papers.json by default. Google
Scholar has no official free API, so the script intentionally avoids replacing
manual Scholar counts with Semantic Scholar/OpenAlex counts from a different
source.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PAPERS_PATH = ROOT / "data" / "papers.json"
README_PATH = ROOT / "README.md"


def read_json_url(url: str) -> dict[str, Any] | None:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "awesome-umm-papers/1.0"},
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        print(f"warning: failed to fetch {url}: {exc}", file=sys.stderr)
        return None


def refresh_with_serpapi(papers: list[dict[str, Any]]) -> bool:
    """Refresh Google Scholar counts when SERPAPI_KEY is configured."""
    api_key = os.environ.get("SERPAPI_KEY")
    if not api_key:
        print("SERPAPI_KEY is not set; keeping checked-in citation counts.")
        return False

    changed = False
    for paper in papers:
        query = paper["title"]
        params = urllib.parse.urlencode(
            {
                "engine": "google_scholar",
                "q": f'"{query}"',
                "api_key": api_key,
            }
        )
        payload = read_json_url(f"https://serpapi.com/search.json?{params}")
        organic = (payload or {}).get("organic_results") or []
        if not organic:
            print(f"warning: no Google Scholar result for {query}", file=sys.stderr)
            continue

        inline_links = organic[0].get("inline_links") or {}
        total = (inline_links.get("cited_by") or {}).get("total")
        if isinstance(total, int) and paper.get("citations") != total:
            paper["citations"] = total
            paper["citation_source"] = "Google Scholar via SerpApi"
            changed = True

    if changed:
        PAPERS_PATH.write_text(
            json.dumps(papers, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return changed


def github_stars_badge(repo: str) -> str:
    return f"![GitHub stars](https://img.shields.io/github/stars/{repo}?style=social)"


def scholar_link(title: str) -> str:
    query = urllib.parse.quote(f'"{title}"')
    return f"https://scholar.google.com/scholar?q={query}"


def paper_link(paper: dict[str, Any]) -> str:
    arxiv_id = paper.get("arxiv")
    url = paper.get("paper_url")
    if arxiv_id and url:
        return f"[arXiv:{arxiv_id}]({url})"
    if url:
        return f"[Paper]({url})"
    return "TBA"


def publication_link(paper: dict[str, Any]) -> str | None:
    note = paper.get("publication_note")
    url = paper.get("publication_url")
    if note and url:
        return f"**Publication:** [{note}]({url})  "
    if url:
        return f"**Publication:** [{url}]({url})  "
    return None


def render_paper(paper: dict[str, Any]) -> str:
    repo = paper["github"]
    citations = paper.get("citations")
    citation_text = "0" if citations == 0 else str(citations or "N/A")
    source = paper.get("citation_source", "Google Scholar")
    checked = paper.get("citation_checked", "unchecked")

    lines = [
        f"**Title:** {paper['title']}  ",
        f"**Acceptance:** {paper['acceptance']}  ",
        f"**GitHub:** {github_stars_badge(repo)} [{repo}](https://github.com/{repo})  ",
        f"**Citations:** [{citation_text}]({scholar_link(paper['title'])}) ({source}, checked {checked})  ",
        f"**Paper:** {paper_link(paper)}  ",
    ]

    publication = publication_link(paper)
    if publication:
        lines.append(publication)

    lines.extend(
        [
            f"**Authors:** {paper['authors']}  ",
            f"**Affiliations:** {paper['affiliations']}",
        ]
    )
    return "\n".join(lines)


def render_readme(papers: list[dict[str, Any]]) -> str:
    entries = [render_paper(paper) for paper in papers]

    return (
        "# Awesome UMM Papers\n\n"
        "A curated list of papers on unified multimodal models, agents, and native multimodal pretraining.\n\n"
        "GitHub stars are live Shields.io badges. Citation counts are Google Scholar counts checked manually; "
        "they are not mixed with Semantic Scholar or OpenAlex counts because those sources use different coverage "
        "and can mismatch newly released arXiv papers.\n\n"
        "## Papers\n\n"
        + "\n\n---\n\n".join(entries)
        + "\n"
    )


def main() -> int:
    papers = json.loads(PAPERS_PATH.read_text(encoding="utf-8"))
    if "--refresh-citations" in sys.argv:
        refresh_with_serpapi(papers)
        papers = json.loads(PAPERS_PATH.read_text(encoding="utf-8"))
    README_PATH.write_text(render_readme(papers), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
