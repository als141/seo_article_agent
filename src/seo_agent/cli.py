from __future__ import annotations
import argparse, asyncio, os
from slugify import slugify
from agents import Runner
from rich import print as rprint

from .tools import crawl_site, build_vector_store
from .agents import (
    Coordinator,
    update_vector_store_ids,
    update_mcp_servers,
)
from .mcp import connect_mcp
from .config import settings

def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser("SEO Article Generator (MCP)")
    p.add_argument("url", help="企業ホームページ URL")
    p.add_argument("-n", "--name", required=True, help="企業正式名称")
    p.add_argument("-t", "--topic", help="トピックヒント（無指定で自動選定）")
    return p.parse_args()

async def pipeline():
    args = _parse()

    rprint("[cyan]* Crawling site …[/cyan]")
    pages = await crawl_site(args.url, settings.crawl_limit)
    rprint(f"    → {len(pages)} pages collected")

    rprint("[cyan]* Building vector store …[/cyan]")
    vs_id = await build_vector_store(pages, slugify(args.name))
    rprint(f"    → vector_store_id = {vs_id}")

    update_vector_store_ids(vs_id)

    prompt = args.topic or f"{args.name} の公式ブログ向けに最適なトピックを選んで記事化してください。"
    rprint("[cyan]* Connecting MCP servers …[/cyan]")
    async with connect_mcp() as servers:
        update_mcp_servers(servers)

        rprint("[cyan]* Running multi‑agent pipeline …[/cyan]")
        result = await Runner.run(starting_agent=Coordinator, input=prompt)
        trace = (
            f"https://platform.openai.com/traces/trace?trace_id={result.trace_id}"
            if hasattr(result, 'trace_id') and result.trace_id else "N/A"
        )
        rprint("\n[bold green]=== FINAL ARTICLE ===[/bold green]\n")
        rprint(result.final_output)
        rprint(f"\n[dim]Trace: {trace}[/dim]")

def main():
    try:
        asyncio.run(pipeline())
    except KeyboardInterrupt:
        rprint("\n[bold yellow]Interrupted.[/bold yellow]")
