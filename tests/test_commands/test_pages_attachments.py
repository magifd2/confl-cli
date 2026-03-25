import json
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

_CONTENT_RESPONSE = {
    "id": "123",
    "title": "My Page",
    "space": {"key": "DEV", "name": "Development"},
    "version": {
        "number": 1,
        "when": "2024-01-15T10:00:00.000Z",
        "by": {"displayName": "John"},
    },
    "history": {
        "createdDate": "2024-01-01T00:00:00.000Z",
        "createdBy": {"displayName": "John"},
    },
    "body": {
        "view": {"value": "<p>Content</p>"},
        "storage": {"value": "<p>Content</p>"},
    },
    "ancestors": [],
    "_links": {"webui": "/wiki/spaces/DEV/pages/123"},
}

_ATTACHMENTS_RESPONSE = {
    "results": [
        {
            "id": "att001",
            "title": "report.pdf",
            "mediaType": "application/pdf",
            "fileSize": 1024,
            "_links": {"download": "/wiki/download/attachments/123/report.pdf"},
        }
    ],
    "_links": {},
}

_PAGE_META = {
    "id": "100",
    "title": "Root",
    "version": {"when": "2024-01-10T00:00:00.000Z"},
    "history": {"createdDate": "2024-01-01T00:00:00.000Z"},
    "_links": {"webui": "/wiki/spaces/DEV/pages/100"},
}

def _descendants(*pages: dict) -> dict:  # type: ignore[type-arg]
    return {"results": list(pages), "size": len(pages), "limit": 250}


@pytest.fixture(autouse=True)
def set_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)


