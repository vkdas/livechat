import math
import re
from collections import Counter

import numpy as np

_TOKEN = re.compile(r"[^\s\.,;:!?()\[\]{}\"'“”‘’।|/\\\-–—_<>=+*#@&%$^~`]+")
_BN = re.compile(r"[ঀ-৿]")
_BN_SUFFIX = ("গুলোতে", "গুলোর", "গুলো", "গুলি", "দের", "ের", "কে", "তে", "রা", "টি", "টা", "র", "ে")


def has_bengali(text: str) -> bool:
    return bool(_BN.search(text))


def _stem(tok: str) -> str:
    if _BN.search(tok):
        for suf in _BN_SUFFIX:
            if tok.endswith(suf) and len(tok) - len(suf) >= 2:
                return tok[: -len(suf)]
    return tok


def tokenize(text: str) -> list[str]:
    return [_stem(t) for t in _TOKEN.findall(text.lower())]


class BM25:
    def __init__(self, docs_tokens, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.N = len(docs_tokens)
        self.dl = np.array([len(d) for d in docs_tokens], dtype=np.float32)
        self.avg = float(self.dl.mean()) if self.N else 0.0
        self.tf = [Counter(d) for d in docs_tokens]
        df = Counter()
        for c in self.tf:
            df.update(c.keys())
        self.idf = {t: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for t, n in df.items()}

    def scores(self, q_tokens) -> np.ndarray:
        s = np.zeros(self.N, dtype=np.float32)
        if not self.N:
            return s
        for t in set(q_tokens):
            idf = self.idf.get(t)
            if idf is None:
                continue
            for i, tf in enumerate(self.tf):
                f = tf.get(t)
                if f:
                    s[i] += idf * f * (self.k1 + 1) / (
                        f + self.k1 * (1 - self.b + self.b * self.dl[i] / (self.avg or 1))
                    )
        return s


def chunk_text(text: str, size: int = 1200, overlap: int = 150) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n+", text) if p.strip()]
    chunks: list[str] = []
    cur = ""
    for p in paras:
        while len(p) > size:
            cut = max(p.rfind("।", 0, size), p.rfind(". ", 0, size), p.rfind(" ", 0, size))
            if cut < size * 0.5:
                cut = size - 1
            piece, p = p[: cut + 1].strip(), p[cut + 1:].strip()
            if cur:
                chunks.append(cur)
                cur = ""
            if piece:
                chunks.append(piece)
        if not p:
            continue
        if len(cur) + len(p) + 1 <= size:
            cur = (cur + "\n" + p).strip()
        else:
            if cur:
                chunks.append(cur)
            cur = p
    if cur:
        chunks.append(cur)

    if overlap and len(chunks) > 1:
        out = [chunks[0]]
        for i in range(1, len(chunks)):
            tail = chunks[i - 1][-overlap:]
            tail = tail.split(" ", 1)[-1] if " " in tail else tail
            out.append(tail + "\n" + chunks[i])
        chunks = out
    return [c for c in chunks if len(c.strip()) >= 20]
