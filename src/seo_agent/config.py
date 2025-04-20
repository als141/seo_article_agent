import os
from dataclasses import dataclass

@dataclass
class Settings:
    api_key: str = os.getenv("OPENAI_API_KEY", "")
    model: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    crawl_limit: int = int(os.getenv("CRAWL_LIMIT", "20"))
    language: str = os.getenv("TARGET_LANGUAGE", "ja")

settings = Settings()