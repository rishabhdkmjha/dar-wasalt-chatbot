"""Tiny dependency-free BM25 retriever over chunked documents."""
from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

TOKEN_RE = re.compile(r"[\w؀-ۿ]+", re.UNICODE)  # latin + arabic letters/digits
STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is", "are", "was", "were",
    "be", "by", "with", "as", "at", "it", "this", "that", "from", "what", "who", "how", "do",
    "does", "can", "you", "me", "about", "tell", "which", "their", "its",
}


def stem(t: str) -> str:
    """Very light stemmer: plurals and '-ships' (brands->brand, partnerships->partner)."""
    if len(t) > 6 and t.endswith("ships"):
        return t[:-5]
    if len(t) > 5 and t.endswith("ship"):
        return t[:-4]
    if len(t) > 3 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


def tokenize(text: str) -> list[str]:
    return [stem(t) for t in TOKEN_RE.findall(text.lower()) if t not in STOP and len(t) > 1]


@dataclass
class Chunk:
    company: str          # "darglobal" | "wasalt"
    title: str
    url: str
    text: str


def chunk_text(text: str, size: int = 140, overlap: int = 30) -> list[str]:
    words = text.split()
    if len(words) <= size:
        return [" ".join(words)] if words else []
    out, step = [], size - overlap
    for i in range(0, len(words), step):
        piece = words[i : i + size]
        if piece:
            out.append(" ".join(piece))
        if i + size >= len(words):
            break
    return out


def load_seed(path: Path) -> list[Chunk]:
    """Seed format: '## Title' then 'Source: url' and 'Company: x' lines, then body."""
    if not path.exists():
        return []
    chunks: list[Chunk] = []
    for block in re.split(r"^## ", path.read_text(encoding="utf-8"), flags=re.M)[1:]:
        lines = block.strip().splitlines()
        title, url, company, body = lines[0].strip(), "", "", []
        for ln in lines[1:]:
            if ln.startswith("Source:"):
                url = ln.split(":", 1)[1].strip()
            elif ln.startswith("Company:"):
                company = ln.split(":", 1)[1].strip().lower()
            else:
                body.append(ln)
        for piece in chunk_text(" ".join(body)):
            chunks.append(Chunk(company, title, url, piece))
    return chunks


def load_scraped(path: Path) -> list[Chunk]:
    if not path.exists():
        return []
    chunks: list[Chunk] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            for piece in chunk_text(d.get("text", "")):
                chunks.append(Chunk(d.get("company", ""), d.get("title", ""), d.get("url", ""), piece))
    return chunks


class BM25Index:
    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1, self.b = k1, b
        # Title is searchable too: it often carries the project/product name.
        self.docs = [tokenize(c.title + " " + c.text) for c in chunks]
        self.tf = [Counter(d) for d in self.docs]
        self.lens = [len(d) for d in self.docs]
        self.avg = (sum(self.lens) / len(self.lens)) if self.lens else 0.0
        df: Counter = Counter()
        for d in self.docs:
            df.update(set(d))
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, k: int = 5) -> list[tuple[float, Chunk]]:
        q = tokenize(query)
        if not q or not self.chunks:
            return []
        wants = {c for c in ("darglobal", "wasalt") if c in query.lower().replace(" ", "")
                 or (c == "darglobal" and "dar global" in query.lower())}
        scored = []
        for i, tf in enumerate(self.tf):
            s = 0.0
            for t in q:
                f = tf.get(t)
                if not f:
                    continue
                denom = f + self.k1 * (1 - self.b + self.b * self.lens[i] / (self.avg or 1))
                s += self.idf.get(t, 0.0) * f * (self.k1 + 1) / denom
            if s > 0:
                if wants and self.chunks[i].company in wants:
                    s *= 1.25  # small nudge when the user names a company
                scored.append((s, self.chunks[i]))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:k]
