"""Check for kyma-project repos with docs that are not in docs_sources.json.

Usage:
    uv run python scripts/check_missing_sources.py
    uv run python scripts/check_missing_sources.py --auto-add   # write missing entries to JSON
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


def build_source_entry(org: str, repo: str, doc_path: str, html_url: str) -> dict:
    """Build a conservative docs_sources.json entry for a repo."""
    entry: dict = {
        "name": repo,
        "source_type": "Github",
        "url": f"{html_url}.git",
    }
    if doc_path.endswith("/user"):
        entry["include_files"] = [f"{doc_path}/*"]
        entry["exclude_files"] = [f"{doc_path}/README.md", "*/_sidebar.md"]
    else:
        entry["include_files"] = ["README.md", f"{doc_path}/*"]
        entry["exclude_files"] = ["*/_sidebar.md"]
    return entry


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", default=str(SOURCES_DEFAULT))
    parser.add_argument(
        "--auto-add",
        action="store_true",
        help="Automatically add missing entries to docs_sources.json with conservative include patterns",
    )
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
            html_url = repo.get("html_url", "").rstrip("/")
            if html_url in indexed_urls:
                continue
            if repo.get("archived") or repo.get("fork"):
                continue
            doc_path = has_user_docs(org, name)
            if doc_path:
                missing.append(
                    {"name": name, "html_url": html_url, "doc_path": doc_path, "org": org}
                )
                print(f"  MISSING  {name:40s}  {doc_path}")

    if not missing:
        print("\nNo missing sources found.")
        return

    print(f"\nFound {len(missing)} repo(s) with docs not in sources.")

    if not args.auto_add:
        print("\nRe-run with --auto-add to write these entries to docs_sources.json.")
        return

    new_entries = [
        build_source_entry(m["org"], m["name"], m["doc_path"], m["html_url"]) for m in missing
    ]
    sources.extend(new_entries)
    sources_path.write_text(json.dumps(sources, indent=2) + "\n")
    print(f"\nAdded {len(new_entries)} new entrie(s) to {sources_path}")
    print("Review the added entries and adjust include_files as needed before merging.")
    for e in new_entries:
        print(f"  - {e['name']}: {e['include_files']}")


if __name__ == "__main__":
    main()
