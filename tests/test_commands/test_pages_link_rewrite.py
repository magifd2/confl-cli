"""Integration tests for link rewriting in pages get / pages tree."""
from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock
from typer.testing import CliRunner

from ccli.main import app

runner = CliRunner()

BASE_URL = "https://example.atlassian.net"
ENV = {
    "CONFLUENCE_URL": BASE_URL,
    "CONFLUENCE_USERNAME": "user@example.com",
    "CONFLUENCE_API_TOKEN": "token123",
}

# Page response with an internal page link and an attachment link
_PAGE_WITH_LINKS = {
    "id": "100",
    "title": "Root",
    "space": {"key": "DEV", "name": "Development"},
    "version": {
        "number": 1,
        "when": "2024-01-10T00:00:00.000Z",
        "by": {"displayName": "Alice"},
    },
    "history": {
        "createdDate": "2024-01-01T00:00:00.000Z",
        "createdBy": {"displayName": "Alice"},
    },
    "body": {
        "view": {
            "value": (
                '<p>See <a href="/wiki/spaces/DEV/pages/200">another page</a>.</p>'
                '<p><a href="/wiki/download/attachments/100/doc.pdf">doc.pdf</a></p>'
            )
        },
        "storage": {"value": "<p>raw</p>"},
    },
    "ancestors": [],
    "_links": {"webui": "/wiki/spaces/DEV/pages/100"},
}

_ATTACHMENTS_WITH_DOC = {
    "results": [
        {
            "id": "att1",
            "title": "doc.pdf",
            "mediaType": "application/pdf",
            "fileSize": 10,
            "_links": {"download": "/wiki/download/attachments/100/doc.pdf"},
        }
    ],
    "_links": {},
}

_PAGE_200_META = {
    "id": "200",
    "title": "Another Page",
    "version": {"when": "2024-01-20T00:00:00.000Z"},
    "history": {"createdDate": "2024-01-05T00:00:00.000Z"},
    "_links": {"webui": "/wiki/spaces/DEV/pages/200"},
}


def _descendants(*pages: dict) -> dict:  # type: ignore[type-arg]
    return {"results": list(pages), "size": len(pages), "limit": 250}


@pytest.fixture(autouse=True)
def set_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)


# ---------------------------------------------------------------------------
# pages get --base-path
# ---------------------------------------------------------------------------


