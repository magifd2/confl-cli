# ccli 詳細仕様書

## 1. 概要

Atlassian Confluence Cloud をコマンドラインから操作するための CLI ツール。
UNIX 哲学に基づき、パイプで他コマンドと組み合わせて使えるよう設計する。
スペース・ページの検索・取得、添付ファイル取得を主機能とする。

## 2. 対象環境

| 項目 | 内容 |
|------|------|
| Confluence エディション | Cloud（REST API v2） |
| 対象 OS | macOS / Linux / Windows |
| Python バージョン | 3.11 以上 |
| パッケージ管理 | uv |

## 3. 認証

### 方式
Confluence Cloud の HTTP Basic 認証:
- ユーザー名: メールアドレス
- パスワード: API Token（<https://id.atlassian.com/manage-profile/security/api-tokens> で発行）

### 認証情報の管理（セキュリティ優先）

優先順位（高い順）:

1. **環境変数**（推奨）
   ```
   CONFLUENCE_URL=https://your-domain.atlassian.net
   CONFLUENCE_USERNAME=you@example.com
   CONFLUENCE_API_TOKEN=your-api-token
   ```

2. **設定ファイル**（フォールバック）
   - パス: `~/.config/ccli/config.toml`（XDG Base Dir 準拠、Windows は `%APPDATA%\ccli\config.toml`）
   - 作成時にパーミッション `600` を設定（Windows は ACL で同等の制限）

**禁止事項**: コマンドライン引数でのトークン受け渡し（プロセスリスト漏洩防止）

## 4. CLI コマンド体系

```
confl-cli [グローバルオプション] <コマンド> <サブコマンド> [引数] [オプション]
```

### グローバルオプション

| オプション | 説明 |
|-----------|------|
| `--no-color` | カラー出力を無効化 |
| `--version` | バージョン表示（`importlib.metadata` から動的取得） |

### 4.1 spaces コマンド

#### `confl-cli spaces list`
全スペースを一覧表示する。

```
confl-cli spaces list [--limit N] [--type personal|global]
```

text 出力例:
```
KEY       NAME                     TYPE      STATUS
DEV       Development              global    current
~john     John's Space             personal  current
```

#### `confl-cli spaces search <query>`
クエリ文字列でスペースを検索する（クライアントサイドの部分一致）。

```
confl-cli spaces search <query> [--limit N]
```

#### `confl-cli spaces export <space-key>`
スペース内の全ページをツリー形式でエクスポートする。v1 API でホームページ ID を解決し、`pages tree` と同じロジックで処理する。

```
confl-cli spaces export <space-key>
  [--depth N]
  [--format {text,json}]
  [--attachments]
  [--output-dir DIR]
  [--page-format {text,html,json,storage}]
  [--no-rewrite-links]
```

`--page-format` は `--output-dir` と併用が必須。

### 4.2 pages コマンド

#### `confl-cli pages search <query>`
ページを全文検索する（CQL）。

```
confl-cli pages search <query> [--space SPACE_KEY] [--limit N] [--format {text,json}]
```

text 出力例（日時はローカルタイム `YYYY-MM-DD HH:MM` 形式）:
```
ID          SPACE   TITLE                    LAST MODIFIED
123456789   DEV     Getting Started Guide    2024-01-15 19:00
987654321   ARCH    System Architecture      2024-01-10 14:30
```

#### `confl-cli pages get <page-id>`
指定ページを取得する。

```
confl-cli pages get <page-id> [--format {text,html,json,storage}] [--attachments] [--output-dir DIR]
```

| オプション | 説明 |
|-----------|------|
| `--format` | `text`=Markdown変換（デフォルト）, `html`=生HTML, `json`=構造化データ, `storage`=Confluence Storage Format |
| `--attachments` | 添付ファイルメタデータも取得する |
| `--output-dir DIR` | 添付ファイルをダウンロードして保存 |

テキスト表示のメタ行: `Space: XX  |  Version: N  |  Updated: YYYY-MM-DD HH:MM  |  Author: 氏名`

JSON 出力スキーマ:
```json
{
  "id": "string",
  "title": "string",
  "space_key": "string",
  "space_name": "string",
  "version": "number",
  "created_at": "ISO8601 UTC",
  "updated_at": "ISO8601 UTC",
  "author": { "display_name": "string", "email": "string | null" },
  "body_html": "string",
  "body_storage": "string",
  "url": "string",
  "parent_id": "string | null",
  "attachments": [
    {
      "id": "string",
      "filename": "string",
      "media_type": "string",
      "size_bytes": "number",
      "download_url": "string",
      "saved_path": "string | null"
    }
  ]
}
```

