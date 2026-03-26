from enum import StrEnum
from pathlib import Path

import httpx
import typer

from ..auth import build_client
from ..client.base import ConfluenceClient
from ..client.spaces import SpacesClient
from ..config import Config, load_config
from ..exceptions import CCLIError, ConfigError
from ..formatters.base import use_color
from ..formatters.json_fmt import print_json
from ..formatters.text import print_spaces
from .pages import OutputFormat as PageFormat
from .pages import TreeOutputFormat, _execute_tree

spaces_app = typer.Typer(help="Space operations.")


class OutputFormat(StrEnum):
    text = "text"
    json = "json"


class SpaceType(StrEnum):
    global_ = "global"
    personal = "personal"


def _setup_full() -> tuple[Config, httpx.Client, ConfluenceClient, SpacesClient]:
    try:
        config = load_config()
    except ConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=exc.exit_code) from None
    http_client = build_client(config)
    cc = ConfluenceClient(http_client)
    return config, http_client, cc, SpacesClient(cc)


def _make_spaces_client() -> SpacesClient:
    _, _, cc, sc = _setup_full()
    return sc


@spaces_app.command("list")
def spaces_list(
    limit: int = typer.Option(25, "--limit", "-n", help="Maximum number of results."),
    space_type: SpaceType | None = typer.Option(None, "--type", help="Filter by space type."),
    format: OutputFormat = typer.Option(OutputFormat.text, "--format", "-f"),
) -> None:
    """List spaces."""
    client = _make_spaces_client()
    try:
        spaces = client.list(
            limit=limit,
            space_type=space_type.value if space_type else None,
        )
    except CCLIError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=exc.exit_code) from None

    if format == OutputFormat.json:
        print_json([s.model_dump(by_alias=False) for s in spaces])
    else:
        print_spaces(spaces, color=use_color())


@spaces_app.command("search")
def spaces_search(
    query: str = typer.Argument(help="Search query (matches space name or key)."),
    limit: int = typer.Option(25, "--limit", "-n", help="Maximum number of results."),
    format: OutputFormat = typer.Option(OutputFormat.text, "--format", "-f"),
) -> None:
    """Search spaces by name or key."""
    client = _make_spaces_client()
    try:
        spaces = client.search(query=query, limit=limit)
    except CCLIError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=exc.exit_code) from None

    if format == OutputFormat.json:
        print_json([s.model_dump(by_alias=False) for s in spaces])
    else:
        print_spaces(spaces, color=use_color())


@spaces_app.command("export")
def spaces_export(
    space_key: str = typer.Argument(help="Space key (e.g. DEV)."),
    depth: int | None = typer.Option(
        None, "--depth", "-d", help="Max recursion depth (default: unlimited)."
    ),
    format: TreeOutputFormat = typer.Option(TreeOutputFormat.text, "--format", "-f"),
    with_attachments: bool = typer.Option(False, "--attachments", help="Fetch attachment metadata."),  # noqa: E501
    output_dir: Path | None = typer.Option(
        None, "--output-dir", help="Download attachments to this directory."
    ),
    page_format: PageFormat | None = typer.Option(
        None, "--page-format", help="Save each page body in this format to --output-dir."
    ),
    no_rewrite_links: bool = typer.Option(
        False, "--no-rewrite-links", help="Disable automatic link rewriting."
    ),
) -> None:
    """Export all pages in a space as a tree, starting from the space home page."""
    if page_format is not None and output_dir is None:
        typer.echo("Error: --page-format requires --output-dir.", err=True)
        raise typer.Exit(code=6)

    config, http_client, cc, sc = _setup_full()
    try:
        homepage_id = sc.get_homepage_id(space_key)
    except CCLIError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=exc.exit_code) from None

    _execute_tree(
        homepage_id, config, http_client, cc,
        depth=depth, format=format, with_attachments=with_attachments,
        output_dir=output_dir, page_format=page_format, no_rewrite_links=no_rewrite_links,
    )
