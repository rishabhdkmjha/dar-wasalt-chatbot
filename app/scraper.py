"""Polite scraper for public pages of DarGlobal and Wasalt.

Usage:  python -m app.scraper            (writes data/scraped.jsonl)
        python -m app.scraper --max 25   (pages per site)

- Respects robots.txt, identifies itself, rate-limits (1 req/sec), same-domain only.
- Extracts visible text from static HTML; also pulls Wasalt blog posts via the public
  WordPress REST API (blog.wasalt.sa/en/wp-json/wp/v2/posts).
"""
from __future__ import annotations

import argparse
import json
import re
import time
from collections import deque
from urllib import robotparser
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from . import config

UA = "DarWasaltChatbotBot/1.0 (assessment project; polite crawler)"
DELAY = 1.0
SITES = {
    "darglobal": {
        "seeds": ["https://darglobal.co.uk/", "https://darglobal.co.uk/projects/", "https://darglobal.co.uk/about-us/"],
        "domains": {"darglobal.co.uk", "www.darglobal.co.uk"},
    },
    "wasalt": {
        "seeds": ["https://wasalt.sa/en", "https://wasalt.sa/en/about", "https://wasalt.sa/en/corporate"],
        "domains": {"wasalt.sa", "www.wasalt.sa", "wasalt.com", "www.wasalt.com"},
    },
}
SKIP_EXT = re.compile(r"\.(jpg|jpeg|png|gif|svg|webp|pdf|zip|mp4|css|js|ico|woff2?)$", re.I)
SKIP_PATH = re.compile(r"(/ar/|/login|/signup|/cart|/wp-admin|/search|/property/|/auction/\d)", re.I)

session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept-Language": "en"})


def robots_for(base: str) -> robotparser.RobotFileParser:
    rp = robotparser.RobotFileParser()
    try:
        r = session.get(urljoin(base, "/robots.txt"), timeout=10)
        rp.parse(r.text.splitlines() if r.status_code == 200 else [])
    except requests.RequestException:
        rp.parse([])
    return rp


def clean_text(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header", "form", "iframe"]):
        tag.decompose()
    title = (soup.title.string or "").strip() if soup.title else ""
    root = soup.find("main") or soup.body or soup
    lines = []
    for el in root.find_all(["h1", "h2", "h3", "h4", "p", "li", "td", "th", "span", "div"]):
        # keep only leaf-ish text to avoid duplicating nested content
        if el.name in ("span", "div") and el.find(["p", "li", "h1", "h2", "h3", "div"]):
            continue
        t = re.sub(r"\s+", " ", el.get_text(" ", strip=True))
        if len(t) > 2:
            lines.append(t)
    seen, out = set(), []
    for ln in lines:
        if ln not in seen:
            seen.add(ln)
            out.append(ln)
    return title, "\n".join(out)


def crawl(company: str, cfg: dict, max_pages: int) -> list[dict]:
    rp = robots_for(cfg["seeds"][0])
    queue, seen, docs = deque(cfg["seeds"]), set(), []
    while queue and len(docs) < max_pages:
        url = urldefrag(queue.popleft())[0].rstrip("/")
        if url in seen:
            continue
        seen.add(url)
        if not rp.can_fetch(UA, url):
            print(f"  [robots] skip {url}")
            continue
        try:
            time.sleep(DELAY)
            r = session.get(url, timeout=20)
        except requests.RequestException as e:
            print(f"  [err] {url}: {e}")
            continue
        if r.status_code != 200 or "text/html" not in r.headers.get("content-type", ""):
            continue
        title, text = clean_text(r.text)
        if len(text) >= 200:
            docs.append({"company": company, "url": url, "title": title or url, "text": text})
            print(f"  [ok] {url} ({len(text)} chars)")
        for a in BeautifulSoup(r.text, "lxml").find_all("a", href=True):
            nxt = urldefrag(urljoin(url + "/", a["href"]))[0]
            p = urlparse(nxt)
            if (
                p.scheme in ("http", "https")
                and p.netloc in cfg["domains"]
                and not SKIP_EXT.search(p.path)
                and not SKIP_PATH.search(p.path)
                and nxt.rstrip("/") not in seen
            ):
                queue.append(nxt)
    return docs


def wasalt_blog(limit: int = 20) -> list[dict]:
    api = "https://blog.wasalt.sa/en/wp-json/wp/v2/posts"
    try:
        time.sleep(DELAY)
        r = session.get(api, params={"per_page": limit, "_fields": "link,title,content"}, timeout=20)
        r.raise_for_status()
    except (requests.RequestException, ValueError) as e:
        print(f"  [blog err] {e}")
        return []
    docs = []
    for p in r.json():
        text = BeautifulSoup(p["content"]["rendered"], "lxml").get_text(" ", strip=True)
        title = BeautifulSoup(p["title"]["rendered"], "lxml").get_text(strip=True)
        if len(text) > 200:
            docs.append({"company": "wasalt", "url": p["link"], "title": title, "text": text})
    print(f"  [blog] {len(docs)} posts")
    return docs


def run(max_pages: int = 30) -> int:
    all_docs: list[dict] = []
    for company, cfg in SITES.items():
        print(f"Crawling {company} ...")
        all_docs += crawl(company, cfg, max_pages)
    all_docs += wasalt_blog()
    if not all_docs:
        print("Nothing scraped (offline or blocked). Existing data left untouched; seed data still works.")
        return 0
    config.DATA_DIR.mkdir(exist_ok=True)
    with config.SCRAPED_FILE.open("w", encoding="utf-8") as f:
        for d in all_docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    print(f"Wrote {len(all_docs)} documents to {config.SCRAPED_FILE}")
    return len(all_docs)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=30, help="max pages per site")
    run(ap.parse_args().max)
