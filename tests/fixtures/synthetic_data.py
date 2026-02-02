import asyncio
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field

sys.path.append(str(Path(__file__).parent.parent.parent))

from agents.base_agent import OssBaseAgent


class Headquarters(BaseModel):
    city: str
    country: str


class CompanyProfile(BaseModel):
    company_id: str
    legal_name: str
    trade_name: str
    status: str
    incorporation_country: str
    industry: List[str]
    headquarters: Headquarters
    employee_band: str
    revenue_band_usd: str
    web_domain: str
    risk_flags: List[str]
    last_verified: str
    source_systems: List[str]


class EnrichedCompanyProfile(CompanyProfile):
    products: List[str] = Field(
        description="List of 2-5 specific products or services offered by the company"
    )
    risk_categories: List[str] = Field(
        description="Risk categories such as: 'weapons_manufacturing', 'dual_use_technology', 'sanctioned_regions', 'politically_exposed', 'high_value_transactions', 'cryptocurrency', 'gambling', 'adult_content', 'sensitive_data_processing', 'critical_infrastructure', 'none'"
    )


class GeneratedFields(BaseModel):
    products: List[str] = Field(
        description="List of 2-5 specific products or services that match the company's industry and size"
    )
    risk_categories: List[str] = Field(
        description="List of 0-3 risk categories based on industry, risk_flags, and business nature. Choose from: 'weapons_manufacturing', 'dual_use_technology', 'sanctioned_regions', 'politically_exposed', 'high_value_transactions', 'cryptocurrency', 'gambling', 'adult_content', 'sensitive_data_processing', 'critical_infrastructure', or 'none' if no special risks"
    )


class SyntheticDataGenerator:
    def __init__(self, model_name: str = "meta-llama/Llama-3.3-70B-Instruct"):
        self.agent = OssBaseAgent(model_name=model_name)
    
    async def generate_missing_fields(self, company: CompanyProfile) -> GeneratedFields:
        prompt = f"""Generate realistic products and risk categories for this company:

Company: {company.trade_name}
Industry: {', '.join(company.industry)}
Employee Band: {company.employee_band}
Revenue Band: {company.revenue_band_usd}
Country: {company.incorporation_country}
Risk Flags: {', '.join(company.risk_flags) if company.risk_flags else 'None'}

Instructions:
1. Generate 2-5 specific, realistic products/services that match the company's industry and scale
2. Assign 0-3 risk categories based on:
   - Industry type (e.g., weapons, gambling, crypto)
   - Existing risk_flags (payment disputes, sanctions, PEP matches)
   - Business nature and geography
3. Use 'none' only if there are truly no special risk categories

Risk Categories Available:
- weapons_manufacturing: Arms, military equipment
- dual_use_technology: Technology with civilian and military applications
- sanctioned_regions: Operations in sanctioned countries
- politically_exposed: PEP connections or government contracts
- high_value_transactions: Large financial movements
- cryptocurrency: Crypto trading or services
- gambling: Gaming, betting, casinos
- adult_content: Adult entertainment
- sensitive_data_processing: Healthcare, financial data
- critical_infrastructure: Energy, utilities, telecom
- none: No special risk categories"""

        result = await self.agent.generate(
            input=prompt,
            schema=GeneratedFields,
            think=True,
            temperature=0.7,
            max_tokens=2048
        )
        
        return result
    
    async def enrich_company(self, company_data: dict) -> dict:
        company = CompanyProfile(**company_data)
        
        generated = await self.generate_missing_fields(company)
        
        enriched_data = company_data.copy()
        enriched_data['products'] = generated.products
        enriched_data['risk_categories'] = generated.risk_categories
        
        return enriched_data
    
    async def process_companies_concurrent(
        self, 
        input_file: Path, 
        output_file: Path,
        max_concurrent: int = 20
    ):
        print(f"Reading companies from {input_file}")
        
        with open(input_file, 'r') as f:
            companies = [json.loads(line) for line in f if line.strip()]
        
        print(f"Loaded {len(companies)} companies")
        print(f"Processing with max {max_concurrent} concurrent requests...")
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_semaphore(company_data: dict, idx: int) -> dict:
            async with semaphore:
                try:
                    print(f"Processing {idx+1}/{len(companies)}: {company_data['trade_name']}")
                    enriched = await self.enrich_company(company_data)
                    print(f"✓ Completed {idx+1}/{len(companies)}: {company_data['trade_name']}")
                    return enriched
                except Exception as e:
                    print(f"✗ Error processing {company_data['trade_name']}: {e}")
                    enriched_data = company_data.copy()
                    enriched_data['products'] = ["Error generating products"]
                    enriched_data['risk_categories'] = ["none"]
                    return enriched_data
        
        tasks = [
            process_with_semaphore(company, idx) 
            for idx, company in enumerate(companies)
        ]
        
        enriched_companies = await asyncio.gather(*tasks)
        
        print(f"\nWriting enriched data to {output_file}")
        with open(output_file, 'w') as f:
            for company in enriched_companies:
                f.write(json.dumps(company) + '\n')
        
        print(f"✓ Successfully wrote {len(enriched_companies)} enriched companies")
        
        self._print_sample(enriched_companies[0])
    
    def _print_sample(self, company: dict):
        print("\n" + "="*80)
        print("SAMPLE ENRICHED COMPANY:")
        print("="*80)
        print(f"Company: {company['trade_name']}")
        print(f"Industry: {', '.join(company['industry'])}")
        print(f"Products: {', '.join(company['products'])}")
        print(f"Risk Categories: {', '.join(company['risk_categories'])}")
        print("="*80 + "\n")


async def main():
    script_dir = Path(__file__).parent
    database_dir = script_dir.parent.parent / "database"
    
    input_file = database_dir / "simulated_companies_100.jsonl"
    output_file = database_dir / "enriched_companies_100.jsonl"
    
    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}")
        return
    
    generator = SyntheticDataGenerator()
    
    await generator.process_companies_concurrent(
        input_file=input_file,
        output_file=output_file,
        max_concurrent=20
    )


if __name__ == "__main__":
    asyncio.run(main())
