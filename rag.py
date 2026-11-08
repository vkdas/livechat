import hashlib
import logging
import re
import time

import llm, region
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


CLARIFY = {
    "bn": "আপনি ঠিক কী জানতে চান, আরেকটু খুলে বলবেন? আমি চাকরির বিজ্ঞপ্তি, শেষ তারিখ, যোগ্যতা, কাগজপত্র ও আবেদনের নিয়ম নিয়ে সাহায্য করতে পারি।",
    "en": "Could you tell me a little more about what you need? I can help with job circulars, deadlines, eligibility, documents and how to apply.",
    "hi": "क्या आप थोड़ा और बता सकते हैं कि आपको क्या जानना है? मैं नौकरी के सर्कुलर, अंतिम तिथि, योग्यता, दस्तावेज़ और आवेदन में मदद कर सकती हूँ।",
    "ar": "هل يمكنك أن توضح أكثر ما تحتاجه؟ يمكنني المساعدة في الوظائف والمواعيد والشروط والمستندات وطريقة التقديم.",
}


def _not_found(question: str) -> dict:
    short = len(question.split()) <= 5  # a short, vague message: ask what they mean instead of a dead end
    return {"found": False, "answer": (CLARIFY if short else NOT_FOUND)[detect_lang(question)],
            "sources": [], "followups": []}


_SMALL = re.compile(
    r"^\W*(কোথায় থাক\S*|কোথা থেকে\S*|কোথায় বাস\S*|where do you (live|stay)|hi+|hello+|hey+|as+a?l+a?m\w*|as+al\w*|wa\s*alaikum\w*|salam\w*|slm|kemon\s+ach\w+|kemon\s+achen|valo\s+ach\w+|bhalo\s+ach\w+|dhonnobad|dhanyabad|good\s*(morning|afternoon|evening|night)|how are you|thanks?( you)?|thank u|bye|who are you|"
    r"are you (a )?(human|bot|ai|real)|what('?s| is) your name|"
    r"হ্যালো|হাই|হেলো|আসসালামু\s*আলাইকুম|সালাম|নমস্কার|কেমন আছ\S*|কি খবর|ধন্যবাদ|থ্যাংক\S*|শুভ\s*\S+|বিদায়|"
    r"তুমি কী কী পারো|তোমার কাছে কি আছে|তোমার কাছে কী আছে|আপনার কাছে কি আছে|কিভাবে করব|কীভাবে করব|কি করতে পারো|কী করতে পারো|সাহায্য|help|what can you do|তুমি কে|আপনি কে|বয়স কত\S*|আপনার বয়স\S*|তোমার বয়স\S*|how old\S*|তোমার নাম কী?|আপনার নাম কী?|তুমি কি (মানুষ|বট|রোবট)|आप कैसे हैं|नमस्ते|धन्यवाद|مرحبا|السلام عليكم|شكرا)"
    r"[\s\W]*(\S+[\s\W]*){0,3}$", re.I)


