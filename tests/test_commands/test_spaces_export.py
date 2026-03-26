import json

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

_SPACE_DETAIL = {"homepage": {"id": "100"}}

_ROOT_META = {
    "id": "100",
    "title": "Home Page",
    "version": {"when": "2024-01-10T00:00:00.000Z"},
    "history": {"createdDate": "2024-01-01T00:00:00.000Z"},
    "_links": {"webui": "/wiki/spaces/DEV/pages/100"},
}
_DESC_CHILD = {
    "id": "101",
    "title": "Child Page",
    "version": {"when": "2024-01-15T00:00:00.000Z"},
    "history": {"createdDate": "2024-01-05T00:00:00.000Z"},
    "ancestors": [{"id": "100"}],
    "_links": {"webui": "/wiki/spaces/DEV/pages/101"},
}


def _descendants(*pages: dict) -> dict:  # type: ignore[type-arg]
    return {"results": list(pages), "size": len(pages), "limit": 250}


@pytest.fixture(autouse=True)
def set_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)


class TestSpacesExport:
    def test_text_output_shows_tree(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=_SPACE_DETAIL)  # space detail
        httpx_mock.add_response(json=_ROOT_META)     # root page meta
        httpx_mock.add_response(json=_descendants(_DESC_CHILD))  # descendants
        result = runner.invoke(app, ["spaces", "export", "DEV"])
        assert result.exit_code == 0
        assert "Home Page" in result.output
        assert "Child Page" in result.output

    def test_json_output(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=_SPACE_DETAIL)
        httpx_mock.add_response(json=_ROOT_META)
        httpx_mock.add_response(json=_descendants(_DESC_CHILD))
        result = runner.invoke(app, ["spaces", "export", "DEV", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "100"
        assert data["children"][0]["id"] == "101"

    def test_no_children(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=_SPACE_DETAIL)
        httpx_mock.add_response(json=_ROOT_META)
        httpx_mock.add_response(json=_descendants())
        result = runner.invoke(app, ["spaces", "export", "DEV"])
        assert result.exit_code == 0
        assert "Home Page" in result.output

    def test_space_not_found_exits_3(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=404)
        result = runner.invoke(app, ["spaces", "export", "NOKEY"])
        assert result.exit_code == 3

    def test_page_format_without_output_dir_exits_6(self, httpx_mock: HTTPXMock) -> None:
        result = runner.invoke(app, ["spaces", "export", "DEV", "--page-format", "text"])
        assert result.exit_code == 6

    def test_depth_option(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=_SPACE_DETAIL)
        httpx_mock.add_response(json=_ROOT_META)
        result = runner.invoke(app, ["spaces", "export", "DEV", "--depth", "0"])
        assert result.exit_code == 0
        assert "Home Page" in result.output
        assert "Child Page" not in result.output
