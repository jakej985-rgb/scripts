from __future__ import annotations

import socket
from urllib.parse import urlparse


LOOPBACK_ALIASES = {"localhost", "127.0.0.1", "::1"}


def normalize_host_identifier(raw_host: str | None) -> str:
    if not raw_host:
        return ""

    host = raw_host.strip()
    if "://" in host:
        parsed = urlparse(host)
        host = parsed.hostname or host

    if "@" in host:
        host = host.rsplit("@", 1)[1]

    if host.startswith("[") and "]" in host:
        host = host[1:host.index("]")]
    elif host.count(":") == 1:
        hostname, port = host.rsplit(":", 1)
        if port.isdigit():
            host = hostname

    return host.strip().lower()


def get_local_host_aliases() -> set[str]:
    aliases = set(LOOPBACK_ALIASES)

    for candidate in (socket.gethostname(), socket.getfqdn()):
        normalized = normalize_host_identifier(candidate)
        if normalized:
            aliases.add(normalized)

    for candidate in tuple(aliases):
        try:
            _, _, addresses = socket.gethostbyname_ex(candidate)
            aliases.update(normalize_host_identifier(address) for address in addresses if address)
        except OSError:
            continue

    return {alias for alias in aliases if alias}


def is_local_host(raw_host: str | None) -> bool:
    normalized = normalize_host_identifier(raw_host)
    if not normalized:
        return True

    return normalized in get_local_host_aliases()


def get_local_identity() -> str:
    hostname = normalize_host_identifier(socket.gethostname())
    return hostname or "localhost"