_SALAM = re.compile(r"(as+a?l+a?m\w*|as+al\w*|salam\w*|slm|আসসালামু|আস্সালামু|সালাম|السلام)", re.I)
_IDENT = re.compile(r"(human|\bbot\b|robot|\bai\b|real person|মানুষ|বট|রোবট|এআই|যন্ত্র|इंसान|रोबोट|إنسان|روبوت)", re.I)
_WHERE = re.compile(r"(কোথায় থাক|কোথা থেকে|কোথায় বাস|where do you (live|stay))", re.I)
_AGE = re.compile(r"(how old|\bage\b|বয়স|उम्र|عمرك)", re.I)
_NAME = re.compile(r"(who are you|your name|তুমি কে|আপনি কে|নাম|कौन|नाम|اسمك|من أنت)", re.I)
CANNED = {
    "bn": {"where": "আমি অনলাইনে, BD JOBS INFO সাইটেই থাকি। চাকরির কোন তথ্য জানতে চান, বলুন।",
           "salam": "ওয়ালাইকুম আসসালাম! আমি KaKoli Ray। চাকরির সার্কুলার, শেষ তারিখ বা আবেদনের নিয়মে কী জানতে চান, বলুন।",
           "hello": "হ্যালো! আমি ভালো আছি, ধন্যবাদ। আপনি কেমন আছেন? চাকরির সার্কুলার, শেষ তারিখ বা আবেদনের নিয়মে কী জানতে চান, বলুন।",
           "name": "আমি KaKoli Ray, BD JOBS INFO-এর সহকারী। চাকরির সার্কুলার, শেষ তারিখ ও আবেদনের নিয়মে আপনাকে সাহায্য করতে পারি।",
           "age": "আমার বয়স বলে কিছু নেই, আমি BD JOBS INFO-এর সহকারী। চাকরির কোন তথ্য জানতে চান, বলুন।",
           "ident": "আমি একটি এআই-চালিত ভার্চুয়াল সহকারী, মানুষ নই। তবে চাকরির সার্কুলার, শেষ তারিখ ও আবেদনের নিয়মে আপনাকে সাহায্য করতে পারি।"},
    "en": {"where": "I live online, right here on the BD JOBS INFO site. What would you like to know about jobs?",
           "salam": "Wa alaikum assalam! I'm KaKoli Ray. Tell me what you'd like to know about job circulars, deadlines or how to apply.",
           "hello": "Hello! I'm doing well, thank you. How are you? Tell me what you'd like to know about job circulars, deadlines or how to apply.",
           "name": "I'm KaKoli Ray, the assistant of BD JOBS INFO. I can help with job circulars, deadlines and how to apply.",
           "age": "I don't have an age. I'm the assistant of BD JOBS INFO. What would you like to know about jobs?",
           "ident": "I'm an AI-powered virtual assistant, not a human. I can still help with job circulars, deadlines and how to apply."},
    "hi": {"where": "मैं ऑनलाइन, BD JOBS INFO साइट पर ही रहती हूँ। नौकरी के बारे में क्या जानना चाहते हैं?",
           "salam": "वा अलैकुम अस्सलाम! मैं KaKoli Ray हूँ। नौकरी के सर्कुलर या आवेदन के बारे में पूछिए।",
           "hello": "नमस्ते! मैं ठीक हूँ, धन्यवाद। आप कैसे हैं? नौकरी के सर्कुलर, अंतिम तिथि या आवेदन के बारे में पूछिए।",
           "name": "मैं KaKoli Ray, BD JOBS INFO की सहायक हूँ। नौकरी के सर्कुलर और आवेदन में मदद कर सकती हूँ।",
           "age": "मेरी कोई उम्र नहीं है, मैं BD JOBS INFO की सहायक हूँ। नौकरी के बारे में क्या जानना चाहते हैं?",
           "ident": "मैं एक एआई-संचालित वर्चुअल सहायक हूँ, इंसान नहीं। फिर भी नौकरी के सर्कुलर और आवेदन में मदद कर सकती हूँ।"},
    "ar": {"where": "أنا أعيش على الإنترنت، هنا في موقع BD JOBS INFO. ماذا تريد أن تعرف عن الوظائف؟",
           "salam": "وعليكم السلام! أنا KaKoli Ray. اسألني عن الوظائف وطريقة التقديم.",
           "hello": "مرحبًا! أنا بخير، شكرًا. كيف حالك؟ اسألني عن الوظائف والمواعيد وطريقة التقديم.",
           "name": "أنا KaKoli Ray، مساعدة موقع BD JOBS INFO. يمكنني مساعدتك في الوظائف وطريقة التقديم.",
           "age": "ليس لي عمر، أنا مساعدة موقع BD JOBS INFO. ماذا تريد أن تعرف عن الوظائف؟",
           "ident": "أنا مساعد افتراضي يعمل بالذكاء الاصطناعي ولست إنسانًا، لكن يمكنني مساعدتك في الوظائف وطريقة التقديم."},
}


def canned_smalltalk(q: str) -> str:
    kind = "where" if _WHERE.search(q) else "salam" if _SALAM.search(q) else "ident" if _IDENT.search(q) else "age" if _AGE.search(q) else "name" if _NAME.search(q) else "hello"
    return CANNED[detect_lang(q)][kind]


def is_smalltalk(q: str) -> bool:
    return len(q) <= 60 and bool(_SMALL.match(q.strip()))


