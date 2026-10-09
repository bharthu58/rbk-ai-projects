---
wiki_root: /path/to/obsidian-vault/Agent Access/rbk-pkm-wiki
staging_root: /path/to/pkm-wiki
blacklist: []

index_excludes:
  - raw/
  - archive/
  - ingested/

ingested_folder: ingested

ingested_subdirs:
  - clippings
  - documentation
  - articles
  - notes
  - data
  - assets
  - podcasts

log_format: "## [YYYY-MM-DD] {type} | {subject}"
---

**wiki_root:** Absolute path to the Obsidian vault wiki folder — the folder containing synthesised wiki pages, index.md, and log.md. This is the clean, final knowledge base.

**staging_root:** Absolute path to the agent project repo — the folder containing raw/, ingested/, archive/, and tools/. Source files and agent artifacts live here, not in the vault.

**blacklist:** Skill definition folders — wiki page creation is forbidden here.

**index_excludes:** Paths excluded from index.md tracking.

**ingested_folder:** Folder where processed source files are archived (relative to staging_root).

**ingested_subdirs:** Archival taxonomy within ingested_folder.

**log_format:** Do not change without updating all wiki skills.
