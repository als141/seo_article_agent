from __future__ import annotations
import json, os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).parent.parent.parent

def load_mcp_config() -> Dict[str, Any]:
    try:
        return json.loads((ROOT / "mcp_settings.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}  # ファイルが存在しないか、不正なJSONの場合は空の辞書を返す

@dataclass(frozen=True, slots=True)
class Settings:
    api_key: str = os.getenv("OPENAI_API_KEY", "")
    model: str = os.getenv("OPENAI_MODEL", "gpt-4.1")
    crawl_limit: int = int(os.getenv("CRAWL_LIMIT", "30"))
    language: str = os.getenv("TARGET_LANGUAGE", "ja")
    mcp_cfg: Dict[str, Any] = field(default_factory=load_mcp_config)

settings = Settings()
