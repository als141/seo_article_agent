"""
Crawler + ローカル関数ツール（keyword_density, readability_score）
LLM はこれらを MCP 経由で呼び出せる。
"""
from __future__ import annotations
import aiohttp, asyncio, os, re
from collections import deque
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from readability import Document
from slugify import slugify
from openai import AsyncOpenAI
from textstat import flesch_reading_ease

from .config import settings

client = AsyncOpenAI(api_key=settings.api_key)

# ────────────────────────────────────── CRAWLER
async def _fetch(session: aiohttp.ClientSession, url: str, timeout: int = 30) -> str:
    async with session.get(url, timeout=timeout) as res:
        res.raise_for_status()
        return await res.text()

async def crawl_site(root_url: str, limit: int = 40) -> dict[str, str]:
    seen, texts = set(), {}
    q: deque[str] = deque([root_url])

    async with aiohttp.ClientSession() as session:
        while q and len(texts) < limit:
            url = q.popleft()
            if url in seen:
                continue
            seen.add(url)
            try:
                html = await _fetch(session, url)
            except Exception:
                continue

            doc = Document(html)
            txt = BeautifulSoup(doc.summary(), "html.parser").get_text(" ", strip=True)
            if txt.strip():
                texts[url] = txt[:20_000]

            for a in BeautifulSoup(html, "html.parser").find_all("a", href=True):
                href = a["href"]
                if href.startswith("#"):
                    continue
                tgt = urljoin(url, href)
                if urlparse(tgt).netloc == urlparse(root_url).netloc:
                    q.append(tgt)
    return texts

# ────────────────────────────────────── VECTOR STORE
async def build_vector_store(pages: dict[str, str], name: str) -> str:
    if not pages:
        raise RuntimeError("ページが取得できませんでした。")

    file_ids = []
    for url, txt in pages.items():
        with NamedTemporaryFile("w+", delete=False, suffix=".txt") as f:
            f.write(txt)
            tmp = f.name
        try:
            res = await client.files.create(file=open(tmp, "rb"), purpose="assistants")
            file_ids.append(res.id)
        finally:
            os.remove(tmp)

    vs = await client.vector_stores.create(name=slugify(name), file_ids=file_ids)
    return vs.id

# ────────────────────────────────────── LOCAL ANALYSIS
def keyword_density(text: str, keyword: str) -> float:
    tokens = re.findall(r"\w+", text.lower())
    kw_tokens = re.findall(r"\w+", keyword.lower())
    hits = sum(1 for i in range(len(tokens)) if tokens[i:i+len(kw_tokens)] == kw_tokens)
    return round(100 * hits / max(1, len(tokens)), 2)

def readability_score(text: str) -> float:
    """Flesch Reading Ease (英語指標だが日本語でも相対値として使う)"""
    if not text:
        return 0.0
    return round(flesch_reading_ease(text), 2)
