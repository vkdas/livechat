import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _int(name, default):
    return int(os.getenv(name, str(default)))


def _float(name, default):
    return float(os.getenv(name, str(default)))


APP_NAME = os.getenv("APP_NAME", "LIVE CHAT")
BLOG_URL = os.getenv("BLOG_URL", "https://bdjobsinfo.com").rstrip("/")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# More keys (each from a DIFFERENT Google project, quotas are per project): GEMINI_API_KEY_2, _3 ... or GEMINI_API_KEYS=a,b,c
GEMINI_API_KEYS = list(dict.fromkeys(
    [k.strip() for k in [GEMINI_API_KEY] + os.getenv("GEMINI_API_KEYS", "").split(",")
     + [os.getenv(f"GEMINI_API_KEY_{i}", "") for i in range(2, 11)] if k and k.strip()]))
CHAT_MODEL = os.getenv("CHAT_MODEL", "gemini-3.8-flash")
CHAT_FALLBACK_MODEL = os.getenv("CHAT_FALLBACK_MODEL", "gemini-3.5-flash-lite")
OCR_MODEL = os.getenv("OCR_MODEL", "gemini-3.5-flash-lite")
EMBED_MODEL = os.getenv("EMBED_MODEL", "gemini-embedding-001")
EMBED_DIM = _int("EMBED_DIM", 768)
# auto = keyword search first, meaning-based vectors added within the free daily quota; off = keyword search only
EMBEDDINGS = os.getenv("EMBEDDINGS", "auto").lower()
EMBED_DAILY_LIMIT = _int("EMBED_DAILY_LIMIT", 1000 * max(1, len(GEMINI_API_KEYS)))   # Google free tier: embedding requests per day
EMBED_CHAT_RESERVE = _int("EMBED_CHAT_RESERVE", 150)  # kept free for visitors' questions

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
ALLOWED_ORIGINS = [
    o.strip().rstrip("/")
    for o in os.getenv("ALLOWED_ORIGINS", BLOG_URL).split(",")
    if o.strip()
]
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))

# Sync / crawl
SYNC_INTERVAL_MIN = _int("SYNC_INTERVAL_MIN", 60)
MAX_FILES_PER_POST = _int("MAX_FILES_PER_POST", 5)
MAX_IMAGES_PER_POST = _int("MAX_IMAGES_PER_POST", 3)
# posts that already have this much text skip image OCR (saves a lot of free quota)
OCR_SKIP_IF_TEXT_CHARS = _int("OCR_SKIP_IF_TEXT_CHARS", 800)
MAX_FILE_MB = _int("MAX_FILE_MB", 15)
LINKED_PAGES = os.getenv("LINKED_PAGES", "true").lower() == "true"
MAX_LINKED_PER_POST = _int("MAX_LINKED_PER_POST", 3)
WEB_FALLBACK = os.getenv("WEB_FALLBACK", "true").lower() == "true"
OCR_IMAGES = os.getenv("OCR_IMAGES", "true").lower() == "true"
PDF_OCR = os.getenv("PDF_OCR", "auto").lower()  # auto | always | never
PDF_MAX_OCR_PAGES = _int("PDF_MAX_OCR_PAGES", 40)
MAX_CHUNKS_PER_DOC = _int("MAX_CHUNKS_PER_DOC", 150)

# Retrieval
CHUNK_CHARS = _int("CHUNK_CHARS", 1800)
CHUNK_OVERLAP = _int("CHUNK_OVERLAP", 120)
TOP_K = _int("TOP_K", 6)
MIN_SIM = _float("MIN_SIM", 0.35)

# Protection (free tier friendly)
RATE_LIMIT_PER_HOUR = _int("RATE_LIMIT_PER_HOUR", 0)
DAILY_CHAT_CAP = _int("DAILY_CHAT_CAP", 0)

# 0 = no limit
