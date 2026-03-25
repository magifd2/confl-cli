import httpx

from .config import Config


def build_client(config: Config) -> httpx.Client:
    """Build an authenticated httpx client for Confluence REST API v2."""
    return httpx.Client(
        base_url=f"{config.confluence.url}/wiki/api/v2",
        auth=(config.confluence.username, config.confluence.api_token),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )
