---
name: triage-kyma-doc-sources
description: Triage doc source changes in the kyma-knowledge-mcp repo. Use this skill whenever: (1) a PR modifies docs_sources.json (especially auto-generated chore/auto-add-doc-sources-* branches), (2) the user runs check_missing_sources.py or check_source_drift.py locally and wants to evaluate the output, or (3) any docs_sources.json diff needs review. The skill evaluates new entries for user/developer value, determines the correct ChromaDB collection (user vs developer), removes internal tooling repos, drops stub/empty docs, and can directly update the PR branch or current working branch.
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
Group entries by repo name so user + developer pairs are evaluated together.

## Step 2 — Evaluate each entry

For each new entry (or pair of entries for the same repo), apply these rules in order.

### Instant DROP (name pattern match — no LLM needed)
Drop both user and developer entries without further analysis if the repo name contains any of:
`test-infra`, `template-`, `qa-`, `dev-tool`, `-toolkit`, `check-link`, `bootstrapper`, `-watcher` (unless it's a user-facing module), `gpu-driver`, `price-calculator`, `security-test`, `networking-dev`, `wait-for-commit`

### KEEP criteria — user collection
Keep the user entry if the repo is any of:
- A Kyma module users deploy/configure (e.g. `serverless`, `eventing-*`, `api-gateway`, `telemetry-manager`)
- A CLI or tool users run directly (e.g. `cli`, `modulectl`)
- Infrastructure users manage (e.g. `kyma-environment-broker`, `kyma-infrastructure-manager`)
- An AI assistant or tutorial resource (e.g. `kyma-companion`, `interactive-tutorials`)
- A community module catalog (`community-modules`)
- An alert/notification service users operate (`ans-manager`)

### KEEP criteria — developer collection
Keep a developer entry (collection: developer) when the covered paths contain actual developer-facing content:
- `docs/contributor/` — contribution guides, development setup, PR process
- `docs/adr/` — Architecture Decision Records
- `docs/agents/` — AI-agent coding guides
- `docs/guidelines/` — development guidelines
- `docs/internal/` — internal architecture/design docs

Drop developer entries that are stub-only or cover nothing beyond a single README (see Stub Detection below).

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
# or for developer entries:
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

Apply stub detection separately to user and developer entries:
- User entry is stub but developer entry has real content → drop user, keep developer
- Both stub → drop both

## Step 4 — Determine correct collection

For each KEEP entry, verify the collection assignment:

```bash
gh api repos/kyma-project/<name>/contents/docs --jq '[.[].name]'
```

- Has `user/` subfolder → user collection (default, no `collection` field needed)
- Has `contributor/` / `adr/` / `agents/` subfolder with non-stub content → needs a separate developer entry
- Has only `docs/*` with no `user/` subfolder → inspect content: operation guides = user, architecture/contributing = developer
- User entry uses `docs/*` instead of `docs/user/*` when `docs/user/` exists → flag as **BROAD** (should be narrowed to avoid indexing developer paths into user collection)

## Step 5 — Print triage results grouped by priority

Output results in **five separate sections**, in this order:

### 🟡 REVIEW — needs your input (highest priority, shown first)
Only present if there are unresolved REVIEW items.

| Repo | Why uncertain | README summary |
|------|--------------|----------------|
| registry-proxy | Ambiguous name | "Registry Proxy helps ensure security compliance…" |

---

### ✅ KEEP — will be added

Show user and developer entries separately in the same table.

| Repo | Collection | Stub check | Dual entry? | Doc subdirs | Reason |
|------|-----------|------------|-------------|-------------|--------|
| cli | user | ✅ has content | No | user | User-facing Kyma CLI |
| serverless | user | ✅ has content | Yes (developer) | user, contributor | Module with user + contributor docs |
| kyma-infrastructure-manager | developer | ✅ has content | — | adr, contributor | ADRs + contribution guides |

> **Stub check**: ✅ = has real content · ⚠️ = marginal (single README only) · ❌ = stub (no indexable content)
> **Dual entry?**: Yes when the repo needs entries in both user and developer collections.
> **Doc subdirs**: from the `[brackets]` printed by `check_missing_sources.py` or from the API listing.

---

### 🔴 DROP — reviewed and rejected
Repos where README confirmed they are internal tooling or otherwise not appropriate.

| Repo | Entries dropped | Reason |
|------|----------------|--------|
| compass-manager | user + developer | Internal Control Plane component — registers runtimes in Compass Director |
| eventing-publisher-proxy | user + developer | Internal proxy — not user-configurable |

---

### 🟠 DROP — stub/empty docs
Repos that are KEEP-worthy in principle but have no substantive content to index yet.
These can be re-added once documentation is written.

| Repo | Entries dropped | Stub evidence |
|------|----------------|---------------|
| gpu | user + developer | docs/user/ = [README.md, assets, _sidebar.ts]; contributor/ = [README.md] |
| registry-cache | user + developer | docs/user/ = [README.md, _sidebar.md] only |

---

### ⚫ DROP — instant (name pattern match)
Repos dropped without further analysis due to name patterns.

| Repo | Matched pattern |
|------|----------------|
| test-infra | `test-infra` |
| template-operator | `template-` |

---

Then print a one-line summary:
**"X to keep (Y user · Z developer) · A reviewed drops · B stub drops · C instant drops · D need review"**

## Step 6 — Flag additional issues found during triage

After the tables, call out any problems with **existing** (already-in-main) entries that were modified by the drift fix. Common issues to flag:

- **BROAD user entry**: `include_files` contains `docs/*` when `docs/user/` exists — user entry will ingest developer content
- **Misclassified directory**: A directory that is developer-facing (e.g. `guidelines/`, `contributing/`) was added to the user collection by the drift fix
- **Dead patterns not cleaned up**: Any `DEAD` pattern still present after the fix

Format as:
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
- Fix misclassified directories (move developer-only paths from user to developer entries)
- For repos needing both user + developer entries, ensure both are present

Commit and push:
```bash
git add kyma_knowledge_mcp/indexing/docs_sources.json
git commit -m "chore: triage auto-discovered doc sources — keep user-facing, remove internal tooling"
git push
```

## Key rules

- Default collection is `"user"` — only add the `collection` field when it's `"developer"`
- Never add internal tooling: CI/CD infra, templates, dev toolboxes, GitHub Actions, link checkers
- Stub repos (docs/user/ or docs/contributor/ contains only README + sidebar) produce zero indexed content — drop them; they can be re-added when docs are written
- REVIEW items block the apply step — resolve them first
- Evaluate user and developer entries independently: a repo can have a KEEP developer entry and a STUB DROP user entry (or vice versa)
- The `check_missing_sources.py` blocklist already filters the most obvious cases; this skill handles the remainder
