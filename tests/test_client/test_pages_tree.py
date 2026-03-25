from __future__ import annotations

import pytest
from pytest_httpx import HTTPXMock

from ccli.auth import build_client
from ccli.client.base import ConfluenceClient
from ccli.client.pages import PagesClient
from ccli.config import Config, ConfluenceSettings
from ccli.exceptions import NotFoundError

BASE_URL = "https://example.atlassian.net"

# Root uses v1 content format (expand=version,history)
_ROOT_META = {
    "id": "100",
    "title": "Root Page",
    "version": {"when": "2024-01-10T00:00:00.000Z"},
    "history": {"createdDate": "2024-01-01T00:00:00.000Z"},
    "_links": {"webui": "/wiki/spaces/DEV/pages/100"},
}

# Descendants use v1 descendant format (includes ancestors list)
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
_DESC_GRANDCHILD = {
    "id": "201",
    "title": "Grandchild",
    "version": {"when": "2024-01-25T10:00:00.000Z"},
    "history": {"createdDate": "2024-01-07T00:00:00.000Z"},
    "ancestors": [{"id": "100"}, {"id": "101"}],
    "_links": {"webui": "/wiki/spaces/DEV/pages/201"},
}


def _descendants(*pages: dict) -> dict:  # type: ignore[type-arg]
    return {"results": list(pages), "size": len(pages), "limit": 250}


def _make_client(httpx_mock: HTTPXMock) -> PagesClient:
    config = Config(
        confluence=ConfluenceSettings(url=BASE_URL, username="u@example.com", api_token="tok")
    )
    return PagesClient(ConfluenceClient(build_client(config)), BASE_URL)


