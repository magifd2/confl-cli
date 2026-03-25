# confl-cli

Atlassian Confluence Cloud をコマンドラインから操作する CLI ツール。

UNIX 哲学に基づき、stdout はデータ・stderr はログとして設計されており、`jq` や `grep` などのシェルツールとパイプでシームレスに連携できます。

[English README](README.md)

## 機能

- スペースの一覧・検索
- ページの検索・取得（テキスト / HTML / JSON / Confluence Storage Format）
- ページツリーの再帰的取得（深さ制限オプション付き）
- 添付ファイルのメタデータ取得・ファイル保存（パストラバーサル防御付き）

## インストール

```bash
uv tool install git+https://github.com/magifd2/confl-cli.git
```

## 設定

環境変数で認証情報を設定する（推奨）:

```bash
export CONFLUENCE_URL=https://your-domain.atlassian.net
export CONFLUENCE_USERNAME=you@example.com
export CONFLUENCE_API_TOKEN=your-api-token
```

API Token の発行: <https://id.atlassian.com/manage-profile/security/api-tokens>

または対話式セットアップで設定ファイルを作成する:

```bash
confl-cli config init
```

設定ファイルの保存先: `~/.config/ccli/config.toml`（Linux/macOS）、`%APPDATA%\ccli\config.toml`（Windows）

## 使い方

```bash
# スペース一覧
confl-cli spaces list

# スペース検索
confl-cli spaces search "Engineering"

# ページ検索（CQL 全文検索）
confl-cli pages search "Getting Started" --space DEV

# ページ取得（テキスト / Markdown 形式）
confl-cli pages get 123456789

# ページ取得（JSON 形式、jq に渡す）
confl-cli pages get 123456789 --format json | jq '.title'

# ページ取得（Confluence Storage Format — 内部 XHTML 形式）
confl-cli pages get 123456789 --format storage

# ページ取得 + 添付ファイルをディレクトリへ保存
confl-cli pages get 123456789 --attachments --output-dir ./downloads

# ページツリーを再帰取得（JSON）
confl-cli pages tree 123456789 --format json | jq '.'

# ページツリー（深さ2まで、添付ファイル付き）
confl-cli pages tree 123456789 --depth 2 --attachments --output-dir ./downloads

# ページツリーの各記事を Markdown で保存（--output-dir 必須）
confl-cli pages tree 123456789 --page-format text --output-dir ./downloads

# ページツリーの各記事を JSON で保存 + 添付ファイルもダウンロード
confl-cli pages tree 123456789 --page-format json --attachments --output-dir ./downloads
```

### `pages tree` の `--page-format`

| フラグ | 保存ファイル |
|--------|------------|
| `--page-format text` | `<page-id>/page.md`（markdownify によるテキスト変換） |
| `--page-format html` | `<page-id>/page.html` |
| `--page-format json` | `<page-id>/page.json` |
| `--page-format storage` | `<page-id>/page.xml`（Confluence Storage Format） |

`--output-dir` が必要。`--attachments` と組み合わせて記事本文と添付ファイルを同時にダウンロード可能。

### `pages get` の出力フォーマット

| フラグ | 出力 |
|--------|------|
| （省略時） | markdownify によるテキスト変換 |
| `--format html` | レンダリング済み HTML |
| `--format json` | 構造化 JSON（タイトル・本文・メタデータ・添付ファイル情報） |
| `--format storage` | Confluence Storage Format（内部 XHTML 形式） |

### 終了コード

| コード | 意味 |
|--------|------|
| 0 | 成功 |
| 1 | 認証エラー |
| 2 | アクセス拒否 |
| 3 | リソース未発見 |
| 4 | ネットワークエラー |
| 5 | レート制限超過 |
| 6 | 設定エラー |

## 開発

Python 3.11 以上と [uv](https://docs.astral.sh/uv/) が必要です。

```bash
git clone https://github.com/magifd2/confl-cli.git
cd ccli
uv sync --all-extras
```

テスト実行:

```bash
uv run pytest
uv run pytest --cov=ccli --cov-report=term-missing
```

Lint / フォーマット / 型チェック:

```bash
uv run ruff check .
uv run ruff format .
uv run mypy src/
```

## ライセンス

MIT © magifd2
