import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

# getaddrinfo wants a port, so fill in the scheme default when the URL omits one
_DEFAULT_PORTS = {"http": 80, "https": 443}


class UnsafeUrlError(Exception):
    """Raised when a URL must not be fetched (bad scheme or internal address)."""


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """True for any address that points back into our own network."""
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped

    return (
        ip.is_loopback
        or ip.is_link_local  # covers the cloud metadata address 169.254.169.254
        or ip.is_private
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
        # `is_private` reports False for CGNAT (100.64.0.0/10) — ipaddress encodes
        # that carve-out only in `is_global`, and clouds route the range to internal
        # services. `is_global` is True for multicast, so the checks above stay.
        or not ip.is_global
    )


async def assert_public_url(url: str) -> None:
    """Raise UnsafeUrlError unless the URL is http(s) and resolves to public IPs.

    The hostname is resolved and *every* returned address is checked, so a public
    name whose A record points into RFC1918 is refused too. This does not stop
    DNS rebinding between the check here and the actual connect — closing that
    would mean pinning the socket to the validated address and overriding the
    Host header, which is more machinery than this bot needs.
    """
    parsed = urlparse(url)

    if parsed.scheme not in _DEFAULT_PORTS:
        raise UnsafeUrlError("Only http:// and https:// URLs can be fetched.")

    host = (parsed.hostname or "").lower()
    if not host or host == "localhost":
        raise UnsafeUrlError("Refusing to fetch an internal/loopback address.")

    try:
        port = parsed.port or _DEFAULT_PORTS[parsed.scheme]
    except ValueError as e:
        raise UnsafeUrlError("URL has an invalid port.") from e

    try:
        infos = await asyncio.get_running_loop().getaddrinfo(
            host, port, type=socket.SOCK_STREAM
        )
    except socket.gaierror as e:
        raise UnsafeUrlError(f"Could not resolve host: {host}") from e

    if not infos:
        raise UnsafeUrlError(f"Could not resolve host: {host}")

    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError as e:
            raise UnsafeUrlError(f"Could not resolve host: {host}") from e

        if _is_blocked_ip(ip):
            raise UnsafeUrlError("Refusing to fetch an internal/loopback address.")
