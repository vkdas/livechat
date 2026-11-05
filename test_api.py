from fastapi.testclient import TestClient


def test_api_endpoints(monkeypatch):
    from app import main, sync
    monkeypatch.setattr(sync, "loop", lambda: None)
    monkeypatch.setattr(sync, "maybe_run_async", lambda: None)
    monkeypatch.setattr(main.rag, "ask", lambda q, h: {"found": True, "answer": "ok", "sources": [], "followups": []})
    c = TestClient(main.app)
    assert c.get("/health").json()["ok"]
    assert c.post("/chat", json={"question": "hi"}).json()["answer"] == "ok"
    assert c.post("/chat", json={"question": ""}).status_code == 422
    assert c.post("/feedback", json={"question": "q", "answer": "a", "rating": 1}).json()["ok"]
    assert c.get("/widget.js").status_code == 200
    assert c.get("/admin/stats").status_code == 401
    assert c.get("/admin/stats", headers={"Authorization": "Bearer secret"}).json()["feedback"]["up"] == 1
