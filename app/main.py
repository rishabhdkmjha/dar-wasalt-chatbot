from __future__ import annotations

import threading
from typing import Literal

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, llm, scraper
from .retriever import BM25Index, load_scraped, load_seed

app = FastAPI(title="DarGlobal & Wasalt Chatbot", version="1.0.0")
_lock = threading.Lock()
_index: BM25Index | None = None


def get_index() -> BM25Index:
    global _index
    with _lock:
        if _index is None:
            chunks = load_seed(config.SEED_FILE) + load_scraped(config.SCRAPED_FILE)
            _index = BM25Index(chunks)
        return _index


def reset_index() -> None:
    global _index
    with _lock:
        _index = None


class Msg(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[Msg] = []


class Source(BaseModel):
    title: str
    url: str
    company: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
    mode: Literal["llm", "retrieval-only"]
    model: str | None = None


@app.get("/api/health")
def health():
    idx = get_index()
    return {
        "status": "ok",
        "chunks": len(idx.chunks),
        "llm_configured": bool(config.OPENROUTER_API_KEY),
        "model": config.OPENROUTER_MODEL,
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    idx = get_index()
    hits = idx.search(req.message, k=config.TOP_K)
    if not hits:
        return ChatResponse(
            answer="I couldn't find anything about that in the collected DarGlobal and Wasalt data. "
                   "Try asking about their projects, services, markets or history.",
            sources=[], mode="retrieval-only",
        )

    seen, sources = set(), []
    for _, c in hits:
        if c.url not in seen:
            seen.add(c.url)
            sources.append(Source(title=c.title, url=c.url, company=c.company))

    history = [m.model_dump() for m in req.history]
    try:
        answer, model = await llm.ask(req.message, hits, history)
        return ChatResponse(answer=answer, sources=sources, mode="llm", model=model)
    except llm.LLMError as e:
        # Graceful degradation: still useful without the LLM.
        top = "\n\n".join(f"• {c.text[:350]}…" for _, c in hits[:3])
        note = ("(LLM unavailable — showing the most relevant passages instead.)"
                if config.OPENROUTER_API_KEY else
                "(No OPENROUTER_API_KEY configured — showing the most relevant passages instead.)")
        print(f"[llm-fallback] {e}")
        return ChatResponse(answer=f"{note}\n\n{top}", sources=sources, mode="retrieval-only")


@app.post("/api/refresh")
def refresh(x_refresh_token: str = Header(default="")):
    """Re-scrape both sites and rebuild the index. Disabled unless REFRESH_TOKEN is set."""
    if not config.REFRESH_TOKEN or x_refresh_token != config.REFRESH_TOKEN:
        raise HTTPException(status_code=403, detail="forbidden")
    n = scraper.run(max_pages=30)
    reset_index()
    return {"documents_scraped": n, "chunks": len(get_index().chunks)}


@app.get("/")
def home():
    return FileResponse(config.STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")
