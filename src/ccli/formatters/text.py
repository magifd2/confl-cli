from rich.console import Console
from rich.table import Table
from rich.tree import Tree

from ..client.pages import Page, PageNode, PageSummary
from ..client.spaces import Space
from ..converters.html_to_text import html_to_markdown


def _console(color: bool) -> Console:
    return Console(highlight=False, no_color=not color)


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
        last_mod = s.last_modified[:10] if s.last_modified else ""
        table.add_row(s.id, s.space_key, s.title, last_mod)

    console.print(table)


def print_page_tree(node: PageNode, *, color: bool = True) -> None:
    console = _console(color)
    label = (
        f"[bold]{node.title}[/bold] [dim]({node.id})[/dim]"
        if color
        else f"{node.title} ({node.id})"
    )
    tree = Tree(label)
    _add_to_tree(tree, node.children, color=color)
    console.print(tree)


def _add_to_tree(parent: Tree, children: list[PageNode], *, color: bool) -> None:
    for child in children:
        label = (
            f"[bold]{child.title}[/bold] [dim]({child.id})[/dim]"
            if color
            else f"{child.title} ({child.id})"
        )
        branch = parent.add(label)
        _add_to_tree(branch, child.children, color=color)


def print_page(page: Page, *, color: bool = True) -> None:
    console = _console(color)

    title_style = "bold" if color else ""
    meta_style = "dim" if color else ""

    console.print(f"# {page.title}", style=title_style)
    console.print(
        f"Space: {page.space_key}  |  Version: {page.version}  |  "
        f"Updated: {page.updated_at[:10]}  |  Author: {page.author.display_name}",
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
