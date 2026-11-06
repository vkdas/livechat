import hmac
import logging
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

import rag, sync
from config import (ADMIN_TOKEN, ALLOWED_ORIGINS, APP_NAME, BLOG_URL, DAILY_CHAT_CAP,
                     RATE_LIMIT_PER_HOUR)
from store import store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
STATIC = Path(__file__).parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=sync.loop, daemon=True).start()
    yield


app = FastAPI(title=APP_NAME, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or ["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ---------- rate limiting ----------
_hits: dict[str, deque] = defaultdict(deque)
_daily = {"d": None, "n": 0}
_rl_lock = threading.Lock()


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?")


def check_rate(ip: str):
    now = time.time()
    with _rl_lock:
        today = time.strftime("%Y-%m-%d", time.gmtime())
        if _daily["d"] != today:
            _daily.update(d=today, n=0)
        if _daily["n"] >= DAILY_CHAT_CAP:
            raise HTTPException(429, "আজকের জন্য প্রশ্নের সীমা শেষ। আগামীকাল আবার চেষ্টা করুন।")
        q = _hits[ip]
        while q and now - q[0] > 3600:
            q.popleft()
        if len(q) >= RATE_LIMIT_PER_HOUR:
            raise HTTPException(429, "এক ঘণ্টায় অনেক প্রশ্ন করা হয়েছে। একটু পরে আবার চেষ্টা করুন।")
        q.append(now)
        _daily["n"] += 1


# ---------- models ----------
class Msg(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=1500)


class ChatIn(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    history: list[Msg] = Field(default_factory=list, max_length=12)


class FeedbackIn(BaseModel):
    question: str = Field(max_length=500)
    answer: str = Field(max_length=3000)
    rating: Literal[1, -1]
    comment: str = Field(default="", max_length=500)


def admin_auth(authorization: str = Header(default=""), token: str = Query(default="")):
    if not ADMIN_TOKEN:
        raise HTTPException(403, "ADMIN_TOKEN সেট করা নেই")
    supplied = authorization.removeprefix("Bearer ").strip() or token
    if not hmac.compare_digest(supplied, ADMIN_TOKEN):
        raise HTTPException(401, "ভুল টোকেন")


# ---------- routes ----------
@app.get("/")
def root():
    return {"name": APP_NAME, "site": BLOG_URL, "chunks": store.chunk_count(),
            "embed": '<script src="THIS_SERVER/widget.js" defer></script>'}


@app.get("/health")
def health():
    return {"ok": True, "chunks": store.chunk_count(), "syncing": sync.state["running"],
            "last_sync": store.get_meta("last_sync")}


@app.post("/chat")
def chat(body: ChatIn, request: Request):
    check_rate(client_ip(request))
    sync.maybe_run_async()
    history = [m.model_dump() for m in body.history]
    try:
        return rag.ask(body.question, history)
    except Exception as exc:
        logging.getLogger("chat").exception("chat failed")
        store.set_meta("last_chat_error",
                       time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()) + " UTC | " + repr(exc)[:500])
        raise HTTPException(503, "এই মুহূর্তে উত্তর দিতে পারছি না। একটু পরে আবার চেষ্টা করুন।")


@app.post("/feedback")
def feedback(body: FeedbackIn):
    store.add_feedback(body.question, body.answer, body.rating, body.comment)
    return {"ok": True}


@app.get("/widget.js")
def widget():
    return FileResponse(STATIC / "widget.js", media_type="application/javascript",
                        headers={"Cache-Control": "public, max-age=300"})


@app.get("/avatar")
def avatar():
    for name in ("avatar.jpg", "avatar.jpeg", "avatar.png", "avatar.webp"):
        p = STATIC / name
        if p.exists():
            return FileResponse(p, headers={"Cache-Control": "public, max-age=3600"})
    raise HTTPException(404, "no avatar")


@app.get("/admin")
def admin_page():
    return FileResponse(STATIC / "admin.html")


@app.get("/admin/stats", dependencies=[Depends(admin_auth)])
def admin_stats():
    return store.stats()


@app.post("/admin/reindex", dependencies=[Depends(admin_auth)])
def admin_reindex(force: bool = False):
    if sync.state["running"]:
        return JSONResponse({"started": False, "reason": "already running"})
    sync.run_async(force)
    return {"started": True, "force": force}
