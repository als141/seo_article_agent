from __future__ import annotations
import argparse, asyncio, os
from slugify import slugify
from agents import Runner
from rich import print

from . import tools as crawl_tools
from .agents import Coordinator, update_mcp_servers, update_vector_store_ids
from .config import settings
from .mcp import create_mcp_servers, connect_mcp_servers

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser("SEO記事ジェネレーター (MCP版)")
    p.add_argument("url", help="対象企業のホームページURL")
    p.add_argument("-n", "--name", required=True, help="企業の正式名称")
    p.add_argument("-t", "--topic", help="オプションのトピックヒント")
    p.add_argument("-l", "--language", default=settings.language)
    p.add_argument("--auto", action="store_true", help="中断なしで完全なパイプラインを実行")
    return p.parse_args()

async def pipeline():
    args = parse_args()
    print("[cyan]* クロール中…[/cyan]")
    pages = await crawl_tools.crawl_site(args.url, settings.crawl_limit)
    print(f"    → {len(pages)}ページを収集しました")

    print("[cyan]* ベクトルストアを構築中…[/cyan]")
    vs_id = await crawl_tools.build_vector_store(pages, slugify(args.name))
    print(f"    → vector_store_id = {vs_id}")
    
    # ベクトルストアIDを更新
    update_vector_store_ids(vs_id)

    # MCPサーバーを作成
    print("[cyan]* MCPサーバーを初期化中…[/cyan]")
    servers = await create_mcp_servers()
    
    prompt = (
        args.topic
        or f"『{args.name}』の公式ブログに最適なトピックを自動選定し記事化してください。"
    )

    # コンテキストマネージャーを使用してMCPサーバーに接続
    async with connect_mcp_servers(servers) as connected_servers:
        # サーバーがうまく接続されたかチェック
        if not connected_servers:
            print("[bold red]警告: 接続されたMCPサーバーがありません。機能が制限されます。[/bold red]")
        else:
            # 接続されたサーバーでエージェントを更新
            update_mcp_servers(connected_servers)
        
        # コーディネーターを実行
        print("[cyan]* 多層エージェントパイプラインを実行中…[/cyan]")
        try:
            # エージェントを実行
            result = await Runner.run(starting_agent=Coordinator, input=prompt)
            print("\n[bold green]=== 最終記事 ===[/bold green]\n")
            print(result.final_output)
        except Exception as e:
            print(f"[bold red]エラーが発生しました: {e}[/bold red]")
            raise

def main():
    try:
        # 必要なディレクトリが存在することを確認
        workspace_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'workspace')
        os.makedirs(workspace_dir, exist_ok=True)
        
        asyncio.run(pipeline())
    except KeyboardInterrupt:
        print("\n[bold yellow]ユーザーによる中断[/bold yellow]")
    except Exception as e:
        print(f"[bold red]致命的なエラー: {e}[/bold red]")
        raise

if __name__ == "__main__":
    main()
