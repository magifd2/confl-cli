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
    "version": {"createdAt": "2024-01-10T00:00:00.000Z"},
    "_links": {"webui": "/wiki/spaces/DEV/pages/100"},
}

# v1 child/page format: includes version.when and _links.webui
_CHILD_A = {
    "id": "101",
    "title": "Child A",
    "version": {"when": "2024-01-15T10:00:00.000Z"},
    "_links": {"webui": "/wiki/spaces/DEV/pages/101"},
}
_CHILD_B = {
    "id": "102",
    "title": "Child B",
    "version": {"when": "2024-01-20T10:00:00.000Z"},
    "_links": {"webui": "/wiki/spaces/DEV/pages/102"},
}
_GRANDCHILD = {
    "id": "201",
    "title": "Grandchild",
    "version": {"when": "2024-01-25T10:00:00.000Z"},
    "_links": {"webui": "/wiki/spaces/DEV/pages/201"},
}

# v1 children response wrapper
def _children(*pages: dict) -> dict:  # type: ignore[type-arg]
    return {"results": list(pages), "size": len(pages), "limit": 250}


def _make_client(httpx_mock: HTTPXMock) -> PagesClient:
    config = Config(
        confluence=ConfluenceSettings(url=BASE_URL, username="u@example.com", api_token="tok")
    )
    return PagesClient(ConfluenceClient(build_client(config)), BASE_URL)


class TestGetTree:
    def test_root_only_when_no_children(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=_ROOT_META)  # GET /pages/100 (v2)
        httpx_mock.add_response(json=_children())  # GET /content/100/child/page (v1)
        client = _make_client(httpx_mock)
        tree = client.get_tree("100")
        assert tree.id == "100"
        assert tree.title == "Root Page"
        assert tree.children == []

    def test_single_level_children(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=_ROOT_META)
        httpx_mock.add_response(json=_children(_CHILD_A, _CHILD_B))
        httpx_mock.add_response(json=_children())  # children of A
        httpx_mock.add_response(json=_children())  # children of B
        client = _make_client(httpx_mock)
        tree = client.get_tree("100")
        assert len(tree.children) == 2
        assert tree.children[0].id == "101"
        assert tree.children[1].id == "102"

    def test_nested_children(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=_ROOT_META)
        httpx_mock.add_response(json=_children(_CHILD_A))
        httpx_mock.add_response(json=_children(_GRANDCHILD))
        httpx_mock.add_response(json=_children())  # grandchild has no children
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
        httpx_mock.add_response(json=_children(_CHILD_A))
        # Children of child A should NOT be fetched (depth=1 stops here)
        client = _make_client(httpx_mock)
        tree = client.get_tree("100", depth=1)
        assert len(tree.children) == 1
        assert tree.children[0].children == []

    def test_url_populated(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=_ROOT_META)
        httpx_mock.add_response(json=_children(_CHILD_A))
        httpx_mock.add_response(json=_children())  # children of A
        client = _make_client(httpx_mock)
        tree = client.get_tree("100")
        assert tree.url.startswith(BASE_URL)
        assert tree.children[0].url.startswith(BASE_URL)

    def test_404_raises_not_found(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=404)
        client = _make_client(httpx_mock)
        with pytest.raises(NotFoundError):
            client.get_tree("999")

    def test_updated_at_populated(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=_ROOT_META)
        httpx_mock.add_response(json=_children(_CHILD_A))
        httpx_mock.add_response(json=_children())
        client = _make_client(httpx_mock)
        tree = client.get_tree("100")
        assert tree.updated_at == "2024-01-10T00:00:00.000Z"
        assert tree.children[0].updated_at == "2024-01-15T10:00:00.000Z"

    def test_pagination_in_children(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=_ROOT_META)
        # First page: size == limit (250), triggers next page fetch
        httpx_mock.add_response(
            json={"results": [_CHILD_A], "size": 250, "limit": 250}
        )
        # Second page: size < limit, stops pagination
        httpx_mock.add_response(json=_children(_CHILD_B))
        # Children of A and B
        httpx_mock.add_response(json=_children())
        httpx_mock.add_response(json=_children())
        client = _make_client(httpx_mock)
        tree = client.get_tree("100")
        assert len(tree.children) == 2
