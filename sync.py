import hashlib
import logging
import threading
import time

import crawler, extract, llm
from config import CHUNK_CHARS, CHUNK_OVERLAP, MAX_CHUNKS_PER_DOC, SYNC_INTERVAL_MIN
from store import store
from textutil import chunk_text

log = logging.getLogger("sync")
_lock = threading.Lock()
state = {"running": False, "last_ts": 0.0}


def build_docs(entry):
    text, links, imgs = extract.html_to_text(entry.content, entry.url, keep_links=True)
    docs = []
    if text.strip():
        docs.append(dict(url=entry.url, title=entry.title, kind=entry.kind, text=text))
    for att in extract.find_attachments(links, imgs, entry.url):
        try:
            d = extract.fetch_attachment(att)
        except Exception as exc:
            log.warning("attachment %s failed: %s", att.url, exc)
            continue
        if d and d["text"] and d["text"].strip():
            if d["kind"] != "web":
                d["title"] = f"{d['title']} ({entry.title})"
            docs.append(d)
    return docs


def embed_docs(docs):
    items = []
    for d in docs:
        pieces = chunk_text(d["text"], CHUNK_CHARS, CHUNK_OVERLAP)[:MAX_CHUNKS_PER_DOC]
        for c in pieces:
            items.append(dict(url=d["url"], title=d["title"], kind=d["kind"], text=c))
    if not items:
        return []
    vecs = llm.embed([f"{i['title']}\n{i['text']}" for i in items])
    for item, v in zip(items, vecs):
        item["emb"] = v
    return items


def run(force: bool = False) -> str:
    if not _lock.acquire(blocking=False):
        return "already running"
    state["running"] = True
    try:
        entries = crawler.fetch_all()
        if not entries:
            msg = "ফিড থেকে কোনো পোস্ট পাওয়া যায়নি; কিছু মোছা হয়নি"
            store.set_meta("last_sync_result", msg)
            return msg
        urls = {e.url for e in entries}
        changed = failed = consecutive = 0
        for e in entries:
            h = hashlib.sha1(f"{e.title}|{e.updated}|{e.content}".encode()).hexdigest()
            if not force and store.post_hash(e.url) == h:
                continue
            try:
                chunks = embed_docs(build_docs(e))
                store.replace_post(e.url, h, chunks)
                changed += 1
                consecutive = 0
                if changed % 10 == 0:
                    store.reload()  # chat starts answering from what is already read
            except Exception:
                log.exception("failed to index %s", e.url)
                failed += 1
                consecutive += 1
                if consecutive >= 3:
                    log.error("too many consecutive failures (quota?), stopping this run")
                    break
        removed = store.delete_posts_not_in(urls)
        if changed or removed:
            store.reload()
        msg = f"নতুন/বদলানো: {changed}, ব্যর্থ: {failed}, মোছা: {removed}, মোট পোস্ট/পেজ: {len(urls)}"
        store.set_meta("last_sync", time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + " UTC")
        store.set_meta("last_sync_result", msg)
        log.info(msg)
        return msg
    finally:
        state["running"] = False
        state["last_ts"] = time.time()
        _lock.release()


def run_async(force: bool = False):
    threading.Thread(target=_safe_run, args=(force,), daemon=True).start()


def _safe_run(force=False):
    try:
        run(force)
    except Exception:
        log.exception("sync failed")


def maybe_run_async():
    if not state["running"] and time.time() - state["last_ts"] > SYNC_INTERVAL_MIN * 60:
        state["last_ts"] = time.time()
        run_async()


def loop():
    time.sleep(2)
    while True:
        _safe_run()
        time.sleep(SYNC_INTERVAL_MIN * 60)
