from __future__ import annotations
import os, json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).parent.parent.parent

def _load_mcp_cfg() -> Dict[str, Any]:
    try:
        return json.loads((ROOT / "mcp_settings.json").read_text("utf-8"))
    except Exception:
        return {}

@dataclass(frozen=True, slots=True)
class Settings:
    api_key: str = os.getenv("OPENAI_API_KEY", "")
    model: str   = os.getenv("OPENAI_MODEL", "gpt-4o")
    crawl_limit: int = int(os.getenv("CRAWL_LIMIT", "40"))
    language: str = os.getenv("TARGET_LANGUAGE", "ja")
    mcp_cfg: Dict[str, Any] = field(default_factory=_load_mcp_cfg)

settings = Settings()
