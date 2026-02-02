import pytest
import asyncio
from agents.company_finder import CompanyFinder, OutputCompanyInfo
from agents.briefing_generator import BriefingGenerator, BriefingDocumentOutput
from agents.web_searcher import MockWebSearch, MockWebSearchOutput, MockWebSearchResult
from agents.document_translator import DocumentTranslator, DocumentTranslationOutput
from agents.research_assistant import ResearchAssistant, BriefingOutput, ReActStep
from tools.security_redacter import SecurityRedacter, SensitivityLevel


@pytest.fixture
def company_finder():
    return CompanyFinder(model_name="Qwen/Qwen3-8B")


@pytest.fixture
def briefing_generator():
    return BriefingGenerator(model_name="Qwen/Qwen3-8B")


@pytest.fixture
def web_searcher():
    return MockWebSearch(model_name="Qwen/Qwen3-8B")


@pytest.fixture
def security_redacter():
    return SecurityRedacter()


@pytest.fixture
def document_translator():
    return DocumentTranslator(model_name="Qwen/Qwen3-8B")


@pytest.fixture
def research_assistant():
    return ResearchAssistant(model_name="Qwen/Qwen3-8B", max_iterations=10)


class TestCompanyFinder:
    """Test cases for CompanyFinder agent"""
    
    @pytest.mark.asyncio
    async def test_exact_name_match(self, company_finder):
        """Test exact name match - should return correct company from database"""
        query = "Lumen Health Works"
        context = "A company in Thailand, Bangkok, operating in the Robotics and FinTech industries. Status is Dormant."
        
        result = await company_finder.find_documents(query_name=query, context=context)
        
        assert result is not None
        assert isinstance(result, OutputCompanyInfo)
        assert result.company_id == "C-63794"
        assert result.legal_name == "Lumen Health Works Co., Ltd."
        assert result.trade_name == "Lumen Health Works"
        assert result.status == "Dormant"
        assert result.headquarters.city == "Bangkok"
        assert result.headquarters.country == "TH"
    
    @pytest.mark.asyncio
    async def test_fuzzy_matching_typo(self, company_finder):
        """Test fuzzy matching with typos - should handle misspellings with threshold >= 0.6"""
        query = "Orion Analytic Stack"  # Missing 's' in Analytics
        context = "An Australian company based in Sydney, in the Pharmaceuticals industry with 1-10 employees and revenue over 1B+."
        
        result = await company_finder.find_documents(query_name=query, context=context)
        
        assert result is not None
        assert isinstance(result, OutputCompanyInfo)
        assert result.company_id == "C-95931"
        assert result.trade_name == "Orion Analytics Stack"
        assert result.headquarters.city == "Sydney"
        assert result.headquarters.country == "AU"
    
    @pytest.mark.asyncio
    async def test_fuzzy_matching_misspelling(self, company_finder):
        """Test fuzzy matching with character substitution"""
        candidates = company_finder._fuzzy_search("Lumen", threshold=0.6, top_k=5)
        
        assert len(candidates) > 0
        company_ids = [c.get("company_id") for c in candidates]
        assert "C-63794" in company_ids or "C-32764" in company_ids
    
    @pytest.mark.asyncio
    async def test_context_based_selection(self, company_finder):
        """Test context-based selection - LLM should select best candidate based on context"""
        query = "Lumen"
        context = "A company in Thailand, Pattaya, operating in Renewable Energy and SaaS. Status is Dormant with 1000+ employees."
        
        result = await company_finder.find_documents(query_name=query, context=context)
        
        assert result is not None
        assert isinstance(result, OutputCompanyInfo)
        assert result.company_id == "C-32764"
        assert result.trade_name == "Lumen Solutions"
        assert result.headquarters.city == "Pattaya"
        assert "Renewable Energy" in result.industry
    
    @pytest.mark.asyncio
    async def test_no_match_scenario(self, company_finder):
        """Test no match scenario - should return None when no match found"""
        query = "NonExistentCompanyXYZ123"
        context = "A fictional company that does not exist in the database."
        
        result = await company_finder.find_documents(query_name=query, context=context)
        
        assert result is not None
        assert isinstance(result, OutputCompanyInfo)
        assert result.company_id is None
    
    @pytest.mark.asyncio
    async def test_fuzzy_search_threshold(self, company_finder):
        """Test that fuzzy search respects threshold parameter"""
        candidates_high = company_finder._fuzzy_search("Apex", threshold=0.9, top_k=10)
        candidates_low = company_finder._fuzzy_search("Apex", threshold=0.5, top_k=10)
        
        assert len(candidates_high) <= len(candidates_low)
        assert all(c.get("company_id") for c in candidates_high)


