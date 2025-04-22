#!/usr/bin/env python
import sys
import os
import asyncio

# srcディレクトリをPYTHONPATHに追加
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from seo_agent.cli import pipeline

if __name__ == "__main__":
    # コマンドライン引数のセットアップ
    sys.argv = ["seo-agent", "https://matsuokoumuten.com/", "-n", "松尾工務店", "-t", "自然素材の注文住宅"]
    # メイン処理を実行
    asyncio.run(pipeline())
