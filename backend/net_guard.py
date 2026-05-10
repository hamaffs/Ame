# Source Generated with Decompyle++
# File: net_guard.pyc (Python 3.11)

'''SSRF / URL guard.

Resolves URLs to IP addresses and rejects requests to loopback, link-local,
RFC1918, cloud-metadata (169.254.169.254, fd00:ec2::254), carrier-NAT,
multicast, and reserved ranges. Also rejects schemes other than http/https,
rejects userinfo in the URL (`user:pass@host`), and optionally returns the
resolved IP so callers can connect by IP (defeating DNS rebinding ΓÇö the
Host header should then carry the original hostname).

Usage:
    ok, info = net_guard.resolve_and_check("https://example.com/foo")
    if not ok:
        return {"success": False, "error": info["reason"]}
    # info contains: host, ip, port, scheme
'''
from __future__ import annotations
import ipaddress
import socket
from urllib.parse import urlparse
_ALLOWED_SCHEMES = {
    'http',
    'https'}
_EXTRA_BLOCKED_V4_NETS = [
    ipaddress.ip_network('169.254.0.0/16'),
    ipaddress.ip_network('100.64.0.0/10'),
    ipaddress.ip_network('192.0.0.0/24'),
    ipaddress.ip_network('192.0.2.0/24'),
    ipaddress.ip_network('198.18.0.0/15'),
    ipaddress.ip_network('198.51.100.0/24'),
    ipaddress.ip_network('203.0.113.0/24'),
    ipaddress.ip_network('240.0.0.0/4')]
_EXTRA_BLOCKED_V6_NETS = [
    ipaddress.ip_network('fd00:ec2::/32'),
    ipaddress.ip_network('fc00::/7'),
    ipaddress.ip_network('::/128'),
    ipaddress.ip_network('::1/128'),
    ipaddress.ip_network('fe80::/10'),
    ipaddress.ip_network('ff00::/8'),
    ipaddress.ip_network('100::/64'),
    ipaddress.ip_network('2001:db8::/32')]

def _ip_is_safe(ip_str = None):
    ip = ipaddress.ip_address(ip_str)
# WARNING: Decompyle incomplete


def resolve_and_check(url = None):
    '''Validate *url* and resolve its host. Returns (ok, info).'''
    if not url or isinstance(url, str):
        return (False, {
            'reason': 'Empty URL' })
    u = None.strip()
    if not u.startswith(('http://', 'https://')):
        u = 'https://' + u
    parsed = urlparse(u)
# WARNING: Decompyle incomplete


def guard_or_error(url = None):
    '''Tool-friendly helper: return a `{success: False, ...}` dict when the
    URL is refused, or None when allowed.'''
    (ok, info) = resolve_and_check(url)
    if ok:
        return None
    return {
        'success': None,
        'error': f'''URL blocked by guard: {info.get('reason', 'unknown')}''',
        'blocked': True,
        'reason': info.get('reason', 'unknown') }

