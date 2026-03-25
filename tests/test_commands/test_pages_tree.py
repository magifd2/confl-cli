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

_ROOT_META = {
    "id": "100",
    "title": "Root Page",
    "version": {"when": "2024-01-10T00:00:00.000Z"},
    "history": {"createdDate": "2024-01-01T00:00:00.000Z"},
    "_links": {"webui": "/wiki/spaces/DEV/pages/100"},
}
# Descendants include ancestors list
_DESC_CHILD_A = {
    "id": "101",
    "title": "Child A",
    "version": {"when": "2024-01-15T10:00:00.000Z"},
    "history": {"createdDate": "2024-01-05T00:00:00.000Z"},
    "ancestors": [{"id": "100"}],
    "_links": {"webui": "/wiki/spaces/DEV/pages/101"},
}
_DESC_CHILD_B = {
    "id": "102",
    "title": "Child B",
    "version": {"when": "2024-01-20T10:00:00.000Z"},
    "history": {"createdDate": "2024-01-06T00:00:00.000Z"},
    "ancestors": [{"id": "100"}],
    "_links": {"webui": "/wiki/spaces/DEV/pages/102"},
}


def _descendants(*pages: dict) -> dict:  # type: ignore[type-arg]
    return {"results": list(pages), "size": len(pages), "limit": 250}


@pytest.fixture(autouse=True)
def set_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)


def _setup_flat_tree(httpx_mock: HTTPXMock) -> None:
    """Root with two children (2 API calls total)."""
    httpx_mock.add_response(json=_ROOT_META)
    httpx_mock.add_response(json=_descendants(_DESC_CHILD_A, _DESC_CHILD_B))


class TestPagesTree:
    def test_text_output_shows_titles(self, httpx_mock: HTTPXMock) -> None:
        _setup_flat_tree(httpx_mock)
        result = runner.invoke(app, ["pages", "tree", "100"])
        assert result.exit_code == 0
        assert "Root Page" in result.output
        assert "Child A" in result.output
        assert "Child B" in result.output

    def test_text_output_shows_ids(self, httpx_mock: HTTPXMock) -> None:
        _setup_flat_tree(httpx_mock)
        result = runner.invoke(app, ["pages", "tree", "100"])
        assert "100" in result.output
        assert "101" in result.output

    def test_json_output(self, httpx_mock: HTTPXMock) -> None:
        _setup_flat_tree(httpx_mock)
        result = runner.invoke(app, ["pages", "tree", "100", "--format", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["id"] == "100"
        assert data["title"] == "Root Page"
        assert len(data["children"]) == 2
        assert data["children"][0]["id"] == "101"

    def test_depth_option(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=_ROOT_META)
        httpx_mock.add_response(json=_descendants(_DESC_CHILD_A))
        result = runner.invoke(app, ["pages", "tree", "100", "--depth", "1"])
        assert result.exit_code == 0
        assert "Child A" in result.output

    def test_depth_zero(self, httpx_mock: HTTPXMock) -> None:
        # depth=0 → only root meta is fetched, no descendant request
        httpx_mock.add_response(json=_ROOT_META)
        result = runner.invoke(app, ["pages", "tree", "100", "--depth", "0"])
        assert result.exit_code == 0
        assert "Root Page" in result.output
        assert "Child A" not in result.output

    def test_not_found_exits_3(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=404)
        result = runner.invoke(app, ["pages", "tree", "999"])
        assert result.exit_code == 3

    def test_json_children_structure(self, httpx_mock: HTTPXMock) -> None:
        _setup_flat_tree(httpx_mock)
        result = runner.invoke(app, ["pages", "tree", "100", "--format", "json"])
        data = json.loads(result.output)
        assert data["children"][0]["children"] == []
