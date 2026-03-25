from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from ..auth import API_V1, API_V2
from .attachments import Attachment
from .base import ConfluenceClient

_SEARCH_PATH = f"{API_V1}/search"
_CONTENT_PATH = f"{API_V1}/content"

_GET_EXPAND = "body.view,body.storage,space,version,ancestors,history"

_HL_PATTERN = re.compile(r"@@@hl@@@|@@@endhl@@@")


def _strip_highlights(text: str) -> str:
    """Remove Confluence search highlight markers from a string."""
    return _HL_PATTERN.sub("", text)


# --------------------------------------------------------------------------- #
# Public domain models                                                         #
# --------------------------------------------------------------------------- #


class Author(BaseModel):
    display_name: str
    email: str | None = None


class Page(BaseModel):
    id: str
    title: str
    space_key: str
    space_name: str
    version: int
    created_at: str
    updated_at: str
    author: Author
    body_html: str
    body_storage: str  # Confluence Storage Format (XHTML-like)
    url: str
    parent_id: str | None = None
    attachments: list[Attachment] = []


class PageSummary(BaseModel):
    id: str
    space_key: str
    space_name: str
    title: str
    url: str
    last_modified: str
    excerpt: str = ""


class PageNode(BaseModel):
    """Lightweight page node used for tree traversal (metadata only, no body content)."""

    id: str
    title: str
    url: str = ""
    updated_at: str = ""  # populated from version.createdAt in v2 API
    attachments: list[Attachment] = []  # populated when --attachments is used
    children: list[PageNode] = []


PageNode.model_rebuild()


# --------------------------------------------------------------------------- #
# Internal Pydantic models for v2 API responses (tree / metadata)              #
# --------------------------------------------------------------------------- #


class _V2Version(BaseModel):
    created_at: str = Field("", alias="createdAt")

    model_config = {"populate_by_name": True}


class _V2PageMeta(BaseModel):
    id: str
    title: str
    version: _V2Version = Field(default_factory=_V2Version)
    links: dict[str, Any] = Field(default_factory=dict, alias="_links")

    model_config = {"populate_by_name": True}


class _V2ListResponse(BaseModel):
    results: list[_V2PageMeta]
    links: dict[str, Any] = Field(default_factory=dict, alias="_links")

    model_config = {"populate_by_name": True}


# v1 child/page response models (used to get version.when and _links.webui for children)

class _V1ChildVersion(BaseModel):
    when: str = ""


class _V1ChildLinks(BaseModel):
    webui: str = ""

    model_config = {"populate_by_name": True}


class _V1ChildPage(BaseModel):
    id: str
    title: str
    version: _V1ChildVersion = Field(default_factory=_V1ChildVersion)
    links: _V1ChildLinks = Field(default_factory=_V1ChildLinks, alias="_links")

    model_config = {"populate_by_name": True}


class _V1ChildrenResponse(BaseModel):
    results: list[_V1ChildPage]
    size: int = 0
    limit: int = 25

    model_config = {"populate_by_name": True}


# --------------------------------------------------------------------------- #
# Internal Pydantic models for v1 API responses                                #
# --------------------------------------------------------------------------- #


class _SpaceInfo(BaseModel):
    key: str = ""
    name: str = ""


class _By(BaseModel):
    display_name: str = Field("", alias="displayName")
    email: str | None = None

    model_config = {"populate_by_name": True}


class _Version(BaseModel):
    number: int
    when: str
    by: _By


class _History(BaseModel):
    created_date: str = Field("", alias="createdDate")
    created_by: _By = Field(default_factory=_By, alias="createdBy")

    model_config = {"populate_by_name": True}


class _BodyValue(BaseModel):
    value: str = ""


class _Body(BaseModel):
    view: _BodyValue = Field(default_factory=_BodyValue)
    storage: _BodyValue = Field(default_factory=_BodyValue)


class _Ancestor(BaseModel):
    id: str


class _ContentResponse(BaseModel):
    id: str
    title: str
    space: _SpaceInfo = Field(default_factory=_SpaceInfo)
    version: _Version
    history: _History = Field(default_factory=_History)
    body: _Body = Field(default_factory=_Body)
    ancestors: list[_Ancestor] = []
    links: dict[str, Any] = Field(default_factory=dict, alias="_links")

    model_config = {"populate_by_name": True}


class _SearchContent(BaseModel):
    id: str = ""
    space: _SpaceInfo = Field(default_factory=_SpaceInfo)
    links: dict[str, Any] = Field(default_factory=dict, alias="_links")

    model_config = {"populate_by_name": True}


