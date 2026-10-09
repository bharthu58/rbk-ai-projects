# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

This is the **agent project repo** for the RBK PKM wiki system. It is a staging area and toolbox — it does NOT contain the final wiki. The final wiki pages live in the Obsidian vault at a separate path (see `wiki-config.md`).

This repo contains:
- `.claude/skills/` — the five wiki skills
- `tools/` — Python ingestion tools (medium_ingest, podcast_ingest)
- `raw/` — drop zone for source files awaiting ingestion
- `ingested/` — archive of processed source files
- `archive/` — deprecated pages and lint reports
- `wiki-config.md` — single config file read by all five skills

## Agent access boundary

This repo is entirely within agent scope. The Obsidian vault at `wiki_root` (see `wiki-config.md`) is a separate location — agents write wiki pages there, but never touch personal vault areas outside `Agent Access/rbk-pkm-wiki/`.

## The wiki system

The wiki is built on the [LLM-wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f): a persistent, compounding Markdown knowledge base maintained by LLM agents rather than retrieved from raw documents at query time.

### Five skills (installed in Claude Desktop)

| Skill | Slash command | What it does |
|---|---|---|
| `wiki-ingest` | `/wiki-ingest` | Reads files from `raw/`, synthesises wiki pages, moves files to `ingested/` as atomic commit |
| `wiki-query` | `/wiki-query` | Answers questions from wiki content with `[[wikilink]]` citations |
| `wiki-lint` | `/wiki-lint` | Health-checks wiki: broken links, orphans, stale index entries, orphaned sources |
| `wiki-integrate` | `/wiki-integrate` | Weaves a new/updated page into the knowledge graph with backlinks and index entry |
| `wiki-crystallize` | `/wiki-crystallize` | Distils a working session or chat into a structured wiki page |

Skill definitions live in `.claude/skills/` (not inside `rbk-pkm-wiki/`).

### Wiki directory layout

**Agent project repo** (`staging_root` in wiki-config.md):
```
pkm-wiki/                  ← this repo
├── wiki-config.md         ← single config file read by all five skills
├── .claude/skills/        ← skill definitions
├── tools/                 ← Python ingestion tools
├── raw/                   ← drop source files here; wiki-ingest processes them
│   ├── web-clippings/
│   └── assets/
├── ingested/              ← processed sources archived here (the move = the record)
│   ├── clippings/
│   ├── documentation/
│   ├── articles/
│   ├── notes/
│   ├── data/
│   ├── podcasts/
│   └── assets/            ← images and unreadable files land here
└── archive/               ← lint reports and deprecated agent artifacts
```

**Obsidian vault** (`wiki_root` in wiki-config.md) — final wiki only:
```
Agent Access/rbk-pkm-wiki/    ← ALL wiki pages live here (vault path)
├── Overview.md               ← top-level summary; session bootstrap for new agents
├── index.md                  ← page catalogue (agent-maintained)
├── log.md                    ← append-only audit trail (agent-maintained)
├── ai/
├── cpp/
├── devops/
├── linux/
├── python/
├── obsidian/
├── web/
└── meta/
```

### How `wiki-config.md` works

All five skills search for `wiki-config.md` by filename. It contains:
- `wiki_root` — absolute path to the Obsidian vault wiki folder (final wiki pages, index.md, log.md)
- `staging_root` — absolute path to this agent repo (raw/, ingested/, archive/)
- `blacklist` — paths where wiki page creation is forbidden (does not block reads or file moves)
- `index_excludes` — paths excluded from `index.md` (always: `raw/`, `ingested/`, `archive/`)
- `ingested_folder` / `ingested_subdirs` — archive taxonomy (relative to staging_root)
- `log_format` — do not change without updating all skill files

### Key conventions

- **Every new wiki page** must have YAML frontmatter: `title`, `version`, `date`, `changes` (traces back to the ingested source or session)
- **The `changes:` field** is the traceability link: `Created by wiki-ingest from ingested/[subdir]/[filename]`
- **`ingested/` is the filesystem truth** — whether a source has been processed is determined by its presence in `ingested/`, not by `log.md`
- **`log.md` is append-only** — never edit existing entries; new entries go at the top
- **Synthesise, do not copy** — wiki pages contain synthesised knowledge, not verbatim transcripts
- **`raw/` links in wiki pages** will break after ingest — always reference the post-move `ingested/` path

### Session bootstrap

Start any new session by reading `Overview.md` and `index.md` from `wiki_root` (the vault). The wiki is the persistent context — do not rely on chat history.

## Tools

Python ingestion tools that scrape sources and write structured notes to `raw/`. After any tool run, follow up with `/wiki-ingest` to synthesise the files into wiki pages.

### medium_ingest

Scrapes Medium articles via a persistent authenticated Chrome session and writes structured notes to `raw/`.

**First-time setup:**
```bash
pip install -r tools/medium_ingest/requirements.txt
playwright install chrome
bash tools/run_medium.sh --login   # opens browser; log in, then press ENTER
```

**Usage:**
```bash
# Check auth status
bash tools/run_medium.sh --check-auth

# Fetch from your bookmarks
bash tools/run_medium.sh --bookmarks --limit 5

# Fetch by topic tag
bash tools/run_medium.sh --topic "system design" --limit 10

# Fetch from a reading list URL
bash tools/run_medium.sh --list-url "https://medium.com/me/list/YOUR-LIST-ID" --limit 10

# Skip LLM structuring — write raw extracted text for /wiki-ingest to handle
bash tools/run_medium.sh --bookmarks --raw

# Preview without writing files
bash tools/run_medium.sh --bookmarks --dry-run --limit 3
```

**Other flags:** `--no-cache` (reprocess seen articles), `--clear-cache`, `--resolve-only` (print discovered URLs and exit).

**Env vars:** `ANTHROPIC_API_KEY` (required unless `--raw`), `MEDIUM_LLM_MODEL` (default: `claude-haiku-4-5-20251001`).

### podcast_ingest

Resolves a Spotify podcast episode to audio, transcribes it, and writes a structured note to `raw/`.

**Setup:**
```bash
pip install -r tools/podcast_ingest/requirements.txt
# Spotify credentials are already set in run_podcast.sh
# OPENAI_API_KEY only needed if Whisper audio fallback triggers
```

**Usage:**
```bash
# Ingest a Spotify episode
bash tools/run_podcast.sh "https://open.spotify.com/episode/XYZ"

# Preview without writing
bash tools/run_podcast.sh "https://open.spotify.com/episode/XYZ" --dry-run

# Print resolver result only (no transcription)
bash tools/run_podcast.sh "https://open.spotify.com/episode/XYZ" --resolve-only

# Use local Whisper model instead of OpenAI API
bash tools/run_podcast.sh "https://open.spotify.com/episode/XYZ" --whisper-local
```

**Pipeline:** Resolver → audio source (direct MP3 / YouTube / RSS / record) → transcript (yt-dlp captions or Whisper) → structured note in `raw/`.

### Workflow

```
bash tools/run_medium.sh --bookmarks --limit 10
#   → writes raw/medium--article-title--YYYY-MM-DD.md

/wiki-ingest
#   → synthesises wiki pages, moves files to ingested/articles/, updates index.md
```

## Vault structure outside rbk-pkm-wiki/

For reference only — do not write to these areas in the Obsidian vault:

| Folder | Contents |
|---|---|
| `MOCs/` | Maps of Content — domain hub pages |
| `DOCS/` | Reference documentation |
| `Daily Notes/` | Daily logs |
| `_templates/` | Obsidian note templates |
| `.obsidian/` | Obsidian app config and plugins |
