# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- `pages tree`: pages whose `ancestors` list contains a virtual space-root node (instead of the queried page ID) were silently orphaned and missing from the tree output. This caused the space home page to show only 1 node. Now falls back to the nearest known ancestor in the chain, then to root.

### Added
- `pages get --base-path <dir>`: rewrite Confluence page links to `<base-path>/<id>/page.<ext>` and attachment links to their downloaded location in text/HTML output. No effect for JSON or storage format.
- `pages tree --page-format` now automatically rewrites cross-page links and attachment links to relative local paths when `--output-dir` is set.
- `--no-rewrite-links` flag on both `pages get` and `pages tree` to opt out of link rewriting and preserve original Confluence URLs.

## [0.1.5] - 2026-03-26

### Changed
- `pages tree` now fetches all descendants in a single paginated request to
  `/content/{id}/descendant/page?expand=version,history,ancestors` and
  reconstructs the tree client-side. API calls reduced from O(N) sequential
  to 1 (root) + ceil(N/250) (descendants) — effectively 2 calls for most trees.

## [0.1.4] - 2026-03-25

### Fixed
- `--version` now shows `confl-cli <version>` (previously hardcoded as `ccli 0.1.0`). Version is read dynamically from package metadata.

## [0.1.3] - 2026-03-25

### Added
- `PageNode` (pages tree) now includes `created_at` (page creation date) in addition to `updated_at`. Both fields are populated for root and all child nodes via v1 API `history.createdDate`.

### Changed
- Tree metadata fetching unified to v1 API (`/content/{id}?expand=version,history`) for both root and child nodes. Removes dependency on Confluence v2 API for tree operations.

## [0.1.2] - 2026-03-25

### Added
- `pages tree --page-format <text|html|json|storage>`: save each page body to `<output-dir>/<page-id>/page.md|.html|.json|.xml`. Requires `--output-dir`. Combine with `--attachments` to download both bodies and attachments in one pass.
- `pages tree`: last modified date shown next to each node title in text output; `updated_at` field added to JSON output.

### Fixed
- `pages tree`: child pages now fetch version info and web URL via v1 API (`/content/{id}/child/page?expand=version`). Previously the v2 `/children` endpoint returned neither field, leaving child URLs and dates empty.
- All text displays (`pages tree`, `pages get`, `pages search`) now convert UTC timestamps to local time (`YYYY-MM-DD HH:MM`). JSON output retains the original UTC ISO 8601 value.

## [0.1.0] - 2026-03-25

### Added
- Project scaffolding: `pyproject.toml`, MIT license, `.gitignore`, `CLAUDE.md`
- Exception hierarchy (`CCLIError` and subclasses) with typed exit codes (1–6)
- Configuration system: env vars (`CONFLUENCE_URL/USERNAME/API_TOKEN`) and TOML file (`~/.config/ccli/config.toml`); `config init` / `config show` commands
- HTTP client with Basic Auth, 30 s timeout, and automatic 429 retry with exponential backoff
- Spaces commands: `spaces list` (paginated), `spaces search` (client-side substring match)
- Pages commands: `pages search` (CQL full-text), `pages get` (text/html/json/storage formats), `pages tree` (recursive with optional depth limit)
- Confluence Storage Format output (`--format storage`) exposing the raw XHTML-like internal format
- Attachment support: `--attachments` flag fetches metadata; `--output-dir` streams downloads to disk for both `pages get` and `pages tree`
- Path-traversal defense in `safe_attachment_dest`: basename stripping, null-byte removal, degenerate name rejection, page-id sanitisation, and `is_relative_to()` final guard
- TTY-aware output: Rich tables/tree with color when stdout is a terminal; plain text when piped; `NO_COLOR` respected
- 124 tests, 94 % line coverage; ruff and mypy (strict) clean
