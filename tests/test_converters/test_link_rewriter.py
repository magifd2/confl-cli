from pathlib import Path

from ccli.client.attachments import Attachment
from ccli.client.pages import PageNode
from ccli.converters.link_rewriter import (
    build_attachment_map,
    build_page_map,
    rewrite_html,
    rewrite_markdown,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

OUT = Path("/out")


def _att(download_url: str, saved_path: str | None = None) -> Attachment:
    return Attachment(
        id="a1",
        filename="file.pdf",
        media_type="application/pdf",
        size_bytes=100,
        download_url=download_url,
        saved_path=saved_path,
    )


# ---------------------------------------------------------------------------
# build_page_map
# ---------------------------------------------------------------------------


def test_build_page_map_root_only() -> None:
    root = PageNode(id="100", title="Root")
    m = build_page_map(root, OUT, "page.md")
    assert m == {"100": OUT / "100" / "page.md"}


def test_build_page_map_with_children() -> None:
    child = PageNode(id="101", title="Child")
    root = PageNode(id="100", title="Root", children=[child])
    m = build_page_map(root, OUT, "page.html")
    assert "100" in m
    assert "101" in m
    assert m["101"] == OUT / "101" / "page.html"


def test_build_page_map_nested() -> None:
    gc = PageNode(id="201", title="Grandchild")
    child = PageNode(id="101", title="Child", children=[gc])
    root = PageNode(id="100", title="Root", children=[child])
    m = build_page_map(root, OUT, "page.md")
    assert len(m) == 3
    assert "201" in m


# ---------------------------------------------------------------------------
# build_attachment_map
# ---------------------------------------------------------------------------


def test_build_attachment_map_downloaded() -> None:
    att = _att("/wiki/download/attachments/123/file.pdf", "/out/123/file.pdf")
    m = build_attachment_map([att])
    assert m["/wiki/download/attachments/123/file.pdf"] == Path("/out/123/file.pdf")


def test_build_attachment_map_not_downloaded() -> None:
    att = _att("/wiki/download/attachments/123/file.pdf")
    assert build_attachment_map([att]) == {}


def test_build_attachment_map_strips_query() -> None:
    att = _att("/wiki/download/attachments/123/f.pdf?version=1&date=123", "/out/123/f.pdf")
    m = build_attachment_map([att])
    assert "/wiki/download/attachments/123/f.pdf" in m


# ---------------------------------------------------------------------------
# rewrite_html — page links
# ---------------------------------------------------------------------------


def test_rewrite_html_sibling_page() -> None:
    html = '<a href="/wiki/spaces/DEV/pages/101">Link</a>'
    pm = {"101": OUT / "101" / "page.html"}
    result = rewrite_html(html, OUT / "100" / "page.html", pm, {})
    assert 'href="../101/page.html"' in result


def test_rewrite_html_with_title_slug() -> None:
    html = '<a href="/wiki/spaces/DEV/pages/101/My-Page-Title">Link</a>'
    pm = {"101": OUT / "101" / "page.html"}
    result = rewrite_html(html, OUT / "100" / "page.html", pm, {})
    assert 'href="../101/page.html"' in result


def test_rewrite_html_with_anchor() -> None:
    html = '<a href="/wiki/spaces/DEV/pages/101#section">Link</a>'
    pm = {"101": OUT / "101" / "page.html"}
    result = rewrite_html(html, OUT / "100" / "page.html", pm, {})
    assert 'href="../101/page.html#section"' in result


def test_rewrite_html_with_title_and_anchor() -> None:
    html = '<a href="/wiki/spaces/DEV/pages/101/Title#section">Link</a>'
    pm = {"101": OUT / "101" / "page.html"}
    result = rewrite_html(html, OUT / "100" / "page.html", pm, {})
    assert 'href="../101/page.html#section"' in result


def test_rewrite_html_full_url() -> None:
    html = '<a href="https://x.atlassian.net/wiki/spaces/DEV/pages/101">Link</a>'
    pm = {"101": OUT / "101" / "page.html"}
    result = rewrite_html(
        html, OUT / "100" / "page.html", pm, {}, base_url="https://x.atlassian.net"
    )
    assert 'href="../101/page.html"' in result


def test_rewrite_html_unknown_page_no_rewrite() -> None:
    html = '<a href="/wiki/spaces/DEV/pages/999">?</a>'
    result = rewrite_html(html, OUT / "100" / "page.html", {}, {})
    assert 'href="/wiki/spaces/DEV/pages/999"' in result


def test_rewrite_html_base_path_fallback() -> None:
    """base_path rewrites links even for page IDs not in page_map."""
    html = '<a href="/wiki/spaces/DEV/pages/999">?</a>'
    result = rewrite_html(
        html,
        OUT / "100" / "page.html",
        {},
        {},
        base_path=OUT,
        page_filename="page.html",
    )
    assert 'href="../999/page.html"' in result


def test_rewrite_html_external_link_unchanged() -> None:
    html = '<a href="https://example.com">External</a>'
    result = rewrite_html(html, OUT / "100" / "page.html", {}, {})
    assert 'href="https://example.com"' in result


def test_rewrite_html_src_attribute() -> None:
    html = '<img src="/wiki/download/attachments/100/img.png">'
    att_map = {"/wiki/download/attachments/100/img.png": OUT / "100" / "img.png"}
    result = rewrite_html(html, OUT / "100" / "page.html", {}, att_map)
    assert 'src="img.png"' in result


# ---------------------------------------------------------------------------
# rewrite_html — attachment links
# ---------------------------------------------------------------------------


def test_rewrite_html_attachment_link() -> None:
    html = '<a href="/wiki/download/attachments/100/file.pdf">DL</a>'
    att_map = {"/wiki/download/attachments/100/file.pdf": OUT / "100" / "file.pdf"}
    result = rewrite_html(html, OUT / "100" / "page.html", {}, att_map)
    assert 'href="file.pdf"' in result


def test_rewrite_html_attachment_with_query_params() -> None:
    html = '<a href="/wiki/download/attachments/100/file.pdf?version=1">DL</a>'
    att_map = {"/wiki/download/attachments/100/file.pdf": OUT / "100" / "file.pdf"}
    result = rewrite_html(html, OUT / "100" / "page.html", {}, att_map)
    assert 'href="file.pdf"' in result


def test_rewrite_html_attachment_not_downloaded_unchanged() -> None:
    html = '<a href="/wiki/download/attachments/100/file.pdf">DL</a>'
    result = rewrite_html(html, OUT / "100" / "page.html", {}, {})
    assert 'href="/wiki/download/attachments/100/file.pdf"' in result


# ---------------------------------------------------------------------------
# rewrite_markdown — page links
# ---------------------------------------------------------------------------


def test_rewrite_markdown_page_link() -> None:
    md = "[Page](/wiki/spaces/DEV/pages/101)"
    pm = {"101": OUT / "101" / "page.md"}
    result = rewrite_markdown(md, OUT / "100" / "page.md", pm, {})
    assert "(../101/page.md)" in result


def test_rewrite_markdown_image_link() -> None:
    md = "![img](/wiki/download/attachments/100/img.png)"
    att_map = {"/wiki/download/attachments/100/img.png": OUT / "100" / "img.png"}
    result = rewrite_markdown(md, OUT / "100" / "page.md", {}, att_map)
    assert "(img.png)" in result


def test_rewrite_markdown_external_unchanged() -> None:
    md = "[External](https://google.com)"
    result = rewrite_markdown(md, OUT / "100" / "page.md", {}, {})
    assert "(https://google.com)" in result


def test_rewrite_markdown_anchor_preserved() -> None:
    md = "[Link](/wiki/spaces/DEV/pages/101#heading)"
    pm = {"101": OUT / "101" / "page.md"}
    result = rewrite_markdown(md, OUT / "100" / "page.md", pm, {})
    assert "(../101/page.md#heading)" in result


def test_rewrite_markdown_base_path_fallback() -> None:
    md = "[Link](/wiki/spaces/DEV/pages/999)"
    result = rewrite_markdown(
        md, OUT / "100" / "page.md", {}, {}, base_path=OUT, page_filename="page.md"
    )
    assert "(../999/page.md)" in result


def test_rewrite_markdown_attachment_link() -> None:
    md = "[DL](/wiki/download/attachments/100/file.pdf)"
    att_map = {"/wiki/download/attachments/100/file.pdf": OUT / "100" / "file.pdf"}
    result = rewrite_markdown(md, OUT / "100" / "page.md", {}, att_map)
    assert "(file.pdf)" in result


# ---------------------------------------------------------------------------
# Single-quoted attributes
# ---------------------------------------------------------------------------


def test_rewrite_html_single_quote() -> None:
    html = "<a href='/wiki/spaces/DEV/pages/101'>Link</a>"
    pm = {"101": OUT / "101" / "page.html"}
    result = rewrite_html(html, OUT / "100" / "page.html", pm, {})
    assert "href='../101/page.html'" in result