_RECENT = re.compile(r"(latest|newest|new |recent|today|yesterday|this week|just (published|posted)|নতুন|সর্বশেষ|সাম্প্রতিক|আজ|কাল|কালকে|গতকাল|আজকের|প্রকাশ|এই সপ্তাহ|নতুন সার্কুলার|नया|ताज़ा|आज|कल|جديد|اليوم|أمس)", re.I)


def recent_hits(country: str = "", cat: str = "") -> list[dict]:
    import json
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    try:
        items = json.loads(store.get_meta("recent") or "[]")
    except Exception:
        return []
    if country:
        items = [i for i in items if region.post_region(i["title"]) in (country, "")]
    if cat:
        items = [i for i in items if region.in_category(i["title"], cat)]
    items = sorted(items, key=lambda i: i["published"], reverse=True)
    since = (datetime.now(ZoneInfo("Asia/Dhaka")) - timedelta(days=3)).strftime("%Y-%m-%d")
    fresh = [i for i in items if i["published"] >= since]  # "today / latest": the last few days first
    items = fresh if len(fresh) >= 3 else items
    return [dict(title=i["title"], url=i["url"], kind="post", sem=1.0, kw=1.0,
                 text=f"Published: {i['published']}. Title: {i['title']}") for i in items[:8]]


BILINGUAL = {
    "বই": "book books", "চাকরি": "job jobs", "চাকুরি": "job jobs", "নিয়োগ": "recruitment appointment", "বিজ্ঞপ্তি": "notice circular",
    "সার্কুলার": "circular notice", "আবেদন": "apply application", "পরীক্ষা": "exam examination test", "ফলাফল": "result results",
    "প্রবেশপত্র": "admit card", "বেতন": "salary pay scale", "যোগ্যতা": "eligibility qualification", "ব্যাংক": "bank",
    "সরকারি": "government govt", "বেসরকারি": "private", "শিক্ষক": "teacher", "প্রশ্ন": "question questions", "সিলেবাস": "syllabus",
    "সাজেশন": "suggestion", "ডাউনলোড": "download", "ড্রাইভার": "driver", "সেনাবাহিনী": "army", "নৌবাহিনী": "navy",
    "বিমানবাহিনী": "air force", "পুলিশ": "police", "বয়স": "age", "শেষ তারিখ": "deadline last date", "মৌখিক": "viva oral",
    "লিখিত": "written", "ভর্তি": "admission", "বৃত্তি": "scholarship", "নার্স": "nurse", "ডাক্তার": "doctor", "ফি": "fee fees",
    "কাগজপত্র": "documents", "প্রয়োজনীয়": "required", "নম্বর": "marks number", "বিভাগ": "department division", "পদ": "post position",
    "অফিসার": "officer", "সহকারী": "assistant", "কর্মকর্তা": "officer", "ইন্টারভিউ": "interview", "সনদ": "certificate",
    "প্রতিষ্ঠান": "organization institute", "কোম্পানি": "company", "জেলা": "district", "বিশ্ববিদ্যালয়": "university",
    "স্কুল": "school", "কলেজ": "college", "ভিসা": "visa", "বিদেশ": "abroad foreign overseas", "ফরম": "form", "ফর্ম": "form",
}
_EN2BN = {}
for _bn, _en in BILINGUAL.items():
    for _w in _en.split():
        _EN2BN.setdefault(_w, _bn)


def expand_query(q: str) -> str:
    """Bangla <-> English keyword bridge for the keyword search (most posts are in English, visitors write Bangla)."""
    low = q.lower()
    extra = [en for bn, en in BILINGUAL.items() if bn in low]
    extra += [bn for en, bn in _EN2BN.items() if re.search(r"\b" + re.escape(en) + r"s?\b", low)]
    return q if not extra else q + " " + " ".join(dict.fromkeys(" ".join(extra).split()))


SEARCH_ONLY = {
    "bn": "এই মুহূর্তে এআই-উত্তর দেওয়া যাচ্ছে না, তবে আপনার প্রশ্নের সাথে মিল আছে এমন তথ্য আমাদের সাইটে পাওয়া গেছে:",
    "en": "I can't compose an answer right now, but I found these matching items on our site:",
    "hi": "अभी उत्तर तैयार नहीं हो पा रहा, लेकिन हमारी साइट पर आपके प्रश्न से मिलती जानकारी मिली:",
    "ar": "لا أستطيع صياغة إجابة الآن، لكنني وجدت هذه المعلومات المطابقة على موقعنا:",
}


