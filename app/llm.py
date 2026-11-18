"""OpenRouter client (OpenAI-compatible chat completions) with free-model fallbacks."""
from __future__ import annotations

import httpx

from . import config

SYSTEM_PROMPT = """You are the assistant for a demo chatbot about two companies:
- DarGlobal (Dar Global PLC): London-listed luxury international real-estate developer, international arm of Saudi Dar Al Arkan.
- Wasalt: Saudi Arabia's AI-powered real-estate platform (listings, projects, auctions, matchmaker, broker app).

Rules:
1. Answer ONLY from the numbered CONTEXT passages provided with each question.
2. If the context does not contain the answer, say you don't have that information in the collected data. Never guess or invent figures, prices, dates or names.
3. Be concise (2-6 sentences, or a short list). Cite passages inline like [1], [2].
4. Reply in the same language the user wrote in.
5. Figures can differ between sources and dates; if passages disagree, mention both and the source.
6. You are not a financial adviser; do not give investment advice."""


def build_context(hits) -> str:
    parts = []
    for i, (_, c) in enumerate(hits, 1):
        parts.append(f"[{i}] ({c.company}) {c.title}\nURL: {c.url}\n{c.text}")
    return "\n\n".join(parts)


class LLMError(RuntimeError):
    pass


async def ask(question: str, hits, history: list[dict]) -> tuple[str, str]:
    """Returns (answer, model_used). Raises LLMError if every model fails."""
    if not config.OPENROUTER_API_KEY:
        raise LLMError("OPENROUTER_API_KEY not set")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += history[-config.MAX_HISTORY :]
    messages.append(
        {"role": "user", "content": f"CONTEXT:\n{build_context(hits)}\n\nQUESTION: {question}"}
    )

    models = [config.OPENROUTER_MODEL, *config.FALLBACK_MODELS]
    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": config.SITE_URL,
        "X-Title": "DarGlobal-Wasalt Chatbot",
    }
    last_err = "unknown error"
    async with httpx.AsyncClient(timeout=60) as client:
        for model in models:
            try:
                r = await client.post(
                    config.OPENROUTER_URL,
                    headers=headers,
                    json={"model": model, "messages": messages, "temperature": 0.2, "max_tokens": 600},
                )
                if r.status_code != 200:
                    last_err = f"{model}: HTTP {r.status_code} {r.text[:200]}"
                    continue
                data = r.json()
                text = (data["choices"][0]["message"].get("content") or "").strip()
                if text:
                    return text, data.get("model", model)
                last_err = f"{model}: empty response"
            except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
                last_err = f"{model}: {e!r}"
    raise LLMError(last_err)
