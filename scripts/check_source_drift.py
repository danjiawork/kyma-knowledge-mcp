"""Audit existing docs_sources.json entries for doc drift in tracked repos.

For each tracked repo, checks:
  NEW_PATH    — doc directories present in the repo but not covered by include_files
  DEAD        — include_files patterns that match no files in the repo
  MISSING_DEV — repos with docs/contributor/* but no developer collection entry

Usage:
    uv run python scripts/check_source_drift.py
    uv run python scripts/check_source_drift.py --auto-fix   # write fixes to docs_sources.json
    uv run python scripts/check_source_drift.py --repo api-gateway
    uv run python scripts/check_source_drift.py --sources path/to/docs_sources.json
"""

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

SOURCES_DEFAULT = Path(__file__).parent.parent / "kyma_knowledge_mcp/indexing/docs_sources.json"

# Doc directory roots worth scanning for drift.
DOC_ROOTS = ["docs", "tutorials"]


def gh_json(endpoint: str) -> dict | list | None:
    result = subprocess.run(
        ["gh", "api", endpoint],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def get_repo_md_files(org: str, repo: str) -> list[str]:
    """Return all .md file paths in the repo via the git tree API."""
    data = gh_json(f"repos/{org}/{repo}/git/trees/HEAD?recursive=1")
    if not data or not isinstance(data, dict):
        return []
    return [
        item["path"]
        for item in data.get("tree", [])
        if item.get("type") == "blob" and item["path"].lower().endswith(".md")
    ]


def repo_name_from_url(url: str) -> tuple[str, str]:
    """Return (org, repo) from a GitHub clone URL."""
    path = urlparse(url).path.strip("/").removesuffix(".git")
    parts = path.split("/")
    return parts[-2], parts[-1]


def is_covered(file_path: str, include_files: list[str] | None) -> bool:
    if include_files is None:
        return True
    return any(fnmatch.fnmatch(file_path, p) for p in include_files)


def infer_doc_roots(include_files: list[str] | None) -> set[str]:
    """Derive top-level doc directories implied by include_files patterns."""
    if not include_files:
        return set(DOC_ROOTS)
    roots = set()
    for pattern in include_files:
        top = pattern.split("/")[0]
        if top and top not in ("README.md", "CONTRIBUTING.md"):
            roots.add(top)
    return roots or set(DOC_ROOTS)


def check_source(source: dict, all_md_files: list[str]) -> dict:
    """Return drift findings for one source entry."""
    include_files = source.get("include_files")
    collection = source.get("collection", "user")

    doc_roots = infer_doc_roots(include_files)

    # Only look at files under relevant doc roots
    candidate_files = [f for f in all_md_files if f.split("/")[0] in doc_roots]

    # NEW_PATH: doc files not covered by include_files
    uncovered = [f for f in candidate_files if not is_covered(f, include_files)]
    # Summarise by directory (avoid listing every individual file)
    uncovered_dirs: set[str] = set()
    for f in uncovered:
        parts = f.split("/")
        summary = "/".join(parts[:3]) if len(parts) > 2 else "/".join(parts[:2])
        uncovered_dirs.add(summary + "/")

    # DEAD: patterns that match nothing
    dead_patterns = []
    if include_files:
        for pattern in include_files:
            if not any(fnmatch.fnmatch(f, pattern) for f in all_md_files):
                dead_patterns.append(pattern)

    # MISSING_DEV: has docs/contributor/* but no developer entry
    has_contributor = any(f.startswith("docs/contributor/") for f in all_md_files)
    missing_dev = has_contributor and collection != "developer"

    return {
        "uncovered_dirs": sorted(uncovered_dirs),
        "dead_patterns": dead_patterns,
        "missing_dev": missing_dev,
    }


def apply_fixes(source: dict, findings: dict, new_developer_entries: list[dict]) -> dict:
    """Return updated source entry with drift fixes applied in-place."""
    updated = dict(source)
    include_files = list(source.get("include_files") or [])

    # Add conservative glob patterns for uncovered directories
    for d in findings["uncovered_dirs"]:
        pattern = d.rstrip("/") + "/*"
        if pattern not in include_files:
            include_files.append(pattern)

    # Remove dead patterns
    for p in findings["dead_patterns"]:
        if p in include_files:
            include_files.remove(p)

    # Add a developer collection entry for repos with contributor docs,
    # and remove docs/contributor/* from the user entry to avoid cross-collection noise.
    if findings["missing_dev"]:
        include_files = [p for p in include_files if not p.startswith("docs/contributor/")]
        new_developer_entries.append(
            {
                "name": source["name"],
                "source_type": source["source_type"],
                "url": source["url"],
                "collection": "developer",
                "include_files": ["docs/contributor/*"],
            }
        )

    if include_files != list(source.get("include_files") or []):
        updated["include_files"] = include_files

    return updated


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", default=str(SOURCES_DEFAULT))
    parser.add_argument("--repo", help="Audit a single repo by name")
    parser.add_argument(
        "--auto-fix",
        action="store_true",
        help="Automatically apply fixes to docs_sources.json",
    )
    args = parser.parse_args()

    sources_path = Path(args.sources)
    if not sources_path.exists():
        print(f"ERROR: {sources_path} not found")
        sys.exit(1)

    with open(sources_path) as f:
        sources = json.load(f)

    if args.repo:
        sources = [s for s in sources if s["name"] == args.repo]
        if not sources:
            print(f"ERROR: repo '{args.repo}' not found in sources")
            sys.exit(1)

    found_any = False
    new_developer_entries: list[dict] = []
    updated_sources = []

    # Track which names already have a developer entry so we don't duplicate
    existing_dev_names = {s["name"] for s in sources if s.get("collection") == "developer"}

    for source in sources:
        name = source["name"]
        url = source.get("url", "")
        try:
            org, repo = repo_name_from_url(url)
        except (IndexError, ValueError):
            updated_sources.append(source)
            continue

        all_md = get_repo_md_files(org, repo)
        if not all_md:
            print(f"  SKIP  {name}  (no files returned or repo inaccessible)")
            updated_sources.append(source)
            continue

        findings = check_source(source, all_md)

        # Suppress MISSING_DEV if a developer entry already exists
        if findings["missing_dev"] and name in existing_dev_names:
            findings = dict(findings, missing_dev=False)

        lines = []
        for d in findings["uncovered_dirs"]:
            lines.append(f"    NEW_PATH  {d}")
        for p in findings["dead_patterns"]:
            lines.append(f"    DEAD      {p}")
        if findings["missing_dev"]:
            lines.append(
                "    MISSING_DEV  docs/contributor/* exists but no developer collection entry"
            )

        if lines:
            found_any = True
            print(f"\n{name}")
            for line in lines:
                print(line)

        if args.auto_fix and lines:
            updated_sources.append(apply_fixes(source, findings, new_developer_entries))
        else:
            updated_sources.append(source)

    if not found_any:
        print("\nNo drift found in any tracked source.")
    else:
        if args.auto_fix:
            all_sources = updated_sources + new_developer_entries
            sources_path.write_text(json.dumps(all_sources, indent=2) + "\n")
            print(f"\nAuto-fixed {len(new_developer_entries)} new developer entries added.")
            print("Review the changes with /triage-kyma-doc-sources before merging.")
        else:
            print("\nRe-run with --auto-fix to apply these fixes to docs_sources.json.")


if __name__ == "__main__":
    main()
