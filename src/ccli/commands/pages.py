import json as _json
from enum import StrEnum
from pathlib import Path

import httpx
import typer

from ..auth import build_client
from ..client.attachments import AttachmentsClient
from ..client.base import ConfluenceClient
from ..client.pages import Page, PageNode, PagesClient
from ..config import Config, load_config
from ..converters.html_to_text import html_to_markdown
from ..converters.link_rewriter import build_attachment_map, build_page_map
from ..converters.link_rewriter import rewrite_html as _rewrite_html
from ..converters.link_rewriter import rewrite_markdown as _rewrite_markdown
from ..downloader import download_file, safe_attachment_dest
from ..exceptions import CCLIError, ConfigError
from ..formatters.base import use_color
from ..formatters.html_fmt import print_html
from ..formatters.json_fmt import print_json
from ..formatters.text import print_page, print_page_summaries, print_page_tree

pages_app = typer.Typer(help="Page operations.")


class OutputFormat(StrEnum):
    text = "text"
    json = "json"
    html = "html"
    storage = "storage"  # Confluence Storage Format (XHTML-like source)


class TreeOutputFormat(StrEnum):
    text = "text"
    json = "json"


def _setup() -> tuple[Config, httpx.Client, ConfluenceClient]:
    try:
        config = load_config()
    except ConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=exc.exit_code) from None
    http_client = build_client(config)
    return config, http_client, ConfluenceClient(http_client)


@pages_app.command("search")
def pages_search(
    query: str = typer.Argument(help="Search query (full-text search via CQL)."),
    space: str | None = typer.Option(None, "--space", "-s", help="Filter by space key."),
    limit: int = typer.Option(25, "--limit", "-n", help="Maximum number of results."),
    format: OutputFormat = typer.Option(OutputFormat.text, "--format", "-f"),
) -> None:
    """Search pages by full-text query."""
    if not query.strip():
        typer.echo("Error: search query must not be empty.", err=True)
        raise typer.Exit(code=1)
    config, _, cc = _setup()
    try:
        summaries = PagesClient(cc, config.confluence.url).search(
            query=query, space_key=space, limit=limit
        )
    except CCLIError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=exc.exit_code) from None

    if format == OutputFormat.json:
        print_json([s.model_dump() for s in summaries])
    else:
        print_page_summaries(summaries, color=use_color())


@pages_app.command("get")
def pages_get(
    page_id: str = typer.Argument(help="Page ID."),
    format: OutputFormat = typer.Option(OutputFormat.text, "--format", "-f"),
    with_attachments: bool = typer.Option(False, "--attachments", help="Fetch attachment metadata."),  # noqa: E501
    output_dir: Path | None = typer.Option(
        None, "--output-dir", help="Download attachments to this directory."
    ),
    base_path: Path | None = typer.Option(
        None,
        "--base-path",
        help=(
            "Root directory used for link rewriting. "
            "Confluence page links are rewritten to <base-path>/<id>/page.<ext>; "
            "attachment links to their downloaded location. "
            "Has no effect without --format text or html."
        ),
    ),
    no_rewrite_links: bool = typer.Option(
        False, "--no-rewrite-links", help="Disable automatic link rewriting."
    ),
) -> None:
    """Get a single page by ID."""
    config, http_client, cc = _setup()
    try:
        page = PagesClient(cc, config.confluence.url).get(page_id)
    except CCLIError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=exc.exit_code) from None

    if with_attachments or output_dir:
        try:
            attachments = AttachmentsClient(cc).list(page_id)
        except CCLIError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=exc.exit_code) from None

        if output_dir:
            for att in attachments:
                try:
                    dest = safe_attachment_dest(output_dir, page_id, att.filename)
                    download_file(http_client, att.download_url, dest)
                    att.saved_path = str(dest)
                except Exception as exc:  # noqa: BLE001
                    typer.echo(f"Warning: could not download {att.filename}: {exc}", err=True)

        page.attachments = attachments

    if format == OutputFormat.json:
        print_json(page.model_dump())
    elif format == OutputFormat.storage:
        print(page.body_storage)
    elif not no_rewrite_links and base_path is not None and format in (
        OutputFormat.text, OutputFormat.html
    ):
        page_filename = _PAGE_FORMAT_EXT[format]
        current_file = base_path / page_id / page_filename
        att_map = build_attachment_map(page.attachments)
        if format == OutputFormat.html:
            print_html(
                _rewrite_html(
                    page.body_html, current_file, {}, att_map,
                    base_path=base_path, page_filename=page_filename,
                    base_url=config.confluence.url,
                )
            )
        else:
            md = html_to_markdown(page.body_html)
            print(
                _rewrite_markdown(
                    md, current_file, {}, att_map,
                    base_path=base_path, page_filename=page_filename,
                    base_url=config.confluence.url,
                )
            )
    elif format == OutputFormat.html:
        print_html(page.body_html)
    else:
        print_page(page, color=use_color())