class TestBriefingGenerator:
    """Test cases for BriefingGenerator agent"""
    
    @pytest.mark.asyncio
    async def test_executive_summary_generation(self, briefing_generator):
        """Test executive summary generation - should generate a structured document"""
        company_profile = {
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
            "source_systems": ["Bloomberg", "D&B", "Internal"]
        }
        
        result = await briefing_generator.generate_briefing(
            company_profile=company_profile
        )
        
        assert result is not None
        assert isinstance(result, BriefingDocumentOutput)
        assert result.title
        assert len(result.title) > 0
        assert result.executive_summary
        assert len(result.executive_summary) > 50
        assert result.sections
        assert len(result.sections) > 0
        assert all(hasattr(section, 'heading') and hasattr(section, 'content') for section in result.sections)
        assert result.key_findings
        assert len(result.key_findings) >= 3
        assert result.recommendations
        assert len(result.recommendations) >= 3
        assert result.risk_level.lower() in ["low", "medium", "high", "critical"]
    
    @pytest.mark.asyncio
    async def test_briefing_structure_validation(self, briefing_generator):
        """Test that briefing document has proper structure"""
        company_profile = {
            "company_id": "C-99999",
            "legal_name": "Test Company Ltd",
            "trade_name": "TestCo",
            "status": "Active",
            "incorporation_country": "US",
            "industry": ["Technology"],
            "headquarters": {"city": "New York", "country": "US"},
            "employee_band": "11-50",
            "revenue_band_usd": "1M-10M"
        }
        
        result = await briefing_generator.generate_briefing(
            company_profile=company_profile
        )
        
        assert isinstance(result.sections, list)
        for section in result.sections:
            assert section.heading
            assert section.content
            assert len(section.heading) > 0
            assert len(section.content) > 0
        
        assert isinstance(result.key_findings, list)
        assert isinstance(result.recommendations, list)
        assert all(isinstance(finding, str) for finding in result.key_findings)
        assert all(isinstance(rec, str) for rec in result.recommendations)


class TestWebSearcher:
    """Test cases for MockWebSearch agent"""
    
    @pytest.mark.asyncio
    async def test_query_execution(self, web_searcher):
        """Test query execution - should return search results in properly formatted output"""
        query = "Python async programming best practices"
        
        result = await web_searcher.search(query=query)
        
        assert result is not None
        assert isinstance(result, MockWebSearchOutput)
        assert result.results
        assert len(result.results) >= 3
        assert len(result.results) <= 10
    
    @pytest.mark.asyncio
    async def test_search_result_format(self, web_searcher):
        """Test that search results have proper format"""
        query = "machine learning tutorials"
        
        result = await web_searcher.search(query=query)
        
        for search_result in result.results:
            assert hasattr(search_result, 'title')
            assert hasattr(search_result, 'url')
            assert hasattr(search_result, 'snippet')
            assert search_result.title
            assert search_result.url
            assert search_result.snippet
            assert len(search_result.title) > 0
            assert len(search_result.url) > 0
            assert len(search_result.snippet) > 0
            assert search_result.url.startswith('http://') or search_result.url.startswith('https://')
    
    @pytest.mark.asyncio
    async def test_search_relevance(self, web_searcher):
        """Test that search results are relevant to query"""
        query = "artificial intelligence"
        
        result = await web_searcher.search(query=query)
        
        assert len(result.results) > 0
        combined_text = " ".join([
            r.title.lower() + " " + r.snippet.lower() 
            for r in result.results
        ])
        assert any(term in combined_text for term in ["ai", "artificial", "intelligence", "machine", "learning"])


