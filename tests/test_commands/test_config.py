from pathlib import Path

import pytest
from typer.testing import CliRunner

from ccli.main import app

runner = CliRunner()

ENV_VARS = {
    "CONFLUENCE_URL": "https://example.atlassian.net",
    "CONFLUENCE_USERNAME": "user@example.com",
    "CONFLUENCE_API_TOKEN": "supersecrettoken",
}


@pytest.fixture(autouse=True)
def clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ENV_VARS:
        monkeypatch.delenv(key, raising=False)


class TestConfigShow:
    def test_shows_config_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        for k, v in ENV_VARS.items():
            monkeypatch.setenv(k, v)
        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "https://example.atlassian.net" in result.output
        assert "user@example.com" in result.output
        # Token must be masked
        assert "supersecrettoken" not in result.output
        assert "supe" in result.output  # first 4 chars visible

    def test_shows_config_from_file(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            "[confluence]\n"
            'url = "https://example.atlassian.net"\n'
            'username = "user@example.com"\n'
            'api_token = "mytoken"\n'
        )
        result = runner.invoke(app, ["config", "show", "--config", str(config_file)])
        assert result.exit_code == 0
        assert "https://example.atlassian.net" in result.output

    def test_exits_with_code_6_when_no_config(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app, ["config", "show", "--config", str(tmp_path / "nonexistent.toml")]
        )
        assert result.exit_code == 6


class TestConfigInit:
    def test_creates_config_file(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.toml"
        user_input = "\n".join([
            "https://example.atlassian.net",
            "user@example.com",
            "my-api-token",
        ])
        result = runner.invoke(
            app,
            ["config", "init", "--config", str(config_file)],
            input=user_input,
        )
        assert result.exit_code == 0
        assert config_file.exists()
        content = config_file.read_text()
        assert 'url = "https://example.atlassian.net"' in content
        assert 'username = "user@example.com"' in content
        assert 'api_token = "my-api-token"' in content

    def test_output_includes_saved_path(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.toml"
        user_input = "\n".join([
            "https://example.atlassian.net",
            "user@example.com",
            "token",
        ])
        result = runner.invoke(
            app,
            ["config", "init", "--config", str(config_file)],
            input=user_input,
        )
        assert result.exit_code == 0
        assert str(config_file) in result.output
