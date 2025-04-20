import asyncio
from typing import Optional, List
from openai import OpenAI
from agents import Agent, function_tool
from .config import settings
from . import tools as mytools

client = OpenAI(api_key=settings.api_key)

class SEOAgent(Agent):
    """An agent that plans, drafts, and polishes SEO articles for a target website."""

    def __init__(self, company_url: str, company_name: str, topic: Optional[str] = None,
                 target_language: str = "ja", **kwargs):
        super().__init__(
            name="seo_article_agent",
            instructions=(
                "You are an elite Japanese SEO strategist. "
                "Research the client's website via the provided vector‑store tool, "
                "propose topics, outlines and draft a human‑like article that beats SEO best‑practices."
            ),
        )
        self.company_url = company_url
        self.company_name = company_name
        self.topic_hint = topic
        self.target_language = target_language
        self.vector_store_id: Optional[str] = None

    # === Tools =========================================================

    @function_tool()
    async def crawl_and_embed(self) -> str:
        """Crawl the company website, build a vector store, and return its id."""
        texts = await mytools.crawl_site(self.company_url, settings.crawl_limit)
        self.vector_store_id = await mytools.build_vector_store(texts, f"{self.company_name}_site")
        return self.vector_store_id

    @function_tool()
    async def generate_topics(self) -> List[str]:
        """Propose 5 engaging blog topics (Japanese) for the company."""
        prompt = f"""You are an elite Japanese SEO strategist. Based on the company's website content,
        propose 5 distinct, high‑impact blog post topics with primary keywords.
        Output JSON list of objects with 'title' and 'keywords'."""
        response = client.responses.create(
            model=settings.model,
            input=prompt,
            tools=[{"type": "vector_store", "vector_store_id": self.vector_store_id}],
        )
        return response.output[0].content[0].text

    @function_tool()
    async def expand_outline(self, topic_json: str) -> str:
        """Create an H2/H3 outline for the selected topic."""
        prompt = f"Make a detailed outline (Markdown) with H2/H3 headings for the topic below.\n\n{topic_json}"
        response = client.responses.create(
            model=settings.model,
            input=prompt,
        )
        return response.output[0].content[0].text

    @function_tool()
    async def draft_article(self, outline_md: str, keywords: str, style: str = "human") -> str:
        """Write a 2000–2500‑word Japanese article following the outline and keyword set."""
        prompt = f"""Write the full article in Japanese following this outline:\n{outline_md}\n
        Requirements:\n- Natural human tone ({style})\n- Include all subheadings\n
        - Use keywords: {keywords}\n- Avoid obvious AI patterns\n"""
        response = client.responses.create(
            model=settings.model,
            input=prompt,
        )
        return response.output[0].content[0].text

    @function_tool()
    async def score_seo(self, article_text: str) -> dict:
        """Return a simple SEO score plus suggestions."""
        prompt = (
            "You are an SEO auditor. Score the following article (0‑100) and suggest 5 improvements:\n" +
            article_text
        )
        response = client.responses.create(
            model=settings.model,
            input=prompt,
        )
        return {"report": response.output[0].content[0].text}

    # === Flow ==========================================================

    async def on_start(self) -> str:
        return (
            f"Starting SEO generation for {self.company_name}. Let's begin by crawling the site.\n" +
            "Use `crawl_and_embed()`."
        )