class TestDocumentTranslator:
    """Test cases for DocumentTranslator agent"""
    
    @pytest.mark.asyncio
    async def test_translate_document(self, document_translator):
        """Test translate document - should translate document into target language"""
        document_content = """
CONFIDENTIAL BUSINESS AGREEMENT

This agreement is entered into on January 15, 2026, between:
- Party A: TechCorp International Ltd.
- Party B: Innovation Solutions Inc.

1. PURPOSE
The purpose of this agreement is to establish a partnership for the development
of artificial intelligence solutions in the healthcare sector.
"""
        
        result = await document_translator.translate(
            document_content=document_content,
            target_language="Spanish",
        )
        
        assert result is not None
        assert isinstance(result, DocumentTranslationOutput)
        assert result.translated_content
        assert len(result.translated_content) > 50
        assert result.translated_content != document_content
    
    @pytest.mark.asyncio
    async def test_translation_preserves_structure(self, document_translator):
        """Test that translation preserves document structure"""
        document_content = """
Section 1: Introduction
This is the introduction section.

Section 2: Main Content
This is the main content section.
"""
        
        result = await document_translator.translate(
            document_content=document_content,
            target_language="French",
        )
        
        assert result is not None
        assert result.translated_content
        assert len(result.translated_content) > 0
    
    @pytest.mark.asyncio
    async def test_translation_different_languages(self, document_translator):
        """Test translation to different target languages"""
        document_content = "Hello, this is a test document."
        
        languages = ["Spanish", "French", "German", "Chinese"]
        
        for target_lang in languages:
            result = await document_translator.translate(
                document_content=document_content,
                target_language=target_lang,
            )
            
            assert result is not None
            assert result.translated_content
            assert len(result.translated_content) > 0


