# DarGlobal & Wasalt Chatbot

A retrieval-augmented (RAG) chatbot that answers questions about **DarGlobal** (luxury real-estate developer) and **Wasalt** (Saudi AI real-estate platform), using public data and a **free OpenRouter model**. Dockerised, one-command deploy.

## What it does

```
 darglobal.co.uk ─┐                      ┌── user question
 wasalt.sa/blog  ─┼─► scraper ─► JSONL ─►│  BM25 retriever (top 5 chunks)
 curated seed .md ┘   (polite)           └─► OpenRouter free LLM (grounded prompt) ─► answer + sources
```

1. **Scrape** (`app/scraper.py`): crawls public pages of both sites (robots.txt respected, 1 req/s, same-domain only) plus Wasalt's public blog API. Output → `data/scraped.jsonl`. It runs automatically during `docker build`.
2. **Seed data** (`data/seed_knowledge.md`): a hand-curated snapshot with source URLs, so the bot works even if scraping is blocked.
3. **Retrieve** (`app/retriever.py`): chunks text (~140 words) and ranks with BM25 (no vector DB, no extra API, fast on free tiers).
4. **Generate** (`app/llm.py`): sends the top chunks + question to OpenRouter. The system prompt forces answers **only from the context**, with `[1]`-style citations, and "I don't know" when data is missing.
5. **Serve** (`app/main.py` + `static/index.html`): FastAPI backend and a single-page chat UI. If the LLM is down or no key is set, it degrades to showing the best passages (no crash).

Endpoints: `GET /` (UI), `POST /api/chat`, `GET /api/health`, `POST /api/refresh` (re-scrape; needs `REFRESH_TOKEN`).

## Run locally (no Docker)

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # put your OpenRouter key in .env
export $(grep -v '^#' .env | xargs)                    # Windows PowerShell: set vars manually
python -m app.scraper                                  # optional: fetch fresh data
uvicorn app.main:app --reload                          # http://localhost:8000
pytest -q                                              # run tests
```

## Run with Docker

```bash
cp .env.example .env        # add OPENROUTER_API_KEY
docker compose up --build   # http://localhost:8000
# or: docker build -t dar-wasalt-chatbot . && docker run -p 8000:8000 --env-file .env dar-wasalt-chatbot
```

## Deploy (free) and get your working URL

Get a free key first: https://openrouter.ai/keys

**Option A - Render (easiest, free web service)**
1. Push this folder to a GitHub repo (`.env` is git-ignored).
2. Render → New → Blueprint (or Web Service → Docker) → pick the repo (`render.yaml` is included).
3. Add env var `OPENROUTER_API_KEY`. Deploy → you get `https://<name>.onrender.com`.
   Free instances sleep when idle; open the URL once before the reviewer does.

**Option B - Hugging Face Spaces (Docker, always-on free CPU)**
1. New Space → SDK: Docker. Upload these files.
2. Add this front-matter at the top of the Space's README.md:
   ```
   ---
   title: DarGlobal Wasalt Chatbot
   sdk: docker
   app_port: 7860
   ---
   ```
3. Settings → Variables and secrets: add secret `OPENROUTER_API_KEY` and variable `PORT=7860`.
4. URL: `https://<user>-<space>.hf.space`

**Option C - Any VPS**: `docker compose up -d --build` behind Caddy/nginx.

## Config

| Variable | Purpose |
|---|---|
| `OPENROUTER_API_KEY` | required for LLM answers |
| `OPENROUTER_MODEL` | default `openrouter/free` (auto-picks a free model); or pin e.g. `...:free` |
| `OPENROUTER_FALLBACK_MODELS` | comma-separated, **only `:free` IDs** (paid fallbacks can bill you) |
| `REFRESH_TOKEN` | enables `POST /api/refresh` |

Free-model availability changes often: check https://openrouter.ai/models?pricing=free if a pinned model starts failing.

## Design notes / limitations

- BM25 instead of embeddings: no second API dependency, deterministic, good enough for a small corpus. Swapping in embeddings later only touches `retriever.py`.
- Scraping is static-HTML only; JS-rendered content on the sites may be missing, which is why the seed file exists.
- Figures differ across sources/dates (e.g. portfolio GDV); the prompt tells the model to flag conflicts.
- Free OpenRouter models are rate-limited; the app retries fallbacks and then degrades gracefully.
- Not financial advice; answers reflect collected public data only.
