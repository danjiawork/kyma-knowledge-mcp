"""Audit existing docs_sources.json entries for doc drift in tracked repos.

For each tracked repo, checks:
  NEW_PATH    — doc directories present in the repo but not covered by
                include_files
  DEAD        — include_files patterns that match no files in the repo
  MISSING_DEV — repos with developer-facing docs but no developer entry

Usage:
    uv run python scripts/check_source_drift.py
    uv run python scripts/check_source_drift.py --auto-fix
    uv run python scripts/check_source_drift.py --repo api-gateway
    uv run python scripts/check_source_drift.py \\
        --sources path/to/docs_sources.json
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

# Second-level subdirectory names skipped when checking USER collection drift.
# These are developer-facing paths — they should not be reported as NEW_PATH
# for user entries (they belong in the developer collection instead).
_SKIP_USER_SUBDIRS = {
    "contributor",
    "contributing",
    "agents",  # AI-agent coding guides, developer-facing
    "adr",  # Architecture Decision Records, developer-facing
    "internal",  # internal architecture/design docs
    "guidelines",  # development guidelines, developer-facing
    "release-notes",
    "release_notes",
    "assets",
    "images",
    "img",
    "figures",
    "operator",  # platform-operator/admin guides, not end-user docs
    "governance",  # project governance, not product docs
    "loadtest",  # load-testing tooling, developer-facing
}

# Second-level subdirectory names skipped when checking DEVELOPER collection
# drift.  Only non-content directories are listed here — developer-facing
# paths (agents, adr, etc.) are intentionally absent so that uncovered
# developer content is reported as NEW_PATH.
_SKIP_DEV_SUBDIRS = {
    "release-notes",
    "release_notes",
    "assets",
    "images",
    "img",
    "figures",
    "governance",
    "loadtest",
    "operator",
}

# Developer-facing subdirectory names.  MISSING_DEV fires when any of these
# exist in a repo but no developer collection entry covers them.
_DEVELOPER_SUBDIRS = {
    "contributor",
    "contributing",
    "agents",
    "adr",
    "guidelines",
    "internal",
}

# Minimum path depth for a file to be considered inside a subdirectory.
_MIN_SUBDIR_DEPTH = 2


def gh_json(endpoint: str) -> dict | list | None:
    """Call the GitHub API and return parsed JSON, or None on error."""
    result = subprocess.run(
        ["gh", "api", endpoint],
        capture_output=True,
        text=True,
        check=False,
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
    """Return True if file_path matches at least one pattern in include_files."""
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


def _uncovered_dirs(
    uncovered: list[str],
    collection: str,
) -> set[str]:
    """Summarise uncovered files as directory paths, skipping irrelevant dirs."""
    skip = _SKIP_DEV_SUBDIRS if collection == "developer" else _SKIP_USER_SUBDIRS
    dirs: set[str] = set()
    for f in uncovered:
        parts = f.split("/")
        if len(parts) >= _MIN_SUBDIR_DEPTH and parts[1] in skip:
            continue
        parent = parts[:-1]
        if len(parent) <= 1:
            continue
        dirs.add("/".join(parent[:3]) + "/")
    return dirs


def check_source(source: dict, all_md_files: list[str]) -> dict:
    """Return drift findings for one source entry."""
    include_files = source.get("include_files")
    collection = source.get("collection", "user")

    if collection == "developer":
        # Scope candidate files to developer-facing directories only.
        candidate_files = [
            f
            for f in all_md_files
            if any(f.startswith(f"docs/{sub}/") for sub in _DEVELOPER_SUBDIRS)
        ]
    else:
        doc_roots = infer_doc_roots(include_files)
        candidate_files = [f for f in all_md_files if f.split("/")[0] in doc_roots]

    uncovered = [f for f in candidate_files if not is_covered(f, include_files)]
    uncovered_dir_set = _uncovered_dirs(uncovered, collection)

    dead_patterns: list[str] = []
    if include_files:
        dead_patterns = [
            p for p in include_files if not any(fnmatch.fnmatch(f, p) for f in all_md_files)
        ]

    dev_subdirs_found = sorted(
        sub for sub in _DEVELOPER_SUBDIRS if any(f.startswith(f"docs/{sub}/") for f in all_md_files)
    )
    missing_dev = bool(dev_subdirs_found) and collection != "developer"

    broad_patterns: list[str] = []
    if include_files and any(f.startswith("docs/user/") for f in all_md_files):
        broad_patterns = [p for p in include_files if p == "docs/*"]

    return {
        "uncovered_dirs": sorted(uncovered_dir_set),
        "dead_patterns": dead_patterns,
        "missing_dev": missing_dev,
        "dev_subdirs": dev_subdirs_found,
        "broad_patterns": broad_patterns,
    }


def _deduplicate_patterns(patterns: list[str]) -> list[str]:
    """Remove patterns already covered by a broader sibling in the same list.

    e.g. if docs/user/* and docs/user/architecture/* both exist,
    docs/user/architecture/* is redundant and gets removed.
    """
    result = []
    for p in patterns:
        representative = (p[:-1] + "x.md") if p.endswith("/*") else p
        covered = any(other != p and fnmatch.fnmatch(representative, other) for other in patterns)
        if not covered:
            result.append(p)
    return result


def apply_fixes(source: dict, findings: dict, new_developer_entries: list[dict]) -> dict:
    """Return updated source entry with drift fixes applied."""
    updated = dict(source)
    include_files = list(source.get("include_files") or [])

    # Fix BROAD: replace docs/* with docs/user/* when docs/user/ exists.
    for p in findings.get("broad_patterns", []):
        if p in include_files:
            include_files.remove(p)
            if "docs/user/*" not in include_files:
                include_files.append("docs/user/*")

    # Add glob patterns for uncovered directories (skip already-covered ones).
    for d in findings["uncovered_dirs"]:
        pattern = d.rstrip("/") + "/*"
        if pattern in include_files:
            continue
        representative = d.rstrip("/") + "/x.md"
        if any(fnmatch.fnmatch(representative, p) for p in include_files):
            continue
        include_files.append(pattern)

    # Remove dead patterns.
    for p in findings["dead_patterns"]:
        if p in include_files:
            include_files.remove(p)

    # Create a developer entry covering all found developer subdirs,
    # and strip those paths from the user entry to avoid noise.
    if findings["missing_dev"]:
        dev_subdirs = findings.get("dev_subdirs", ["contributor"])
        include_files = [
            p for p in include_files if not any(p.startswith(f"docs/{sub}/") for sub in dev_subdirs)
        ]
        new_developer_entries.append(
            {
                "name": source["name"],
                "source_type": source["source_type"],
                "url": source["url"],
                "collection": "developer",
                "include_files": [f"docs/{sub}/*" for sub in dev_subdirs],
            }
        )

    include_files = _deduplicate_patterns(include_files)
    if include_files != list(source.get("include_files") or []):
        updated["include_files"] = include_files
    return updated


def _format_findings(findings: dict) -> list[str]:
    """Return printable report lines for a set of drift findings."""
    lines = []
    for d in findings["uncovered_dirs"]:
        lines.append(f"    NEW_PATH  {d}")
    for p in findings["dead_patterns"]:
        lines.append(f"    DEAD      {p}")
    for p in findings["broad_patterns"]:
        lines.append(f"    BROAD     {p}  (docs/user/ exists — use docs/user/*)")
    if findings["missing_dev"]:
        dev_paths = ", ".join(f"docs/{s}/*" for s in findings.get("dev_subdirs", ["contributor"]))
        lines.append(
            f"    MISSING_DEV  developer content ({dev_paths}) — no developer collection entry"
        )
    return lines


def _process_source(
    source: dict,
    existing_dev_names: set[str],
    auto_fix: bool,
    new_developer_entries: list[dict],
) -> tuple[dict, list[str]]:
    """Fetch remote md files, check drift, and optionally apply fixes.

    Returns (updated_source, report_lines).
    """
    name = source["name"]
    url = source.get("url", "")
    try:
        org, repo = repo_name_from_url(url)
    except (IndexError, ValueError):
        return source, []

    all_md = get_repo_md_files(org, repo)
    if not all_md:
        print(f"  SKIP  {name}  (no files returned or repo inaccessible)")
        return source, []

    findings = check_source(source, all_md)
    if findings["missing_dev"] and name in existing_dev_names:
        findings = dict(findings, missing_dev=False)

    lines = _format_findings(findings)
    if auto_fix and lines:
        return apply_fixes(source, findings, new_developer_entries), lines
    return source, lines


def main() -> None:
    """Audit docs_sources.json entries for doc drift and optionally fix them."""
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

    with open(sources_path, encoding="utf-8") as f:
        sources = json.load(f)

    if args.repo:
        sources = [s for s in sources if s["name"] == args.repo]
        if not sources:
            print(f"ERROR: repo '{args.repo}' not found in sources")
            sys.exit(1)

    existing_dev_names = {s["name"] for s in sources if s.get("collection") == "developer"}

    found_any = False
    new_developer_entries: list[dict] = []
    updated_sources = []

    for source in sources:
        updated, lines = _process_source(
            source, existing_dev_names, args.auto_fix, new_developer_entries
        )
        updated_sources.append(updated)
        if lines:
            found_any = True
            print(f"\n{source['name']}")
            for line in lines:
                print(line)

    if not found_any:
        print("\nNo drift found in any tracked source.")
        return

    if args.auto_fix:
        all_sources = updated_sources + new_developer_entries
        sources_path.write_text(json.dumps(all_sources, indent=2) + "\n", encoding="utf-8")
        print(f"\nAuto-fixed. {len(new_developer_entries)} new developer entries added.")
        print("Review the changes with /triage-kyma-doc-sources before merging.")
    else:
        print("\nRe-run with --auto-fix to apply these fixes to docs_sources.json.")


if __name__ == "__main__":
    main()