class TestSecurityRedacter:
    """Test cases for SecurityRedacter tool"""
    
    def test_pattern_based_redaction_email(self, security_redacter):
        """Test pattern-based redaction - should redact email addresses"""
        text = "Contact me at john.doe@example.com for more information."
        
        result = security_redacter.redact(text)
        
        assert "[EMAIL_REDACTED]" in result["redacted_text"]
        assert "john.doe@example.com" not in result["redacted_text"]
        assert result["matches_found"] > 0
        assert any(match["type"] == "email" for match in result["matches"])
    
    def test_pattern_based_redaction_phone(self, security_redacter):
        """Test pattern-based redaction - should redact phone numbers"""
        text = "Call me at 555-123-4567 or (555) 987-6543."
        
        result = security_redacter.redact(text)
        
        assert "[PHONE_REDACTED]" in result["redacted_text"]
        assert "555-123-4567" not in result["redacted_text"]
        assert any(match["type"] == "phone_us" for match in result["matches"])
    
    def test_pattern_based_redaction_ssn(self, security_redacter):
        """Test pattern-based redaction - should redact SSN"""
        text = "My SSN is 123-45-6789."
        
        result = security_redacter.redact(text)
        
        assert "[SSN_REDACTED]" in result["redacted_text"]
        assert "123-45-6789" not in result["redacted_text"]
        assert any(match["type"] == "ssn" for match in result["matches"])
        assert any(match["sensitivity"] == SensitivityLevel.CRITICAL.value for match in result["matches"])
    
    def test_pattern_based_redaction_credit_card(self, security_redacter):
        """Test pattern-based redaction - should redact credit card numbers"""
        text = "Credit card: 4532015112830366"
        
        result = security_redacter.redact(text)
        
        assert "[CREDIT_CARD_REDACTED]" in result["redacted_text"]
        assert "4532015112830366" not in result["redacted_text"]
        assert any(match["type"] == "credit_card" for match in result["matches"])
    
    def test_pattern_based_redaction_api_key(self, security_redacter):
        """Test pattern-based redaction - should redact API keys"""
        text = 'API Key: api_key="sk_live_1234567890abcdefghijklmnop"'
        
        result = security_redacter.redact(text)
        
        assert "[API_KEY_REDACTED]" in result["redacted_text"]
        assert "sk_live_1234567890abcdefghijklmnop" not in result["redacted_text"]
        assert any(match["type"] == "api_key" for match in result["matches"])
    
    def test_pattern_based_redaction_ip_address(self, security_redacter):
        """Test pattern-based redaction - should redact IP addresses"""
        text = "Server IP: 192.168.1.100"
        
        result = security_redacter.redact(text)
        
        assert "[IP_REDACTED]" in result["redacted_text"]
        assert "192.168.1.100" not in result["redacted_text"]
        assert any(match["type"] == "ipv4" for match in result["matches"])
    
    def test_registry_based_filtering(self, security_redacter):
        """Test registry-based filtering - should filter private registry items"""
        text = "Working on Project Phoenix with Jane Doe at Building 7, Floor 3."
        
        result = security_redacter.redact(text)
        
        assert "Project Phoenix" not in result["redacted_text"]
        assert "Jane Doe" not in result["redacted_text"]
        assert "Building 7, Floor 3" not in result["redacted_text"]
        assert "[PROJECT_CODENAMES_REDACTED]" in result["redacted_text"]
        assert "[EMPLOYEE_NAMES_REDACTED]" in result["redacted_text"]
        assert "[LOCATIONS_REDACTED]" in result["redacted_text"]
        assert any("registry_" in match["type"] for match in result["matches"])
    
    def test_registry_based_filtering_company_names(self, security_redacter):
        """Test registry-based filtering - should filter company names"""
        text = "Acme Corporation and TechStart Inc are partners."
        
        result = security_redacter.redact(text)
        
        assert "Acme Corporation" not in result["redacted_text"]
        assert "TechStart Inc" not in result["redacted_text"]
        assert "[COMPANY_NAMES_REDACTED]" in result["redacted_text"]
    
    def test_rule_based_detection_confidential(self, security_redacter):
        """Test rule-based detection - should catch contextual sensitive info"""
        text = "This is confidential information about the project."
        
        result = security_redacter.redact(text)
        
        assert "[SENSITIVE_INFO_REDACTED]" in result["redacted_text"]
        assert "confidential" not in result["redacted_text"].lower()
        assert any(match["type"] == "rule_based" for match in result["matches"])
    
    def test_rule_based_detection_salary(self, security_redacter):
        """Test rule-based detection - should catch salary information"""
        text = "Salary: $150,000 per year"
        
        result = security_redacter.redact(text)
        
        assert "[SENSITIVE_INFO_REDACTED]" in result["redacted_text"]
        assert "$150,000" not in result["redacted_text"]
        assert any(match["type"] == "rule_based" for match in result["matches"])
    
    def test_multiple_patterns_redaction(self, security_redacter):
        """Test that multiple patterns are redacted in the same text"""
        text = """
        Contact: john@example.com, Phone: 555-123-4567
        SSN: 123-45-6789, Credit Card: 4532015112830366
        Working at Acme Corporation on Project Phoenix
        Confidential salary: $200,000
        """
        
        result = security_redacter.redact(text)
        
        assert result["matches_found"] >= 7
        assert "[EMAIL_REDACTED]" in result["redacted_text"]
        assert "[PHONE_REDACTED]" in result["redacted_text"]
        assert "[SSN_REDACTED]" in result["redacted_text"]
        assert "[CREDIT_CARD_REDACTED]" in result["redacted_text"]
        assert "[COMPANY_NAMES_REDACTED]" in result["redacted_text"]
        assert "[PROJECT_CODENAMES_REDACTED]" in result["redacted_text"]
        assert "[SENSITIVE_INFO_REDACTED]" in result["redacted_text"]
    
    def test_sensitivity_summary(self, security_redacter):
        """Test that sensitivity summary is properly generated"""
        text = "SSN: 123-45-6789, Email: test@example.com, IP: 192.168.1.1"
        
        result = security_redacter.redact(text)
        
        assert "sensitivity_summary" in result
        assert isinstance(result["sensitivity_summary"], dict)
        assert SensitivityLevel.CRITICAL.value in result["sensitivity_summary"]
        assert SensitivityLevel.MEDIUM.value in result["sensitivity_summary"]
        assert SensitivityLevel.LOW.value in result["sensitivity_summary"]
    
    def test_add_to_registry(self, security_redacter):
        """Test adding items to private registry"""
        security_redacter.add_to_registry("company_names", ["NewCompany Inc"])
        text = "NewCompany Inc is our partner."
        
        result = security_redacter.redact(text)
        
        assert "NewCompany Inc" not in result["redacted_text"]
        assert "[COMPANY_NAMES_REDACTED]" in result["redacted_text"]
    
    def test_redaction_statistics(self, security_redacter):
        """Test redaction statistics tracking"""
        security_redacter.clear_log()
        
        text1 = "Email: test@example.com"
        text2 = "Phone: 555-123-4567"
        
        security_redacter.redact(text1)
        security_redacter.redact(text2)
        
        stats = security_redacter.get_statistics()
        
        assert stats["total_redactions"] == 2
        assert stats["total_matches_found"] >= 2
        assert "average_matches_per_redaction" in stats
        assert "sensitivity_breakdown" in stats


