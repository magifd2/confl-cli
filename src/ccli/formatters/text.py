from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from ..client.pages import Page, PageNode, PageSummary
from ..client.spaces import Space
from ..converters.html_to_text import html_to_markdown


def _console(color: bool) -> Console:
    return Console(highlight=False, no_color=not color)


def _local_dt(ts: str) -> str:
    """Convert a UTC ISO 8601 timestamp to local datetime string (YYYY-MM-DD HH:MM).

    Falls back to the first 10 characters (date only) if parsing fails.
    """
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%Y-%m-%d %H:%M")
    except (ValueError, OSError):
        return ts[:10]


def print_spaces(spaces: list[Space], *, color: bool = True) -> None:
    console = _console(color)
    if not spaces:
        console.print("No spaces found.")
        return

    table = Table(show_header=True, header_style="bold" if color else "", box=None, pad_edge=False)
    table.add_column("KEY", min_width=8)
    table.add_column("NAME", min_width=24)
    table.add_column("TYPE", min_width=8)
    table.add_column("STATUS")

    for space in spaces:
        table.add_row(space.key, space.name, space.type, space.status)

    console.print(table)


def print_page_summaries(summaries: list[PageSummary], *, color: bool = True) -> None:
    console = _console(color)
    if not summaries:
        console.print("No pages found.")
        return

    table = Table(show_header=True, header_style="bold" if color else "", box=None, pad_edge=False)
    table.add_column("ID", min_width=10)
    table.add_column("SPACE", min_width=8)
    table.add_column("TITLE", min_width=28)
    table.add_column("LAST MODIFIED")

    for s in summaries:
        table.add_row(s.id, s.space_key, s.title, _local_dt(s.last_modified))

    console.print(table)


def _node_label(node: PageNode, *, color: bool) -> str:
    date = f"  {_local_dt(node.updated_at)}" if node.updated_at else ""
    if color:
        return f"[bold]{node.title}[/bold] [dim]({node.id}){date}[/dim]"
    return f"{node.title} ({node.id}){date}"


def print_page_tree(node: PageNode, *, color: bool = True) -> None:
    console = _console(color)
    tree = Tree(_node_label(node, color=color))
    _add_to_tree(tree, node.children, color=color)
    console.print(tree)


def _add_to_tree(parent: Tree, children: list[PageNode], *, color: bool) -> None:
    for child in children:
        branch = parent.add(_node_label(child, color=color))
        _add_to_tree(branch, child.children, color=color)


def print_page(page: Page, *, color: bool = True) -> None:
    console = _console(color)

    title_style = "bold" if color else ""
    meta_style = "dim" if color else ""

    console.print(f"# {page.title}", style=title_style)
    console.print(
        f"Space: {page.space_key}  |  Version: {page.version}  |  "
        f"Updated: {_local_dt(page.updated_at)}  |  Author: {page.author.display_name}",
        style=meta_style,
    )
    if page.url:
        console.print(page.url, style=meta_style)
    console.print()

    markdown = html_to_markdown(page.body_html)
    if markdown:
        console.print(markdown)
    else:
        console.print("(no content)")
