"""
動的MCPサーバーローダー

mcp_settings.jsonを読み込み → インスタンス化されたサーバーを返します
エージェントに渡せる状態にします。
"""
from __future__ import annotations
import asyncio
import logging
import contextlib
from pathlib import Path
from typing import List, AsyncContextManager

from agents.mcp import MCPServer, MCPServerStdio, MCPServerSse
from .config import settings

# ロガーを設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp_server")

ROOT = Path(__file__).parent.parent.parent

async def create_mcp_servers() -> List[MCPServer]:
    """MCPサーバーのインスタンスを作成（接続はしない）"""
    servers: list[MCPServer] = []
    
    try:
        # workspaceディレクトリを作成（存在しない場合）
        workspace_dir = ROOT / "workspace"
        workspace_dir.mkdir(exist_ok=True)
        
        for name, cfg in settings.mcp_cfg.get("servers", {}).items():
            if not cfg.get("enabled", False):
                continue
                
            typ = cfg["type"]
            try:
                if typ == "stdio":
                    server = MCPServerStdio(
                        name=name,
                        params={"command": cfg["command"], "args": cfg.get("args", [])},
                        cache_tools_list=True,
                    )
                    servers.append(server)
                    
                elif typ == "sse":
                    server = MCPServerSse(
                        name=name,
                        params={"url": cfg["url"]},
                        cache_tools_list=True,
                    )
                    servers.append(server)
                    
                else:
                    logger.warning(f"不明なMCPサーバータイプ: {typ}")
                    
            except Exception as e:
                logger.error(f"MCPサーバー '{name}' の作成中にエラーが発生しました: {str(e)}")
                # エラーが発生しても他のサーバーの初期化を続行
                continue
    
    except Exception as e:
        logger.error(f"MCPサーバーのロード中に予期しないエラーが発生しました: {str(e)}")
    
    return servers

@contextlib.asynccontextmanager
async def connect_mcp_servers(servers: List[MCPServer]) -> AsyncContextManager[List[MCPServer]]:
    """
    MCPサーバーのリストを接続し、コンテキストマネージャーとして提供します。
    使用例:
    async with connect_mcp_servers(servers) as connected_servers:
        # connected_serversを使用する
    """
    connected = []
    try:
        # サーバーを一つずつ接続
        for server in servers:
            try:
                await server.connect()
                connected.append(server)
                logger.info(f"MCPサーバー '{server.name}' が正常に接続されました")
            except Exception as e:
                logger.error(f"MCPサーバー '{server.name}' の接続中にエラーが発生しました: {str(e)}")
                # 他のサーバーの接続を続行
        
        yield connected
    
    finally:
        # コンテキスト終了時に、接続されたすべてのサーバーを適切にクリーンアップ
        for server in connected:
            try:
                await server.cleanup()
                logger.info(f"MCPサーバー '{server.name}' がクリーンアップされました")
            except Exception as e:
                logger.error(f"MCPサーバー '{server.name}' のクリーンアップ中にエラーが発生しました: {str(e)}")

# グローバルMCPサーバーリスト
_mcp_servers = []

async def initialize_mcp_servers():
    """MCPサーバーを初期化し、グローバル変数に格納"""
    global _mcp_servers
    _mcp_servers = await create_mcp_servers()
    return _mcp_servers

def get_mcp_servers() -> List[MCPServer]:
    """初期化済みのMCPサーバーを取得"""
    global _mcp_servers
    return _mcp_servers

