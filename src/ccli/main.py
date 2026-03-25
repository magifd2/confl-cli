
from importlib.metadata import version as _pkg_version

import typer

from .commands.config import config_app
from .commands.pages import pages_app
from .commands.spaces import spaces_app

app = typer.Typer(help="Atlassian Confluence CLI")
app.add_typer(config_app, name="config")
app.add_typer(spaces_app, name="spaces")
app.add_typer(pages_app, name="pages")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool | None = typer.Option(None, "--version", is_eager=True, help="Show version."),
) -> None:
    if version:
        typer.echo(f"confl-cli {_pkg_version('confl-cli')}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


if __name__ == "__main__":
    app()
