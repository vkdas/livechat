"""Which country a post is about (Bangladesh or India), and which country the visitor is interested in."""
import re

BD_WORDS = [
    "bangladesh", "বাংলাদেশ", "dhaka", "ঢাকা", "bpsc", "teletalk", "টেলিটক", ".gov.bd", ".edu.bd", ".com.bd", "bangladesh bank",
    "bdjobs", "চট্টগ্রাম", "chattogram", "chittagong", "rajshahi", "রাজশাহী", "khulna", "খুলনা", "sylhet", "সিলেট", "barisal", "barishal",
    "বরিশাল", "rangpur", "রংপুর", "mymensingh", "ময়মনসিংহ", "cumilla", "comilla", "gazipur", "narayanganj", "bogura", "jessore",
    "tk.", "taka", "টাকা", "বিজিবি", "bgb", "ansar", "আনসার", "এনএসআই", "nsi", "dpe", "ডিপিই", "ntrca", "এনটিআরসিএ",
]
IN_WORDS = [
    "india", "indian", "ভারত", "ভারতের", "upsc", "ssc cgl", "rrb", "railway recruitment", "ibps", "sarkari", ".gov.in", ".nic.in", "nic.in",
    "₹", "rs.", "rupee", "রুপি", "west bengal", "পশ্চিমবঙ্গ", "kolkata", "কলকাতা", "bihar", "tamil nadu", "kerala", "maharashtra",
    "uttar pradesh", "delhi", "new delhi", "karnataka", "odisha", "gujarat", "rajasthan", "punjab", "assam", "telangana", "andhra",
    "madhya pradesh", "jharkhand", "chhattisgarh", "haryana", "aiims", "isro", "drdo", "bsf", "crpf", "cisf", "nabard", "rbi",
    "sbi ", "lic ", "ongc", "ntpc", "bhel", "gail", "iocl", "bpcl", "hpcl", "ssc ", "kvs", "nvs", "wbssc", "wbpsc", "tnpsc", "kpsc",
]


def _hits(text: str, words: list[str]) -> int:
    return sum(1 for w in words if w in text)


def post_region(title: str, text: str = "") -> str:
    """'BD', 'IN' or '' (unknown / both). Title counts triple, the first 700 characters count once."""
    t = (title or "").lower()
    body = (text or "")[:700].lower()
    bd = 3 * _hits(t, BD_WORDS) + _hits(body, BD_WORDS)
    ind = 3 * _hits(t, IN_WORDS) + _hits(body, IN_WORDS)
    if bd >= ind + 2 or (bd and not ind):
        return "BD"
    if ind >= bd + 2 or (ind and not bd):
        return "IN"
    return ""


_Q_BD = re.compile(r"(বাংলাদেশ|bangladesh|\bbd\b|ঢাকা|dhaka|bpsc|বিপিএসসি)", re.I)
_Q_IN = re.compile(r"(ভারত|india|indian|কলকাতা|kolkata|পশ্চিমবঙ্গ|west bengal|upsc|rrb|ibps|\bssc cgl\b|ভারতীয়)", re.I)


def question_country(q: str) -> str:
    """The visitor names a country in the question itself: that wins over any guess."""
    bd, ind = bool(_Q_BD.search(q)), bool(_Q_IN.search(q))
    return "BD" if bd and not ind else "IN" if ind and not bd else ""


def clean(country: str) -> str:
    c = (country or "").strip().upper()
    return c if c in ("BD", "IN") else ""


def prefer(hits: list[dict], country: str, keep: int) -> list[dict]:
    """Put posts of the visitor's country first and drop the other country's posts when enough remain."""
    if not country:
        return hits[:keep]
    for h in hits:
        h.setdefault("region", post_region(h["title"], h["text"]))
    same = [h for h in hits if h["region"] in (country, "")]
    if len(same) >= 2:
        ordered = [h for h in same if h["region"] == country] + [h for h in same if h["region"] == ""]
        return ordered[:keep]
    return hits[:keep]
