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


# job categories: (name shown to the AI, words in the question, words in a post title)
CATEGORIES = {
    "bank": ("Bank jobs", r"ব্যাংক|ব্যাঙ্ক|bank|ibps|sbi", r"ব্যাংক|ব্যাঙ্ক|bank|ibps|sbi|ঋণ|বীমা|insurance"),
    "teacher": ("Teacher / education jobs", r"শিক্ষক|টিচার|teacher|ntrca|এনটিআরসিএ|প্রভাষক|lecturer|kvs|nvs",
                r"শিক্ষক|শিক্ষা|teacher|ntrca|এনটিআরসিএ|প্রভাষক|lecturer|kvs|nvs|school|স্কুল|কলেজ|college|মাদ্রাসা|বিদ্যালয়|ডিপিই|dpe"),
    "university": ("University jobs", r"বিশ্ববিদ্যালয়|ভার্সিটি|university", r"বিশ্ববিদ্যালয়|ভার্সিটি|university"),
    "police": ("Police jobs", r"পুলিশ|police|constable|কনস্টেবল|এসআই|sub.?inspector", r"পুলিশ|police|constable|কনস্টেবল|এসআই|sub.?inspector"),
    "army": ("Army / defence jobs", r"সেনা|আর্মি|army|নৌবাহিনী|navy|বিমান|air ?force|বিজিবি|bgb|bsf|crpf|cisf|defence|প্রতিরক্ষা|আনসার|ansar",
             r"সেনা|আর্মি|army|navy|নৌবাহিনী|বিমান|air ?force|বিজিবি|bgb|bsf|crpf|cisf|defence|প্রতিরক্ষা|আনসার|ansar"),
    "railway": ("Railway jobs", r"রেল|railway|rrb", r"রেল|railway|rrb"),
    "health": ("Health / medical jobs", r"স্বাস্থ্য|হাসপাতাল|নার্স|ডাক্তার|চিকিৎসক|medical|nurse|doctor|hospital|aiims|health|ফার্মাসি",
               r"স্বাস্থ্য|হাসপাতাল|নার্স|ডাক্তার|চিকিৎসক|medical|nurse|doctor|hospital|aiims|health|ফার্মাসি"),
    "ngo": ("NGO / development jobs", r"এনজিও|ngo|ব্র্যাক|brac|unicef|undp", r"এনজিও|ngo|ব্র্যাক|brac|unicef|undp|\bun\b|প্রকল্প|project"),
    "engineer": ("Engineering / technical jobs", r"ইঞ্জিনিয়ার|প্রকৌশল|engineer|ডিপ্লোমা|diploma|technician", r"ইঞ্জিনিয়ার|প্রকৌশল|engineer|ডিপ্লোমা|diploma|technician"),
    "it": ("IT jobs", r"আইটি|software|সফটওয়্যার|programmer|developer", r"আইটি|\bit\b|software|সফটওয়্যার|programmer|developer|কম্পিউটার"),
    "driver": ("Driver jobs", r"ড্রাইভার|চালক|driver", r"ড্রাইভার|চালক|driver"),
    "govt": ("Government jobs", r"সরকারি|govt|government|বিসিএস|bcs|bpsc|সচিবালয়|মন্ত্রণালয়|ministry|upsc|সরকারী",
             r"সরকারি|govt|government|বিসিএস|bcs|bpsc|সচিবালয়|মন্ত্রণালয়|ministry|upsc|ssc|অধিদপ্তর|অধিদফতর|পরিদপ্তর"),
    "private": ("Private company jobs", r"বেসরকারি|প্রাইভেট|private|কোম্পানি|company|গার্মেন্টস|garments", r"বেসরকারি|প্রাইভেট|private|কোম্পানি|company|গার্মেন্টস|garments|limited|লিমিটেড"),
}
_CAT_Q = {k: re.compile(v[1], re.I) for k, v in CATEGORIES.items()}
_CAT_T = {k: re.compile(v[2], re.I) for k, v in CATEGORIES.items()}


def question_category(q: str) -> str:
    """The job category the visitor asks about ('' if none or several different ones)."""
    found = [k for k, rx in _CAT_Q.items() if rx.search(q or "")]
    if len(found) > 1 and "govt" in found:
        found.remove("govt")  # "সরকারি ব্যাংক": the more specific category wins
    return found[0] if len(found) == 1 else ""


def in_category(title: str, cat: str) -> bool:
    return not cat or bool(_CAT_T[cat].search(title or ""))


def category_name(cat: str) -> str:
    return CATEGORIES[cat][0] if cat in CATEGORIES else ""


def prefer_category(hits: list[dict], cat: str) -> list[dict]:
    """Keep posts of the asked category (by title); other posts only when too few match."""
    if not cat:
        return hits
    same = [h for h in hits if in_category(h["title"], cat)]
    return same if len(same) >= 2 else hits
