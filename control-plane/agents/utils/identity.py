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


# --- Container Matching logic (V4.1) ------------------------------------------

def normalize_container_name(name: str | None) -> str:
    """Strips symbols and leading slashes for fuzzy matching."""
    if not name:
        return ""
    # Docker names often come with leading slashes, e.g., "/radarr"
    return name.lstrip("/").lower().replace("-", "").replace("_", "").replace(".", "")


def match_container_safe(target: str, containers: list[dict]) -> dict | None:
    """Hardened container matching strategy.
    Priority:
    1. Exact Name match
    2. Startswith match (handles m3tal- prefix)
    3. Unique Fuzzy match (normalized)
    
    Returns the container dict if a unique match is found, else None.
    """
    if not target or not containers:
        return None

    # 1. Exact Name Match (highest confidence)
    for c in containers:
        # Names is a string in docker ps --format {{json .}} output
        names = [n.lstrip("/") for n in c.get("Names", "").split(",")]
        if target in names:
            return c

    # 2. Startswith Match (common in Docker Compose)
    starts_matches = []
    for c in containers:
        names = [n.lstrip("/") for n in c.get("Names", "").split(",")]
        for n in names:
            if n.startswith(f"m3tal-{target}") or n.startswith(target):
                starts_matches.append(c)
                break
    
    if len(starts_matches) == 1:
        return starts_matches[0]

    # 3. Unique Fuzzy Match (normalized)
    norm_target = normalize_container_name(target)
    fuzzy_matches = []
    for c in containers:
        names = [n.lstrip("/") for n in c.get("Names", "").split(",")]
        for n in names:
            if norm_target in normalize_container_name(n):
                fuzzy_matches.append(c)
                break
                
    if len(fuzzy_matches) == 1:
        return fuzzy_matches[0]
    elif len(fuzzy_matches) > 1:
        # Ambiguous match (e.g. radarr vs readarr) - abort for safety
        return None

    return None
