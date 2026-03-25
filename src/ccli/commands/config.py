import sys
from pathlib import Path
from typing import Optional

import typer

from ..config import Config, ConfluenceSettings, get_default_config_path, load_config, save_config
from ..exceptions import ConfigError

config_app = typer.Typer(help="Manage ccli configuration.")


@config_app.command("init")
def config_init(
    config_path: Optional[Path] = typer.Option(None, "--config", help="Config file path."),
) -> None:
    """Interactively initialize configuration."""
    dest = config_path or get_default_config_path()

    typer.echo("Setting up ccli configuration.")
    typer.echo(f"Config will be saved to: {dest}\n")

    url = typer.prompt("Confluence URL (e.g. https://your-domain.atlassian.net)")
    username = typer.prompt("Username (email address)")
    api_token = typer.prompt("API Token", hide_input=True)

    config = Config(
        confluence=ConfluenceSettings(url=url, username=username, api_token=api_token)
    )

    try:
        saved_path = save_config(config, dest)
    except Exception as e:
        typer.echo(f"Error saving config: {e}", err=True)
        raise typer.Exit(code=6)

    typer.echo(f"\nConfiguration saved to: {saved_path}")
    if sys.platform != "win32":
        typer.echo("File permissions set to 600 (owner read/write only).")


@config_app.command("show")
def config_show(
    config_path: Optional[Path] = typer.Option(None, "--config", help="Config file path."),
) -> None:
    """Show current configuration (API token is masked)."""
    try:
        config = load_config(config_path)
    except ConfigError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=e.exit_code)

    token = config.confluence.api_token
    masked = token[:4] + "*" * max(len(token) - 4, 4) if len(token) > 4 else "****"

    typer.echo(f"URL:       {config.confluence.url}")
    typer.echo(f"Username:  {config.confluence.username}")
    typer.echo(f"API Token: {masked}")
    typer.echo(f"Format:    {config.defaults.format}")
    typer.echo(f"Limit:     {config.defaults.limit}")
