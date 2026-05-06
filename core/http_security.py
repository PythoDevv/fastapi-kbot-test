from urllib.parse import unquote

from fastapi import Request
from fastapi.responses import PlainTextResponse, Response

SUSPICIOUS_PATH_PARTS = (
    "/.env",
    "/wp-",
    "/wordpress",
    "/xmlrpc.php",
    "/phpinfo.php",
    "/phpmyadmin",
    "/pma",
    "/adminer",
    "/manager/html",
    "/hudson",
    "/jenkins",
    "/cgi-bin/",
    "/boaform/",
    "/vendor/phpunit/",
    "/server-status",
)

SUSPICIOUS_SUFFIXES = (
    ".php",
    ".asp",
    ".aspx",
    ".jsp",
    ".cgi",
    ".env",
)


def _normalize_path(path: str) -> str:
    path = unquote(path or "/").strip()
    if not path.startswith("/"):
        path = f"/{path}"
    while "//" in path:
        path = path.replace("//", "/")
    return path.lower()


def is_suspicious_probe(path: str) -> bool:
    normalized = _normalize_path(path)
    if any(part in normalized for part in SUSPICIOUS_PATH_PARTS):
        return True
    return normalized.endswith(SUSPICIOUS_SUFFIXES)


async def block_scanner_probes(request: Request, call_next) -> Response:
    if is_suspicious_probe(request.url.path):
        return PlainTextResponse("Not Found", status_code=404)
    return await call_next(request)
