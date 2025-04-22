#!/usr/bin/env python
import asyncio, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from seo_agent.cli import pipeline

if __name__ == "__main__":
    asyncio.run(pipeline())
