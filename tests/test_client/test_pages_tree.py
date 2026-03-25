from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from ccli.auth import build_client
from ccli.client.base import ConfluenceClient
from ccli.client.pages import PagesClient
from ccli.config import Config, ConfluenceSettings
from ccli.exceptions import NotFoundError

BASE_URL = "https://example.atlassian.net"

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
_GRANDCHILD = {
    "id": "201",
    "title": "Grandchild",
    "_links": {"webui": "/wiki/spaces/DEV/pages/201"},
}


def _make_client(httpx_mock: HTTPXMock) -> PagesClient:
    config = Config(
        confluence=ConfluenceSettings(url=BASE_URL, username="u@example.com", api_token="tok")
    )
    return PagesClient(ConfluenceClient(build_client(config)), BASE_URL)


class TestGetTree:
    def test_root_only_when_no_children(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=_ROOT_META)  # GET /pages/100
        httpx_mock.add_response(json={"results": [], "_links": {}})  # GET /pages/100/children
        client = _make_client(httpx_mock)
        tree = client.get_tree("100")
        assert tree.id == "100"
        assert tree.title == "Root Page"
        assert tree.children == []

    def test_single_level_children(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=_ROOT_META)
        httpx_mock.add_response(json={"results": [_CHILD_A, _CHILD_B], "_links": {}})
        httpx_mock.add_response(json={"results": [], "_links": {}})  # children of A
        httpx_mock.add_response(json={"results": [], "_links": {}})  # children of B
        client = _make_client(httpx_mock)
        tree = client.get_tree("100")
        assert len(tree.children) == 2
        assert tree.children[0].id == "101"
        assert tree.children[1].id == "102"

    def test_nested_children(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=_ROOT_META)
        httpx_mock.add_response(json={"results": [_CHILD_A], "_links": {}})
        httpx_mock.add_response(json={"results": [_GRANDCHILD], "_links": {}})
        httpx_mock.add_response(json={"results": [], "_links": {}})  # grandchild has no children
        client = _make_client(httpx_mock)
        tree = client.get_tree("100")
        assert tree.children[0].children[0].id == "201"
        assert tree.children[0].children[0].title == "Grandchild"

    def test_depth_zero_fetches_root_only(self, httpx_mock: HTTPXMock) -> None:
        # depth=0 → _fill_children returns immediately; only 1 request (root meta)
        httpx_mock.add_response(json=_ROOT_META)
        client = _make_client(httpx_mock)
        tree = client.get_tree("100", depth=0)
        assert tree.id == "100"
        assert tree.children == []

    def test_depth_one_fetches_direct_children_only(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=_ROOT_META)
        httpx_mock.add_response(json={"results": [_CHILD_A], "_links": {}})
        # Children of child A should NOT be fetched (depth=1 stops here)
        client = _make_client(httpx_mock)
        tree = client.get_tree("100", depth=1)
        assert len(tree.children) == 1
        assert tree.children[0].children == []

    def test_url_populated(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=_ROOT_META)
        httpx_mock.add_response(json={"results": [], "_links": {}})
        client = _make_client(httpx_mock)
        tree = client.get_tree("100")
        assert tree.url.startswith(BASE_URL)

    def test_404_raises_not_found(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=404)
        client = _make_client(httpx_mock)
        with pytest.raises(NotFoundError):
            client.get_tree("999")

    def test_pagination_in_children(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=_ROOT_META)
        # First page of children
        httpx_mock.add_response(
            json={
                "results": [_CHILD_A],
                "_links": {"next": f"{BASE_URL}/wiki/api/v2/pages/100/children?cursor=abc"},
            }
        )
        # Second page of children
        httpx_mock.add_response(json={"results": [_CHILD_B], "_links": {}})
        # Children of A and B
        httpx_mock.add_response(json={"results": [], "_links": {}})
        httpx_mock.add_response(json={"results": [], "_links": {}})
        client = _make_client(httpx_mock)
        tree = client.get_tree("100")
        assert len(tree.children) == 2
