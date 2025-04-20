import asyncio
import argparse
from agents import Runner
from .agent import SEOAgent

def parse_args():
    p = argparse.ArgumentParser(description="SEO Article Generator Agent")
    p.add_argument("url", help="Target company homepage URL")
    p.add_argument("-n", "--name", required=True, help="Company official name")
    p.add_argument("-t", "--topic", help="Optional topic hint", default=None)
    p.add_argument("-l", "--language", help="Target language (ja/en/etc.)", default="ja")
    return p.parse_args()

def main() -> None:
    """同期エントリーポイント (console‑script 用)"""

    async def _inner():
        args = parse_args()
        agent = SEOAgent(company_url=args.url, company_name=args.name,
                         topic=args.topic, target_language=args.language)
        run_result = await Runner.run(agent, "")
        print(run_result.final_output)

    asyncio.run(_inner())

# `seo-agent` コマンドから呼ばれるのは ↑ の main()
if __name__ == "__main__":
    main()