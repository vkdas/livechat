import hashlib
import logging
import re

import llm
from config import EMBED_DAILY_LIMIT, EMBEDDINGS, MIN_SIM, TOP_K
from store import store
from textutil import has_bengali

NOT_FOUND = {
    "bn": "দুঃখিত, এই সাইটে আমি এ বিষয়ে কোনো তথ্য খুঁজে পাইনি। অন্যভাবে বা আরেকটু স্পষ্ট করে প্রশ্ন করে দেখবেন?",
    "en": "Sorry, I couldn't find anything about this on the site. Could you try rephrasing your question?",
    "hi": "क्षमा करें, मुझे इस विषय पर साइट पर कोई जानकारी नहीं मिली। क्या आप अपना प्रश्न दूसरे तरीके से पूछ सकते हैं?",
    "ar": "عذرًا، لم أجد أي معلومات عن هذا الموضوع على الموقع. هل يمكنك إعادة صياغة سؤالك؟",
}


def _norm(q: str) -> str:
    return re.sub(r"\s+", " ", q.strip().lower())


def detect_lang(text: str) -> str:
    """Rough script-based detection, used only for the canned 'not found' reply."""
    if has_bengali(text):
        return "bn"
    if re.search(r"[ऀ-ॿ]", text):
        return "hi"
    if re.search(r"[؀-ۿ]", text):
        return "ar"
    return "en"


def _not_found(question: str) -> dict:
    return {"found": False, "answer": NOT_FOUND[detect_lang(question)],
            "sources": [], "followups": []}


def ask(question: str, history: list[dict]) -> dict:
    q = question.strip()
    key = None
    if not history:
        key = f"{store.version}:{hashlib.sha1(_norm(q).encode()).hexdigest()}"
        cached = store.cache_get(key)
        if cached:
            store.log_question(q, cached["found"], True)
            return cached

    # follow-up questions are often short: add the previous user question for retrieval
    query_text = q
    if history and len(q.split()) < 6:
        prev = [m["content"] for m in history if m["role"] == "user"]
        if prev:
            query_text = f"{prev[-1]} {q}"

    qvec = None
    if EMBEDDINGS != "off" and store.embed_available():
        try:
            qvec = llm.embed([query_text], query=True)[0]
            store.add_embed_used(1)
        except Exception as exc:  # quota or network: fall back to keyword search instead of failing
            if llm.is_daily_quota(exc):
                store.set_embed_used(EMBED_DAILY_LIMIT)
            logging.getLogger("rag").warning("query embedding skipped: %s", str(exc)[:200])
    hits = store.search(qvec, query_text, TOP_K)

    if not hits or (max(h["sem"] for h in hits) < MIN_SIM and max(h["kw"] for h in hits) == 0):
        result = _not_found(q)
    else:
        ans = llm.generate_answer(q, history, hits)
        if not ans.found:
            result = _not_found(q)
            result["answer"] = ans.answer or result["answer"]
        else:
            used = [n for n in ans.used_sources if 1 <= n <= len(hits)] or [1, 2][:len(hits)]
            sources, seen = [], set()
            for n in used:
                h = hits[n - 1]
                if h["url"] in seen:
                    continue
                seen.add(h["url"])
                sources.append({"n": n, "title": h["title"], "url": h["url"], "kind": h["kind"]})
            result = {"found": True, "answer": ans.answer, "sources": sources,
                      "followups": [f for f in ans.followups if f.strip()][:3]}

    store.log_question(q, result["found"], False)
    if key:
        store.cache_put(key, result)
    return result
