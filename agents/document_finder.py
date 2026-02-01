from agents.base_agent import OssBaseAgent
from pydantic import BaseModel
from typing import Optional
import json
from rapidfuzz import fuzz
from utils.logger import Logger

logger = Logger(__name__)

PROMPT = """
You are a document finder assistant. Your task is to select the correct company from a list of candidate companies based on the provided context.

You will be given:
1. A query name - the company name being searched for
2. Context - additional information about the company (e.g., location, industry, status, etc.)
3. A list of indexed candidate companies with their details

Your job is to:
- Carefully analyze the context and compare it with each candidate's information
- Select the company that best matches the context by returning its index (0-based)
- If none of the candidates match the context well enough, return null for the index
- Consider factors like: location (city, country), industry, company status, employee count, revenue, and any other relevant details

Be strict in your matching - only return a company index if you are confident it matches the context.

Provide your reasoning for the selection and the index of the selected candidate (0-based indexing).
If no candidate matches, set index to null.

Context:
{context}

Query Name:
{query_name}

Candidate Companies:
{candidates_text}

"""

class Headquarter(BaseModel):
    city: str
    country: str

class OutputCompanyInfo(BaseModel):
    company_id: str
    legal_name: str
    trade_name: str
    status: str
    incorporation_country: str
    industry: list[str]
    headquarters: Headquarter
    employee_band: str
    revenue_band_usd: str
    web_domain: str
    risk_flags: list[str]
    last_verified: str
    source_systems: list[str]


class DocumentSelectionResult(BaseModel):
    reasoning: str
    index: Optional[int]


class DocumentFinder(OssBaseAgent):
    def __init__(self, model_name: str, api_key: Optional[str] = None):
        logger.info(f"Initializing DocumentFinder with model: {model_name}")
        super().__init__(model_name, api_key)
        self.database = []
        with open("database/simulated_companies_100.jsonl", "r") as f:
            for line in f:
                self.database.append(json.loads(line.strip()))

    def _fuzzy_search(self, input_str: str, threshold: float = 0.6, top_k: int = 3) -> list:
        """
        Fuzzy search across company records based on company name.
        Searches in legal_name and trade_name fields only.
        
        Args:
            input_str: Search query string
            threshold: Minimum similarity score (0-1) to include results
            top_k: Maximum number of results to return
            
        Returns:
            List of matching company records sorted by relevance
        """
        logger.debug(f"Starting fuzzy search for: '{input_str}' (threshold={threshold}, top_k={top_k})")
        input_lower = input_str.lower()
        results = []
        
        for doc in self.database:
            max_score = 0.0
            
            # Search only in company name fields
            searchable_fields = [
                doc.get("legal_name", ""),
                doc.get("trade_name", ""),
                doc.get("web_domain", ""),
            ]
            
            for field_value in searchable_fields:
                field_lower = str(field_value).lower()
                
                # Exact substring match gets highest score
                if input_lower in field_lower:
                    max_score = max(max_score, 1.0)
                    logger.debug(f"Exact match found in '{field_value}' for company {doc.get('company_id')}")
                    break
                
                # Otherwise use fuzzy matching
                similarity = fuzz.ratio(input_lower, field_lower) / 100.0
                max_score = max(max_score, similarity)
            
            if max_score >= threshold:
                results.append({"score": max_score, "document": doc})
                logger.debug(f"Candidate found: {doc.get('company_id')} - {doc.get('trade_name')} (score={max_score:.3f})")
        
        # Sort by score descending and return top_k
        results.sort(key=lambda x: x["score"], reverse=True)
        top_results = [r["document"] for r in results[:top_k]]
        
        logger.info(f"Fuzzy search for '{input_str}' returned {len(top_results)} candidates out of {len(results)} matches")
        if top_results:
            logger.debug(f"Top candidate: {top_results[0].get('company_id')} - {top_results[0].get('trade_name')}")
        
        return top_results

    async def find_documents(self, query_name: str, context: str) -> Optional[OutputCompanyInfo]:
        """
        Find the most relevant company document based on query name and context.
        
        Args:
            query_name: The company name to search for
            context: Additional context about the company to help with selection
            
        Returns:
            OutputCompanyInfo object if a match is found, None otherwise
        """
        logger.info(f"Finding documents for query: '{query_name}'")
        logger.debug(f"Context: {context}")
        
        top_candidates = self._fuzzy_search(query_name)
        
        if not top_candidates:
            logger.warning(f"No candidates found for query: '{query_name}'")
            return None
        
        logger.info(f"Found {len(top_candidates)} candidates, sending to LLM for selection")
        
        # Format candidates for the LLM with 0-based indexing
        candidates_text = "\n\n".join([
            f"Index {i}:\n{json.dumps(candidate, indent=2)}"
            for i, candidate in enumerate(top_candidates)
        ])
        
        # Construct the prompt using the template variables
        full_prompt = PROMPT.format(
            context=context,
            query_name=query_name,
            candidates_text=candidates_text
        )
        
        logger.debug(f"Prompt length: {len(full_prompt)} characters")
        
        try:
            # Use the LLM to select the best candidate
            result = await self.generate(
                input=full_prompt,
                schema=DocumentSelectionResult,
                think=True,
                temperature=0.3
            )
            
            logger.debug(f"Input prompt: {full_prompt}")
            logger.debug(f"LLM reasoning: {result.reasoning}")
            logger.info(f"LLM selected index: {result.index}")
            
            # Return the selected company based on index, or None if no match
            if result.index is None:
                logger.info(f"No matching company found for query: '{query_name}'")
                return None
            
            # Validate index is within range
            if 0 <= result.index < len(top_candidates):
                selected = top_candidates[result.index]
                logger.info(f"Selected company: {selected.get('company_id')} - {selected.get('trade_name')}")
                return OutputCompanyInfo(**selected)
            else:
                logger.error(f"Invalid index {result.index} returned by LLM (valid range: 0-{len(top_candidates)-1})")
                return None
                
        except Exception as e:
            logger.error(f"Error during LLM selection: {e}", exc_info=True)
            raise



