import ipaddress
import socket
from urllib.parse import urlparse


class AppError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code, self.message = status_code, message


def validate_public_url(url: str) -> str:
    """Allow only http(s) URLs whose host resolves exclusively to public IPs (SSRF guard)."""
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise AppError(400, "Only http(s) URLs with a hostname are allowed")
    try:
        infos = socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == "https" else 80))
    except socket.gaierror:
        raise AppError(502, f"Could not resolve host '{p.hostname}'")
    for info in infos:
        # shortcut: DNS is resolved here and again by httpx (rebinding window); pin the IP to close it
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise AppError(400, "URL resolves to a private or internal address")
    return url
