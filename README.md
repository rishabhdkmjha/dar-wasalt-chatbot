# DarGlobal & Wasalt AI Chatbot

An AI-powered **Retrieval-Augmented Generation (RAG) chatbot** built to answer questions about **DarGlobal**, an international luxury real-estate developer, and **Wasalt**, a Saudi Arabia-based real-estate technology platform.

The application collects publicly available information from both platforms, retrieves relevant knowledge using **BM25-based information retrieval**, and generates contextual, source-grounded responses using a free Large Language Model (LLM) through **OpenRouter**.

**The application is containerised using Docker and deployed on Render**, making it accessible through a live web interface.

**Live Demo:** [Insert your Render URL]

---

## Project Overview

Finding relevant information across multiple company websites can require navigating numerous pages and manually comparing information. This project addresses that problem by providing a conversational interface that retrieves relevant information from collected company data and generates concise, context-aware answers.

Users can ask natural-language questions about company backgrounds, real-estate projects, services, business activities and other information available in the collected knowledge base.

Rather than relying entirely on the LLM's pretrained knowledge, the chatbot retrieves relevant passages from its own knowledge base and uses them as the basis for response generation.

### Key Features

- **Multi-source Data Collection:** Collects publicly available information from DarGlobal and Wasalt websites.
- **Retrieval-Augmented Generation:** Combines information retrieval with LLM-based response generation.
- **BM25 Information Retrieval:** Identifies and ranks relevant text chunks based on the user's query.
- **Context-Grounded Responses:** Instructs the LLM to answer using retrieved context instead of making unsupported assumptions.
- **Source Attribution:** Provides relevant source links and inline passage references to improve answer traceability.
- **OpenRouter Integration:** Uses a free-model endpoint for LLM-powered response generation.
- **Conversation History:** Supports conversational context through previous messages.
- **Graceful Fallback:** Provides relevant retrieved passages when the LLM is unavailable.
- **REST API:** Exposes endpoints for chat, application health checks and data refresh.
- **Docker Containerisation:** Packages the application and its dependencies for deployment.

---

## System Architecture

The application follows a retrieval-augmented generation pipeline:

```text
       PUBLIC DATA SOURCES
       ┌─────────────────────┐
       │  DarGlobal Website  │
       │  Wasalt Website     │
       │  Wasalt Blog API    │
       └──────────┬──────────┘
                  │
                  ▼
          DATA COLLECTION
             Scraper
                  │
                  ▼
          KNOWLEDGE BASE
       ┌─────────────────────┐
       │   Scraped JSONL     │
       │   Curated Seed Data │
       └──────────┬──────────┘
                  │
                  ▼
          TEXT PROCESSING
          Chunk Generation
                  │
                  ▼
          BM25 RETRIEVAL
          Top-5 Relevant Chunks
                  │
                  ▼
           CONTEXT BUILDING
       Retrieved Passages + Query
                  │
                  ▼
           OPENROUTER LLM
          Context-Grounded
             Generation
                  │
                  ▼
          ANSWER + SOURCES
                  │
                  ▼
             CHAT UI
```

### How It Works

**1. Data Collection and Web Scraping**

The application collects publicly available information from:

- DarGlobal official website: https://darglobal.co.uk/
- Wasalt official website: https://wasalt.sa/
- Wasalt public blog API.

The scraper is implemented in `app/scraper.py`. It follows a polite crawling approach, respects `robots.txt`, limits requests to the relevant domains and applies a one-request-per-second delay.

Collected content is stored in JSONL format for further processing.

**2. Knowledge Base Preparation**

The application combines two sources of information:

- Scraped website content stored in `data/scraped.jsonl`.
- Curated company information maintained in `data/seed_knowledge.md`.

The curated seed knowledge provides a baseline when certain pages cannot be scraped or accessed.

**3. Text Chunking and Retrieval**

The collected documents are divided into smaller text chunks of approximately 140 words.

The retrieval component, implemented in `app/retriever.py`, uses **BM25 (Best Matching 25)** to rank documents according to their relevance to the user's query.

The five most relevant chunks are selected and passed to the language model as contextual information.

BM25 was selected because it provides efficient keyword-based retrieval without requiring a separate embedding API or vector database.

**4. LLM-Based Answer Generation**

The retrieved passages and user query are passed to an LLM through the OpenRouter API.

