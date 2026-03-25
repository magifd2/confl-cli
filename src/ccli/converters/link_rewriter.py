"""Rewrite Confluence page and attachment links to local file paths."""
from __future__ import annotations

import os
import re
from collections.abc import Iterator
from pathlib import Path

from ..client.attachments import Attachment
from ..client.pages import PageNode

# ---------------------------------------------------------------------------
# URL patterns (matched against normalized paths — scheme/host/query stripped)
# ---------------------------------------------------------------------------

# /wiki/spaces/KEY/pages/ID[/optional-title][#anchor]
_PAGE_PATH_RE = re.compile(
    r"^/wiki/spaces/[^/#]+/pages/(\d+)(?:/[^#]*)?(#[^\s\"')]*)?$"
)
# /wiki/download/attachments/PAGE_ID/filename
_ATTACHMENT_PATH_RE = re.compile(
    r"^/wiki/download/attachments/\d+/[^?#\"'\s)]+$"
)
# href="..." or src="..."  (both single- and double-quoted)
_HTML_ATTR_RE = re.compile(r'\b(href|src)=(["\'])([^"\']*)\2')
# [text](url) and ![alt](url)  — URL must not contain spaces
_MD_LINK_RE = re.compile(r"(!?\[[^\]]*\])\(([^)\s]+)\)")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def flatten_nodes(root: PageNode) -> Iterator[PageNode]:
    """Yield every node in the tree (depth-first)."""
    yield root
    for child in root.children:
        yield from flatten_nodes(child)


def build_page_map(root: PageNode, output_dir: Path, filename: str) -> dict[str, Path]:
    """Return a mapping of *page_id* → absolute local file path for every node."""
    return {node.id: output_dir / node.id / filename for node in flatten_nodes(root)}


def build_attachment_map(attachments: list[Attachment]) -> dict[str, Path]:
    """Return a mapping of download-URL-path → absolute local path.

    Only includes attachments that have already been downloaded (*saved_path* set).
    Query parameters are stripped from the download URL when used as the key.
    """
    result: dict[str, Path] = {}
    for att in attachments:
        if att.saved_path:
            key = att.download_url.split("?")[0]
            result[key] = Path(att.saved_path)
    return result


def _normalize_url(url: str, base_url: str) -> str:
    """Strip *base_url* prefix and scheme+host; remove query params but keep anchor."""
    path = url
    if base_url and path.startswith(base_url):
        path = path[len(base_url):]
    # strip scheme://host
    path = re.sub(r"^https?://[^/]+", "", path)
    # remove query string, preserve anchor
    if "?" in path:
        before_q, after_q = path.split("?", 1)
        anchor = "#" + after_q.split("#", 1)[1] if "#" in after_q else ""
        path = before_q + anchor
    return path


def _resolve_url(
    url: str,
    current_dir: Path,
    page_map: dict[str, Path],
    attachment_map: dict[str, Path],
    base_path: Path | None,
    page_filename: str,
    base_url: str,
) -> str | None:
    """Return a rewritten local path string, or *None* if no rewrite applies."""
    path = _normalize_url(url, base_url)

    # --- page link ---
    m = _PAGE_PATH_RE.match(path)
    if m:
        pid = m.group(1)
        anchor = m.group(2) or ""
        target = page_map.get(pid)
        if target is None and base_path is not None:
            target = base_path / pid / page_filename
        if target is not None:
            rel = Path(os.path.relpath(target, current_dir)).as_posix()
            return rel + anchor
        return None

    # --- attachment link ---
    if _ATTACHMENT_PATH_RE.match(path):
        target_att = attachment_map.get(path)
        if target_att is not None:
            return Path(os.path.relpath(target_att, current_dir)).as_posix()

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def rewrite_html(
    content: str,
    current_file: Path,
    page_map: dict[str, Path],
    attachment_map: dict[str, Path],
    *,
    base_path: Path | None = None,
    page_filename: str = "page.md",
    base_url: str = "",
) -> str:
    """Rewrite *href* and *src* attribute values in *content* to local paths."""
    current_dir = current_file.parent

    def replace(m: re.Match[str]) -> str:
        attr, quote, url = m.group(1), m.group(2), m.group(3)
        new_url = _resolve_url(
            url, current_dir, page_map, attachment_map, base_path, page_filename, base_url
        )
        if new_url is not None:
            return f"{attr}={quote}{new_url}{quote}"
        return m.group(0)

    return _HTML_ATTR_RE.sub(replace, content)


def rewrite_markdown(
    content: str,
    current_file: Path,
    page_map: dict[str, Path],
    attachment_map: dict[str, Path],
    *,
    base_path: Path | None = None,
    page_filename: str = "page.md",
    base_url: str = "",
) -> str:
    """Rewrite link URLs in Markdown ``[text](url)`` syntax to local paths."""
    current_dir = current_file.parent

    def replace(m: re.Match[str]) -> str:
        label, url = m.group(1), m.group(2)
        new_url = _resolve_url(
            url, current_dir, page_map, attachment_map, base_path, page_filename, base_url
        )
        if new_url is not None:
            return f"{label}({new_url})"
        return m.group(0)

    return _MD_LINK_RE.sub(replace, content)
