from __future__ import annotations

import builtins
from typing import Any
from urllib.parse import parse_qs, urlparse

from pydantic import BaseModel, Field

from ..auth import API_V1, API_V2
from ..exceptions import NotFoundError
from .base import ConfluenceClient

_SPACES_PATH = f"{API_V2}/spaces"
_SPACE_DETAIL_PATH = f"{API_V1}/space"
_MAX_FETCH = 250  # Confluence v2 upper limit per request


class _V1HomepageRef(BaseModel):
    id: str


class _V1SpaceDetail(BaseModel):
    homepage: _V1HomepageRef | None = None


class Space(BaseModel):
    id: str
    key: str
    name: str
    type: str
    status: str = "current"
    homepage_id: str | None = Field(None, alias="homepageId")

    model_config = {"populate_by_name": True}


class _SpacesResponse(BaseModel):
    results: list[Space]
    links: dict[str, Any] = Field(default_factory=dict, alias="_links")

    model_config = {"populate_by_name": True}


class SpacesClient:
    def __init__(self, client: ConfluenceClient) -> None:
        self._client = client

    def list(self, limit: int = 25, space_type: str | None = None) -> builtins.list[Space]:
        """Return up to *limit* spaces, following pagination cursors as needed."""
        params: dict[str, Any] = {"limit": min(limit, _MAX_FETCH)}
        if space_type:
            params["type"] = space_type

        spaces: list[Space] = []
        cursor: str | None = None

        while len(spaces) < limit:
            if cursor:
                params["cursor"] = cursor

            data = self._client.get(_SPACES_PATH, params=params)
            page = _SpacesResponse(**data)
            spaces.extend(page.results)

            next_url = page.links.get("next")
            if not next_url:
                break
            cursor = _extract_cursor(next_url)
            if not cursor:
                break

        return spaces[:limit]

    def get_homepage_id(self, space_key: str) -> str:
        """Return the homepage page ID for *space_key*.

        Uses the v1 ``/space/{key}?expand=homepage`` endpoint.
        Raises :exc:`NotFoundError` if the space does not exist or has no homepage.
        """
        data = self._client.get(
            f"{_SPACE_DETAIL_PATH}/{space_key}", params={"expand": "homepage"}
        )
        detail = _V1SpaceDetail(**data)
        if detail.homepage is None:
            raise NotFoundError(f"Space '{space_key}' has no homepage.")
        return detail.homepage.id

    def search(self, query: str, limit: int = 25) -> builtins.list[Space]:
        """Search spaces by name or key (case-insensitive substring match).

        Confluence v2 does not expose a server-side title filter on the spaces
        endpoint, so we fetch all spaces and filter locally.
        """
        all_spaces = self.list(limit=_MAX_FETCH)
        q = query.lower()
        matched = [s for s in all_spaces if q in s.name.lower() or q in s.key.lower()]
        return matched[:limit]


def _extract_cursor(next_url: str) -> str | None:
    parsed = urlparse(next_url)
    qs = parse_qs(parsed.query)
    cursors = qs.get("cursor", [])
    return cursors[0] if cursors else None