#### `confl-cli pages tree <page-id>`
指定ページを起点に子ページを再帰的に取得する。

```
confl-cli pages tree <page-id> [--format {text,json}] [--depth N]
                               [--attachments] [--output-dir DIR]
                               [--page-format {text,html,json,storage}]
```

| オプション | 説明 |
|-----------|------|
| `--depth N` | 再帰の最大深さ（デフォルト: 無制限） |
| `--format` | ツリー構造の出力形式（`text` または `json`） |
| `--attachments` | 各ページの添付ファイルを取得 |
| `--output-dir DIR` | 添付ファイルおよびページ本文の保存先 |
| `--page-format` | ページ本文の保存形式。`--output-dir` が必須 |

text 出力例（日時はローカルタイム）:
```
Getting Started (123456789)  2024-01-15 19:00
├── Installation (111111111)  2024-01-12 10:30
│   └── Docker Setup (222222222)  2024-01-10 09:00
└── Configuration (333333333)  2024-01-08 15:45
```

`--page-format` 指定時の保存ファイル:

| 形式 | ファイル名 |
|------|-----------|
| `text` | `<output-dir>/<page-id>/page.md` |
| `html` | `<output-dir>/<page-id>/page.html` |
| `json` | `<output-dir>/<page-id>/page.json` |
| `storage` | `<output-dir>/<page-id>/page.xml` |

JSON 出力スキーマ（各ノード）:
```json
{
  "id": "string",
  "title": "string",
  "url": "string",
  "created_at": "ISO8601 UTC",
  "updated_at": "ISO8601 UTC",
  "attachments": [ { "id": "...", "filename": "...", "saved_path": "..." } ],
  "children": [ { /* 同じ構造 */ } ]
}
```

### 4.3 config コマンド

#### `confl-cli config init`
対話形式で設定ファイルを初期化する。

#### `confl-cli config show`
現在の設定を表示（API Token はマスキング）。

## 5. 出力設計（UNIX 哲学）

### stdout / stderr の分離
- **stdout**: データ本体のみ（text/html/json）
- **stderr**: 進捗表示、警告、エラーメッセージ

### tty 自動判定
- stdout が tty の場合: カラー出力、テーブル整形を有効化
- stdout が非 tty（パイプ・リダイレクト）の場合: カラーコード除去、Plain テキスト出力
- `--no-color` / `NO_COLOR` 環境変数でも無効化可能

### json 形式
- データは stdout に JSON のみ出力
- `--format json` 時は stderr 以外には JSON 以外を出さない

## 6. 添付ファイル処理

- `--attachments` フラグ指定時にメタデータ + バイナリを取得
- 大容量ファイルはストリーミングダウンロード（メモリ効率重視）
- 保存先ディレクトリ構造: `<output-dir>/<page-id>/<filename>`
- JSON 出力時: `saved_path` フィールドに保存先パスを格納

## 7. エラーハンドリング

| エラー種別 | 終了コード |
|-----------|-----------|
| 認証失敗（401） | 1 |
| 権限不足（403） | 2 |
| リソース未発見（404） | 3 |
| ネットワークエラー | 4 |
| API レート制限（429） | 5 |
| 設定ファイルエラー | 6 |
| その他 | 99 |

- 終了コードはスクリプト組み込みを前提とした設計
- レート制限時は Exponential Backoff でリトライ（最大 3 回）
- エラーメッセージはすべて stderr へ出力

## 8. 設定ファイル形式

`~/.config/ccli/config.toml`:
```toml
[confluence]
url = "https://your-domain.atlassian.net"
username = "you@example.com"
api_token = "your-api-token"

[defaults]
format = "text"
limit = 25
```

## 9. 使用ライブラリ（候補）

| 用途 | ライブラリ |
|------|-----------|
| CLI フレームワーク | Typer |
| HTTP クライアント | httpx |
| ターミナル出力 | Rich |
| データモデル・バリデーション | Pydantic v2 |
| 設定ファイルパース | tomllib（標準ライブラリ、3.11+） |
| HTML→Markdown 変換 | markdownify |
| テスト | pytest + pytest-httpx + pytest-cov |
