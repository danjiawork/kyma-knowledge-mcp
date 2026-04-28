---
name: triage-kyma-doc-sources
description: Triage doc source changes in the kyma-knowledge-mcp repo. Use this skill whenever: (1) a PR modifies docs_sources.json (especially auto-generated chore/auto-add-doc-sources-* branches), (2) the user runs check_missing_sources.py or check_source_drift.py locally and wants to evaluate the output, or (3) any docs_sources.json diff needs review. The skill evaluates new entries for user/contributor value, determines the correct ChromaDB collection (user vs contributor), removes internal tooling repos, drops stub/empty docs, and can directly update the PR branch or current working branch.
---

# Triage Kyma Doc Sources

## What this skill does

Reviews new entries added to `docs_sources.json` by the auto-discovery workflow, decides which to keep/drop/review, assigns the correct `collection` field, flags stub/empty documentation, and optionally updates the PR branch.

## Step 1 — Get the diff

Three entry points depending on context:

**A. PR number given** (e.g. `/triage-kyma-doc-sources 19`):
```bash
gh pr diff <NUMBER>
```

**B. After running a local script** (user just ran `check_missing_sources.py --auto-add` or `check_source_drift.py`):
```bash
git diff main -- kyma_knowledge_mcp/indexing/docs_sources.json
```
The script has already modified `docs_sources.json` locally — diff against main to see what changed.

**C. No PR, no local changes — run the discovery script first**:
```bash
uv run python scripts/check_missing_sources.py --auto-add
# then diff to get the entries
git diff main -- kyma_knowledge_mcp/indexing/docs_sources.json
```

In all cases, extract every new JSON entry (lines starting with `+` that contain `"name":`).
Group entries by repo name so user + contributor pairs are evaluated together.

## Step 2 — Evaluate each entry

For each new entry (or pair of entries for the same repo), apply these rules in order.

