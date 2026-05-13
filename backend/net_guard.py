"""SSRF / URL guard.

Resolves URLs to IP addresses and rejects requests to loopback, link-local,
RFC1918, cloud-metadata (169.254.169.254, fd00:ec2::254), carrier-NAT,
multicast, and reserved ranges. Also rejects schemes other than http/https,
rejects userinfo in the URL (`user:pass@host`), and returns the resolved IP
so callers can connect by IP (defeating DNS rebinding — the Host header
should then carry the original hostname).

Usage:
    ok, info = net_guard.resolve_and_check("https://example.com/foo")
    if not ok:
        return {"success": False, "error": info["reason"]}
    # info contains: host, ip, port, scheme
"""

from __future__ import annotations
import ipaddress
import socket
from urllib.parse import urlparse


_ALLOWED_SCHEMES = {"http", "https"}

# Extra blocked v4 ranges beyond ipaddress.is_private / is_loopback.
_EXTRA_BLOCKED_V4_NETS = [
    ipaddress.ip_network("169.254.0.0/16"),  # link-local + cloud metadata
    ipaddress.ip_network("100.64.0.0/10"),   # carrier-grade NAT
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),    # TEST-NET-1
    ipaddress.ip_network("198.18.0.0/15"),   # benchmarking
    ipaddress.ip_network("198.51.100.0/24"), # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),  # TEST-NET-3
    ipaddress.ip_network("240.0.0.0/4"),     # reserved
]
_EXTRA_BLOCKED_V6_NETS = [
    ipaddress.ip_network("fd00:ec2::/32"),   # AWS IMDS v6
    ipaddress.ip_network("fc00::/7"),        # ULA (private)
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fe80::/10"),       # link-local
    ipaddress.ip_network("ff00::/8"),        # multicast
    ipaddress.ip_network("100::/64"),
    ipaddress.ip_network("2001:db8::/32"),   # documentation
]


def _ip_is_safe(ip_str: str) -> tuple[bool, str]:
    """Return (safe, reason_if_not)."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False, f"Invalid IP: {ip_str}"

    if ip.is_loopback:
        return False, "Loopback address"
    if ip.is_private:
        return False, "Private RFC1918 address"
    if ip.is_link_local:
        return False, "Link-local address"
    if ip.is_multicast:
        return False, "Multicast address"
    if ip.is_reserved or ip.is_unspecified:
        return False, "Reserved/unspecified address"

    extras = _EXTRA_BLOCKED_V4_NETS if isinstance(ip, ipaddress.IPv4Address) else _EXTRA_BLOCKED_V6_NETS
    for net in extras:
        if ip in net:
            return False, f"Blocked range: {net}"
    return True, ""


def resolve_and_check(url: str) -> tuple[bool, dict]:
    """Validate *url* and resolve its host. Returns (ok, info)."""
    if not url or not isinstance(url, str):
        return False, {"reason": "Empty URL"}

    u = url.strip()
    if not u.startswith(("http://", "https://")):
        u = "https://" + u
    try:
        parsed = urlparse(u)
    except Exception as e:
        return False, {"reason": f"Unparseable URL: {e}"}

    scheme = (parsed.scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES:
        return False, {"reason": f"Scheme not allowed: {scheme}"}

    if parsed.username or parsed.password:
        return False, {"reason": "Userinfo in URL is not allowed"}

    host = (parsed.hostname or "").strip()
    if not host:
        return False, {"reason": "Missing host"}

    port = parsed.port or (443 if scheme == "https" else 80)

    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except Exception as e:
        return False, {"reason": f"DNS resolution failed: {e}"}

    for fam, _t, _p, _c, sockaddr in infos:
        ip = sockaddr[0]
        safe, reason = _ip_is_safe(ip)
        if not safe:
            return False, {"reason": f"{host} resolves to {ip}: {reason}"}

    # All resolved addresses are safe — pick the first for the caller.
    chosen_ip = infos[0][4][0]
    return True, {"host": host, "ip": chosen_ip, "port": port, "scheme": scheme}


def guard_or_error(url: str) -> dict | None:
    """Tool-friendly helper: return a `{success: False, ...}` dict when the
    URL is refused, or None when allowed."""
    ok, info = resolve_and_check(url)
    if ok:
        return None
    return {
        "success": False,
        "error": f"URL blocked by guard: {info.get('reason', 'unknown')}",
        "blocked": True,
        "reason": info.get("reason", "unknown"),
    }
