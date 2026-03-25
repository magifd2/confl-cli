from typer.testing import CliRunner

from ccli.main import app

runner = CliRunner()


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Atlassian Confluence CLI" in result.output


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "ccli" in result.output
