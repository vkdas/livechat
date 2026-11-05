import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import httpx

from config import MAX_FILE_MB

HEADERS = {"User-Agent": "LiveChatBot/1.0 (+site assistant)"}


def _check(url: str):
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ValueError("unsupported url")
    for info in socket.getaddrinfo(p.hostname, None):
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError("blocked address")


def get(url: str, max_mb: int = MAX_FILE_MB, params=None, allow=None):
    """Download with SSRF check, redirect limit and size cap. Returns (bytes, content_type, final_url).

    `allow(hostname) -> bool`, when given, is checked on the first URL and on every redirect hop."""
    max_bytes = max_mb * 1024 * 1024
    cur = url
    for _ in range(4):
        if allow is not None and not allow(urlparse(cur).hostname or ""):
            raise ValueError("host not allowed")
        _check(cur)
        with httpx.stream("GET", cur, params=params if cur == url else None,
                          follow_redirects=False, timeout=30, headers=HEADERS) as r:
            if r.is_redirect:
                cur = urljoin(cur, r.headers["location"])
                continue
            r.raise_for_status()
            ct = r.headers.get("content-type", "").split(";")[0].strip().lower()
            if int(r.headers.get("content-length") or 0) > max_bytes:
                raise ValueError("file too large")
            buf = bytearray()
            for part in r.iter_bytes():
                buf += part
                if len(buf) > max_bytes:
                    raise ValueError("file too large")
            return bytes(buf), ct, cur
    raise ValueError("too many redirects")
