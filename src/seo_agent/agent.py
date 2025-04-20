# src/seo_agent/agent.py
from __future__ import annotations
from openai import AsyncOpenAI
from agents import Agent, FileSearchTool, WebSearchTool
from agents.models.openai_responses import OpenAIResponsesModel
from .config import settings

class SEOArticleAgent(Agent[None]):
    """
    An agent that:
    1. 下調べ（FileSearchTool / WebSearchTool）
    2. アウトライン → 本文 (日本語 2,000–2,500 words)
    3. 簡易 SEO スコア & 改善案
    を **ワンショットで自動** 生成する。
    """

    def __init__(
        self,
        company_name: str,
        vector_store_id: str,
        topic_hint: str | None = None,
        language: str = "ja",
    ):
        instructions = f"""
あなたは一流の日本語 SEO ストラテジスト兼コピーライターです。
目的: 企業「{company_name}」の公式サイト記事として SEO に強く、かつ人間らしいブログ記事を生成すること。

### ワークフロー (自動実行)
1. 必要なら FileSearchTool でサイト内容を検索してインサイトを得る。
2. 与えられたトピック{'（' + topic_hint + '）' if topic_hint else 'が無い場合は自分で最適なトピックを考案'}に対し、
   - 見出し (H2/H3) を設計し、
   - 2,000–2,500 文字相当の本文を Markdown で執筆する。
3. 記事末尾に `## 🔎 Quick SEO Audit` セクションを追加し、
   スコア (0‑100) と改善案 3 点を箇条書きで示す。

制約:
- AI らしい定型句を避け、自然な日本語で書く。
- キーワードは記事全体に自然に散りばめる。
- ユーザ確認は不要。**最終記事だけを出力**する。
"""
        tools = [
            FileSearchTool(max_num_results=4, vector_store_ids=[vector_store_id]),
            WebSearchTool(),
        ]
        super().__init__(
            name="seo_article_agent",
            instructions=instructions,
            tools=tools,
            model=OpenAIResponsesModel(                 # Responses API を強制
                model=settings.model,
                openai_client=AsyncOpenAI(),
            ),
        )
