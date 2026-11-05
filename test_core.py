import numpy as np
from app import extract, llm, rag
from app.store import store
from app.textutil import BM25, chunk_text, tokenize


def test_chunking_respects_size_and_keeps_text():
    text = "\n".join(f"এটি একটি পরীক্ষামূলক বাক্য নম্বর {i}।" for i in range(200))
    chunks = chunk_text(text, size=500, overlap=50)
    assert len(chunks) > 5
    assert all(len(c) <= 500 + 60 for c in chunks)
    assert "নম্বর 199" in "".join(chunks)


def test_bengali_bm25_matches_suffix_variants():
    docs = ["চাকরির আবেদনের নিয়ম জানুন", "আজকের আবহাওয়া ভালো", "ব্যাংকে চাকরি সার্কুলার"]
    bm = BM25([tokenize(d) for d in docs])
    s = bm.scores(tokenize("চাকরির"))
    assert s[0] > 0 and s[2] > 0 and s[1] == 0


def test_only_own_site_files_and_images_are_collected():
    html = ('<p>Notice <a href="/files/a.pdf">download</a> '
            '<a href="https://example.org/info">details</a> '
            '<a href="https://example.org/other.pdf">outside pdf</a> '
            '<a href="https://www.bdjobsinfo.com/files/b.pdf">www pdf</a> '
            '<a href="https://facebook.com/x">fb</a></p>'
            '<img src="https://blogger.googleusercontent.com/img/s320/pic.jpg">'
            '<img src="https://evil.example.net/banner.jpg">'
            '<a href="https://drive.google.com/file/d/ABC123/view">drive</a>')
    text, links, imgs = extract.html_to_text(html, "https://bdjobsinfo.com/p/x.html", keep_links=True)
    assert "https://bdjobsinfo.com/files/a.pdf" in text
    urls = [a.url for a in extract.find_attachments(links, imgs, "https://bdjobsinfo.com/p/x.html")]
    assert "https://bdjobsinfo.com/files/a.pdf" in urls
    assert "https://www.bdjobsinfo.com/files/b.pdf" in urls
    assert any("blogger.googleusercontent.com" in u and "/s1600/" in u for u in urls)
    assert not any("example" in u or "facebook" in u or "drive.google" in u for u in urls)


def test_host_allowlist():
    assert extract.is_own_host("bdjobsinfo.com") and extract.is_own_host("www.bdjobsinfo.com")
    assert not extract.is_own_host("evilbdjobsinfo.com") and not extract.is_own_host("bdjobsinfo.com.evil.io")
    assert not extract.is_own_host("drive.google.com")
    assert extract.is_own_media_host("1.bp.blogspot.com")
    assert not extract.is_own_media_host("example.org")


def test_net_get_blocks_foreign_host_before_connecting():
    import pytest
    from app import net
    with pytest.raises(ValueError, match="host not allowed"):
        net.get("https://example.org/a.pdf", allow=extract.is_own_host)


def _fake_embed(texts, query=False):
    rng = np.random.default_rng(abs(hash(texts[0])) % (2 ** 32))
    v = rng.normal(size=(len(texts), 768)).astype(np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def _seed():
    vecs = _fake_embed(["x", "y"])
    store.replace_post("https://bdjobsinfo.com/a", "h1", [
        dict(url="https://bdjobsinfo.com/a", title="ব্যাংক চাকরি", kind="post",
             text="ব্যাংকে চাকরির আবেদনের শেষ তারিখ ১০ ডিসেম্বর", emb=vecs[0]),
        dict(url="https://bdjobsinfo.com/b", title="রান্না", kind="post",
             text="খিচুড়ি রান্নার রেসিপি", emb=vecs[1]),
    ])
    store.reload()


def test_rag_found_not_found_and_cache(monkeypatch):
    _seed()
    calls = {"gen": 0}
    monkeypatch.setattr(llm, "embed", lambda t, query=False: store.matrix[:1].copy())

    def fake_gen(q, hist, hits):
        calls["gen"] += 1
        return llm.Answer(found=True, answer="শেষ তারিখ ১০ ডিসেম্বর [1]", used_sources=[1], followups=["আবেদন ফি কত?"])

    monkeypatch.setattr(llm, "generate_answer", fake_gen)
    r = rag.ask("ব্যাংকে চাকরির শেষ তারিখ কবে?", [])
    assert r["found"] and r["sources"][0]["url"].startswith("https://bdjobsinfo.com")
    r2 = rag.ask("ব্যাংকে চাকরির শেষ তারিখ কবে?", [])
    assert r2 == r and calls["gen"] == 1  # cached, no second LLM call

    monkeypatch.setattr(llm, "generate_answer",
                        lambda q, h, hits: llm.Answer(found=False, answer="", used_sources=[], followups=[]))
    nf = rag.ask("মঙ্গল গ্রহে কি পানি আছে", [{"role": "user", "content": "হ্যালো"}])
    assert nf["found"] is False and nf["sources"] == []


def test_not_found_message_follows_visitor_script():
    assert rag.detect_lang("চাকরির খবর কী?") == "bn"
    assert rag.detect_lang("नौकरी कब है?") == "hi"
    assert rag.detect_lang("متى الموعد؟") == "ar"
    assert rag.detect_lang("when is the deadline") == "en"
    assert "Sorry" in rag._not_found("hello")["answer"]