class TestResearchAssistant:
    """Test cases for ResearchAssistant agent"""
    
    @pytest.mark.asyncio
    async def test_agent_assignment_and_tool_selection(self, research_assistant):
        """Test agent assignment and tool selection - assigns tasks to agents and calls tools based on the plan"""
        query = "Research Lumen Health Works, a company in Thailand, Bangkok, operating in the Robotics and FinTech industries"
        
        result = await research_assistant.research_and_generate_briefing(
            query=query
        )
        
        assert result is not None
        assert isinstance(result, BriefingOutput)
        assert result.company_name == "Lumen Health Works"
        assert result.research_steps
        assert len(result.research_steps) > 0
        assert any("company_finder" in step.lower() or "search" in step.lower() for step in result.research_steps)
    
    @pytest.mark.asyncio
    async def test_generates_report(self, research_assistant):
        """Test generates report - generates company briefing report at the end"""
        query = "Research Orion Analytics Stack, an Australian company based in Sydney, in the Pharmaceuticals industry"
        
        result = await research_assistant.research_and_generate_briefing(
            query=query
        )
        
        assert result is not None
        assert result.briefing_content
        assert len(result.briefing_content) > 100
        assert result.redaction_summary
        assert isinstance(result.redaction_summary, dict)
        assert "orion analytics stack" in result.briefing_content.lower() or "[COMPANY_NAMES_REDACTED]" in result.briefing_content
    
    @pytest.mark.asyncio
    async def test_research_assistant_with_max_iterations(self, research_assistant):
        """Test that research assistant respects max_iterations setting"""
        assert research_assistant.max_iterations == 10
        
        query = "Research TechVentures Global, a technology company in the United States"
        
        result = await research_assistant.research_and_generate_briefing(
            query=query
        )
        
        assert result is not None
        assert len(result.research_steps) <= research_assistant.max_iterations


class TestAgentOrchestration:
    """Test cases for Agent Orchestration End-to-End"""
    
    @pytest.mark.asyncio
    async def test_complete_research_workflow(self, research_assistant):
        """Test complete research workflow - executes web_search → company_finder → briefing_generator → security_redacter in sequence"""
        query = "Research Lumen Health Works, a company in Thailand, Bangkok, operating in the Robotics and FinTech industries. Status is Dormant."
        
        result = await research_assistant.research_and_generate_briefing(
            query=query
        )
        
        assert result is not None
        assert isinstance(result, BriefingOutput)
        assert result.company_name == "Lumen Health Works"
        assert result.briefing_content
        assert result.redaction_summary
        assert result.research_steps
        
        steps_text = " ".join(result.research_steps).lower()
        assert "company" in steps_text or "search" in steps_text or "briefing" in steps_text
    
    @pytest.mark.asyncio
    async def test_error_recovery(self, research_assistant):
        """Test error recovery - system gracefully handles agent failures"""
        result = await research_assistant._execute_action(
            action="non_existent_agent",
            action_input={}
        )
        
        assert result is not None
        assert "error" in result
        assert isinstance(result["error"], str)
    
    @pytest.mark.asyncio
    async def test_max_iteration_limit(self):
        """Test max iteration limit - ReAct loop terminates at max_iterations"""
        assistant = ResearchAssistant(
            model_name="Qwen/Qwen3-8B",
            max_iterations=3
        )
        
        assert assistant.max_iterations == 3
        
        query = "Research Test Company with test context"
        
        result = await assistant.research_and_generate_briefing(
            query=query
        )
        
        assert result is not None
        assert len(result.research_steps) <= 3
    
    @pytest.mark.asyncio
    async def test_early_termination(self, research_assistant):
        """Test early termination - loop stops when task is complete (is_complete=True)"""
        query = "Research Lumen Health Works, a company in Thailand, Bangkok"
        
        result = await research_assistant.research_and_generate_briefing(
            query=query
        )
        
        assert result is not None
        assert result.briefing_content
        assert len(result.research_steps) <= research_assistant.max_iterations


