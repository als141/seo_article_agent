"""
mcp_settings.json → MCPServer インスタンス化 & connect / cleanup を司るラッパー
"""
from __future__ import annotations
import contextlib, logging, asyncio
from typing import List, AsyncContextManager
from agents.mcp import MCPServer, MCPServerStdio, MCPServerSse
from .config import settings
from agents.model_settings import ModelSettings


logger = logging.getLogger("mcp")

async def _instantiate() -> List[MCPServer]:
    servers: list[MCPServer] = []
    for name, cfg in settings.mcp_cfg.get("servers", {}).items():
        if not cfg.get("enabled"):
            continue
        try:
            if cfg["type"] == "stdio":
                servers.append(
                    MCPServerStdio(
                        name=name,
                        params={"command": cfg["command"], "args": cfg.get("args", [])},
                        cache_tools_list=True,
                    )
                )
            elif cfg["type"] == "sse":
                servers.append(
                    MCPServerSse(
                        name=name,
                        params={"url": cfg["url"]},
                        cache_tools_list=True,
                    )
                )
        except Exception as e:
            logger.error(f"MCPサーバー {name} の生成失敗: {e}")
    return servers

@contextlib.asynccontextmanager
async def connect_mcp() -> AsyncContextManager[list[MCPServer]]:
    servers = await _instantiate()
    connected = []
    try:
        for s in servers:
            try:
                await s.connect()
                connected.append(s)
                logger.info(f"✓ MCP {s.name} connected")
            except Exception as e:
                logger.warning(f"MCP {s.name} connect error: {e}")
        yield connected
    finally:
        for s in connected:
            try:
                await s.cleanup() # Run cleanup directly
            except asyncio.CancelledError:
                logger.warning(f"MCP {s.name} cleanup cancelled.") # Log cancellation if it happens
            except Exception as e:
                logger.error(f"Error during MCP {s.name} cleanup: {e}")
            else:
                logger.info(f"MCP {s.name} cleaned")
