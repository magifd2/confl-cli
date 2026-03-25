import stat
import sys
from pathlib import Path

import pytest

from ccli.config import (
    Config,
    ConfluenceSettings,
    Defaults,
    load_config,
    load_from_env,
    load_from_file,
    save_config,
)
from ccli.exceptions import ConfigError

ENV_VARS = {
    "CONFLUENCE_URL": "https://example.atlassian.net",
    "CONFLUENCE_USERNAME": "user@example.com",
    "CONFLUENCE_API_TOKEN": "token-abc123",
}

TOML_CONTENT = """\
[confluence]
url = "https://example.atlassian.net"
username = "user@example.com"
api_token = "token-abc123"
"""


@pytest.fixture(autouse=True)
def clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure Confluence env vars are not set unless explicitly patched."""
    for key in ENV_VARS:
        monkeypatch.delenv(key, raising=False)


class TestLoadFromEnv:
    def test_all_vars_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for k, v in ENV_VARS.items():
            monkeypatch.setenv(k, v)
        config = load_from_env()
        assert config is not None
        assert config.confluence.url == "https://example.atlassian.net"
        assert config.confluence.username == "user@example.com"
        assert config.confluence.api_token == "token-abc123"

    def test_no_vars_returns_none(self) -> None:
        assert load_from_env() is None

    def test_partial_vars_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CONFLUENCE_URL", "https://example.atlassian.net")
        with pytest.raises(ConfigError, match="Partial environment configuration"):
            load_from_env()

    def test_url_trailing_slash_stripped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CONFLUENCE_URL", "https://example.atlassian.net/")
        monkeypatch.setenv("CONFLUENCE_USERNAME", "user@example.com")
        monkeypatch.setenv("CONFLUENCE_API_TOKEN", "token")
        config = load_from_env()
        assert config is not None
        assert config.confluence.url == "https://example.atlassian.net"


class TestLoadFromFile:
    def test_happy_path(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.toml"
        config_file.write_text(TOML_CONTENT)
        config = load_from_file(config_file)
        assert config.confluence.url == "https://example.atlassian.net"
        assert config.defaults.limit == 25

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="Config file not found"):
            load_from_file(tmp_path / "nonexistent.toml")

    def test_invalid_toml_raises(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.toml"
        config_file.write_text("not valid toml ][")
        with pytest.raises(ConfigError, match="Failed to parse config file"):
            load_from_file(config_file)

    def test_missing_required_field_raises(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.toml"
        config_file.write_text("[confluence]\nurl = 'https://example.com'\n")
        with pytest.raises(ConfigError, match="Invalid config file"):
            load_from_file(config_file)

    def test_custom_defaults_respected(self, tmp_path: Path) -> None:
        content = TOML_CONTENT + '\n[defaults]\nformat = "json"\nlimit = 50\n'
        config_file = tmp_path / "config.toml"
        config_file.write_text(content)
        config = load_from_file(config_file)
        assert config.defaults.format == "json"
        assert config.defaults.limit == 50


class TestLoadConfig:
    def test_env_vars_take_priority_over_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        config_file = tmp_path / "config.toml"
        config_file.write_text(TOML_CONTENT.replace("user@example.com", "other@example.com"))

        for k, v in ENV_VARS.items():
            monkeypatch.setenv(k, v)

        config = load_config(config_file)
        assert config.confluence.username == "user@example.com"  # from env, not file

    def test_falls_back_to_file(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.toml"
        config_file.write_text(TOML_CONTENT)
        config = load_config(config_file)
        assert config.confluence.url == "https://example.atlassian.net"


class TestSaveConfig:
    def test_creates_file_with_correct_content(self, tmp_path: Path) -> None:
        config = Config(
            confluence=ConfluenceSettings(
                url="https://example.atlassian.net",
                username="user@example.com",
                api_token="secret",
            )
        )
        dest = tmp_path / "ccli" / "config.toml"
        saved = save_config(config, dest)
        assert saved == dest
        text = dest.read_text()
        assert 'url = "https://example.atlassian.net"' in text
        assert 'api_token = "secret"' in text

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        config = Config(
            confluence=ConfluenceSettings(
                url="https://example.atlassian.net",
                username="u@example.com",
                api_token="t",
            )
        )
        dest = tmp_path / "a" / "b" / "c" / "config.toml"
        save_config(config, dest)
        assert dest.exists()

    @pytest.mark.skipif(sys.platform == "win32", reason="chmod not applicable on Windows")
    def test_file_permissions_600(self, tmp_path: Path) -> None:
        config = Config(
            confluence=ConfluenceSettings(
                url="https://example.atlassian.net",
                username="u@example.com",
                api_token="t",
            )
        )
        dest = tmp_path / "config.toml"
        save_config(config, dest)
        mode = stat.S_IMODE(dest.stat().st_mode)
        assert mode == 0o600


class TestConfluenceSettings:
    def test_url_trailing_slash_stripped(self) -> None:
        s = ConfluenceSettings(
            url="https://example.atlassian.net/",
            username="u",
            api_token="t",
        )
        assert s.url == "https://example.atlassian.net"

    def test_defaults(self) -> None:
        d = Defaults()
        assert d.format == "text"
        assert d.limit == 25