if __name__ == "__main__":
    import asyncio
    import os
    
    async def main():
        # Set log level from environment variable or default to INFO
        log_level = os.getenv("LOG_LEVEL", "DEBUG")
        logger.logger.setLevel(logger._get_log_level(log_level))
        logger.info(f"Log level set to: {log_level}")
        
        # Initialize the document finder
        finder = DocumentFinder(
            model_name="meta-llama/Llama-3.1-8B-Instruct",
        )
        
        # Example 1: Correct spelling
        print("=" * 80)
        print("Example 1: Correct spelling")
        print("=" * 80)
        query1 = "Lumen Health Works"
        context1 = "A company in Thailand, Bangkok, operating in the Robotics and FinTech industries. Status is Dormant."
        print(f"Query: {query1}")
        print(f"Context: {context1}")
        print(f"Expected: C-63794 - Lumen Health Works Co., Ltd.")
        result1 = await finder.find_documents(query_name=query1, context=context1)
        print(f"Result: {result1}")
        print()
        
        # Example 2: Misspelling - missing letter
        print("=" * 80)
        print("Example 2: Misspelling - missing letter")
        print("=" * 80)
        query2 = "Orion Analytic Stack"  # Missing 's' in Analytics
        context2 = "An Australian company based in Sydney, in the Pharmaceuticals industry with 1-10 employees and revenue over 1B+."
        print(f"Query: {query2}")
        print(f"Context: {context2}")
        print(f"Expected: C-95931 - Orion Analytics Stack Ltd")
        result2 = await finder.find_documents(query_name=query2, context=context2)
        print(f"Result: {result2}")
        print()
        
        # Example 3: Misspelling - typo
        print("=" * 80)
        print("Example 3: Misspelling - typo")
        print("=" * 80)
        query3 = "BlueRok Energy"  # 'Rock' misspelled as 'Rok'
        context3 = "A Korean company in Daejeon, in the Travel industry, with 1-10 employees and revenue under 1M."
        print(f"Query: {query3}")
        print(f"Context: {context3}")
        print(f"Expected: C-27868 - BlueRock Energy Co., Ltd.")
        result3 = await finder.find_documents(query_name=query3, context=context3)
        print(f"Result: {result3}")
        print()
    
    asyncio.run(main())