class TestPagesGetAttachments:
    def test_attachments_in_json_output(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=_CONTENT_RESPONSE)
        httpx_mock.add_response(json=_ATTACHMENTS_RESPONSE)
        result = runner.invoke(app, ["pages", "get", "123", "--attachments", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["attachments"]) == 1
        assert data["attachments"][0]["filename"] == "report.pdf"

    def test_attachments_downloaded_to_output_dir(
        self, httpx_mock: HTTPXMock, tmp_path: Path
    ) -> None:
        httpx_mock.add_response(json=_CONTENT_RESPONSE)
        httpx_mock.add_response(json=_ATTACHMENTS_RESPONSE)
        httpx_mock.add_response(content=b"PDF content")  # download response
        result = runner.invoke(
            app,
            ["pages", "get", "123", "--attachments", "--output-dir", str(tmp_path)],
        )
        assert result.exit_code == 0
        saved = tmp_path / "123" / "report.pdf"
        assert saved.exists()
        assert saved.read_bytes() == b"PDF content"

    def test_saved_path_in_json(self, httpx_mock: HTTPXMock, tmp_path: Path) -> None:
        httpx_mock.add_response(json=_CONTENT_RESPONSE)
        httpx_mock.add_response(json=_ATTACHMENTS_RESPONSE)
        httpx_mock.add_response(content=b"data")
        result = runner.invoke(
            app,
            [
                "pages", "get", "123",
                "--attachments", "--output-dir", str(tmp_path),
                "--format", "json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["attachments"][0]["saved_path"] is not None

    def test_no_attachments_flag_skips_attachment_fetch(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=_CONTENT_RESPONSE)
        # No attachment response registered — would fail if fetched
        result = runner.invoke(app, ["pages", "get", "123", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["attachments"] == []


class TestPagesTreeAttachments:
    def _setup_tree(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=_PAGE_META)
        httpx_mock.add_response(json=_descendants())  # no descendants

    def test_attachments_in_tree_json(self, httpx_mock: HTTPXMock) -> None:
        self._setup_tree(httpx_mock)
        httpx_mock.add_response(json=_ATTACHMENTS_RESPONSE)
        result = runner.invoke(
            app, ["pages", "tree", "100", "--attachments", "--format", "json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["attachments"]) == 1
        assert data["attachments"][0]["filename"] == "report.pdf"

    def test_attachments_downloaded_for_tree(
        self, httpx_mock: HTTPXMock, tmp_path: Path
    ) -> None:
        self._setup_tree(httpx_mock)
        httpx_mock.add_response(json=_ATTACHMENTS_RESPONSE)
        httpx_mock.add_response(content=b"file data")
        result = runner.invoke(
            app,
            ["pages", "tree", "100", "--attachments", "--output-dir", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert (tmp_path / "100" / "report.pdf").exists()


class TestPagesTreePageFormat:
    def _setup_tree(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=_PAGE_META)
        httpx_mock.add_response(json=_descendants())  # no descendants

    def test_page_format_requires_output_dir(self, httpx_mock: HTTPXMock) -> None:
        result = runner.invoke(app, ["pages", "tree", "100", "--page-format", "text"])
        assert result.exit_code == 6
        assert "--output-dir" in result.output

    def test_page_format_text_saves_md(self, httpx_mock: HTTPXMock, tmp_path: Path) -> None:
        self._setup_tree(httpx_mock)
        httpx_mock.add_response(json={"results": [], "_links": {}})  # attachments
        httpx_mock.add_response(json=_CONTENT_RESPONSE)  # pages.get for content
        result = runner.invoke(
            app,
            ["pages", "tree", "100", "--output-dir", str(tmp_path), "--page-format", "text"],
        )
        assert result.exit_code == 0
        saved = tmp_path / "100" / "page.md"
        assert saved.exists()

    def test_page_format_html_saves_html(self, httpx_mock: HTTPXMock, tmp_path: Path) -> None:
        self._setup_tree(httpx_mock)
        httpx_mock.add_response(json={"results": [], "_links": {}})  # attachments
        httpx_mock.add_response(json=_CONTENT_RESPONSE)
        result = runner.invoke(
            app,
            ["pages", "tree", "100", "--output-dir", str(tmp_path), "--page-format", "html"],
        )
        assert result.exit_code == 0
        assert (tmp_path / "100" / "page.html").exists()

    def test_page_format_json_saves_json(self, httpx_mock: HTTPXMock, tmp_path: Path) -> None:
        self._setup_tree(httpx_mock)
        httpx_mock.add_response(json={"results": [], "_links": {}})  # attachments
        httpx_mock.add_response(json=_CONTENT_RESPONSE)
        result = runner.invoke(
            app,
            ["pages", "tree", "100", "--output-dir", str(tmp_path), "--page-format", "json"],
        )
        assert result.exit_code == 0
        saved = tmp_path / "100" / "page.json"
        assert saved.exists()
        data = json.loads(saved.read_text())
        assert "id" in data
        assert "title" in data

    def test_page_format_storage_saves_xml(self, httpx_mock: HTTPXMock, tmp_path: Path) -> None:
        self._setup_tree(httpx_mock)
        httpx_mock.add_response(json={"results": [], "_links": {}})  # attachments
        httpx_mock.add_response(json=_CONTENT_RESPONSE)
        result = runner.invoke(
            app,
            [
                "pages", "tree", "100",
                "--output-dir", str(tmp_path),
                "--page-format", "storage",
            ],
        )
        assert result.exit_code == 0
        assert (tmp_path / "100" / "page.xml").exists()

    def test_page_format_with_attachments(self, httpx_mock: HTTPXMock, tmp_path: Path) -> None:
        self._setup_tree(httpx_mock)
        httpx_mock.add_response(json=_ATTACHMENTS_RESPONSE)
        httpx_mock.add_response(content=b"pdf")
        httpx_mock.add_response(json=_CONTENT_RESPONSE)
        result = runner.invoke(
            app,
            [
                "pages", "tree", "100",
                "--attachments", "--output-dir", str(tmp_path),
                "--page-format", "text",
            ],
        )
        assert result.exit_code == 0
        assert (tmp_path / "100" / "report.pdf").exists()
        assert (tmp_path / "100" / "page.md").exists()
