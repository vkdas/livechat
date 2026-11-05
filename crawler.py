import json
import logging
from dataclasses import dataclass

import net
from config import BLOG_URL

log = logging.getLogger("crawler")


@dataclass
class Entry:
    url: str
    title: str
    content: str
    updated: str
    kind: str  # post | page


def _fetch_feed(kind: str) -> list[Entry]:
    out: list[Entry] = []
    start = 1
    while True:
        data, _, _ = net.get(
            f"{BLOG_URL}/feeds/{kind}/default",
            max_mb=20,
            params={"alt": "json", "max-results": 150, "start-index": start},
        )
        feed = json.loads(data)["feed"]
        entries = feed.get("entry", [])
        if not entries:
            break
        for e in entries:
            link = next((l["href"] for l in e.get("link", []) if l.get("rel") == "alternate"), None)
            if not link:
                continue
            body = (e.get("content") or e.get("summary") or {}).get("$t", "")
            out.append(Entry(
                url=link,
                title=e.get("title", {}).get("$t", "").strip() or link,
                content=body,
                updated=e.get("updated", {}).get("$t", ""),
                kind="page" if kind == "pages" else "post",
            ))
        total = int(feed.get("openSearch$totalResults", {}).get("$t", 0))
        start += len(entries)
        if start > total:
            break
    return out


def fetch_all() -> list[Entry]:
    entries = _fetch_feed("posts")
    try:
        entries += _fetch_feed("pages")
    except Exception as exc:  # pages feed can be empty/unavailable
        log.warning("pages feed failed: %s", exc)
    return entries
