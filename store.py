import hashlib
import json
import shutil
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from config import DATA_DIR, EMBED_DAILY_LIMIT, EMBED_DIM
from textutil import BM25, tokenize

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts(post_url TEXT PRIMARY KEY, hash TEXT, synced_at REAL);
CREATE TABLE IF NOT EXISTS chunks(
  id INTEGER PRIMARY KEY AUTOINCREMENT, post_url TEXT, doc_url TEXT,
  title TEXT, kind TEXT, text TEXT, emb BLOB);
CREATE INDEX IF NOT EXISTS idx_chunks_post ON chunks(post_url);
CREATE TABLE IF NOT EXISTS emb_cache(h TEXT PRIMARY KEY, emb BLOB);
CREATE TABLE IF NOT EXISTS quota(day TEXT PRIMARY KEY, used INTEGER);
CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY, value TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS feedback(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, question TEXT, answer TEXT,
  rating INTEGER, comment TEXT);
CREATE TABLE IF NOT EXISTS questions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, question TEXT, found INTEGER, cached INTEGER);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
"""


def chunk_hash(title: str, text: str) -> str:
    return hashlib.sha1(f"{title}\n{text}".encode("utf-8")).hexdigest()


def quota_day() -> str:
    """Google's free daily quotas reset at midnight Pacific time."""
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("America/Los_Angeles"))
    except Exception:
        now = datetime.now(timezone.utc) - timedelta(hours=8)
    return now.strftime("%Y-%m-%d")


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            # a saved copy shipped next to the code (index.db) seeds a fresh server
            for cand in (Path(__file__).resolve().parent / "index.db", Path.cwd() / "index.db"):
                if cand.exists():
                    shutil.copy(cand, path)
                    break
        self.path = path
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.lock = threading.RLock()
        with self.lock:
            self.db.executescript(SCHEMA)
            self.db.commit()
        self.version = 0
        self.matrix = np.zeros((0, EMBED_DIM), dtype=np.float32)
        self.has_emb = np.zeros(0, dtype=bool)
        self.meta: list[dict] = []
        self.bm25 = BM25([])
        self.reload()

    # ---------- index ----------
    def reload(self):
        with self.lock:
            rows = self.db.execute(
                "SELECT id, post_url, doc_url, title, kind, text, emb FROM chunks ORDER BY id"
            ).fetchall()
        zero = np.zeros(EMBED_DIM, dtype=np.float32)
        embs, has = [], []
        for r in rows:
            v = np.frombuffer(r[6], dtype=np.float32) if r[6] else None
            if v is not None and v.shape[0] == EMBED_DIM:
                embs.append(v)
                has.append(True)
            else:
                embs.append(zero)
                has.append(False)
        matrix = np.vstack(embs) if embs else np.zeros((0, EMBED_DIM), dtype=np.float32)
        meta = [
            dict(id=r[0], post_url=r[1], url=r[2], title=r[3], kind=r[4], text=r[5])
            for r in rows
        ]
        bm25 = BM25([tokenize(m["title"] + " " + m["text"]) for m in meta])
        with self.lock:
            self.matrix, self.has_emb, self.meta, self.bm25 = matrix, np.array(has, dtype=bool), meta, bm25
            self.version += 1

    def chunk_count(self) -> int:
        return len(self.meta)

    def embedded_count(self) -> int:
        return int(self.has_emb.sum())

    def post_hash(self, post_url):
        with self.lock:
            r = self.db.execute("SELECT hash FROM posts WHERE post_url=?", (post_url,)).fetchone()
        return r[0] if r else None

    def stash_post_embs(self, post_url):
        """Remember the vectors of a post's current chunks so unchanged text is never embedded twice."""
        with self.lock:
            rows = self.db.execute(
                "SELECT title, text, emb FROM chunks WHERE post_url=? AND emb IS NOT NULL", (post_url,)
            ).fetchall()
            self.db.executemany(
                "INSERT OR REPLACE INTO emb_cache(h, emb) VALUES (?,?)",
                [(chunk_hash(t, x), e) for t, x, e in rows])
            self.db.commit()

    def emb_cache_get(self, hashes: list[str]) -> dict:
        out = {}
        with self.lock:
            for i in range(0, len(hashes), 400):
                part = hashes[i:i + 400]
                q = ",".join("?" * len(part))
                for h, e in self.db.execute(f"SELECT h, emb FROM emb_cache WHERE h IN ({q})", part):
                    v = np.frombuffer(e, dtype=np.float32)
                    if v.shape[0] == EMBED_DIM:
                        out[h] = v
        return out

    def replace_post(self, post_url, hash_, chunks):
        """chunks: list of dict(url, title, kind, text, emb: np.ndarray | None)"""
        with self.lock:
            cur = self.db.cursor()
            cur.execute("DELETE FROM chunks WHERE post_url=?", (post_url,))
            cur.executemany(
                "INSERT INTO chunks(post_url, doc_url, title, kind, text, emb) VALUES (?,?,?,?,?,?)",
                [
                    (post_url, c["url"], c["title"], c["kind"], c["text"],
                     None if c.get("emb") is None else np.asarray(c["emb"], dtype=np.float32).tobytes())
                    for c in chunks
                ],
            )
            cur.execute(
                "INSERT OR REPLACE INTO posts(post_url, hash, synced_at) VALUES (?,?,?)",
                (post_url, hash_, time.time()),
            )
            self.db.commit()

    def delete_posts_not_in(self, urls: set) -> int:
        with self.lock:
            existing = [r[0] for r in self.db.execute("SELECT post_url FROM posts")]
            gone = [u for u in existing if u not in urls]
            for u in gone:
                self.db.execute("DELETE FROM chunks WHERE post_url=?", (u,))
                self.db.execute("DELETE FROM posts WHERE post_url=?", (u,))
            self.db.commit()
        return len(gone)

    def post_count(self) -> int:
        with self.lock:
            return self.db.execute("SELECT COUNT(*) FROM posts").fetchone()[0]

    # ---------- embeddings that are still missing ----------
    def pending_count(self) -> int:
        with self.lock:
            return self.db.execute("SELECT COUNT(*) FROM chunks WHERE emb IS NULL").fetchone()[0]

    def pending_chunks(self, limit: int):
        """Oldest id first = newest posts first (the blog feed is newest first)."""
        with self.lock:
            return self.db.execute(
                "SELECT id, title, text FROM chunks WHERE emb IS NULL ORDER BY id LIMIT ?", (limit,)
            ).fetchall()

    def set_embeddings(self, ids, vecs):
        with self.lock:
            self.db.executemany(
                "UPDATE chunks SET emb=? WHERE id=?",
                [(np.asarray(v, dtype=np.float32).tobytes(), i) for i, v in zip(ids, vecs)])
            self.db.commit()

    # ---------- daily embedding quota (Google free tier) ----------
    def embed_used(self) -> int:
        with self.lock:
            r = self.db.execute("SELECT used FROM quota WHERE day=?", (quota_day(),)).fetchone()
        return int(r[0]) if r else 0

    def add_embed_used(self, n: int):
        with self.lock:
            self.db.execute(
                "INSERT INTO quota(day, used) VALUES (?, ?) ON CONFLICT(day) DO UPDATE SET used = used + ?",
                (quota_day(), n, n))
            self.db.commit()

    def set_embed_used(self, n: int):
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO quota(day, used) VALUES (?, ?)", (quota_day(), n))
            self.db.commit()

    def embed_available(self) -> bool:
        return self.embedded_count() > 0 and self.embed_used() < EMBED_DAILY_LIMIT

    # ---------- search ----------
    def search(self, qvec, qtext, k=6):
        """Keyword (BM25) search always works; meaning-based search is added when vectors exist."""
        with self.lock:
            n = len(self.meta)
            if n == 0:
                return []
            kw = self.bm25.scores(tokenize(qtext))
            scores: dict[int, float] = {}
            sem = None
            if qvec is not None and self.has_emb.any():
                sem = np.where(self.has_emb, self.matrix @ qvec, -1.0)
                for r, i in enumerate([i for i in np.argsort(-sem)[:20] if sem[i] > -1.0]):
                    scores[i] = scores.get(i, 0.0) + 1.0 / (60 + r)
            for r, i in enumerate([i for i in np.argsort(-kw)[:20] if kw[i] > 0]):
                scores[i] = scores.get(i, 0.0) + 1.0 / (60 + r)
            best = sorted(scores, key=scores.get, reverse=True)[:k]
            return [
                dict(self.meta[i],
                     sem=float(sem[i]) if sem is not None and sem[i] > -1.0 else 0.0,
                     kw=float(kw[i]))
                for i in best
            ]

    # ---------- backup ----------
    def snapshot(self) -> Path:
        """A small copy of the index (no chat logs) that can be put next to the code as index.db."""
        out = self.path.parent / "snapshot.db"
        out.unlink(missing_ok=True)
        dst = sqlite3.connect(str(out))
        with self.lock:
            self.db.backup(dst)
        dst.executescript(
            "DELETE FROM cache; DELETE FROM questions; DELETE FROM feedback; "
            "DELETE FROM quota; DELETE FROM meta; DELETE FROM emb_cache;")
        dst.commit()
        dst.execute("VACUUM")
        dst.close()
        return out

    # ---------- cache / logs ----------
    def cache_get(self, key):
        with self.lock:
            r = self.db.execute("SELECT value FROM cache WHERE key=?", (key,)).fetchone()
        return json.loads(r[0]) if r else None

    def cache_put(self, key, value):
        with self.lock:
            self.db.execute(
                "INSERT OR REPLACE INTO cache(key, value, ts) VALUES (?,?,?)",
                (key, json.dumps(value, ensure_ascii=False), time.time()),
            )
            self.db.commit()

    def log_question(self, question, found, cached):
        with self.lock:
            self.db.execute(
                "INSERT INTO questions(ts, question, found, cached) VALUES (?,?,?,?)",
                (time.time(), question[:500], int(found), int(cached)),
            )
            self.db.commit()

    def add_feedback(self, question, answer, rating, comment=""):
        with self.lock:
            self.db.execute(
                "INSERT INTO feedback(ts, question, answer, rating, comment) VALUES (?,?,?,?,?)",
                (time.time(), question[:500], answer[:3000], int(rating), comment[:500]),
            )
            self.db.commit()

    def set_meta(self, key, value):
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?,?)", (key, str(value)))
            self.db.commit()

    def get_meta(self, key, default=None):
        with self.lock:
            r = self.db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return r[0] if r else default

    def stats(self):
        since = time.time() - 30 * 86400
        with self.lock:
            q = self.db.execute
            top = q(
                "SELECT question, COUNT(*) c FROM questions WHERE ts>? GROUP BY question "
                "ORDER BY c DESC LIMIT 20", (since,)).fetchall()
            unanswered = q(
                "SELECT question, COUNT(*) c FROM questions WHERE ts>? AND found=0 GROUP BY question "
                "ORDER BY c DESC LIMIT 30", (since,)).fetchall()
            total = q("SELECT COUNT(*) FROM questions WHERE ts>?", (since,)).fetchone()[0]
            up = q("SELECT COUNT(*) FROM feedback WHERE rating>0").fetchone()[0]
            down = q("SELECT COUNT(*) FROM feedback WHERE rating<0").fetchone()[0]
            bad = q(
                "SELECT question, answer, comment FROM feedback WHERE rating<0 "
                "ORDER BY ts DESC LIMIT 15").fetchall()
        return {
            "posts": self.post_count(),
            "chunks": self.chunk_count(),
            "embedded": self.embedded_count(),
            "pending": self.pending_count(),
            "embed_used": self.embed_used(),
            "embed_limit": EMBED_DAILY_LIMIT,
            "last_sync": self.get_meta("last_sync"),
            "last_sync_result": self.get_meta("last_sync_result"),
            "last_chat_error": self.get_meta("last_chat_error"),
            "questions_30d": total,
            "top_questions": [{"q": a, "count": b} for a, b in top],
            "unanswered": [{"q": a, "count": b} for a, b in unanswered],
            "feedback": {"up": up, "down": down},
            "recent_downvotes": [{"q": a, "answer": b, "comment": c} for a, b, c in bad],
        }


store = Store(DATA_DIR / "index.db")
