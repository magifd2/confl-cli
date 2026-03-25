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
    "_links": {"webui": "/wiki/spaces/DEV/pages/100"},
}
_CHILD_A = {
    "id": "101",
    "title": "Child A",
    "_links": {"webui": "/wiki/spaces/DEV/pages/101"},
}
_CHILD_B = {
    "id": "102",
    "title": "Child B",
    "_links": {"webui": "/wiki/spaces/DEV/pages/102"},
}


@pytest.fixture(autouse=True)
def set_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)


def _setup_flat_tree(httpx_mock: HTTPXMock) -> None:
    """Root with two children, no grandchildren."""
    httpx_mock.add_response(json=_ROOT_META)
    httpx_mock.add_response(json={"results": [_CHILD_A, _CHILD_B], "_links": {}})
    httpx_mock.add_response(json={"results": [], "_links": {}})
    httpx_mock.add_response(json={"results": [], "_links": {}})


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
        httpx_mock.add_response(json={"results": [_CHILD_A], "_links": {}})
        result = runner.invoke(app, ["pages", "tree", "100", "--depth", "1"])
        assert result.exit_code == 0
        assert "Child A" in result.output

    def test_depth_zero(self, httpx_mock: HTTPXMock) -> None:
        # depth=0 → only root meta is fetched, no children request
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
        # Children should have empty children lists (no grandchildren)
        assert data["children"][0]["children"] == []
