"""Refresh data/knowledge_base_scraped.json from kristujayanti.edu.in.

Run on your own machine (needs internet):
    pip install requests beautifulsoup4
    python scrape_site.py

Then point chatbot.KB_PATH at the new file (or merge it into knowledge_base.json).
Pages built with JavaScript may come back thin; the hand-checked knowledge_base.json
remains the main source.
"""
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urldefrag, urlparse

import requests
from bs4 import BeautifulSoup

START = "https://kristujayanti.edu.in/"
HOST = urlparse(START).netloc
MAX_PAGES = 120
OUT = Path(__file__).parent / "data" / "knowledge_base_scraped.json"


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def chunks(text: str, size: int = 900):
    words, cur = text.split(), []
    for w in words:
        cur.append(w)
        if sum(len(x) + 1 for x in cur) > size:
            yield " ".join(cur)
            cur = []
    if cur:
        yield " ".join(cur)


def main():
    seen, queue, docs = set(), [START], []
    headers = {"User-Agent": "KJU-Chatbot-Student-Project/1.0"}
    while queue and len(seen) < MAX_PAGES:
        url = urldefrag(queue.pop(0))[0]
        if url in seen:
            continue
        seen.add(url)
        try:
            r = requests.get(url, headers=headers, timeout=20)
        except requests.RequestException:
            continue
        if r.status_code != 200 or "text/html" not in r.headers.get("content-type", ""):
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            link = urldefrag(urljoin(url, a["href"]))[0]
            if urlparse(link).netloc == HOST and link not in seen and not link.endswith((".pdf", ".jpg", ".png")):
                queue.append(link)
        for tag in soup(["script", "style", "nav", "footer", "noscript"]):
            tag.decompose()
        title = clean(soup.title.get_text()) if soup.title else url
        body = clean(soup.get_text(" "))
        for i, part in enumerate(chunks(body)):
            docs.append({"id": f"{len(docs)}", "title": f"{title} ({i+1})", "url": url, "keywords": "", "text": part})
        time.sleep(0.5)  # be polite to the server
    OUT.write_text(json.dumps(docs, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Saved {len(docs)} chunks from {len(seen)} pages to {OUT}")


if __name__ == "__main__":
    main()
