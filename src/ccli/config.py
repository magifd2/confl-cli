import os
import sys
import tomllib
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, field_validator

from .exceptions import ConfigError


class ConfluenceSettings(BaseModel):
    url: str
    username: str
    api_token: str

    @field_validator("url")
    @classmethod
    def normalize_url(cls, v: str) -> str:
        return v.rstrip("/")


class Defaults(BaseModel):
    format: str = "text"
    limit: int = 25


class Config(BaseModel):
    confluence: ConfluenceSettings
    defaults: Defaults = Defaults()


def get_default_config_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", str(Path.home())))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return base / "ccli" / "config.toml"


def load_from_env() -> Optional[Config]:
    url = os.environ.get("CONFLUENCE_URL")
    username = os.environ.get("CONFLUENCE_USERNAME")
    api_token = os.environ.get("CONFLUENCE_API_TOKEN")

    if url and username and api_token:
        return Config(
            confluence=ConfluenceSettings(url=url, username=username, api_token=api_token)
        )

    # Partial env vars are a configuration mistake — fail loudly
    if any([url, username, api_token]):
        missing = [
            k
            for k, v in [
                ("CONFLUENCE_URL", url),
                ("CONFLUENCE_USERNAME", username),
                ("CONFLUENCE_API_TOKEN", api_token),
            ]
            if not v
        ]
        raise ConfigError(f"Partial environment configuration. Missing: {', '.join(missing)}")

    return None


def load_from_file(path: Path) -> Config:
    if not path.exists():
        raise ConfigError(
            f"Config file not found: {path}\n"
            "Run 'ccli config init' to create it, or set environment variables:\n"
            "  CONFLUENCE_URL, CONFLUENCE_USERNAME, CONFLUENCE_API_TOKEN"
        )
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except Exception as e:
        raise ConfigError(f"Failed to parse config file: {e}") from e

    try:
        return Config(**data)
    except Exception as e:
        raise ConfigError(f"Invalid config file: {e}") from e


def load_config(config_path: Optional[Path] = None) -> Config:
    """Load config from env vars (priority) or config file (fallback)."""
    config = load_from_env()
    if config:
        return config
    path = config_path or get_default_config_path()
    return load_from_file(path)


def save_config(config: Config, path: Optional[Path] = None) -> Path:
    dest = path or get_default_config_path()
    dest.parent.mkdir(parents=True, exist_ok=True)

    content = (
        "[confluence]\n"
        f'url = "{config.confluence.url}"\n'
        f'username = "{config.confluence.username}"\n'
        f'api_token = "{config.confluence.api_token}"\n'
        "\n"
        "[defaults]\n"
        f'format = "{config.defaults.format}"\n'
        f"limit = {config.defaults.limit}\n"
    )
    dest.write_text(content, encoding="utf-8")

    if sys.platform != "win32":
        dest.chmod(0o600)

    return dest
