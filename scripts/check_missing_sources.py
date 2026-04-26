"""Check for kyma-project repos with docs that are not in docs_sources.json.

Usage:
    uv run python scripts/check_missing_sources.py
    uv run python scripts/check_missing_sources.py --sources kyma_knowledge_mcp/indexing/docs_sources.json
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

ORGS = ["kyma-project"]
DOC_PATHS = ["docs/user", "docs"]
SOURCES_DEFAULT = Path(__file__).parent.parent / "kyma_knowledge_mcp/indexing/docs_sources.json"


def gh(endpoint: str) -> list | dict:
    result = subprocess.run(
        ["gh", "api", "--paginate", endpoint],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    try:
        data = json.loads(result.stdout)
        return data if isinstance(data, list) else [data]
    except json.JSONDecodeError:
        return []


def has_user_docs(org: str, repo: str) -> str | None:
    """Return the doc path if the repo has user-facing docs, else None."""
    for path in DOC_PATHS:
        items = gh(f"repos/{org}/{repo}/contents/{path}")
        if not items:
            continue
        names = [item.get("name", "") for item in items if isinstance(item, dict)]
        if "user" in names:
            return f"{path}/user"
        md_files = [n for n in names if n.endswith(".md") and not n.startswith("_")]
        if md_files:
            return path
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", default=str(SOURCES_DEFAULT))
    args = parser.parse_args()

    sources_path = Path(args.sources)
    if not sources_path.exists():
        print(f"ERROR: {sources_path} not found")
        sys.exit(1)

    with open(sources_path) as f:
        sources = json.load(f)

    indexed_urls = {s["url"].rstrip("/").removesuffix(".git") for s in sources}

    print(f"Indexed sources: {len(indexed_urls)}\n")
    print("Scanning kyma-project org for repos with docs...\n")

    missing = []
    for org in ORGS:
        repos = gh(f"orgs/{org}/repos?per_page=100&sort=pushed")
        for repo in repos:
            name = repo.get("name", "")
            url = repo.get("html_url", "").rstrip("/")
            if url in indexed_urls:
                continue
            if repo.get("archived") or repo.get("fork"):
                continue
            doc_path = has_user_docs(org, name)
            if doc_path:
                missing.append({"name": name, "url": f"{url}.git", "doc_path": doc_path})
                print(f"  MISSING  {name:40s}  {doc_path}")

    print(f"\nFound {len(missing)} repo(s) with docs not in sources:")
    for m in missing:
        print(f"  {m['url']}  →  {m['doc_path']}")


if __name__ == "__main__":
    main()
