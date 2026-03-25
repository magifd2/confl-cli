from typing import Optional

import typer

app = typer.Typer(help="Atlassian Confluence CLI")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(None, "--version", is_eager=True, help="Show version."),
) -> None:
    if version:
        typer.echo("ccli 0.1.0")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


if __name__ == "__main__":
    app()
