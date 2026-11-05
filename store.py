import json
import sqlite3
import threading
import time

import numpy as np

from .config import DATA_DIR, EMBED_DIM
from .textutil import BM25, tokenize

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts(post_url TEXT PRIMARY KEY, hash TEXT, synced_at REAL);
CREATE TABLE IF NOT EXISTS chunks(
  id INTEGER PRIMARY KEY AUTOINCREMENT, post_url TEXT, doc_url TEXT,
  title TEXT, kind TEXT, text TEXT, emb BLOB);
CREATE INDEX IF NOT EXISTS idx_chunks_post ON chunks(post_url);
CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY, value TEXT, ts REAL);
CREATE TABLE IF NOT EXISTS feedback(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, question TEXT, answer TEXT,
  rating INTEGER, comment TEXT);
CREATE TABLE IF NOT EXISTS questions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, question TEXT, found INTEGER, cached INTEGER);
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
"""


class Store:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.lock = threading.RLock()
        with self.lock:
            self.db.executescript(SCHEMA)
            self.db.commit()
        self.version = 0
        self.matrix = np.zeros((0, EMBED_DIM), dtype=np.float32)
        self.meta: list[dict] = []
        self.bm25 = BM25([])
        self.reload()

    # ---------- index ----------
    def reload(self):
        with self.lock:
            rows = self.db.execute(
                "SELECT id, post_url, doc_url, title, kind, text, emb FROM chunks"
            ).fetchall()
        embs = [np.frombuffer(r[6], dtype=np.float32) for r in rows]
        matrix = np.vstack(embs) if embs else np.zeros((0, EMBED_DIM), dtype=np.float32)
        meta = [
            dict(id=r[0], post_url=r[1], url=r[2], title=r[3], kind=r[4], text=r[5])
            for r in rows
        ]
        bm25 = BM25([tokenize(m["title"] + " " + m["text"]) for m in meta])
        with self.lock:
            self.matrix, self.meta, self.bm25 = matrix, meta, bm25
            self.version += 1

    def chunk_count(self) -> int:
        return len(self.meta)

    def post_hash(self, post_url):
        with self.lock:
            r = self.db.execute("SELECT hash FROM posts WHERE post_url=?", (post_url,)).fetchone()
        return r[0] if r else None

    def replace_post(self, post_url, hash_, chunks):
        """chunks: list of dict(url, title, kind, text, emb: np.ndarray)"""
        with self.lock:
            cur = self.db.cursor()
            cur.execute("DELETE FROM chunks WHERE post_url=?", (post_url,))
            cur.executemany(
                "INSERT INTO chunks(post_url, doc_url, title, kind, text, emb) VALUES (?,?,?,?,?,?)",
                [
                    (post_url, c["url"], c["title"], c["kind"], c["text"],
                     np.asarray(c["emb"], dtype=np.float32).tobytes())
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

    # ---------- search ----------
    def search(self, qvec, qtext, k=6):
        with self.lock:
            n = len(self.meta)
            if n == 0:
                return []
            sem = self.matrix @ qvec
            kw = self.bm25.scores(tokenize(qtext))
            sem_rank = list(np.argsort(-sem)[:20])
            kw_rank = [i for i in np.argsort(-kw)[:20] if kw[i] > 0]
            scores: dict[int, float] = {}
            for r, i in enumerate(sem_rank):
                scores[i] = scores.get(i, 0.0) + 1.0 / (60 + r)
            for r, i in enumerate(kw_rank):
                scores[i] = scores.get(i, 0.0) + 1.0 / (60 + r)
            best = sorted(scores, key=scores.get, reverse=True)[:k]
            return [dict(self.meta[i], sem=float(sem[i]), kw=float(kw[i])) for i in best]

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
            "last_sync": self.get_meta("last_sync"),
            "last_sync_result": self.get_meta("last_sync_result"),
            "questions_30d": total,
            "top_questions": [{"q": a, "count": b} for a, b in top],
            "unanswered": [{"q": a, "count": b} for a, b in unanswered],
            "feedback": {"up": up, "down": down},
            "recent_downvotes": [{"q": a, "answer": b, "comment": c} for a, b, c in bad],
        }


store = Store(DATA_DIR / "index.db")
