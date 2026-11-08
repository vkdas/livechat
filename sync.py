import hashlib
import json
import logging
import threading
import time

import crawler, extract, llm
from config import (CHUNK_CHARS, CHUNK_OVERLAP, EMBEDDINGS, EMBED_CHAT_RESERVE, EMBED_DAILY_LIMIT,
                     MAX_CHUNKS_PER_DOC, MAX_RETRIES, OCR_SKIP_IF_TEXT_CHARS, SYNC_INTERVAL_MIN)
from store import chunk_hash, store
from textutil import chunk_text

log = logging.getLogger("sync")
_lock = threading.Lock()
state = {"running": False, "last_ts": 0.0, "failed": 0, "paused": False, "att_ok": 0, "att_fail": 0, "att_why": []}


def _att_fail(url, exc):
    state["att_fail"] += 1
    if extract.is_transient(exc):
        extract.transient_flag["n"] += 1
    if len(state["att_why"]) < 6:
        state["att_why"].append(f"{url[-70:]} -> {str(exc)[:110]}")


def build_docs(entry):
    text, links, imgs = extract.html_to_text(entry.content, entry.url, keep_links=True)
    docs = []
    if text.strip():
        if entry.published:
            text = f"Published: {entry.published[:10]}\n{text}"
        docs.append(dict(url=entry.url, title=entry.title, kind=entry.kind, text=text))
    for att in extract.find_attachments(links, imgs, entry.url, skip_images=bool(OCR_SKIP_IF_TEXT_CHARS) and len(text) >= OCR_SKIP_IF_TEXT_CHARS):
        try:
            d = store.cache_get("att:" + att.url) or extract.fetch_attachment(att)
            if d and d.get("text"):
                store.cache_put("att:" + att.url, d)
        except Exception as exc:
            log.warning("attachment %s failed: %s", att.url, exc)
            _att_fail(att.url, exc)
            continue
        if d and d["text"] and d["text"].strip():
            d["title"] = f"{d['title']} ({entry.title})"
            docs.append(d)
            state["att_ok"] += 1
        else:
            _att_fail(att.url, "no readable text")
    for u in extract.find_linked_pages(links):
        try:
            d = store.cache_get("lnk:" + u) or extract.fetch_linked(u, entry.url, entry.title)
            if d:
                store.cache_put("lnk:" + u, d)
        except Exception as exc:
            log.warning("linked page %s failed: %s", u, exc)
            _att_fail(u, exc)
            continue
        if d:
            docs.append(d)
            state["att_ok"] += 1
    return docs


def make_chunks(post_url, docs):
    """Cut documents into chunks. Vectors are reused from earlier runs when the text is unchanged;
    new chunks get theirs later (backfill), so keyword search works immediately."""
    items = []
    for d in docs:
        for c in chunk_text(d["text"], CHUNK_CHARS, CHUNK_OVERLAP)[:MAX_CHUNKS_PER_DOC]:
            items.append(dict(url=d["url"], title=d["title"], kind=d["kind"], text=c))
    store.stash_post_embs(post_url)
    cached = store.emb_cache_get([chunk_hash(i["title"], i["text"]) for i in items])
    for i in items:
        i["emb"] = cached.get(chunk_hash(i["title"], i["text"]))
    return items


def backfill():
    """Add meaning-based vectors for chunks that have none, without passing the free daily quota.
    Returns (number embedded, reason it stopped)."""
    if EMBEDDINGS == "off":
        return 0, "বন্ধ"
    done = since_reload = 0
    while True:
        allowed = EMBED_DAILY_LIMIT - EMBED_CHAT_RESERVE - store.embed_used()
        if allowed <= 0:
            state["paused"] = True
            return done, "আজকের কোটা শেষ, কাল আবার চলবে"
        rows = store.pending_chunks(min(50, allowed))
        if not rows:
            state["paused"] = False
            return done, "সব শেষ"
        try:
            vecs = llm.embed([f"{t}\n{x}" for _, t, x in rows])
        except Exception as exc:
            if llm.is_daily_quota(exc):
                store.set_embed_used(EMBED_DAILY_LIMIT)
                state["paused"] = True
                return done, "Google-এর দৈনিক সীমা শেষ"
            log.exception("embedding failed")
            store.set_meta("last_embed_error", time.strftime("%H:%M:%S", time.gmtime()) + " UTC | " + str(exc)[:400])
            return done, "ত্রুটি, পরে আবার চেষ্টা হবে"
        store.set_embeddings([r[0] for r in rows], vecs)
        store.add_embed_used(len(rows))
        store.set_meta("last_embed_error", "")
        done += len(rows)
        since_reload += len(rows)
        if since_reload >= 200:
            store.reload()
            since_reload = 0


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
        recent = sorted((e for e in entries if e.kind == "post" and e.published), key=lambda e: e.published, reverse=True)[:40]
        store.set_meta("recent", json.dumps([dict(url=e.url, title=e.title, published=e.published[:10]) for e in recent]))
        changed = failed = incomplete = 0
        for e in entries:
            h = hashlib.sha1(f"{e.title}|{e.updated}|{e.content}".encode()).hexdigest()
            if not force and store.post_hash(e.url) == h:
                continue
            try:
                extract.transient_flag["n"] = 0
                docs = build_docs(e)
                retries = json.loads(store.get_meta("retries") or "{}")
                tries = retries.get(e.url, 0)
                if extract.transient_flag["n"] and tries < MAX_RETRIES:
                    retries[e.url] = tries + 1  # a file timed out or quota ran out: look again on a later sync
                    store.replace_post(e.url, h + "|retry", make_chunks(e.url, docs))
                    incomplete += 1
                else:
                    retries.pop(e.url, None)
                    store.replace_post(e.url, h, make_chunks(e.url, docs))
                store.set_meta("retries", json.dumps(retries))
                changed += 1
                if changed % 10 == 0:
                    store.reload()  # chat starts answering from what is already read
            except Exception:
                log.exception("failed to read %s", e.url)
                failed += 1
        state["failed"] = failed
        state["incomplete"] = incomplete
        removed = store.delete_posts_not_in(urls)
        if changed or removed:
            store.reload()
        embedded, why = backfill()
        if embedded:
            store.reload()
        msg = (f"আংশিক পড়া (পরে আবার চেষ্টা): {incomplete} | নতুন/বদলানো: {changed}, ব্যর্থ: {failed}, মোছা: {removed}, মোট পোস্ট/পেজ: {len(urls)} | "
               f"এমবেডিং: +{embedded} ({why}), বাকি চাংক: {store.pending_count()}")
        store.set_meta("attach_report", f"ফাইল/ছবি/লিংক পড়া গেছে: {state['att_ok']}, পড়া যায়নি: {state['att_fail']}"
                       + (" | উদাহরণ: " + " ; ".join(state["att_why"]) if state["att_why"] else ""))
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
        if state["paused"]:
            wait = 30  # daily quota used up: look again in half an hour
        elif state["failed"]:
            wait = 10  # some posts could not be read: try again soon
        else:
            wait = SYNC_INTERVAL_MIN
        time.sleep(wait * 60)
