import pytest
from pytest_httpx import HTTPXMock

from ccli.auth import build_client
from ccli.client.base import ConfluenceClient
from ccli.client.spaces import SpacesClient, _extract_cursor
from ccli.config import Config, ConfluenceSettings
from ccli.exceptions import NotFoundError

BASE_URL = "https://example.atlassian.net"
SPACES_URL = f"{BASE_URL}/wiki/api/v2/spaces"
SPACE_DETAIL_URL = f"{BASE_URL}/wiki/rest/api/space"

_SPACE_A = {"id": "1", "key": "DEV", "name": "Development", "type": "global", "status": "current"}
_SPACE_B = {"id": "2", "key": "ARCH", "name": "Architecture", "type": "global", "status": "current"}
_SPACE_P = {
    "id": "3", "key": "~john", "name": "John's Space", "type": "personal", "status": "current"
}


def _make_spaces_client(httpx_mock: HTTPXMock) -> SpacesClient:
    config = Config(
        confluence=ConfluenceSettings(url=BASE_URL, username="u@example.com", api_token="tok")
    )
    return SpacesClient(ConfluenceClient(build_client(config)))


class TestSpacesList:
    def test_returns_spaces(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            json={"results": [_SPACE_A, _SPACE_B], "_links": {}}
        )
        client = _make_spaces_client(httpx_mock)
        spaces = client.list(limit=25)
        assert len(spaces) == 2
        assert spaces[0].key == "DEV"
        assert spaces[1].key == "ARCH"

    def test_respects_limit(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            json={"results": [_SPACE_A, _SPACE_B], "_links": {}}
        )
        client = _make_spaces_client(httpx_mock)
        spaces = client.list(limit=1)
        assert len(spaces) == 1

    def test_follows_pagination_cursor(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            json={
                "results": [_SPACE_A],
                "_links": {"next": "/wiki/api/v2/spaces?cursor=abc&limit=1"},
            }
        )
        httpx_mock.add_response(
            json={"results": [_SPACE_B], "_links": {}}
        )
        client = _make_spaces_client(httpx_mock)
        spaces = client.list(limit=10)
        assert len(spaces) == 2

    def test_filters_by_type(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json={"results": [_SPACE_P], "_links": {}})
        client = _make_spaces_client(httpx_mock)
        spaces = client.list(limit=25, space_type="personal")
        request = httpx_mock.get_requests()[0]
        assert "type=personal" in str(request.url)
        assert spaces[0].type == "personal"

    def test_empty_results(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(json={"results": [], "_links": {}})
        client = _make_spaces_client(httpx_mock)
        assert client.list() == []


class TestSpacesSearch:
    def test_matches_by_name(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            json={"results": [_SPACE_A, _SPACE_B, _SPACE_P], "_links": {}}
        )
        client = _make_spaces_client(httpx_mock)
        results = client.search("arch")
        assert len(results) == 1
        assert results[0].key == "ARCH"

    def test_matches_by_key(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            json={"results": [_SPACE_A, _SPACE_B, _SPACE_P], "_links": {}}
        )
        client = _make_spaces_client(httpx_mock)
        results = client.search("dev")
        assert results[0].key == "DEV"

    def test_case_insensitive(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            json={"results": [_SPACE_A], "_links": {}}
        )
        client = _make_spaces_client(httpx_mock)
        results = client.search("DEVELOPMENT")
        assert len(results) == 1

    def test_no_match_returns_empty(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            json={"results": [_SPACE_A, _SPACE_B], "_links": {}}
        )
        client = _make_spaces_client(httpx_mock)
        assert client.search("zzznomatch") == []


class TestGetHomepageId:
    def test_returns_homepage_id(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url=f"{SPACE_DETAIL_URL}/DEV?expand=homepage",
            json={"homepage": {"id": "555"}},
        )
        client = _make_spaces_client(httpx_mock)
        assert client.get_homepage_id("DEV") == "555"

    def test_raises_not_found_when_no_homepage(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url=f"{SPACE_DETAIL_URL}/DEV?expand=homepage",
            json={},
        )
        client = _make_spaces_client(httpx_mock)
        with pytest.raises(NotFoundError, match="no homepage"):
            client.get_homepage_id("DEV")

    def test_raises_not_found_on_404(self, httpx_mock: HTTPXMock) -> None:
        httpx_mock.add_response(
            url=f"{SPACE_DETAIL_URL}/NOKEY?expand=homepage",
            status_code=404,
        )
        client = _make_spaces_client(httpx_mock)
        with pytest.raises(NotFoundError):
            client.get_homepage_id("NOKEY")


class TestExtractCursor:
    def test_extracts_cursor(self) -> None:
        url = "/wiki/api/v2/spaces?cursor=abc123&limit=25"
        assert _extract_cursor(url) == "abc123"

    def test_returns_none_when_absent(self) -> None:
        url = "/wiki/api/v2/spaces?limit=25"
        assert _extract_cursor(url) is None
