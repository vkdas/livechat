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
CHAT_MODEL = os.getenv("CHAT_MODEL", "gemini-2.5-flash")
EMBED_MODEL = os.getenv("EMBED_MODEL", "gemini-embedding-001")
EMBED_DIM = _int("EMBED_DIM", 768)

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
MAX_IMAGES_PER_POST = _int("MAX_IMAGES_PER_POST", 5)
MAX_FILE_MB = _int("MAX_FILE_MB", 15)
OCR_IMAGES = os.getenv("OCR_IMAGES", "true").lower() == "true"
PDF_OCR = os.getenv("PDF_OCR", "auto").lower()  # auto | always | never
PDF_MAX_OCR_PAGES = _int("PDF_MAX_OCR_PAGES", 40)
MAX_CHUNKS_PER_DOC = _int("MAX_CHUNKS_PER_DOC", 300)

# Retrieval
CHUNK_CHARS = _int("CHUNK_CHARS", 1200)
CHUNK_OVERLAP = _int("CHUNK_OVERLAP", 150)
TOP_K = _int("TOP_K", 6)
MIN_SIM = _float("MIN_SIM", 0.35)

# Protection (free tier friendly)
RATE_LIMIT_PER_HOUR = _int("RATE_LIMIT_PER_HOUR", 20)
DAILY_CHAT_CAP = _int("DAILY_CHAT_CAP", 800)
