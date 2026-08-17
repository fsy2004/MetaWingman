"""Network guards for bounded public HTTPS retrieval."""

from __future__ import annotations

import ipaddress
import socket
import urllib.request
from urllib.parse import urlsplit


class PublicNetworkError(ValueError):
    """Raised when a URL could reach a non-public network destination."""


def validate_public_https_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme.casefold() != "https" or not parsed.hostname:
        raise PublicNetworkError("retrieval URL must use HTTPS and include a hostname")
    if parsed.username is not None or parsed.password is not None:
        raise PublicNetworkError("retrieval URL must not contain credentials")
    try:
        port = parsed.port
    except ValueError as exc:
        raise PublicNetworkError("retrieval URL has an invalid port") from exc
    if port not in {None, 443}:
        raise PublicNetworkError("retrieval URL must use the standard HTTPS port")
    try:
        addresses = {
            item[4][0].split("%", 1)[0]
            for item in socket.getaddrinfo(parsed.hostname, port or 443, type=socket.SOCK_STREAM)
        }
    except socket.gaierror as exc:
        raise PublicNetworkError(f"retrieval hostname cannot be resolved: {parsed.hostname}") from exc
    if not addresses:
        raise PublicNetworkError(f"retrieval hostname has no resolved addresses: {parsed.hostname}")
    for raw in addresses:
        address = ipaddress.ip_address(raw)
        if not address.is_global:
            raise PublicNetworkError(
                f"retrieval hostname resolves to a non-public address: {parsed.hostname}"
            )
    return url


class PublicHTTPSRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject redirects away from validated public HTTPS destinations."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        validate_public_https_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def public_https_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(PublicHTTPSRedirectHandler())


_original_getaddrinfo = socket.getaddrinfo


def force_ipv4_resolution() -> None:
    """Restrict all future resolution to IPv4 (AF_INET).

    Containers without IPv6 routes can blackhole IPv6 connection attempts;
    this forces the IPv4 path for environments where that matters.
    """

    def ipv4_only(host, port, family=0, type=0, proto=0, flags=0):  # type: ignore[no-untyped-def]
        return [
            entry for entry in _original_getaddrinfo(host, port, family, type, proto, flags)
            if entry[0] == socket.AF_INET
        ]

    socket.getaddrinfo = ipv4_only  # type: ignore[assignment]