### Instant DROP (name pattern match — no LLM needed)
Drop both user and contributor entries without further analysis if the repo name contains any of:
`test-infra`, `template-`, `qa-`, `dev-tool`, `-toolkit`, `check-link`, `bootstrapper`, `-watcher` (unless it's a user-facing module), `gpu-driver`, `price-calculator`, `security-test`, `networking-dev`, `wait-for-commit`

### KEEP criteria — user collection
Keep the user entry if the repo is any of:
- A Kyma module users deploy/configure (e.g. `serverless`, `eventing-*`, `api-gateway`, `telemetry-manager`)
- A CLI or tool users run directly (e.g. `cli`, `modulectl`)
- Infrastructure users manage (e.g. `kyma-environment-broker`, `kyma-infrastructure-manager`)
- An AI assistant or tutorial resource (e.g. `kyma-companion`, `interactive-tutorials`)
- A community module catalog (`community-modules`)
- An alert/notification service users operate (`ans-manager`)

### KEEP criteria — contributor collection
Keep a contributor entry (collection: contributor) when the covered paths contain actual contributor-facing content:
- `docs/contributor/` — contribution guides, development setup, PR process
- `docs/adr/` — Architecture Decision Records
- `docs/agents/` — AI-agent coding guides
- `docs/guidelines/` — development guidelines
- `docs/internal/` — internal architecture/design docs

Drop contributor entries that are stub-only or cover nothing beyond a single README (see Stub Detection below).

### REVIEW (uncertain — needs human judgment)
Flag as REVIEW if:
- Name alone is ambiguous (e.g. `registry-proxy`, `gpu`, `ip-auth`, `compliancy`)
- Fetch the repo's README first paragraph via:
  ```bash
  gh api repos/kyma-project/<name>/contents/README.md | jq -r '.content' | base64 -d | head -20
  ```

## Step 3 — Stub detection (apply to every KEEP candidate)

After deciding a repo is KEEP-worthy by name/purpose, verify it actually has substantive content.
Run **both** checks in parallel for each KEEP candidate:

**Check A — doc directory listing:**
```bash
gh api repos/kyma-project/<name>/contents/docs/user --jq '[.[].name]'
# or for contributor entries:
gh api repos/kyma-project/<name>/contents/docs/contributor --jq '[.[].name]'
```
A directory containing only `README.md`, `_sidebar.md`, `_sidebar.ts`, or `assets` (after filtering) has **no indexable content**.

**Check B — README template detection:**
```bash
gh api repos/kyma-project/<name>/contents/README.md | jq -r '.content' | base64 -d | head -5
```
If the output contains `# {Project Title}` or `> Modify the title` or `> Provide a description`, the README is still an unfilled template.

**Stub verdict:**
- `docs/<path>/` lists **only** README/sidebar/assets → **STUB DROP** (no content to index after exclusions)
- README is template boilerplate AND no subdirectories with actual docs → **STUB DROP**
- Has subdirectories with real content (e.g. `resources/`, `tutorials/`, `technical-reference/`) → **not a stub, proceed**

Apply stub detection separately to user and contributor entries:
- User entry is stub but contributor entry has real content → drop user, keep contributor
- Both stub → drop both

## Step 4 — Determine correct collection

For each KEEP entry, verify the collection assignment:

```bash
gh api repos/kyma-project/<name>/contents/docs --jq '[.[].name]'
```

- Has `user/` subfolder → user collection (default, no `collection` field needed)
- Has `contributor/` / `adr/` / `agents/` subfolder with non-stub content → needs a separate contributor entry
- Has only `docs/*` with no `user/` subfolder → inspect content: operation guides = user, architecture/contributing = contributor
- User entry uses `docs/*` instead of `docs/user/*` when `docs/user/` exists → flag as **BROAD** (should be narrowed to avoid indexing contributor paths into user collection)

## Step 5 — Print triage results grouped by priority

Output results in **five separate sections**, in this order:

### 🟡 REVIEW — needs your input (highest priority, shown first)
Only present if there are unresolved REVIEW items.

| Repo | Why uncertain | README summary |
|------|--------------|----------------|
| registry-proxy | Ambiguous name | "Registry Proxy helps ensure security compliance…" |

---

### ✅ KEEP — will be added

Show user and contributor entries separately in the same table.

| Repo | Collection | Stub check | Dual entry? | Doc subdirs | Reason |
|------|-----------|------------|-------------|-------------|--------|
| cli | user | ✅ has content | No | user | User-facing Kyma CLI |
| serverless | user | ✅ has content | Yes (contributor) | user, contributor | Module with user + contributor docs |
| kyma-infrastructure-manager | contributor | ✅ has content | — | adr, contributor | ADRs + contribution guides |

> **Stub check**: ✅ = has real content · ⚠️ = marginal (single README only) · ❌ = stub (no indexable content)
> **Dual entry?**: Yes when the repo needs entries in both user and contributor collections.
> **Doc subdirs**: from the `[brackets]` printed by `check_missing_sources.py` or from the API listing.

---

### 🔴 DROP — reviewed and rejected
Repos where README confirmed they are internal tooling or otherwise not appropriate.

| Repo | Entries dropped | Reason |
|------|----------------|--------|
| compass-manager | user + contributor | Internal Control Plane component — registers runtimes in Compass Director |
| eventing-publisher-proxy | user + contributor | Internal proxy — not user-configurable |

---

### 🟠 DROP — stub/empty docs
Repos that are KEEP-worthy in principle but have no substantive content to index yet.
These can be re-added once documentation is written.

| Repo | Entries dropped | Stub evidence |
|------|----------------|---------------|
| gpu | user + contributor | docs/user/ = [README.md, assets, _sidebar.ts]; contributor/ = [README.md] |
| registry-cache | user + contributor | docs/user/ = [README.md, _sidebar.md] only |

---

### ⚫ DROP — instant (name pattern match)
Repos dropped without further analysis due to name patterns.

| Repo | Matched pattern |
|------|----------------|
| test-infra | `test-infra` |
| template-operator | `template-` |

---

Then print a one-line summary:
**"X to keep (Y user · Z contributor) · A reviewed drops · B stub drops · C instant drops · D need review"**

## Step 6 — Flag additional issues found during triage

After the tables, call out any problems with **existing** (already-in-main) entries. Two categories:

### 6a — Issues in entries modified by drift fix
- **BROAD user entry**: `include_files` contains `docs/*` when `docs/user/` exists — user entry will ingest contributor content
- **Misclassified directory**: A directory that is contributor-facing (e.g. `guidelines/`, `contributing/`) was added to the user collection by the drift fix
- **Dead patterns not cleaned up**: Any `DEAD` pattern still present after the fix

### 6b — Audit ALL existing non-kyma-project entries (run every triage)

Identify every existing entry whose `url` does not contain `kyma-project`. For each one:

1. **Broad pattern check**: if `include_files` contains any pattern matching `docs/*`, `*`, or `tutorials/*` without a Kyma-specific qualifier, flag as **BROAD-NON-KYMA** — these are the highest-risk entries because `fnmatch` treats `*` as matching `/`, so `docs/*` recursively matches the entire `docs/` tree.

2. **Path-level Kyma relevance AND quality check**: apply the following tiers in order.

   **Tier 1 — Fast KEEP** (skip content check): path is `docs/user/*` on a `kyma-project` repo. These are standard, low-risk patterns — the `docs/user/` convention is used consistently across Kyma modules for user-facing content.

   **Tier 2 — Content check required** — applies to all of:
   - Any path on a **non-kyma-project** repo (regardless of whether "kyma" appears in the name)
   - Contributor collection paths (`docs/contributor/*`, `docs/adr/*`, etc.) on ANY repo
   - Non-standard patterns on kyma-project repos (e.g. `docs/*` without `/user/`, `tutorials/*`, root `.md` files)

   **For non-kyma-project repos or repos without `docs/user/`**: don't try to guess which subdirectory glob to include. Instead, search the repo for Kyma-specific files first, then build targeted `*kyma*` patterns per subdirectory:

   ```bash
   # Step 1: list all subdirectories of docs/ and check which contain kyma-named files
   gh api repos/<org>/<repo>/contents/docs --jq '[.[] | select(.type=="dir") | .name]'

   # Step 2: for each subdirectory, find files with "kyma" in the filename
   gh api repos/<org>/<repo>/contents/docs/<subdir> \
     --jq '[.[] | select(.name | ascii_downcase | contains("kyma")) | .name]'
   ```

   If a subdirectory has kyma-named files, add `docs/<subdir>/*kyma*` to `include_files`. This pattern uses fnmatch (where `*` matches any character including `/`), so it recursively selects any path under that subdirectory whose full path contains "kyma" — while the fetcher's `filter_file_types: ["md"]` already excludes images and other non-.md assets.

   Note: the fetcher always filters out non-.md files regardless of include patterns, so you do NOT need to add `*.md` suffixes to patterns or explicitly exclude asset directories.

   For Tier 2 contributor content, also evaluate on **two dimensions** after finding the files:

   ```bash
   # Step 1: list files in the directory
   gh api repos/<org>/<repo>/contents/<path> | jq -r '.[].name'
   # Step 2: fetch content of the first 1-2 .md files
   gh api repos/<org>/<repo>/contents/<path>/<file> | jq -r '.content' | base64 -d | head -40
   ```

   **Dimension A — Kyma relevance** (is it about Kyma?):
   - Relevant: discusses Kyma runtime, Kyma modules, Kyma-specific resources (APIRule, Kyma CR, Kyma Functions, SAP BTP Kyma Environment)
   - Not relevant: covers only generic BTP, CF, ABAP, HANA, or Fiori topics with no Kyma-specific guidance

   **Dimension B — User/contributor value vs internal infrastructure** (even if Kyma-related):
   - Valuable: contribution guides, API docs, module configuration reference, architecture decisions (ADRs), tutorials
   - ⚠️ Internal infrastructure noise — **exclude even if Kyma-related**: hyperscaler account pool rules, region/machine/zone configuration tables, internal routing configs, platform team operational runbooks. These use region/hyperscaler terminology that semantically matches user questions but describe internal platform behavior — RAG will surface them as false authoritative answers.
   - When a specific file within an otherwise-good directory is infrastructure noise, add it to `exclude_files` rather than removing the entire directory from `include_files`. For directories with many bad files, switch to explicit per-file include patterns instead of `*` globs.

3. **Output a path-level table** for each non-kyma-project repo:

| Path pattern | Verdict | Reason |
|---|---|---|
| `tutorials/cp-kyma-*` | ✅ KEEP | "kyma" in path name |
| `tutorials/remote-service-configure-connectivity/*` | ❌ DROP | Generic BTP connectivity, no Kyma content |
| `docs/*` | ⚠️ BROAD-NON-KYMA | Matches entire doc tree — needs specific Kyma paths |

Format per-repo issues as:
> ⚠️ **Issue — `<repo>`**: `<field>` = `<value>` — `<why it's a problem>` · Suggested fix: `<fix>`

## Step 7 — Ask for confirmation

Ask the user:
1. Confirm the KEEP/DROP decisions (especially REVIEW and stub items)
2. Whether to fix any flagged issues in existing entries
3. Whether to apply all changes now

## Step 8 — Apply changes (if confirmed)

Fetch the PR branch and apply the filtered `docs_sources.json`:

```bash
# Fetch PR branch
gh pr checkout <NUMBER>

# Or if working on current branch, skip the checkout
```

Then edit `kyma_knowledge_mcp/indexing/docs_sources.json`:
- Remove all DROP entries (reviewed drops, stub drops, instant drops)
- Fix BROAD entries (narrow `docs/*` → `docs/user/*` where appropriate)
- Fix misclassified directories (move contributor-only paths from user to contributor entries)
- For repos needing both user + contributor entries, ensure both are present

### Blocklist update — permanent drops only

After removing DROP entries, decide whether each drop is **permanent** or **temporary**:

**Permanent drop** — repo is definitively not Kyma-relevant (internal tooling, CI infra, unrelated project):
→ Add the repo name to `_BLOCKLIST_SUBSTRINGS` in `scripts/check_missing_sources.py` so it is never re-discovered by the auto-discovery script.

```python
_BLOCKLIST_SUBSTRINGS = [
    ...
    "eventing-publisher-proxy",  # internal proxy, not user-configurable
    "compass-manager",           # internal control plane component
]
```

**Temporary drop** — repo exists but docs are a stub or the project is in early stage:
→ Only remove from `docs_sources.json`. Do NOT add to the blocklist. The CI will re-discover it on the next run, and the triage skill will re-run stub detection — if docs have matured since the last drop, it can be kept then.

Commit and push:
```bash
git add kyma_knowledge_mcp/indexing/docs_sources.json scripts/check_missing_sources.py
git commit -m "chore: triage auto-discovered doc sources — keep user-facing, remove internal tooling"
git push
```

## Key rules

- Default collection is `"user"` — only add the `collection` field when it's `"contributor"`
- Never add internal tooling: CI/CD infra, templates, dev toolboxes, GitHub Actions, link checkers
- Stub repos (docs/user/ or docs/contributor/ contains only README + sidebar) produce zero indexed content — drop them temporarily; they can be re-added when docs are written
- REVIEW items block the apply step — resolve them first
- Evaluate user and contributor entries independently: a repo can have a KEEP contributor entry and a STUB DROP user entry (or vice versa)
- The `check_missing_sources.py` blocklist already filters the most obvious cases; this skill handles the remainder
- **Permanent drops go to the blocklist; temporary drops (stubs, early-stage) do not** — this ensures stub repos are re-evaluated automatically as they mature