The implementation in `app/llm.py` uses an OpenAI-compatible chat completions interface.

A grounding-focused system prompt instructs the model to:

- Answer using only the retrieved context.
- Avoid fabricating information, names, dates or figures.
- Acknowledge when the available context does not contain an answer.
- Provide inline references to supporting passages.
- Respond in the same language as the user's question.
- Identify conflicting information when sources disagree.

**5. Response Delivery**

The generated response is returned through the FastAPI backend and displayed in the web-based chat interface.

Relevant source documents are also provided alongside the answer, allowing users to inspect the original information.

If LLM generation fails, the application falls back to displaying the most relevant retrieved passages instead of failing completely.

---

## Technology Stack

| Component | Technologies |
|---|---|
| Programming Language | Python |
| Backend Framework | FastAPI |
| Information Retrieval | BM25 |
| LLM Integration | OpenRouter API |
| Language Model | Free OpenRouter model |
| Web Scraping | Requests, BeautifulSoup4, lxml |
| Data Storage | JSONL, Markdown |
| Frontend | HTML, CSS, JavaScript |
| Containerisation | Docker, Docker Compose |
| Deployment | Render |
| Testing | Pytest |
| Configuration | Python dotenv |

---

## Project Structure

```text
dar-wasalt-chatbot/
│
├── app/
│   ├── main.py              # FastAPI application and API endpoints
│   ├── config.py            # Application configuration
│   ├── scraper.py           # Website data collection
│   ├── retriever.py         # Text chunking and BM25 retrieval
│   └── llm.py               # OpenRouter integration and generation
│
├── data/
│   ├── seed_knowledge.md    # Curated company knowledge
│   └── scraped.jsonl        # Collected website content
│
├── static/
│   └── index.html           # Chat interface
│
├── tests/                   # Automated tests
│
├── Dockerfile               # Container configuration
├── docker-compose.yml       # Docker Compose configuration
├── requirements.txt         # Python dependencies
├── .env.example             # Environment variable template
├── .gitignore
└── README.md
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Serves the chatbot interface |
| POST | `/api/chat` | Processes user questions and generates answers |
| GET | `/api/health` | Returns application health and configuration status |
| POST | `/api/refresh` | Re-scrapes the configured websites and rebuilds the knowledge index |

The refresh endpoint requires a configured `REFRESH_TOKEN`.

---

## Design Decisions

**Why RAG instead of a standalone LLM?**

A standalone LLM may generate answers using information outside the collected company data. RAG provides relevant source material to the model before generation, helping keep responses aligned with the available knowledge base.

**Why BM25 instead of vector embeddings?**

BM25 offers lightweight, efficient lexical retrieval without requiring embedding generation, a vector database or an additional external API. It is a practical choice for the relatively small knowledge corpus used in this project.

**Why OpenRouter?**

OpenRouter provides access to multiple language models through a unified API, including free-model options suitable for experimentation and deployment within limited budgets.

**Why FastAPI?**

FastAPI provides a lightweight backend with asynchronous request handling, API validation through Pydantic and straightforward integration with Python-based AI components.

**Why Docker?**

Docker packages the application and its dependencies into a consistent runtime environment, making the application easier to deploy and reproduce across environments.

---

## Limitations and Future Improvements

The current implementation provides a functional RAG pipeline, with several opportunities for further improvement:

- **Semantic Retrieval:** Introduce embedding-based retrieval and vector search to improve matching for semantically related queries.
- **Hybrid Search:** Combine BM25 with semantic retrieval to improve retrieval coverage.
- **Advanced Reranking:** Add a reranking model to improve the relevance of retrieved passages.
- **Improved Data Extraction:** Support JavaScript-rendered pages and additional content formats.
- **Automated Data Refresh:** Introduce scheduled crawling and incremental knowledge-base updates.
- **Evaluation Framework:** Measure retrieval and generation quality using metrics such as Recall@K, Precision@K and answer faithfulness.
- **Conversation Management:** Improve persistent conversation context and session handling.

---

## Acknowledgements

This project was developed as part of the technical assignment for the **Junior AI Engineer – Applied AI** role at DarGlobal.

The chatbot uses publicly available information from DarGlobal and Wasalt for demonstration and informational purposes. Responses are limited to the information collected in the project's knowledge base and should not be considered financial or investment advice.