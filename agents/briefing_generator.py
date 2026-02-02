from agents.base_agent import OssBaseAgent
from typing import Optional
from pydantic import BaseModel
from utils.logger import Logger
import json

logger = Logger(__name__)

PROMPT = """
You are a briefing document generator. Your task is to create comprehensive briefing documents from predefined company profile templates.

You will be given:
1. A company profile with structured information about the company
2. A briefing type (e.g., executive_summary, risk_assessment, due_diligence, investment_brief)

Your job is to:
- Analyze the company profile data and generate a well-structured briefing document
- Tailor the content and focus based on the briefing type
- Include relevant sections such as: executive summary, company overview, financial highlights, risk factors, key strengths, recommendations
- Provide actionable insights and clear recommendations
- Highlight any red flags or areas of concern
- Format the output in a professional, executive-ready style

# Return your response as a JSON object with the following fields:
# - title: The title of the briefing document
# - executive_summary: A concise 1 paragraph summary
# - sections: A list of section objects, each with "heading" and "content" fields
# - key_findings: A list of the most important findings (3-5 items)
# - recommendations: A list of actionable recommendations (3-5 items)
# - risk_level: Overall risk assessment (low, medium, high, critical)

Company Profile:
{company_profile}
"""

class BriefingSection(BaseModel):
    heading: str
    content: str

class BriefingDocumentOutput(BaseModel):
    title: str
    executive_summary: str
    sections: list[BriefingSection]
    key_findings: list[str]
    recommendations: list[str]
    risk_level: str


class BriefingGenerator(OssBaseAgent):
    def __init__(self, model_name: str, api_key: Optional[str] = None):
        logger.info(f"Initializing BriefingGenerator with model: {model_name}")
        super().__init__(model_name, api_key)
    
    async def generate_briefing(
        self,
        company_profile: dict,
    ) -> BriefingDocumentOutput:
        logger.info("Generating briefing document")
        logger.debug(f"Company: {company_profile.get('trade_name', 'Unknown')}")
        logger.debug(f"Company ID: {company_profile.get('company_id', 'Unknown')}")
        
        company_profile_str = json.dumps(company_profile, indent=2)
        logger.debug(f"Profile data size: {len(company_profile_str)} characters")
        
        full_prompt = PROMPT.format(
            company_profile=company_profile_str
        )
        logger.debug(f"Prompt length: {len(full_prompt)} characters")
        
        try:
            result = await self.generate(
                input=full_prompt,
                schema=BriefingDocumentOutput,
                think=False,
                temperature=0.4,
            )
            
            logger.info(f"Briefing document generated successfully")
            logger.info(f"Title: {result.title}")
            logger.info(f"Risk level: {result.risk_level}")
            logger.debug(f"Number of sections: {len(result.sections)}")
            logger.debug(f"Number of key findings: {len(result.key_findings)}")
            logger.debug(f"Number of recommendations: {len(result.recommendations)}")
            
            for i, section in enumerate(result.sections, 1):
                logger.debug(f"Section {i}: {section.heading} ({len(section.content)} chars)")
            
            logger.info(f"Key findings summary:")
            for i, finding in enumerate(result.key_findings, 1):
                logger.info(f"  {i}. {finding[:100]}{'...' if len(finding) > 100 else ''}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error during briefing generation: {e}", exc_info=True)
            raise


if __name__ == "__main__":
    import asyncio
    import os
    import json
    
    async def main():
        log_level = os.getenv("LOG_LEVEL", "DEBUG")
        logger.logger.setLevel(logger._get_log_level(log_level))
        logger.info(f"Log level set to: {log_level}")
        
        generator = BriefingGenerator(
            model_name="meta-llama/Llama-3.3-70B-Instruct",
        )
        
        print("=" * 80)
        print("Example: Briefing Document Generation")
        print("=" * 80)
        
        mock_company_profile = {
            "company_id": "C-12345",
            "legal_name": "TechVentures Global Inc.",
            "trade_name": "TechVentures",
            "status": "Active",
            "incorporation_country": "United States",
            "industry": ["Technology", "Software", "Cloud Services"],
            "headquarters": {
                "city": "San Francisco",
                "country": "United States"
            },
            "employee_band": "501-1000",
            "revenue_band_usd": "100M-500M",
            "web_domain": "techventures.com",
            "risk_flags": [
                "Pending litigation in EU market",
                "Recent executive turnover"
            ],
            "last_verified": "2026-01-15",
            "source_systems": ["Bloomberg", "D&B", "Internal"],
            "additional_info": {
                "founded": "2015",
                "funding_rounds": 4,
                "total_funding": "150M USD",
                "key_products": ["Cloud Platform", "AI Analytics", "Data Security"],
                "major_clients": ["Fortune 500 companies", "Government agencies"],
                "recent_news": "Announced expansion into Asian markets"
            }
        }
        
        print("Company Profile:")
        print(json.dumps(mock_company_profile, indent=2))
        print()
        print()
        
        result = await generator.generate_briefing(
            company_profile=mock_company_profile,
        )
        
        print("=" * 80)
        print("Generated Briefing Document:")
        print("=" * 80)
        print(f"\nTitle: {result.title}")
        print(f"Risk Level: {result.risk_level.upper()}")
        print()
        print("Executive Summary:")
        print(result.executive_summary)
        print()
        
        print("=" * 80)
        print("Detailed Sections:")
        print("=" * 80)
        for i, section in enumerate(result.sections, 1):
            print(f"\n{i}. {section.heading}")
            print("-" * 40)
            print(section.content)
        
        print()
        print("=" * 80)
        print("Key Findings:")
        print("=" * 80)
        for i, finding in enumerate(result.key_findings, 1):
            print(f"{i}. {finding}")
        
        print()
        print("=" * 80)
        print("Recommendations:")
        print("=" * 80)
        for i, rec in enumerate(result.recommendations, 1):
            print(f"{i}. {rec}")
        print()
    
    asyncio.run(main())