class TestPagesGetLinkRewrite:
    def test_page_links_rewritten_in_markdown(
        self, httpx_mock: HTTPXMock, tmp_path: Path
    ) -> None:
        httpx_mock.add_response(json=_PAGE_WITH_LINKS)
        result = runner.invoke(
            app,
            ["pages", "get", "100", "--format", "text", "--base-path", str(tmp_path)],
        )
        assert result.exit_code == 0
        # Internal page link should be rewritten to a relative local path
        assert "/wiki/spaces/DEV/pages/200" not in result.output
        assert "200" in result.output  # ID still present in path

    def test_attachment_links_rewritten_when_downloaded(
        self, httpx_mock: HTTPXMock, tmp_path: Path
    ) -> None:
        httpx_mock.add_response(json=_PAGE_WITH_LINKS)
        httpx_mock.add_response(json=_ATTACHMENTS_WITH_DOC)
        httpx_mock.add_response(content=b"pdf")
        result = runner.invoke(
            app,
            [
                "pages", "get", "100",
                "--format", "text",
                "--attachments",
                "--output-dir", str(tmp_path),
                "--base-path", str(tmp_path),
            ],
        )
        assert result.exit_code == 0
        assert "/wiki/download/attachments/100/doc.pdf" not in result.output
        assert "doc.pdf" in result.output

    def test_no_rewrite_links_flag_preserves_original(
        self, httpx_mock: HTTPXMock, tmp_path: Path
    ) -> None:
        httpx_mock.add_response(json=_PAGE_WITH_LINKS)
        result = runner.invoke(
            app,
            [
                "pages", "get", "100",
                "--format", "text",
                "--base-path", str(tmp_path),
                "--no-rewrite-links",
            ],
        )
        assert result.exit_code == 0
        assert "/wiki/spaces/DEV/pages/200" in result.output

    def test_html_format_links_rewritten(
        self, httpx_mock: HTTPXMock, tmp_path: Path
    ) -> None:
        httpx_mock.add_response(json=_PAGE_WITH_LINKS)
        result = runner.invoke(
            app,
            ["pages", "get", "100", "--format", "html", "--base-path", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "/wiki/spaces/DEV/pages/200" not in result.output

    def test_no_base_path_no_rewrite(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=_PAGE_WITH_LINKS)
        result = runner.invoke(app, ["pages", "get", "100", "--format", "text"])
        assert result.exit_code == 0
        # Without --base-path, Confluence page links appear unchanged in Markdown
        assert "/wiki/spaces/DEV/pages/200" in result.output

    def test_json_format_not_rewritten(
        self, httpx_mock: HTTPXMock, tmp_path: Path
    ) -> None:
        httpx_mock.add_response(json=_PAGE_WITH_LINKS)
        result = runner.invoke(
            app,
            ["pages", "get", "100", "--format", "json", "--base-path", str(tmp_path)],
        )
        assert result.exit_code == 0
        # JSON output retains raw HTML body — link rewriting does not apply
        assert "/wiki/spaces/DEV/pages/200" in result.output


# ---------------------------------------------------------------------------
# pages tree (auto link rewriting)
# ---------------------------------------------------------------------------


class TestPagesTreeLinkRewrite:
    def _setup_two_node_tree(self, httpx_mock: HTTPXMock) -> None:
        """Root (100) with one child (200)."""
        _child = {
            "id": "200",
            "title": "Another Page",
            "version": {"when": "2024-01-20T00:00:00.000Z"},
            "history": {"createdDate": "2024-01-05T00:00:00.000Z"},
            "ancestors": [{"id": "100"}],
            "_links": {"webui": "/wiki/spaces/DEV/pages/200"},
        }
        httpx_mock.add_response(
            json={
                "id": "100",
                "title": "Root",
                "version": {"when": "2024-01-10T00:00:00.000Z"},
                "history": {"createdDate": "2024-01-01T00:00:00.000Z"},
                "_links": {"webui": "/wiki/spaces/DEV/pages/100"},
            }
        )
        httpx_mock.add_response(json=_descendants(_child))

    def test_cross_page_links_rewritten_in_tree(
        self, httpx_mock: HTTPXMock, tmp_path: Path
    ) -> None:
        self._setup_two_node_tree(httpx_mock)
        # _populate_tree_attachments processes each node: att → page_content (depth-first)
        # root (100): attachments, then page content
        httpx_mock.add_response(json={"results": [], "_links": {}})  # att for 100
        httpx_mock.add_response(json=_PAGE_WITH_LINKS)               # page content 100
        # child (200): attachments, then page content
        httpx_mock.add_response(json={"results": [], "_links": {}})  # att for 200
        httpx_mock.add_response(json={**_PAGE_WITH_LINKS, "id": "200"})  # page content 200
        result = runner.invoke(
            app,
            [
                "pages", "tree", "100",
                "--output-dir", str(tmp_path),
                "--page-format", "text",
            ],
        )
        assert result.exit_code == 0
        saved = tmp_path / "100" / "page.md"
        assert saved.exists()
        content = saved.read_text()
        # Link to child (200) should be rewritten to a relative local path
        assert "/wiki/spaces/DEV/pages/200" not in content
        assert "200/page.md" in content

    def test_no_rewrite_links_preserves_original(
        self, httpx_mock: HTTPXMock, tmp_path: Path
    ) -> None:
        self._setup_two_node_tree(httpx_mock)
        httpx_mock.add_response(json={"results": [], "_links": {}})  # att for 100
        httpx_mock.add_response(json=_PAGE_WITH_LINKS)               # page content 100
        httpx_mock.add_response(json={"results": [], "_links": {}})  # att for 200
        httpx_mock.add_response(json={**_PAGE_WITH_LINKS, "id": "200"})  # page content 200
        result = runner.invoke(
            app,
            [
                "pages", "tree", "100",
                "--output-dir", str(tmp_path),
                "--page-format", "text",
                "--no-rewrite-links",
            ],
        )
        assert result.exit_code == 0
        content = (tmp_path / "100" / "page.md").read_text()
        assert "/wiki/spaces/DEV/pages/200" in content
