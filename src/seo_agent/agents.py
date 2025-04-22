"""
5つのエージェント:
  - ResearchAgent
  - OutlineAgent
  - DraftAgent
  - AuditAgent
  - Coordinator (最上位、ハンドオフを使用)
すべてがモデル + MCPサーバー + 組み込みツールを共有します。
"""
from __future__ import annotations
import logging
from typing import List
from agents import Agent, function_tool, handoff
from agents.models.openai_responses import OpenAIResponsesModel
from agents import FileSearchTool, WebSearchTool
from agents.mcp import MCPServer
from openai import AsyncOpenAI
from .config import settings
from .tools import keyword_density

# ロガーを設定
logger = logging.getLogger("agents")

# OpenAI クライアントの初期化
client = AsyncOpenAI(api_key=settings.api_key)

# モデルの初期化（openai_clientパラメータを追加）
MODEL = OpenAIResponsesModel(model=settings.model, openai_client=client)

# ── LLMがkeyword_densityを呼び出せるようにするローカルツールラッパー ──────────────
@function_tool
def kw_density(text: str, keyword: str) -> float:
    """指定テキスト内のキーワード密度(%)を返します。"""
    return keyword_density(text, keyword)

# グローバル変数として、後で更新可能なツールリストを定義
BASE_TOOLS = [WebSearchTool(), kw_density]  # FileSearchToolは後で追加

# ベクトルストアIDを格納する変数
VECTOR_STORE_IDS = []

# 非同期関数からMCPサーバーを取得する際に使用するグローバル変数
MCP_SERVERS = []

# ベクトルストアIDを更新する関数
def update_vector_store_ids(vs_id: str) -> None:
    """
    ベクトルストアIDを更新し、FileSearchToolを再作成します。
    """
    global VECTOR_STORE_IDS, BASE_TOOLS
    
    # IDリストをクリアして新しいIDを追加
    VECTOR_STORE_IDS.clear()
    if vs_id:
        VECTOR_STORE_IDS.append(vs_id)
        logger.info(f"ベクトルストアID '{vs_id}' を設定しました")
    
    # FileSearchToolを含まないツールをフィルタリング
    BASE_TOOLS = [tool for tool in BASE_TOOLS if not isinstance(tool, FileSearchTool)]
    
    # 新しいベクトルストアIDを使用してFileSearchToolを追加
    if VECTOR_STORE_IDS:
        file_search_tool = FileSearchTool(vector_store_ids=VECTOR_STORE_IDS, max_num_results=6)
        BASE_TOOLS.append(file_search_tool)
        logger.info(f"FileSearchToolを更新しました。使用するベクトルストアID: {VECTOR_STORE_IDS}")
    
    # 各エージェントのツールリストも更新
    all_agents = [ResearchAgent, OutlineAgent, DraftAgent, AuditAgent, Coordinator]
    for agent in all_agents:
        # 既存のツールリストをクリア
        agent.tools.clear()
        # 新しいツールを追加
        agent.tools.extend(BASE_TOOLS)
    
    logger.info("すべてのエージェントのツールリストを更新しました")

# --- サブエージェント ---------------------------------------------------------
ResearchAgent = Agent(
    name="researcher",
    instructions=(
        "会社とトピックに関する徹底的な背景調査を行ってください。"
        "インサイトのリスト（プレーンテキストのみ）を箇条書きで返してください。"
    ),
    tools=BASE_TOOLS,
    mcp_servers=MCP_SERVERS,
    model=MODEL,
)

OutlineAgent = Agent(
    name="outliner",
    instructions=(
        "<<research>>の洞察テキストに基づいて、SEOにポジティブな記事の詳細な"
        "マークダウンアウトライン（H2/H3）を設計してください。150〜300文字程度。"
    ),
    tools=BASE_TOOLS,
    mcp_servers=MCP_SERVERS,
    model=MODEL,
)

DraftAgent = Agent(
    name="drafter",
    instructions=(
        "<<outline>>に従って完全な記事（2,000〜2,500文字の日本語）を書いてください。"
        "キーワードを自然に埋め込み、AI的なクリシェを避けてください。マークダウン形式のみで出力してください。"
    ),
    tools=BASE_TOOLS,
    mcp_servers=MCP_SERVERS,
    model=MODEL,
)

AuditAgent = Agent(
    name="auditor",
    instructions=(
        "クイックSEOスコア（0〜100）を計算し、3つの改善点をリストアップし、"
        "メインキーワードのキーワード密度が1〜2%の間にあるかどうかを判断してください。"
        "監査結果を「## 🔎 クイックSEO監査」として追加してください。"
    ),
    tools=BASE_TOOLS,
    mcp_servers=MCP_SERVERS,
    model=MODEL,
)

# 上記を連鎖させる監督者 --------------------------------------
Coordinator = Agent(
    name="coordinator",
    instructions=(
        "あなたは多段階の記事パイプラインのコーディネーターです。\n"
        "1. 元のプロンプトをresearcherにハンドオフします。\n"
        "2. 研究サマリーをoutlinerにハンドオフします。\n"
        "3. アウトラインと研究をdrafterにハンドオフします。\n"
        "4. 最終ドラフトをauditorにハンドオフします。\n"
        "auditorの出力を最終結果として返します。"
    ),
    handoffs=[ResearchAgent, OutlineAgent, DraftAgent, AuditAgent],
    tools=[],
    mcp_servers=MCP_SERVERS,
    model=MODEL,
)

def update_mcp_servers(servers: List[MCPServer]) -> None:
    """
    すべてのエージェントのMCPサーバーを更新します。
    これは実行時に新しいMCPサーバーが接続された際に呼び出されます。
    """
    global MCP_SERVERS
    MCP_SERVERS.clear()
    MCP_SERVERS.extend(servers)
    
    # 各エージェントのMCPサーバーリストを更新
    all_agents = [ResearchAgent, OutlineAgent, DraftAgent, AuditAgent, Coordinator]
    for agent in all_agents:
        # 既存のmcp_serversリストをクリア
        agent.mcp_servers.clear()
        # 新しいサーバーを追加
        agent.mcp_servers.extend(servers)
    
    logger.info(f"{len(servers)}個のMCPサーバーをすべてのエージェントに更新しました")

