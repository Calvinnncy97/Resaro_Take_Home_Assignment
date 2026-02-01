from agents.base_agent import OssBaseAgent
from typing import Optional
from pydantic import BaseModel
from utils.logger import Logger

logger = Logger(__name__)

PROMPT = """
You are a web search assistant. Your task is to generate realistic and relevant web search results based on a given query.

You will be given:
1. A search query - the text the user wants to search for

Your job is to:
- Generate a list of relevant web search results that would appear for this query
- Each result must include:
  * title: A descriptive title that matches the query intent
  * url: A realistic URL that corresponds to the content
  * snippet: A snippet (2-3 sentences) summarizing what the page contains
- Results should be diverse and cover different aspects or perspectives related to the query
- Prioritize authoritative sources, official websites, and reputable information sources
- Order results by relevance, with the most relevant appearing first
- Generate between 3-10 results depending on the query complexity

Return your response as a JSON object with a "results" array, where each result has "title", "url", and "snippet" fields.

Query:
{query}
"""

class MockWebSearchResult(BaseModel):
    title: str
    url: str
    snippet: str

class MockWebSearchOutput(BaseModel):
    results: list[MockWebSearchResult]


# Technically we do not need LLM here, but I use LLM here to ghe mock results.
class MockWebSearch(OssBaseAgent):
    def __init__(self, model_name: str, api_key: Optional[str] = None):
        logger.info(f"Initializing MockWebSearch with model: {model_name}")
        super().__init__(model_name, api_key)
    
    async def search(self, query: str) -> MockWebSearchOutput:
        logger.info(f"Performing web search for query: '{query}'")
        logger.debug(f"Query length: {len(query)} characters")
        
        full_prompt = PROMPT.format(query=query)
        logger.debug(f"Prompt length: {len(full_prompt)} characters")
        
        try:
            result = await self.generate(
                input=full_prompt,
                schema=MockWebSearchOutput,
                think=False,
                temperature=0.7
            )
            
            logger.info(f"Search completed successfully, found {len(result.results)} results")
            
            if result.results:
                logger.debug(f"Top result: {result.results[0].title}")
                for i, res in enumerate(result.results):
                    logger.debug(f"Result {i+1}: {res.title} - {res.url}")
            else:
                logger.warning(f"No results generated for query: '{query}'")
            
            return result
            
        except Exception as e:
            logger.error(f"Error during web search: {e}", exc_info=True)
            raise



if __name__ == "__main__":
    import asyncio
    import os
    
    async def main():
        # Set log level from environment variable or default to INFO
        log_level = os.getenv("LOG_LEVEL", "DEBUG")
        logger.logger.setLevel(logger._get_log_level(log_level))
        logger.info(f"Log level set to: {log_level}")
        
        # Initialize the web searcher
        searcher = MockWebSearch(
            model_name="meta-llama/Llama-3.1-8B-Instruct",
        )
        
        # Example search query
        print("=" * 80)
        print("Example: Web Search")
        print("=" * 80)
        query = "best practices for Python async programming"
        print(f"Query: {query}")
        print()
        
        # Perform the search
        results = await searcher.search(query=query)
        
        # Display results
        print(f"Found {len(results.results)} results:\n")
        for i, result in enumerate(results.results, 1):
            print(f"{i}. {result.title}")
            print(f"   URL: {result.url}")
            print(f"   Snippet: {result.snippet}")
            print()
    
    asyncio.run(main())