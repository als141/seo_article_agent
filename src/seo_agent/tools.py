"""
クローラー＋2つの軽量なローカル関数ツール
（LLMはAgents SDKを通してこれらを呼び出せます）
"""
from __future__ import annotations
import asyncio, aiohttp, os, re
from collections import deque
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from readability import Document
from slugify import slugify
from openai import AsyncOpenAI
from .config import settings

client = AsyncOpenAI(api_key=settings.api_key)

async def _fetch(session: aiohttp.ClientSession, url: str, timeout: int = 30) -> str:
    async with session.get(url, timeout=timeout) as resp:
        resp.raise_for_status()
        return await resp.text()

async def crawl_site(root_url: str, limit: int = 30) -> dict[str, str]:
    """幅優先クロール → {url: プレーンテキスト}"""
    seen, texts = set(), {}
    queue: deque[str] = deque([root_url])

    async with aiohttp.ClientSession() as session:
        while queue and len(texts) < limit:
            url = queue.popleft()
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
                texts[url] = txt[:20_000]  # 上限
            # 内部リンクをキューに追加
            for a in BeautifulSoup(html, "html.parser").find_all("a", href=True):
                href = a["href"]
                if href.startswith("#"):
                    continue
                joined = urljoin(url, href)
                if urlparse(joined).netloc == urlparse(root_url).netloc:
                    queue.append(joined)
    return texts

async def build_vector_store(texts: dict[str, str], name: str) -> str:
    valid = [(p, t) for p, t in texts.items() if t.strip()]
    if not valid:
        raise ValueError("収集された非空のページがありません。")

    file_ids = []
    for path, content in valid:
        with NamedTemporaryFile("w+", delete=False, suffix=".txt") as f:
            f.write(content)
            tmp = f.name
        try:
            res = await client.files.create(file=open(tmp, "rb"), purpose="assistants")
            file_ids.append(res.id)
        finally:
            os.remove(tmp)

    vs = await client.vector_stores.create(name=slugify(name), file_ids=file_ids)
    return vs.id

# ── ローカルキーワード分析ツール（シンプルなラッパー） ────────────────────────────────
def keyword_density(text: str, kw: str) -> float:
    if not text:
        return 0.0
    tokens = re.findall(r"\w+", text.lower())
    kw_tokens = re.findall(r"\w+", kw.lower())
    count = sum(1 for i in range(len(tokens)) if tokens[i : i + len(kw_tokens)] == kw_tokens)
    return round(100 * count / max(1, len(tokens)), 2)
