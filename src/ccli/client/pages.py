from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from ..auth import API_V1
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
    created_at: str = ""
    updated_at: str = ""
    attachments: list[Attachment] = []  # populated when --attachments is used
    children: list[PageNode] = []


PageNode.model_rebuild()


# --------------------------------------------------------------------------- #
# Internal Pydantic models for v1 API (tree metadata)                          #
# --------------------------------------------------------------------------- #


class _V1ChildVersion(BaseModel):
    when: str = ""


class _V1ChildHistory(BaseModel):
    created_date: str = Field("", alias="createdDate")

    model_config = {"populate_by_name": True}


class _V1ChildLinks(BaseModel):
    webui: str = ""

    model_config = {"populate_by_name": True}


class _V1PageMeta(BaseModel):
    """v1 page response with version and history (no body content)."""

    id: str
    title: str
    version: _V1ChildVersion = Field(default_factory=_V1ChildVersion)
    history: _V1ChildHistory = Field(default_factory=_V1ChildHistory)
    links: _V1ChildLinks = Field(default_factory=_V1ChildLinks, alias="_links")

    model_config = {"populate_by_name": True}


class _V1DescAncestor(BaseModel):
    id: str


class _V1DescPage(_V1PageMeta):
    """Descendant page — same as _V1PageMeta plus an ancestors chain."""

    ancestors: list[_V1DescAncestor] = []


class _V1DescendantsResponse(BaseModel):
    results: list[_V1DescPage]
    size: int = 0
    limit: int = 25


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
    # Tree operations (v1 API — batch descendant fetch, O(N/250) API calls) #
    # ---------------------------------------------------------------------- #

    def get_tree(self, page_id: str, depth: int | None = None) -> PageNode:
        """Return a tree of PageNode starting from *page_id*.

        Fetches all descendants in one paginated request to
        /content/{id}/descendant/page and reconstructs the tree client-side.
        API calls: 1 (root) + ceil(descendants / 250) — instead of N+1.
        """
        root = self._get_page_meta(page_id)
        if depth == 0:
            return root

        descendants = self._get_all_descendants(page_id)
        if not descendants:
            return root

        # Sort shallowest-first so parents are always added before their children.
        descendants.sort(key=lambda d: len(d.ancestors))

        # Determine how many global ancestors the root page has (its depth in
        # the Confluence hierarchy) by looking at the first descendant's chain.
        first_ancestors = descendants[0].ancestors
        root_global_depth = next(
            (i for i, a in enumerate(first_ancestors) if a.id == page_id), 0
        )

        nodes: dict[str, PageNode] = {page_id: root}
        for desc in descendants:
            depth_from_root = len(desc.ancestors) - root_global_depth
            if depth is not None and depth_from_root > depth:
                continue
            node = PageNode(
                id=desc.id,
                title=desc.title,
                url=f"{self._base_url}{desc.links.webui}" if desc.links.webui else "",
                created_at=desc.history.created_date,
                updated_at=desc.version.when,
            )
            nodes[desc.id] = node
            parent_id = desc.ancestors[-1].id if desc.ancestors else page_id
            parent = nodes.get(parent_id)
            if parent is not None:
                parent.children.append(node)

        return root

    def _get_page_meta(self, page_id: str) -> PageNode:
        data = self._client.get(
            f"{_CONTENT_PATH}/{page_id}", params={"expand": "version,history"}
        )
        meta = _V1PageMeta(**data)
        return PageNode(
            id=meta.id,
            title=meta.title,
            url=f"{self._base_url}{meta.links.webui}" if meta.links.webui else "",
            created_at=meta.history.created_date,
            updated_at=meta.version.when,
        )

    def _get_all_descendants(self, page_id: str) -> list[_V1DescPage]:
        """Fetch all descendant pages in one paginated request."""
        descendants: list[_V1DescPage] = []
        start = 0
        limit = 250

        while True:
            params: dict[str, Any] = {
                "expand": "version,history,ancestors",
                "limit": limit,
                "start": start,
            }
            data = self._client.get(
                f"{_CONTENT_PATH}/{page_id}/descendant/page", params=params
            )
            resp = _V1DescendantsResponse(**data)
            descendants.extend(resp.results)

            if resp.size < limit:
                break
            start += resp.size

        return descendants