class TestGetTree:
    def test_root_only_when_no_descendants(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=_ROOT_META)
        httpx_mock.add_response(json=_descendants())
        client = _make_client(httpx_mock)
        tree = client.get_tree("100")
        assert tree.id == "100"
        assert tree.title == "Root Page"
        assert tree.children == []

    def test_single_level_children(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=_ROOT_META)
        httpx_mock.add_response(json=_descendants(_DESC_CHILD_A, _DESC_CHILD_B))
        client = _make_client(httpx_mock)
        tree = client.get_tree("100")
        assert len(tree.children) == 2
        assert tree.children[0].id == "101"
        assert tree.children[1].id == "102"

    def test_nested_children(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=_ROOT_META)
        httpx_mock.add_response(json=_descendants(_DESC_CHILD_A, _DESC_GRANDCHILD))
        client = _make_client(httpx_mock)
        tree = client.get_tree("100")
        assert len(tree.children) == 1
        assert tree.children[0].children[0].id == "201"
        assert tree.children[0].children[0].title == "Grandchild"

    def test_depth_zero_fetches_root_only(self, httpx_mock: HTTPXMock) -> None:
        # depth=0 → skip descendant request entirely
        httpx_mock.add_response(json=_ROOT_META)
        client = _make_client(httpx_mock)
        tree = client.get_tree("100", depth=0)
        assert tree.id == "100"
        assert tree.children == []

    def test_depth_one_includes_only_direct_children(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=_ROOT_META)
        httpx_mock.add_response(json=_descendants(_DESC_CHILD_A, _DESC_GRANDCHILD))
        client = _make_client(httpx_mock)
        tree = client.get_tree("100", depth=1)
        assert len(tree.children) == 1
        assert tree.children[0].id == "101"
        assert tree.children[0].children == []  # grandchild filtered out

    def test_url_populated(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=_ROOT_META)
        httpx_mock.add_response(json=_descendants(_DESC_CHILD_A))
        client = _make_client(httpx_mock)
        tree = client.get_tree("100")
        assert tree.url.startswith(BASE_URL)
        assert tree.children[0].url.startswith(BASE_URL)

    def test_404_raises_not_found(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(status_code=404)
        client = _make_client(httpx_mock)
        with pytest.raises(NotFoundError):
            client.get_tree("999")

    def test_dates_populated(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=_ROOT_META)
        httpx_mock.add_response(json=_descendants(_DESC_CHILD_A))
        client = _make_client(httpx_mock)
        tree = client.get_tree("100")
        assert tree.updated_at == "2024-01-10T00:00:00.000Z"
        assert tree.created_at == "2024-01-01T00:00:00.000Z"
        assert tree.children[0].updated_at == "2024-01-15T10:00:00.000Z"
        assert tree.children[0].created_at == "2024-01-05T00:00:00.000Z"

    def test_pagination_in_descendants(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json=_ROOT_META)
        # First page: size == limit → fetch more
        httpx_mock.add_response(
            json={"results": [_DESC_CHILD_A], "size": 250, "limit": 250}
        )
        # Second page: size < limit → stop
        httpx_mock.add_response(json=_descendants(_DESC_CHILD_B))
        client = _make_client(httpx_mock)
        tree = client.get_tree("100")
        assert len(tree.children) == 2

    def test_non_root_starting_node(self, httpx_mock: HTTPXMock) -> None:
        """Root with global ancestors — depth calc must account for root's position."""
        root_with_parent = {
            "id": "101",
            "title": "Child A",
            "version": {"when": "2024-01-15T10:00:00.000Z"},
            "history": {"createdDate": "2024-01-05T00:00:00.000Z"},
            "_links": {"webui": "/wiki/spaces/DEV/pages/101"},
        }
        # Grandchild appears as depth-1 descendant of "101"
        grandchild_desc = {
            "id": "201",
            "title": "Grandchild",
            "version": {"when": "2024-01-25T10:00:00.000Z"},
            "history": {"createdDate": "2024-01-07T00:00:00.000Z"},
            # ancestors includes the global parent "100" AND our root "101"
            "ancestors": [{"id": "100"}, {"id": "101"}],
            "_links": {"webui": "/wiki/spaces/DEV/pages/201"},
        }
        httpx_mock.add_response(json=root_with_parent)
        httpx_mock.add_response(json=_descendants(grandchild_desc))
        client = _make_client(httpx_mock)
        tree = client.get_tree("101")
        assert len(tree.children) == 1
        assert tree.children[0].id == "201"

    def test_space_home_page_virtual_root_in_ancestors(
        self, httpx_mock: HTTPXMock
    ) -> None:
        """Regression: Confluence Cloud sometimes returns a virtual space-root node
        in the ancestors list instead of (or in addition to) the queried page.
        Children whose ancestors don't include the queried page ID must still be
        attached to the root rather than dropped as orphans.
        """
        # Home page has no ancestors of its own (it IS the space root)
        home_meta = {
            "id": "100",
            "title": "Space Home",
            "version": {"when": "2024-01-10T00:00:00.000Z"},
            "history": {"createdDate": "2024-01-01T00:00:00.000Z"},
            "_links": {"webui": "/wiki/spaces/DEV/pages/100"},
        }
        # Direct child: ancestors list contains a virtual-space-root ID, NOT "100"
        child_virtual = {
            "id": "200",
            "title": "Page A",
            "version": {"when": "2024-01-15T00:00:00.000Z"},
            "history": {"createdDate": "2024-01-05T00:00:00.000Z"},
            "ancestors": [{"id": "virtual-space-root"}],  # home page 100 absent
            "_links": {"webui": "/wiki/spaces/DEV/pages/200"},
        }
        # Grandchild: ancestors are [virtual-space-root, 200]
        grandchild_virtual = {
            "id": "300",
            "title": "Page B",
            "version": {"when": "2024-01-20T00:00:00.000Z"},
            "history": {"createdDate": "2024-01-06T00:00:00.000Z"},
            "ancestors": [{"id": "virtual-space-root"}, {"id": "200"}],
            "_links": {"webui": "/wiki/spaces/DEV/pages/300"},
        }
        httpx_mock.add_response(json=home_meta)
        httpx_mock.add_response(json=_descendants(child_virtual, grandchild_virtual))
        client = _make_client(httpx_mock)
        tree = client.get_tree("100")
        # Both pages must appear — not orphaned
        assert len(tree.children) == 1
        assert tree.children[0].id == "200"
        assert len(tree.children[0].children) == 1
        assert tree.children[0].children[0].id == "300"