def _snippet(text: str, n: int = 260) -> str:
    t = re.sub(r"^Published:[^\n]*\n", "", text).strip()
    t = re.sub(r"\s+", " ", t)
    return t[:n].rstrip() + ("…" if len(t) > n else "")


def _search_only(q: str, hits: list[dict]) -> dict:
    """No AI available (quota/outage): show the best matching passages and their post links, without any token cost."""
    top, seen = [], set()
    for h in hits:
        if h["url"] in seen:
            continue
        seen.add(h["url"])
        top.append(h)
        if len(top) == 3:
            break
    lines = [SEARCH_ONLY[detect_lang(q)]] + [f"\n**{i}. {h['title']}**\n{_snippet(h['text'])}" for i, h in enumerate(top, 1)]
    sources = [{"n": i, "title": h["title"], "url": h["url"], "kind": h["kind"]} for i, h in enumerate(top, 1)]
    return {"found": True, "answer": "\n".join(lines), "sources": sources, "followups": []}


def ask(question: str, history: list[dict], country: str = "") -> dict:
    q = question.strip()
    country = region.question_country(q) or region.clean(country)  # a country named in the question wins
    llm.visitor_country.set(country)
    cat = region.question_category(q)
    llm.visitor_category.set(cat)
    wants_recent = bool(_RECENT.search(q))
    key = None
    if not history and not wants_recent:  # "today / new" answers change every day: never reuse an old one
        key = f"{store.version}:{country}:{hashlib.sha1(_norm(q).encode()).hexdigest()}"
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
    if history and len(q.split()) < 9:
        prev = [m["content"] for m in history if m["role"] == "user"]
        bot = [m["content"] for m in history if m["role"] != "user"]
        if prev:
            query_text = f"{prev[-1]} {q}"
        if bot:  # "are these still open?": "these" are the posts named in the last answer
            query_text += " " + re.sub(r"https?://\S+|[*_#>\[\]()]", " ", bot[-1])[:500]

    qvec = None
    if EMBEDDINGS != "off" and store.embed_available():
        try:
            qvec = llm.embed([query_text], query=True)[0]
            store.add_embed_used(1)
        except Exception as exc:  # quota or network: fall back to keyword search instead of failing
            if llm.is_daily_quota(exc):
                store.set_embed_used(EMBED_DAILY_LIMIT)
            logging.getLogger("rag").warning("query embedding skipped: %s", str(exc)[:200])
    hits = region.prefer(region.prefer_category(store.search(qvec, expand_query(query_text), TOP_K * 3), cat), country, TOP_K)
    if wants_recent:  # "what's new / today / yesterday": the newest posts (with dates) come FIRST
        new = recent_hits(country, cat)
        known = {h["url"] for h in new}
        hits = new + [h for h in hits if h["url"] not in known][:4]

    if not hits or (max(h["sem"] for h in hits) < MIN_SIM and max(h["kw"] for h in hits) == 0):
        result = _not_found(q)
    else:
        try:
            ans = llm.generate_answer(q, history, hits)
        except Exception as exc:  # every AI is busy or out of quota: still give the visitor the matching passages
            logging.getLogger("rag").warning("answer generation failed: %s", str(exc)[:300])
            store.set_meta("last_chat_error", time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + " UTC | " + repr(exc)[:500])
            result = _search_only(q, hits)
            store.log_question(q, True, False)
            return result  # not cached: a real answer replaces it once the AI is back
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

    if not result["found"] and not result.get("followups"):
        # no answer: suggest only posts about the SAME topic (close matches), never unrelated subjects
        seen_t = []
        for h in hits:
            if (h.get("kw", 0) > 0 or h.get("sem", 0) >= MIN_SIM) and region.in_category(h["title"], cat) and h["title"][:90] not in seen_t:
                seen_t.append(h["title"][:90])
        result["followups"] = seen_t[:3]

    store.log_question(q, result["found"], False)
    if key:
        store.cache_put(key, result)
    return result
