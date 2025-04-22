#!/usr/bin/env python
import sys
import os

# srcディレクトリをPYTHONPATHに追加
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

try:
    import seo_agent
    print("seo_agent モジュールのインポートに成功しました")
    
    from seo_agent.cli import parse_args
    print("parse_args のインポートに成功しました")
    
    # その他の依存関係をチェック
    from agents import Agent, function_tool, handoff
    print("agents モジュールのインポートに成功しました")
    
    from openai import AsyncOpenAI
    print("AsyncOpenAI のインポートに成功しました")
    
    from agents.models.openai_responses import OpenAIResponsesModel
    print("OpenAIResponsesModel のインポートに成功しました")
    
    # コマンドライン引数を表示
    print(f"実行引数: {sys.argv}")
    
except ImportError as e:
    print(f"インポートエラー: {e}")
except Exception as e:
    print(f"エラー: {e}")
