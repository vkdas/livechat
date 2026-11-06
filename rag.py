import hashlib
import logging
import re

import llm
from config import EMBED_DAILY_LIMIT, EMBEDDINGS, MIN_SIM, TOP_K, WEB_FALLBACK
from store import store
from textutil import has_bengali

NOT_FOUND = {
    "bn": "দুঃখিত, এ বিষয়ে আমাদের সাইটে আমি কোনো তথ্য খুঁজে পাইনি। আরেকটু স্পষ্ট করে বা অন্যভাবে প্রশ্ন করে দেখবেন?",
    "en": "Sorry, I couldn't find anything about this on our site. Could you try rephrasing your question?",
    "hi": "क्षमा करें, मुझे इस विषय पर हमारी साइट पर कोई जानकारी नहीं मिली। क्या आप अपना प्रश्न दूसरे तरीके से पूछ सकते हैं?",
    "ar": "عذرًا، لم أجد أي معلومات عن هذا الموضوع على موقعنا. هل يمكنك إعادة صياغة سؤالك؟",
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


_SMALL = re.compile(
    r"^\W*(hi+|hello+|hey+|good\s*(morning|afternoon|evening|night)|how are you|thanks?( you)?|thank u|bye|who are you|"
    r"are you (a )?(human|bot|ai|real)|what('?s| is) your name|"
    r"হ্যালো|হাই|হেলো|আসসালামু\s*আলাইকুম|সালাম|নমস্কার|কেমন আছ\S*|কি খবর|ধন্যবাদ|থ্যাংক\S*|শুভ\s*\S+|বিদায়|"
    r"তুমি কী কী পারো|তোমার কাছে কি আছে|তোমার কাছে কী আছে|আপনার কাছে কি আছে|কিভাবে করব|কীভাবে করব|কি করতে পারো|কী করতে পারো|সাহায্য|help|what can you do|তুমি কে|আপনি কে|তোমার নাম কী?|আপনার নাম কী?|তুমি কি (মানুষ|বট|রোবট)|आप कैसे हैं|नमस्ते|धन्यवाद|مرحبا|السلام عليكم|شكرا)"
    r"[\s\W]*(\S+[\s\W]*){0,3}$", re.I)


_NAME = re.compile(r"(who are you|your name|human|bot|real|তুমি কে|আপনি কে|নাম|মানুষ|বট|রোবট|कौन|नाम|اسمك|من أنت)", re.I)
CANNED = {
    "bn": ("হ্যালো! আমি ভালো আছি, ধন্যবাদ। আপনি কেমন আছেন? চাকরির সার্কুলার, শেষ তারিখ বা আবেদনের নিয়মে কী জানতে চান, বলুন।",
           "আমি KaKoli Ray, BD JOBS INFO-এর ভার্চুয়াল সহকারী, অর্থাৎ একটি এআই-চালিত সহকারী, মানুষ নই। চাকরির সার্কুলার, শেষ তারিখ ও আবেদনের নিয়মে আপনাকে সাহায্য করতে পারি।"),
    "en": ("Hello! I'm doing well, thank you. How are you? Tell me what you'd like to know about job circulars, deadlines or how to apply.",
           "I'm KaKoli Ray, the virtual assistant of BD JOBS INFO. I'm an AI-powered assistant, not a human. I can help with job circulars, deadlines and how to apply."),
    "hi": ("नमस्ते! मैं ठीक हूँ, धन्यवाद। आप कैसे हैं? नौकरी के सर्कुलर, अंतिम तिथि या आवेदन के बारे में पूछिए।",
           "मैं KaKoli Ray, BD JOBS INFO की वर्चुअल सहायक हूँ, यानी एक एआई-संचालित सहायक, इंसान नहीं। मैं नौकरी के सर्कुलर और आवेदन में मदद कर सकती हूँ।"),
    "ar": ("مرحبًا! أنا بخير، شكرًا. كيف حالك؟ اسألني عن الوظائف والمواعيد وطريقة التقديم.",
           "أنا KaKoli Ray، المساعد الافتراضي لموقع BD JOBS INFO، مساعد يعمل بالذكاء الاصطناعي ولست إنسانًا. يمكنني مساعدتك في الوظائف وطريقة التقديم."),
}


def canned_smalltalk(q: str) -> str:
    return CANNED[detect_lang(q)][1 if _NAME.search(q) else 0]


def is_smalltalk(q: str) -> bool:
    return len(q) <= 60 and bool(_SMALL.match(q.strip()))


def ask(question: str, history: list[dict]) -> dict:
    q = question.strip()
    key = None
    if not history:
        key = f"{store.version}:{hashlib.sha1(_norm(q).encode()).hexdigest()}"
        cached = store.cache_get(key)
        if cached:
            store.log_question(q, cached["found"], True)
            return cached

    if is_smalltalk(q):
        try:
            return {"found": True, "answer": llm.smalltalk(q, history), "sources": [], "followups": []}
        except Exception as exc:
            logging.getLogger("rag").warning("smalltalk failed: %s", str(exc)[:200])
            return {"found": True, "answer": canned_smalltalk(q), "sources": [], "followups": []}

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

    if not result["found"] and WEB_FALLBACK:
        try:  # not on the site: general help, without outside links
            result = {"found": False, "answer": llm.general_answer(q, history), "sources": [], "followups": []}
        except Exception as exc:
            logging.getLogger("rag").warning("general fallback failed: %s", str(exc)[:200])

    store.log_question(q, result["found"], False)
    if key:
        store.cache_put(key, result)
    return result
