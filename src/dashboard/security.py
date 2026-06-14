"""Browser-origin checks for the local dashboard's privileged endpoints."""
from urllib.parse import urlsplit

from fastapi import WebSocket

from . import config


def browser_request_is_cross_origin(headers) -> bool:
    """Reject browser traffic that did not originate from this loopback app."""
    if headers.get("sec-fetch-site", "").lower() == "cross-site":
        return True

    origin = headers.get("origin")
    if not origin:
        return False  # Preserve CLI and other non-browser local clients.

    try:
        parsed = urlsplit(origin)
        port = parsed.port
    except ValueError:
        return True

    allowed_hosts = {config.HOST.lower(), "localhost"}
    return not (
        parsed.scheme == "http"
        and parsed.hostname
        and parsed.hostname.lower() in allowed_hosts
        and port == config.PORT
        and not parsed.username
        and not parsed.password
        and parsed.path in ("", "/")
        and not parsed.query
        and not parsed.fragment
    )


async def authorize_websocket(ws: WebSocket) -> bool:
    """Enforce browser origin and the optional explicit session token."""
    if browser_request_is_cross_origin(ws.headers):
        await ws.close(code=4403)
        return False

    token = config.auth_token()
    if token and ws.query_params.get("token") != token:
        await ws.close(code=4401)
        return False
    return True
