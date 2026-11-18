
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from the project's root .env file
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"

SEED_FILE = DATA_DIR / "seed_knowledge.md"
SCRAPED_FILE = DATA_DIR / "scraped.jsonl"

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

OPENROUTER_MODEL = os.getenv(
    "OPENROUTER_MODEL", "openrouter/free"
).strip()

FALLBACK_MODELS = [
    m.strip()
    for m in os.getenv("OPENROUTER_FALLBACK_MODELS", "").split(",")
    if m.strip()
]

TOP_K = int(os.getenv("TOP_K", "5"))
MAX_HISTORY = int(os.getenv("MAX_HISTORY", "6"))

REFRESH_TOKEN = os.getenv("REFRESH_TOKEN", "").strip()
SITE_URL = os.getenv("SITE_URL", "http://localhost:8000")