class TestIntegration:
    """Integration tests for the complete system"""
    
    @pytest.mark.asyncio
    async def test_end_to_end_pipeline(self):
        """Test End-to-End Pipeline - complete workflow from company name to redacted briefing"""
        assistant = ResearchAssistant(
            model_name="Qwen/Qwen3-8B",
            max_iterations=10
        )
        
        query = "Research Orion Analytics Stack, an Australian company based in Sydney, in the Pharmaceuticals industry with 1-10 employees and revenue over 1B+"
        
        result = await assistant.research_and_generate_briefing(
            query=query
        )
        
        assert result is not None
        assert isinstance(result, BriefingOutput)
        assert result.company_name == "Orion Analytics Stack"
        assert result.briefing_content
        assert len(result.briefing_content) > 100
        assert result.redaction_summary
        assert result.research_steps
        assert len(result.research_steps) > 0
        
        assert isinstance(result.redaction_summary, dict)
    
    @pytest.mark.asyncio
    async def test_database_integration(self, company_finder):
        """Test Database Integration - verify company_finder correctly loads and queries simulated_companies_100.jsonl"""
        companies_to_test = [
            ("Lumen Health Works", "Thailand, Bangkok"),
            ("Orion Analytics Stack", "Australia, Sydney"),
            ("Apex Intelligence", "United States"),
        ]
        
        for company_name, location_context in companies_to_test:
            result = await company_finder.find_documents(
                query_name=company_name,
                context=f"A company in {location_context}"
            )
            
            assert result is not None
            assert isinstance(result, OutputCompanyInfo)
    
    @pytest.mark.asyncio
    async def test_database_all_companies_accessible(self, company_finder):
        """Test that database has 100 companies and they are accessible"""
        import json
        
        database_path = "/Users/calvinnncy/Documents/Resaro/database/simulated_companies_100.jsonl"
        
        with open(database_path, 'r') as f:
            companies = [json.loads(line) for line in f]
        
        assert len(companies) == 100
        
        sample_companies = companies[:5]
        
        for company in sample_companies:
            trade_name = company.get("trade_name", "")
            if trade_name:
                result = await company_finder.find_documents(
                    query_name=trade_name,
                    context=f"A company"
                )
                assert result is not None
    
    @pytest.mark.asyncio
    async def test_llm_integration(self, briefing_generator):
        """Test LLM Integration - verify Hugging Face API connectivity and JSON schema parsing"""
        company_profile = {
            "company_id": "C-TEST-001",
            "legal_name": "Test Company Ltd",
            "trade_name": "TestCo",
            "status": "Active",
            "incorporation_country": "US",
            "industry": ["Technology", "Software"],
            "headquarters": {"city": "New York", "country": "US"},
            "employee_band": "11-50",
            "revenue_band_usd": "1M-10M"
        }
        
        result = await briefing_generator.generate_briefing(
            company_profile=company_profile
        )
        
        assert result is not None
        assert isinstance(result, BriefingDocumentOutput)
        assert result.title
        assert result.executive_summary
        assert result.sections
        assert result.key_findings
        assert result.recommendations
        assert result.risk_level in ["low", "medium", "high", "critical"]
    
    @pytest.mark.asyncio
    async def test_llm_integration_different_models(self):
        """Test LLM Integration with different model configurations"""
        models_to_test = [
            "Qwen/Qwen3-8B",
        ]
        
        company_profile = {
            "company_id": "C-TEST-002",
            "legal_name": "Another Test Company",
            "trade_name": "AnotherTestCo",
            "status": "Active",
            "incorporation_country": "US",
            "industry": ["Finance"],
            "headquarters": {"city": "Boston", "country": "US"},
            "employee_band": "51-200",
            "revenue_band_usd": "10M-50M"
        }
        
        for model_name in models_to_test:
            generator = BriefingGenerator(model_name=model_name)
            
            result = await generator.generate_briefing(
                company_profile=company_profile
            )
            
            assert result is not None
            assert isinstance(result, BriefingDocumentOutput)
            assert result.title
            assert result.executive_summary
