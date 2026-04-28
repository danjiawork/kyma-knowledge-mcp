"""Check for kyma-project repos with docs that are not in docs_sources.json.

Usage:
    uv run python scripts/check_missing_sources.py
    uv run python scripts/check_missing_sources.py --auto-add
    uv run python scripts/check_missing_sources.py \\
        --sources kyma_knowledge_mcp/indexing/docs_sources.json
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

ORGS = ["kyma-project"]
SOURCES_DEFAULT = Path(__file__).parent.parent / "kyma_knowledge_mcp/indexing/docs_sources.json"

# Repos whose names match any of these substrings are skipped: they are
# internal tooling that would add noise to user-facing search results.
_BLOCKLIST_SUBSTRINGS = [
    "test-infra",
    "template-",
    "qa-",
    "dev-tool",
    "-toolkit",
    "check-link",
    "bootstrapper",
    "gpu-driver",
    "price-calculator",
    "security-test",
    "networking-dev",
    "wait-for-commit",
]

# Subdirectory names under docs/ that are not user-facing content.
_SKIP_SUBDIRS = {
    "release-notes",
    "release_notes",
    "assets",
    "images",
    "img",
    "figures",
    "contributor",
    "operator",  # platform-operator/admin guides, not end-user docs
    "agents",  # AI-agent coding guides, contributor-facing
    "adr",  # Architecture Decision Records, contributor-facing
    "internal",  # internal architecture/design docs
    "contributing",  # contribution process docs, contributor-facing
    "governance",  # project governance, not product docs
    "guidelines",  # development guidelines, contributor-facing
    "loadtest",  # load-testing tooling, contributor-facing
}

# Contributor-facing subdirectory names under docs/ that belong in the contributor
# collection.  These are skipped in user discovery but picked up when building
# contributor entries — so content like architecture decisions, AI-agent guides,
# and contribution how-tos is captured rather than silently dropped.
_CONTRIBUTOR_SUBDIRS = {
    "contributor",  # contribution guides (canonical path)
    "contributing",  # alternate naming for contribution guides
    "agents",  # AI-agent coding guides
    "adr",  # Architecture Decision Records
    "guidelines",  # development guidelines
    "internal",  # internal architecture/design docs
}

# Root-level .md files that are governance/meta and not user documentation.
_SKIP_ROOT_FILES = {
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "NOTICE.md",
    "SECURITY.md",
    "CODEOWNERS.md",
}

# Loose .md files directly under a doc root that are not user documentation
# (navigation scaffolding, changelogs, framework config, governance).
_SKIP_DOC_LOOSE_FILES = {
    "index.md",
    "release-notes.md",
    "vitepress-structure.md",
    "support-contribution.md",
    "emeritus.md",
    "_sidebar.md",
}


def _is_internal(repo_name: str) -> bool:
    """Return True if the repo is internal tooling that should be skipped."""
    name = repo_name.lower()
    return any(pat in name for pat in _BLOCKLIST_SUBSTRINGS)


def gh(endpoint: str) -> list | dict:
    """Call the GitHub API with pagination and return parsed JSON."""
    result = subprocess.run(
        ["gh", "api", "--paginate", endpoint],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    try:
        data = json.loads(result.stdout)
        return data if isinstance(data, list) else [data]
    except json.JSONDecodeError:
        return []


def get_repo_md_files(org: str, repo: str) -> list[str]:
    """Return all .md paths via git tree API (recursive, any depth)."""
    result = subprocess.run(
        ["gh", "api", f"repos/{org}/{repo}/git/trees/HEAD?recursive=1"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    try:
        data = json.loads(result.stdout)
        return [
            item["path"]
            for item in data.get("tree", [])
            if item.get("type") == "blob" and item["path"].lower().endswith(".md")
        ]
    except (json.JSONDecodeError, KeyError):
        return []


def has_user_docs(md_files: list[str]) -> str | None:
    """Return the doc path type given the repo's full .md file list."""
    if any(f.startswith("docs/user/") for f in md_files):
        return "docs/user"
    if any(f.startswith("docs/") for f in md_files):
        # Only report as having docs if there are user-facing subdirs after
        # skipping contributor/governance/internal dirs.  Repos whose docs/
        # content is entirely under skipped paths produce no useful content.
        if _doc_subdirs(md_files, "docs"):
            return "docs"
    if any(f.startswith("tutorials/") for f in md_files):
        return "tutorials"
    return None


def _doc_subdirs(md_files: list[str], doc_path: str) -> list[str]:
    """Return subdirectory names under doc_path, skipping non-user dirs."""
    seen: set[str] = set()
    prefix = doc_path + "/"
    for f in md_files:
        if f.startswith(prefix):
            rest = f[len(prefix) :]
            if "/" in rest:
                subdir = rest.split("/")[0]
                if subdir not in _SKIP_SUBDIRS and not subdir.startswith("_"):
                    seen.add(subdir)
    return sorted(seen)


