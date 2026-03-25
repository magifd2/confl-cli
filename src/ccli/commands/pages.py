from enum import Enum
from typing import Optional

import typer

from ..auth import build_client
from ..client.base import ConfluenceClient
from ..client.pages import PagesClient
from ..config import load_config
from ..exceptions import CCLIError, ConfigError
from ..formatters.base import use_color
from ..formatters.html_fmt import print_html
from ..formatters.json_fmt import print_json
from ..formatters.text import print_page, print_page_summaries, print_page_tree

pages_app = typer.Typer(help="Page operations.")


class OutputFormat(str, Enum):
    text = "text"
    json = "json"
    html = "html"
    storage = "storage"  # Confluence Storage Format (XHTML-like source)


class TreeOutputFormat(str, Enum):
    text = "text"
    json = "json"


def _make_pages_client() -> PagesClient:
    try:
        config = load_config()
    except ConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=exc.exit_code)
    return PagesClient(ConfluenceClient(build_client(config)), config.confluence.url)


@pages_app.command("search")
def pages_search(
    query: str = typer.Argument(help="Search query (full-text search via CQL)."),
    space: Optional[str] = typer.Option(None, "--space", "-s", help="Filter by space key."),
    limit: int = typer.Option(25, "--limit", "-n", help="Maximum number of results."),
    format: OutputFormat = typer.Option(OutputFormat.text, "--format", "-f"),
) -> None:
    """Search pages by full-text query."""
    client = _make_pages_client()
    try:
        summaries = client.search(query=query, space_key=space, limit=limit)
    except CCLIError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=exc.exit_code)

    if format == OutputFormat.json:
        print_json([s.model_dump() for s in summaries])
    else:
        print_page_summaries(summaries, color=use_color())


@pages_app.command("get")
def pages_get(
    page_id: str = typer.Argument(help="Page ID."),
    format: OutputFormat = typer.Option(OutputFormat.text, "--format", "-f"),
) -> None:
    """Get a single page by ID."""
    client = _make_pages_client()
    try:
        page = client.get(page_id)
    except CCLIError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=exc.exit_code)

    if format == OutputFormat.json:
        print_json(page.model_dump())
    elif format == OutputFormat.html:
        print_html(page.body_html)
    elif format == OutputFormat.storage:
        print(page.body_storage)
    else:
        print_page(page, color=use_color())


@pages_app.command("tree")
def pages_tree(
    page_id: str = typer.Argument(help="Root page ID."),
    depth: Optional[int] = typer.Option(None, "--depth", "-d", help="Max recursion depth (default: unlimited)."),
    format: TreeOutputFormat = typer.Option(TreeOutputFormat.text, "--format", "-f"),
) -> None:
    """Get a page and all its descendants as a tree."""
    client = _make_pages_client()
    try:
        tree = client.get_tree(page_id, depth=depth)
    except CCLIError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=exc.exit_code)

    if format == TreeOutputFormat.json:
        print_json(tree.model_dump())
    else:
        print_page_tree(tree, color=use_color())
