---
name: wiki-publish
description: Publish the rbk-pkm-wiki to the GitHub Pages website. Runs sync-wiki.py to convert wiki pages and wikilinks into Jekyll-compatible markdown, commits the result to the bharthu58.github.io repo, and pushes to trigger the GitHub Actions deploy. Run when you say /wiki-publish or ask to publish, deploy, or sync the wiki to the website.
---

<!-- version: 1.0 -->

# Wiki Publish

Syncs the Obsidian wiki to the GitHub Pages Jekyll site and triggers a live deploy.

---

## Capability Requirements

Requires Bash access to run Python scripts and git commands. The Jekyll site repo must be present at `/home/bharthu/repos/github/bharthu58.github.io`.

---

## Pipeline Overview

```
rbk-pkm-wiki/*.md
      ↓  tools/sync-wiki.py
_wiki/*.md  (wikilinks converted, Jekyll frontmatter injected)
      ↓  git commit + push
GitHub Actions  →  html-proofer  →  GitHub Pages live site
```

---

## Workflow

### Step 1 — Verify preconditions

Check that:
- `/home/bharthu/repos/github/bharthu58.github.io` exists
- `tools/sync-wiki.py` is present in the pkm-wiki repo at `/home/bharthu/repos/github/rbk-ai-projects/claude-code-projects/pkm-wiki/tools/sync-wiki.py`
- The wiki source at `/mnt/g/My Drive/RBK-OBSIDIAN-NOTES/rbk-obsidian-vault/Agent Access/rbk-pkm-wiki` exists

If any check fails, report clearly and stop.

### Step 2 — Run sync-wiki.py

```bash
python3 /home/bharthu/repos/github/rbk-ai-projects/claude-code-projects/pkm-wiki/tools/sync-wiki.py
```

This script:
- Clears all existing `_wiki/*.md` files
- Copies every wiki page (excluding `index.md` and `log.md`)
- Converts `[[wikilinks]]` to `/wiki/<slug>/` markdown links
- Converts unresolved wikilinks to plain text (required — html-proofer runs on CI)
- Injects `layout: page` frontmatter for Jekyll

Report the count of pages synced.

### Step 3 — Check git status

```bash
cd /home/bharthu/repos/github/bharthu58.github.io
git status --short _wiki/ _data/wiki_graph.json
git diff --stat HEAD -- _wiki/ _data/wiki_graph.json
```

If there are no changes to `_wiki/` or `_data/wiki_graph.json`, report "No changes to publish — wiki is already up to date." and stop.

### Step 4 — Commit

```bash
cd /home/bharthu/repos/github/bharthu58.github.io
git add _wiki/ _data/wiki_graph.json
git commit -m "wiki sync $(date +%Y-%m-%d)"
```

Report the commit hash.

### Step 5 — Push

```bash
cd /home/bharthu/repos/github/bharthu58.github.io
git push
```

### Step 6 — Report

Report:
- Number of pages published
- Commit hash
- That GitHub Actions will run html-proofer and deploy (typically takes 1–2 minutes)
- The live site URL: `https://bharthu58.github.io`

---

## Key Rules

1. **Never run `bundle exec jekyll`** during publish — the build runs on GitHub Actions, not locally
2. **Only commit `_wiki/` and `_data/wiki_graph.json`** — do not stage other files unless the user explicitly requests it
3. **`mise exec ruby@3.3.10 --`** prefix is only needed for local `jekyll serve` (via `run.sh`), not for sync or push
4. **Unresolved wikilinks must be plain text** — already handled by sync-wiki.py; do not modify this behaviour
5. **`index.md` and `log.md` are excluded** from sync — they are agent-maintenance files, not public pages

---

## Local Preview (optional, not part of publish)

To preview the site locally before pushing:
```bash
cd /home/bharthu/repos/github/bharthu58.github.io
mise exec ruby@3.3.10 -- bundle exec jekyll serve --livereload
```
Then open `http://localhost:4000`.
