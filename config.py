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
MAX_FILES_PER_POST = _int("MAX_FILES_PER_POST", 20)
MAX_IMAGES_PER_POST = _int("MAX_IMAGES_PER_POST", 10)
# posts that already have this much text skip image OCR (saves a lot of free quota)
OCR_SKIP_IF_TEXT_CHARS = _int("OCR_SKIP_IF_TEXT_CHARS", 0)
MAX_FILE_MB = _int("MAX_FILE_MB", 25)
LINKED_PAGES = os.getenv("LINKED_PAGES", "true").lower() == "true"
MAX_LINKED_PER_POST = _int("MAX_LINKED_PER_POST", 20)
WEB_FALLBACK = os.getenv("WEB_FALLBACK", "true").lower() == "true"
OCR_IMAGES = os.getenv("OCR_IMAGES", "true").lower() == "true"
PDF_OCR = os.getenv("PDF_OCR", "auto").lower()  # auto | always | never
PDF_MAX_OCR_PAGES = _int("PDF_MAX_OCR_PAGES", 40)
MAX_CHUNKS_PER_DOC = _int("MAX_CHUNKS_PER_DOC", 600)

# Retrieval
CHUNK_CHARS = _int("CHUNK_CHARS", 1800)
CHUNK_OVERLAP = _int("CHUNK_OVERLAP", 120)
TOP_K = _int("TOP_K", 6)
MIN_SIM = _float("MIN_SIM", 0.35)

# Protection (free tier friendly)
RATE_LIMIT_PER_HOUR = _int("RATE_LIMIT_PER_HOUR", 0)
DAILY_CHAT_CAP = _int("DAILY_CHAT_CAP", 0)

# 0 = no limit

# Other free AI companies, used in this order when every Gemini key is exhausted or blocked.
# Any OpenAI-compatible service works. A provider is active only if its key is set.
def _provider(name, key_env, url, model_env, model):
    key = os.getenv(key_env, "").strip()
    return dict(name=name, key=key, url=os.getenv(name.upper() + "_BASE_URL", url).rstrip("/"),
                model=os.getenv(model_env, model)) if key else None


PROVIDERS = [p for p in (
    _provider("groq", "GROQ_API_KEY", "https://api.groq.com/openai/v1", "GROQ_MODEL", "openai/gpt-oss-120b"),
    _provider("mistral", "MISTRAL_API_KEY", "https://api.mistral.ai/v1", "MISTRAL_MODEL", "mistral-large-latest"),
    _provider("nvidia", "NVIDIA_API_KEY", "https://integrate.api.nvidia.com/v1", "NVIDIA_MODEL",
              "nvidia/nemotron-3-ultra-550b-a55b"),
    _provider("openrouter", "OPENROUTER_API_KEY", "https://openrouter.ai/api/v1", "OPENROUTER_MODEL",
              "nvidia/nemotron-3-ultra-550b-a55b:free"),
    _provider("custom", "FALLBACK_API_KEY", "https://api.groq.com/openai/v1", "FALLBACK_MODEL", "openai/gpt-oss-120b"),
) if p]

OCR_FALLBACK_MODEL = os.getenv("OCR_FALLBACK_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")  # Groq vision model for images

LINKED_MAX_CHARS = _int("LINKED_MAX_CHARS", 400000)   # text kept from one linked page / PDF
PDF_VISION_PAGES = _int("PDF_VISION_PAGES", 15)       # pages of a scanned PDF read by the vision fallback
VISION_DAILY_LIMIT = _int("VISION_DAILY_LIMIT", 600)  # image reads per day, so chat keeps part of the free quota
MAX_RETRIES = _int("MAX_RETRIES", 30)                  # a post with a temporary failure is tried again on later syncs

# Free fallback providers allow only a few thousand tokens per minute: send them a smaller context
ALT_MAX_HITS = _int("ALT_MAX_HITS", 4)
ALT_CHUNK_CHARS = _int("ALT_CHUNK_CHARS", 1000)
VISION_PAUSE_SEC = _int("VISION_PAUSE_SEC", 8)   # pause between image reads so chat keeps its share of the per-minute limit
