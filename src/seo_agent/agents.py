"""
6‑layer multi‑agent pipeline:
 1. TopicAgent      – トピック自動選定
 2. ResearchAgent   – 背景調査
 3. OutlineAgent    – アウトライン設計
 4. DraftAgentA/B   – 2 通りの草稿生成
 5. EvaluateAgent   – 2 草稿を比較しベストを選択
 6. EditorAgent     – SEO 監査 + 推敲 + 完成
Coordinator が handoff で順に呼び出す。
"""
from __future__ import annotations
import logging, random
from typing import List
from agents import Agent, function_tool, handoff
from agents.models.openai_responses import OpenAIResponsesModel
from agents import WebSearchTool, FileSearchTool
from agents.mcp import MCPServer
from openai import AsyncOpenAI
from .config import settings
from .tools import keyword_density, readability_score
from agents.model_settings import ModelSettings


logger = logging.getLogger("agents")

# ────────────────────── TOOLS
@function_tool
def kw_density(text: str, keyword: str) -> float:
    """Return keyword density (%)"""
    return keyword_density(text, keyword)

@function_tool
def readability(text: str) -> float:
    """Return Flesch Reading Ease score"""
    return readability_score(text)

BASE_TOOLS: List = [WebSearchTool(), kw_density, readability]  # FileSearchTool は動的に追加

VECTOR_STORE_IDS: List[str] = []
MCP_SERVERS: List[MCPServer] = []

def _model():
    return OpenAIResponsesModel(
        model=settings.model,
        openai_client=AsyncOpenAI(api_key=settings.api_key),
    )


# ────────────────────── AGENTS
TopicAgent = Agent(
    name="topic_selector",
    instructions=(
        "対象企業サイトのページ内容を分析し、SEO 効果が高く読者の関心を引くブログトピックを 1 つだけ日本語で提案し、JSON で返す。"
        "キーは {\"topic\": \"...\"}"
    ),
    tools=[],  # browsing は Coordinator が FileSearchTool 付きで渡す
    model=_model(),
)

ResearchAgent = Agent(
    name="researcher",
    instructions="<<topic>> に基づき競合比較や顧客ペルソナを含む詳細な調査を行い、300–400 字で要点を箇条書き。",
    tools=BASE_TOOLS,
    mcp_servers=MCP_SERVERS,
    model=_model(),
)

OutlineAgent = Agent(
    name="outliner",
    instructions="<<research>> を参考に SEO に強い H2/H3 見出し構成を Markdown で作成。150–250 字。",
    tools=BASE_TOOLS,
    mcp_servers=MCP_SERVERS,
    model=_model(),
)

def _draft_agent(idx: int) -> Agent:
    style = "ライトで会話調" if idx == 0 else "専門誌風でフォーマル"
    return Agent(
        name=f"draft_{idx+1}",
        instructions=(
            f"<<outline>> を基に {style} に 2,300±300 文字で本文を生成。"
            "キーワードを過度に繰り返さず自然に散りばめる。Markdown のみで出力。"
        ),
        tools=BASE_TOOLS,
        mcp_servers=MCP_SERVERS,
        model=_model(),
        model_settings=ModelSettings(tool_choice="required"),
    )

DraftAgentA, DraftAgentB = [_draft_agent(i) for i in range(2)]

EvaluateAgent = Agent(
    name="evaluator",
    instructions=(
        "2 つの草稿(<<draft_1>>, <<draft_2>>) を SEO 観点(キーワード密度, 見出し妥当性, 読みやすさ)で採点し、"
        "優れた方の全文を `<<best>>` として抜き出し JSON {\"best\": \"...\"} で返す。"
    ),
    tools=BASE_TOOLS,
    mcp_servers=MCP_SERVERS,
    model=_model(),
    model_settings=ModelSettings(tool_choice="required"),
)

EditorAgent = Agent(
    name="editor",
    instructions=(
        "JSON から取り出した <<best>> を ①文法チェック ②冗長表現の削減 ③語尾バリエーション調整 して最終稿に整える。"
        "最後に `## 🔎 SEO Audit` 見出しを追加し、キーワード密度・FRE スコア・改善案 3 点を列挙。"
        "最終結果のみ Markdown で返す。"
    ),
    tools=BASE_TOOLS,
    mcp_servers=MCP_SERVERS,
    model=_model(),
    model_settings=ModelSettings(tool_choice="required"),
)

# ────────────────────── COORDINATOR
Coordinator = Agent(
    name="coordinator",
    instructions=(
        "0. input(prompt) を topic_selector に渡す\n"
        "1. topic を researcher に handoff\n"
        "2. research 結果を outliner に handoff\n"
        "3. outline を draft_1 と draft_2 に handoff\n"
        "4. draft_1 & draft_2 を evaluator に handoff\n"
        "5. evaluator が返す best を editor に handoff\n"
        "6. editor 出力を最終結果として返す"
    ),
    handoffs=[TopicAgent, ResearchAgent, OutlineAgent, DraftAgentA, DraftAgentB, EvaluateAgent, EditorAgent],
    tools=[],
    mcp_servers=MCP_SERVERS,
    model=_model(),
)

# ────────────────────── UPDATE HELPERS
def update_vector_store_ids(vs_id: str):
    global VECTOR_STORE_IDS, BASE_TOOLS
    VECTOR_STORE_IDS = [vs_id]

    # FileSearchTool を差し替えまたは追加
    existing_tools = [t for t in BASE_TOOLS if not isinstance(t, FileSearchTool)]
    new_file_search_tool = FileSearchTool(vector_store_ids=VECTOR_STORE_IDS, max_num_results=8)
    BASE_TOOLS = existing_tools + [new_file_search_tool]

    # Coordinator と TopicAgent も含めてツールを更新
    agents_to_update = [
        TopicAgent,  # TopicAgent に FileSearchTool を追加
        ResearchAgent,
        OutlineAgent,
        DraftAgentA,
        DraftAgentB,
        EvaluateAgent,
        EditorAgent,
        Coordinator, # Coordinator にもツールアクセス権を与える (handoff のため)
    ]
    for ag in agents_to_update:
        # FileSearchTool 以外の既存ツールを保持しつつ、新しい FileSearchTool を追加/更新
        current_tools_without_fs = [t for t in ag.tools if not isinstance(t, FileSearchTool)]
        
        # TopicAgent は元々 tools=[] だったので、BASE_TOOLS をそのまま設定
        if ag.name == "topic_selector" or ag.name == "coordinator":
             ag.tools.clear()
             ag.tools.extend(BASE_TOOLS) # TopicAgent と Coordinator には全基本ツールを与える
        else:
            # 他のエージェントは既存ツール + 更新された FileSearchTool
            ag.tools.clear()
            ag.tools.extend(current_tools_without_fs)
            # FileSearchTool が BASE_TOOLS に含まれていることを確認して追加
            if any(isinstance(t, FileSearchTool) for t in BASE_TOOLS):
                 ag.tools.append(new_file_search_tool)
            # 他の基本ツールも追加（重複回避は Agent クラス側で行われる想定）
            for base_tool in BASE_TOOLS:
                if not any(isinstance(t, type(base_tool)) for t in ag.tools):
                     ag.tools.append(base_tool)


def update_mcp_servers(servers: List[MCPServer]):
    global MCP_SERVERS
    MCP_SERVERS = servers
    for ag in [ResearchAgent, OutlineAgent, DraftAgentA, DraftAgentB, EvaluateAgent, EditorAgent, Coordinator]:
        ag.mcp_servers.clear()
        ag.mcp_servers.extend(servers)