class _SearchResult(BaseModel):
    content: _SearchContent | None = None
    title: str = ""
    excerpt: str = ""
    url: str = ""
    last_modified: str = Field("", alias="lastModified")

    model_config = {"populate_by_name": True}


class _SearchResponse(BaseModel):
    results: list[_SearchResult]
    total_size: int = Field(0, alias="totalSize")

    model_config = {"populate_by_name": True}


# --------------------------------------------------------------------------- #
# Client                                                                       #
# --------------------------------------------------------------------------- #


class PagesClient:
    def __init__(self, client: ConfluenceClient, confluence_url: str) -> None:
        self._client = client
        self._base_url = confluence_url.rstrip("/")

    def search(
        self,
        query: str,
        space_key: str | None = None,
        limit: int = 25,
    ) -> list[PageSummary]:
        cql = f'text ~ "{query}" AND type = page'
        if space_key:
            cql += f' AND space = "{space_key}"'

        params: dict[str, Any] = {
            "cql": cql,
            "limit": limit,
            "expand": "content.space",
        }

        data = self._client.get(_SEARCH_PATH, params=params)
        response = _SearchResponse(**data)

        summaries: list[PageSummary] = []
        for result in response.results[:limit]:
            content = result.content
            summaries.append(
                PageSummary(
                    id=content.id if content else "",
                    space_key=content.space.key if content else "",
                    space_name=content.space.name if content else "",
                    title=_strip_highlights(result.title),
                    url=result.url or (
                        self._base_url + content.links.get("webui", "") if content else ""
                    ),
                    last_modified=result.last_modified,
                    excerpt=_strip_highlights(result.excerpt),
                )
            )

        return summaries

    def get(self, page_id: str) -> Page:
        params: dict[str, Any] = {"expand": _GET_EXPAND}
        data = self._client.get(f"{_CONTENT_PATH}/{page_id}", params=params)

        resp = _ContentResponse(**data)
        webui = resp.links.get("webui", "")
        parent_id = resp.ancestors[-1].id if resp.ancestors else None

        return Page(
            id=resp.id,
            title=resp.title,
            space_key=resp.space.key,
            space_name=resp.space.name,
            version=resp.version.number,
            created_at=resp.history.created_date,
            updated_at=resp.version.when,
            author=Author(
                display_name=resp.version.by.display_name,
                email=resp.version.by.email,
            ),
            body_html=resp.body.view.value,
            body_storage=resp.body.storage.value,
            url=f"{self._base_url}{webui}" if webui else "",
            parent_id=parent_id,
        )

    # ---------------------------------------------------------------------- #
    # Tree operations (use v2 API — metadata only, no body content)           #
    # ---------------------------------------------------------------------- #

    def get_tree(self, page_id: str, depth: int | None = None) -> PageNode:
        """Return a tree of PageNode starting from *page_id*.

        Only id, title, and url are fetched per node; body content is omitted
        for efficiency.  Use *depth* to limit recursion (None = unlimited).
        """
        root = self._get_page_meta(page_id)
        self._fill_children(root, depth=depth, current_depth=0)
        return root

    def _get_page_meta(self, page_id: str) -> PageNode:
        data = self._client.get(f"{API_V2}/pages/{page_id}")
        meta = _V2PageMeta(**data)
        webui = meta.links.get("webui", "")
        return PageNode(
            id=meta.id,
            title=meta.title,
            url=f"{self._base_url}{webui}" if webui else "",
            updated_at=meta.version.created_at,
        )

    def _get_children_meta(self, page_id: str) -> list[PageNode]:
        """Fetch direct children using v1 API (supports version.when and _links.webui)."""
        children: list[PageNode] = []
        start = 0
        limit = 250

        while True:
            params: dict[str, Any] = {
                "expand": "version",
                "limit": limit,
                "start": start,
            }
            data = self._client.get(
                f"{_CONTENT_PATH}/{page_id}/child/page", params=params
            )
            page = _V1ChildrenResponse(**data)

            for child in page.results:
                webui = child.links.webui
                children.append(
                    PageNode(
                        id=child.id,
                        title=child.title,
                        url=f"{self._base_url}{webui}" if webui else "",
                        updated_at=child.version.when,
                    )
                )

            if page.size < limit:
                break
            start += page.size

        return children

    def _fill_children(
        self, node: PageNode, depth: int | None, current_depth: int
    ) -> None:
        if depth is not None and current_depth >= depth:
            return
        node.children = self._get_children_meta(node.id)
        for child in node.children:
            self._fill_children(child, depth=depth, current_depth=current_depth + 1)