def build_source_entries(
    repo: str,
    doc_path: str,
    html_url: str,
    md_files: list[str],
) -> list[dict]:
    """Build docs_sources.json entries for a repo.

    Returns two entries when both docs/user/ and docs/contributor/ exist,
    otherwise returns a single user entry.
    """
    base: dict = {
        "name": repo,
        "source_type": "Github",
        "url": f"{html_url}.git",
    }

    # --- user entry ---
    if doc_path.endswith("/user"):
        user_entry = dict(base)
        user_entry["include_files"] = [f"{doc_path}/*"]
        user_entry["exclude_files"] = [
            f"{doc_path}/README.md",
            "*/_sidebar.md",
        ]
    else:
        # For docs/ or tutorials/: subdirectory-level globs instead of docs/*
        include: list[str] = []

        # Root-level .md files — skip governance/meta files
        root_mds = [
            f
            for f in md_files
            if "/" not in f
            and f.endswith(".md")
            and not f.startswith("_")
            and f not in _SKIP_ROOT_FILES
        ]
        include.extend(root_mds)

        # Per-subdirectory globs
        for subdir in _doc_subdirs(md_files, doc_path):
            include.append(f"{doc_path}/{subdir}/*")

        # Loose .md files directly under doc_path (e.g. docs/glossary.md)
        prefix = doc_path + "/"
        for f in md_files:
            if f.startswith(prefix):
                tail = f[len(prefix) :]
                if (
                    "/" not in tail
                    and not tail.startswith("_")
                    and tail not in _SKIP_DOC_LOOSE_FILES
                ):
                    include.append(f)

        user_entry = dict(base)
        if include:
            user_entry["include_files"] = sorted(set(include))
        user_entry["exclude_files"] = ["*/_sidebar.md"]

    entries = [user_entry]

    # --- contributor entry (when any contributor-facing subdir exists) ---
    dev_subdirs = sorted(
        sub for sub in _CONTRIBUTOR_SUBDIRS if any(f.startswith(f"docs/{sub}/") for f in md_files)
    )
    if dev_subdirs:
        dev_entry = dict(base)
        dev_entry["collection"] = "contributor"
        dev_entry["include_files"] = [f"docs/{sub}/*" for sub in dev_subdirs]
        entries.append(dev_entry)

    return entries


def main() -> None:
    """Entrypoint."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", default=str(SOURCES_DEFAULT))
    parser.add_argument(
        "--auto-add",
        action="store_true",
        help=(
            "Automatically add missing entries to docs_sources.json"
            " with conservative include patterns"
        ),
    )
    args = parser.parse_args()

    sources_path = Path(args.sources)
    if not sources_path.exists():
        print(f"ERROR: {sources_path} not found")
        sys.exit(1)

    with open(sources_path, encoding="utf-8") as f:
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
            if _is_internal(name):
                continue
            md_files = get_repo_md_files(org, name)
            doc_path = has_user_docs(md_files)
            if doc_path:
                subdirs = _doc_subdirs(md_files, doc_path)
                subdirs_str = ", ".join(subdirs[:5]) + ("..." if len(subdirs) > 5 else "")
                dev_subdirs = sorted(
                    sub
                    for sub in _CONTRIBUTOR_SUBDIRS
                    if any(f.startswith(f"docs/{sub}/") for f in md_files)
                )
                dev_flag = f"  [+contributor: {', '.join(dev_subdirs)}]" if dev_subdirs else ""
                print(f"  MISSING  {name:40s}  {doc_path}/  [{subdirs_str}]{dev_flag}")
                missing.append(
                    {
                        "name": name,
                        "html_url": html_url,
                        "doc_path": doc_path,
                        "org": org,
                        "md_files": md_files,
                    }
                )

    if not missing:
        print("\nNo missing sources found.")
        return

    print(f"\nFound {len(missing)} repo(s) with docs not in sources.")

    if not args.auto_add:
        print("\nRe-run with --auto-add to write these entries to docs_sources.json.")
        return

    new_entries: list[dict] = []
    for m in missing:
        entries = build_source_entries(m["name"], m["doc_path"], m["html_url"], m["md_files"])
        new_entries.extend(entries)

    sources.extend(new_entries)
    sources_path.write_text(json.dumps(sources, indent=2) + "\n", encoding="utf-8")
    print(f"\nAdded {len(new_entries)} new entrie(s) to {sources_path}")
    print("Review the added entries and adjust include_files as needed before merging.")
    for e in new_entries:
        collection = e.get("collection", "user")
        print(f"  - {e['name']} [{collection}]: {e.get('include_files', [])}")


if __name__ == "__main__":
    main()
