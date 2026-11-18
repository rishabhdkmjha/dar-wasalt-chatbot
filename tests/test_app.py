import pytest
from fastapi.testclient import TestClient

from app import config, llm, main
from app.retriever import BM25Index, chunk_text, load_seed, tokenize


def test_seed_loads_both_companies():
    chunks = load_seed(config.SEED_FILE)
    assert {c.company for c in chunks} == {"darglobal", "wasalt"}
    assert all(c.url.startswith("http") for c in chunks)


def test_chunking_overlap():
    text = " ".join(str(i) for i in range(400))
    parts = chunk_text(text, size=100, overlap=20)
    assert len(parts) >= 4 and parts[0].split()[-20:] == parts[1].split()[:20]


@pytest.mark.parametrize("q,company,needle", [
    ("Which luxury brands does Dar Global partner with?", "darglobal", "Lamborghini"),
    ("What is Wasalt Matchmaker?", "wasalt", "questionnaire"),
    ("Tell me about Tierra Viva villas", "darglobal", "53 villas"),
    ("Who is Wasalt's auction licence from?", "wasalt", "Infath"),
])
def test_retrieval_finds_right_passage(q, company, needle):
    idx = BM25Index(load_seed(config.SEED_FILE))
    hits = idx.search(q, k=3)
    assert hits and any(c.company == company and needle in c.text for _, c in hits)


def test_tokenize_drops_stopwords():
    assert "the" not in tokenize("the Wasalt app")


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(config, "OPENROUTER_API_KEY", "")
    main.reset_index()
    return TestClient(main.app)


def test_health(client):
    r = client.get("/api/health").json()
    assert r["status"] == "ok" and r["chunks"] > 10


def test_chat_retrieval_only_without_key(client):
    r = client.post("/api/chat", json={"message": "What is Wasalt?"}).json()
    assert r["mode"] == "retrieval-only" and r["sources"]


def test_chat_uses_llm_when_available(client, monkeypatch):
    async def fake(question, hits, history):
        return "Wasalt is a Saudi AI real-estate platform [1].", "fake/model:free"
    monkeypatch.setattr(llm, "ask", fake)
    r = client.post("/api/chat", json={"message": "What is Wasalt?"}).json()
    assert r["mode"] == "llm" and r["model"] == "fake/model:free"


def test_chat_validates_input(client):
    assert client.post("/api/chat", json={"message": ""}).status_code == 422


def test_refresh_requires_token(client):
    assert client.post("/api/refresh").status_code == 403


def test_homepage(client):
    r = client.get("/")
    assert r.status_code == 200 and "Assistant" in r.text
