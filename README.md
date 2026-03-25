# confl-cli

A CLI tool for Atlassian Confluence Cloud.

Designed around the UNIX philosophy — stdout is data, stderr is logs — so it composes naturally with `jq`, `grep`, and other shell tools.

[日本語版 README](README.ja.md)

## Features

- List and search spaces
- Search pages (full-text via CQL)
- Read a single page (text / HTML / JSON / Confluence Storage Format)
- Recursively read a page tree
- Fetch attachment metadata and download files to disk (path-traversal safe)

## Installation

```bash
uv tool install git+https://github.com/magifd2/confl-cli.git
```

## Configuration

Set credentials via environment variables (recommended):

```bash
export CONFLUENCE_URL=https://your-domain.atlassian.net
export CONFLUENCE_USERNAME=you@example.com
export CONFLUENCE_API_TOKEN=your-api-token
```

Generate an API token at: <https://id.atlassian.com/manage-profile/security/api-tokens>

Or run the interactive setup wizard:

```bash
confl-cli config init
```

The config file is stored at `~/.config/ccli/config.toml` (Linux/macOS) or `%APPDATA%\ccli\config.toml` (Windows).

## Usage

```bash
# List spaces
confl-cli spaces list

# Search spaces
confl-cli spaces search "Engineering"

# Search pages (full-text)
confl-cli pages search "Getting Started" --space DEV

# Get a page as plain text (Markdown-ified)
confl-cli pages get 123456789

# Get a page as JSON and pipe to jq
confl-cli pages get 123456789 --format json | jq '.title'

# Get a page in Confluence Storage Format (internal XHTML-like source)
confl-cli pages get 123456789 --format storage

# Get a page and download its attachments
confl-cli pages get 123456789 --attachments --output-dir ./downloads

# Get the full page tree rooted at a page (JSON)
confl-cli pages tree 123456789 --format json | jq '.'

# Get a page tree to depth 2 and download all attachments
confl-cli pages tree 123456789 --depth 2 --attachments --output-dir ./downloads

# Get a page tree and save each page body as Markdown (requires --output-dir)
confl-cli pages tree 123456789 --page-format text --output-dir ./downloads

# Get a page tree and save each page body as JSON, plus download attachments
confl-cli pages tree 123456789 --page-format json --attachments --output-dir ./downloads
```

### `--page-format` for `pages tree`

| Flag | Saved file |
|------|------------|
| `--page-format text` | `<page-id>/page.md` (Markdown via markdownify) |
| `--page-format html` | `<page-id>/page.html` |
| `--page-format json` | `<page-id>/page.json` |
| `--page-format storage` | `<page-id>/page.xml` (Confluence Storage Format) |

Requires `--output-dir`. Combine with `--attachments` to download both page bodies and attachments.

### Output formats for `pages get`

| Flag | Output |
|------|--------|
| *(default)* | Markdown text via markdownify |
| `--format html` | Raw rendered HTML |
| `--format json` | Structured JSON (title, body, metadata, attachments) |
| `--format storage` | Confluence Storage Format (raw XHTML-like internal source) |

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Authentication error |
| 2 | Forbidden |
| 3 | Not found |
| 4 | Network error |
| 5 | Rate limit exceeded |
| 6 | Configuration error |

## Development

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/magifd2/confl-cli.git
cd ccli
uv sync --all-extras
```

Run tests:

```bash
uv run pytest
uv run pytest --cov=ccli --cov-report=term-missing
```

Lint / format / type-check:

```bash
uv run ruff check .
uv run ruff format .
uv run mypy src/
```

## License

MIT © magifd2
