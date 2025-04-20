"""Custom tools used by the SEO agent."""

import re, asyncio, aiohttp, os
from bs4 import BeautifulSoup
from slugify import slugify
from readability import Document
from urllib.parse import urljoin, urlparse
from collections import deque
from openai import OpenAI
from .config import settings

client = OpenAI(api_key=settings.api_key)

async def fetch(session, url, timeout=30):
    async with session.get(url, timeout=timeout) as resp:
        resp.raise_for_status()
        return await resp.text()

async def crawl_site(root_url: str, limit: int = 20):
    """A very small breadth-first crawler that returns a dict[path->text]."""
    seen, texts = set(), {}
    queue = deque([root_url])
    async with aiohttp.ClientSession() as session:
        while queue and len(texts) < limit:
            url = queue.popleft()
            if url in seen:
                continue
            seen.add(url)
            try:
                html = await fetch(session, url)
            except Exception:
                continue
            doc = Document(html)
            content = BeautifulSoup(doc.summary(), "html.parser").get_text(" ", strip=True)
            texts[url] = content

            for link in BeautifulSoup(html, "html.parser").find_all("a", href=True):
                href = link["href"]
                if href.startswith("#"):  # Skip anchors
                    continue
                joined = urljoin(url, href)
                if urlparse(joined).netloc == urlparse(root_url).netloc:
                    queue.append(joined)
    return texts

async def build_vector_store(texts: dict[str, str], name: str) -> str:
    """
    Create an OpenAI Vector Store from the crawled pages and return its id.
    * 空テキストはスキップ
    * 最低 1 ファイル無い場合は ValueError
    """
    from tempfile import NamedTemporaryFile

    valid_items = [(path, txt.strip()) for path, txt in texts.items() if txt.strip()]
    if not valid_items:
        raise ValueError("All crawled pages were empty – nothing to embed.")

    file_ids = []
    for path, content in valid_items:
        with NamedTemporaryFile("w+", delete=False, suffix=".txt") as tmp:
            tmp.write(content)
            tmp.flush()
            tmp_path = tmp.name

        try:
            f = client.files.create(file=open(tmp_path, "rb"), purpose="assistants")
            file_ids.append(f.id)
        finally:
            os.remove(tmp_path)

    vs = client.vector_stores.create(name=name, file_ids=file_ids)
    return vs.id
