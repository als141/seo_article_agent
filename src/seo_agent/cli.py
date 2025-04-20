# src/seo_agent/cli.py
import argparse, asyncio
from slugify import slugify
from agents import Runner
from . import tools as crawl_tools
from .agent import SEOArticleAgent
from .config import settings

def _parse():
    p = argparse.ArgumentParser("SEO Article Generator Agent")
    p.add_argument("url", help="Target company homepage URL")
    p.add_argument("-n", "--name", required=True, help="Company official name")
    p.add_argument("-t", "--topic", help="Optional topic hint")
    p.add_argument("-l", "--language", default="ja", help="Output language (default: ja)")
    return p.parse_args()

async def _workflow():
    args = _parse()
    print("[*] Crawling site …")
    pages = await crawl_tools.crawl_site(args.url, settings.crawl_limit)
    print(f"    → collected {len(pages)} pages")

    print("[*] Building vector store …")
    vs_id = await crawl_tools.build_vector_store(pages, slugify(args.name))
    print(f"    → vector_store_id = {vs_id}")

    agent = SEOArticleAgent(
        company_name=args.name,
        vector_store_id=vs_id,
        topic_hint=args.topic,
        language=args.language,
    )

    prompt = args.topic or "最適なトピックを自動で選んで記事を作成してください。"
    result = await Runner.run(agent, input=prompt)
    print("\n=== FINAL OUTPUT ===\n")
    print(result.final_output)

def main():
    asyncio.run(_workflow())

if __name__ == "__main__":
    main()