_PAGE_FORMAT_EXT: dict[OutputFormat, str] = {
    OutputFormat.text: "page.md",
    OutputFormat.html: "page.html",
    OutputFormat.json: "page.json",
    OutputFormat.storage: "page.xml",
}


def _save_page_content(
    page: Page,
    dest_dir: Path,
    page_format: OutputFormat,
    page_map: dict[str, Path] | None = None,
    attachment_map: dict[str, Path] | None = None,
    base_url: str = "",
) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / _PAGE_FORMAT_EXT[page_format]
    pm = page_map or {}
    am = attachment_map or {}
    if page_format == OutputFormat.text:
        content = html_to_markdown(page.body_html)
        if pm or am:
            content = _rewrite_markdown(
                content, dest, pm, am,
                page_filename=_PAGE_FORMAT_EXT[page_format], base_url=base_url,
            )
        dest.write_text(content, encoding="utf-8")
    elif page_format == OutputFormat.html:
        content = page.body_html
        if pm or am:
            content = _rewrite_html(
                content, dest, pm, am,
                page_filename=_PAGE_FORMAT_EXT[page_format], base_url=base_url,
            )
        dest.write_text(content, encoding="utf-8")
    elif page_format == OutputFormat.json:
        dest.write_text(
            _json.dumps(page.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
    else:  # storage
        dest.write_text(page.body_storage, encoding="utf-8")


@pages_app.command("tree")
def pages_tree(
    page_id: str = typer.Argument(help="Root page ID."),
    depth: int | None = typer.Option(
        None, "--depth", "-d", help="Max recursion depth (default: unlimited)."
    ),
    format: TreeOutputFormat = typer.Option(TreeOutputFormat.text, "--format", "-f"),
    with_attachments: bool = typer.Option(False, "--attachments", help="Fetch attachment metadata."),  # noqa: E501
    output_dir: Path | None = typer.Option(
        None, "--output-dir", help="Download attachments to this directory."
    ),
    page_format: OutputFormat | None = typer.Option(
        None, "--page-format", help="Save each page body in this format to --output-dir."
    ),
    no_rewrite_links: bool = typer.Option(
        False, "--no-rewrite-links", help="Disable automatic link rewriting."
    ),
) -> None:
    """Get a page and all its descendants as a tree."""
    if page_format is not None and output_dir is None:
        typer.echo("Error: --page-format requires --output-dir.", err=True)
        raise typer.Exit(code=6)

    config, http_client, cc = _setup()
    pc = PagesClient(cc, config.confluence.url)
    try:
        tree = pc.get_tree(page_id, depth=depth)
    except CCLIError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=exc.exit_code) from None

    # Build page_map upfront so every node can resolve cross-page links.
    page_map: dict[str, Path] = {}
    if (
        not no_rewrite_links
        and output_dir is not None
        and page_format in (OutputFormat.text, OutputFormat.html)
    ):
        page_map = build_page_map(tree, output_dir, _PAGE_FORMAT_EXT[page_format])

    if with_attachments or output_dir:
        _populate_tree_attachments(
            tree, AttachmentsClient(cc), http_client, output_dir,
            pages_client=pc if page_format is not None else None,
            page_format=page_format,
            page_map=page_map,
            base_url=config.confluence.url,
        )

    if format == TreeOutputFormat.json:
        print_json(tree.model_dump())
    else:
        print_page_tree(tree, color=use_color())


def _populate_tree_attachments(
    node: PageNode,
    attach_client: AttachmentsClient,
    http_client: httpx.Client,
    output_dir: Path | None,
    pages_client: PagesClient | None = None,
    page_format: OutputFormat | None = None,
    page_map: dict[str, Path] | None = None,
    base_url: str = "",
) -> None:
    """Recursively fetch (and optionally download) attachments and page content for every node."""
    try:
        attachments = attach_client.list(node.id)
    except CCLIError as exc:
        typer.echo(f"Warning: attachments for {node.id} unavailable: {exc}", err=True)
        attachments = []

    if output_dir:
        for att in attachments:
            try:
                dest = safe_attachment_dest(output_dir, node.id, att.filename)
                download_file(http_client, att.download_url, dest)
                att.saved_path = str(dest)
            except Exception as exc:  # noqa: BLE001
                typer.echo(f"Warning: could not download {att.filename}: {exc}", err=True)

        if pages_client is not None and page_format is not None:
            try:
                page = pages_client.get(node.id)
                att_map = build_attachment_map(attachments) if page_map is not None else {}
                _save_page_content(
                    page, output_dir / node.id, page_format,
                    page_map=page_map, attachment_map=att_map, base_url=base_url,
                )
            except CCLIError as exc:
                typer.echo(f"Warning: page content for {node.id} unavailable: {exc}", err=True)
            except Exception as exc:  # noqa: BLE001
                typer.echo(f"Warning: could not save page {node.id}: {exc}", err=True)

    node.attachments = attachments

    for child in node.children:
        _populate_tree_attachments(
            child, attach_client, http_client, output_dir,
            pages_client, page_format, page_map, base_url,
        )
