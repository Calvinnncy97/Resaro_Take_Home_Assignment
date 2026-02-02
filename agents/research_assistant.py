from agents.base_agent import OssBaseAgent
from agents.web_searcher import MockWebSearch
from agents.company_finder import CompanyFinder
from agents.briefing_generator import BriefingGenerator
from agents.agent_registry import AgentRegistry, AgentParameter, ParameterType
from tools.security_redacter import SecurityRedacter
from tools.tool_registry import ToolRegistry, ToolParameter, ParameterType as ToolParameterType
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from utils.logger import Logger
import json

logger = Logger(__name__)


QUERY_EXTRACTION_PROMPT = """
You are a query analyzer that extracts company information from user queries.

Given a user query about a company, extract:
1. The company name
2. Any additional context about the company (location, industry, status, etc.)

User query: {query}

Return JSON with:
- company_name: The name of the company (string)
- context: Additional context about the company (string, can be empty if none provided)
"""

REACT_PROMPT = """
You are a research assistant that helps consultants by gathering information about companies and producing comprehensive briefing notes.

You have access to the following agents:
{agents_description}

You have access to the following tools:
{tools_description}

Your task is to research the company: {company_name}
Additional context: {context}

Use a ReAct (Reasoning-Action-Observation) loop to accomplish this task:
1. THINK: Reason about what information you need and which tool to use next
2. ACT: Decide which tool to call and with what parameters
3. OBSERVE: Analyze the results from the tool
4. Repeat until you have gathered sufficient information

Your goal is to:
1. Search for information about the company (use agents)
2. Find the company in the internal database (use agents)
3. Generate a comprehensive briefing document (use agents)
4. Ensure all sensitive information is redacted before final output (use tools)

IMPORTANT RULES:
- You MUST redact all sensitive and private information before producing the final output
- The security_redacter tool MUST be called on the final briefing before returning it
- Think step by step and be thorough in your research
- If an agent or tool fails, try alternative approaches

Current step: {current_step}
Previous observations: {previous_observations}

Respond with your reasoning and the next action to take.
Return JSON with:
- reasoning: Your thought process
- action: The agent/tool name to call (or "FINISH" if done)
- action_input: The parameters for the agent/tool (as a dict)
- is_complete: Boolean indicating if the task is complete
"""


class QueryExtraction(BaseModel):
    company_name: str
    context: str


class ReActStep(BaseModel):
    reasoning: str
    action: str
    action_input: Dict[str, Any]
    is_complete: bool


class BriefingOutput(BaseModel):
    company_name: str
    briefing_content: str
    redaction_summary: Dict[str, Any]
    research_steps: List[str]


class ResearchAssistant(OssBaseAgent):
    def __init__(
        self,
        model_name: str,
        api_key: Optional[str] = None,
        max_iterations: int = 10
    ):
        logger.info(f"Initializing ResearchAssistant with model: {model_name}")
        super().__init__(model_name, api_key)
        
        self.max_iterations = max_iterations
        self.agent_registry = AgentRegistry()
        self.tool_registry = ToolRegistry()
        
        self.web_search = MockWebSearch(model_name, api_key)
        self.company_finder = CompanyFinder(model_name, api_key)
        self.briefing_generator = BriefingGenerator(model_name, api_key)
        self.security_redacter = SecurityRedacter()
        
        self.agent_registry.register_agent(
            name="web_search",
            description="Search the web for information about a company or topic. Returns a list of search results with titles, URLs, and snippets.",
            parameters=[
                AgentParameter(
                    name="query",
                    type=ParameterType.STRING,
                    description="The search query to execute",
                    required=True
                )
            ],
            agent_type="search",
            callable_func=self.web_search.search
        )
        
        self.agent_registry.register_agent(
            name="company_finder",
            description="Find company information from the internal database. Searches for companies by name and context, returns detailed company information including financials, risk flags, and metadata.",
            parameters=[
                AgentParameter(
                    name="query_name",
                    type=ParameterType.STRING,
                    description="The company name to search for",
                    required=True
                ),
                AgentParameter(
                    name="context",
                    type=ParameterType.STRING,
                    description="Additional context about the company (location, industry, status, etc.)",
                    required=True
                )
            ],
            agent_type="data_retrieval",
            callable_func=self.company_finder.find_documents
        )
        
        self.agent_registry.register_agent(
            name="briefing_generator",
            description="Generate comprehensive briefing documents from company profiles. Creates executive summaries, risk assessments, and actionable recommendations.",
            parameters=[
                AgentParameter(
                    name="company_profile",
                    type=ParameterType.DICT,
                    description="The company profile data containing all relevant information",
                    required=True
                ),
            ],
            agent_type="analysis",
            callable_func=self.briefing_generator.generate_briefing
        )
        
        self.tool_registry.register_tool(
            name="security_redacter",
            description="Redact sensitive and private information from text. Removes PII, credentials, API keys, and proprietary information before output.",
            parameters=[
                ToolParameter(
                    name="text",
                    type=ToolParameterType.STRING,
                    description="The text to redact sensitive information from",
                    required=True
                ),
                ToolParameter(
                    name="enable_logging",
                    type=ToolParameterType.BOOLEAN,
                    description="Whether to log redaction details",
                    required=False,
                    default=True
                )
            ],
            category="security",
            callable_func=self.security_redacter.redact
        )
        
        logger.info(f"Registered {len(self.agent_registry.get_agent_names())} agents and {len(self.tool_registry.get_tool_names())} tools")
    
    async def _execute_action(self, action: str, action_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an agent or tool and return the result."""
        logger.info(f"Executing action: {action}")
        logger.debug(f"Action input: {action_input}")
        
        agent = self.agent_registry.get_agent(action)
        if agent:
            try:
                if agent.callable_func:
                    result = await agent.callable_func(**action_input)
                    logger.info(f"Agent {action} executed successfully")
                    
                    if hasattr(result, 'model_dump'):
                        return result.model_dump()
                    elif action == "web_search":
                        return {"results": [r.model_dump() for r in result.results]}
                    return result
                else:
                    error_msg = f"Agent '{action}' has no callable function"
                    logger.error(error_msg)
                    return {"error": error_msg}
            except Exception as e:
                error_msg = f"Error executing agent {action}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                return {"error": error_msg}
        
        tool = self.tool_registry.get_tool(action)
        if tool:
            try:
                if tool.callable_func:
                    result = tool.callable_func(**action_input)
                    logger.info(f"Tool {action} executed successfully")
                    return result
                else:
                    error_msg = f"Tool '{action}' has no callable function"
                    logger.error(error_msg)
                    return {"error": error_msg}
            except Exception as e:
                error_msg = f"Error executing tool {action}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                return {"error": error_msg}
        
        error_msg = f"Action '{action}' not found in agent or tool registry"
        logger.error(error_msg)
        return {"error": error_msg}
    
    async def _extract_company_info_from_query(self, query: str) -> QueryExtraction:
        """
        Extract company name and context from a natural language query.
        
        Args:
            query: Natural language query about a company
            
        Returns:
            QueryExtraction with company_name and context
        """
        logger.info(f"Extracting company info from query: {query}")
        
        prompt = QUERY_EXTRACTION_PROMPT.format(query=query)
        
        extraction = await self.generate(
            input=prompt,
            schema=QueryExtraction,
            think=False,
            temperature=0.1
        )
        
        logger.info(f"Extracted company: {extraction.company_name}")
        logger.info(f"Extracted context: {extraction.context}")
        
        return extraction
    
    async def research_and_generate_briefing(
        self,
        query: str,
    ) -> BriefingOutput:
        """
        Research a company and generate a briefing using ReAct loop.
        
        Args:
            query: Natural language query about the company to research
            
        Returns:
            BriefingOutput with redacted briefing content
        """
        logger.info(f"Starting research for query: {query}")
        
        extraction = await self._extract_company_info_from_query(query)
        company_name = extraction.company_name
        context = extraction.context
        
        logger.info(f"Researching company: {company_name}")
        logger.info(f"With context: {context}")
        
        observations = []
        research_steps = []
        company_profile = None
        briefing_document = None
        
        agents_description = self.agent_registry.get_all_agents_description_for_llm()
        tools_description = self.tool_registry.get_all_tools_description_for_llm()
        
        for iteration in range(self.max_iterations):
            logger.info(f"ReAct iteration {iteration + 1}/{self.max_iterations}")
            
            previous_obs = "\n".join(observations[-3:]) if observations else "None"
            
            prompt = REACT_PROMPT.format(
                agents_description=agents_description,
                tools_description=tools_description,
                company_name=company_name,
                context=context,
                current_step=iteration + 1,
                previous_observations=previous_obs
            )
            
            try:
                step = await self.generate(
                    input=prompt,
                    schema=ReActStep,
                    think=True,
                    temperature=0.4
                )
                
                logger.info(f"Reasoning: {step.reasoning}")
                logger.info(f"Action: {step.action}")
                
                if step.action == "FINISH" or step.is_complete:
                    logger.info("ReAct loop completed - FINISH action received")
                    break
                
                result = await self._execute_action(step.action, step.action_input)
                
                action_type = "Agent" if self.agent_registry.get_agent(step.action) else "Tool"
                observation = f"{action_type}: {step.action}\nResult: {json.dumps(result, indent=2)[:500]}"
                observations.append(observation)
                logger.debug(f"Observation: {observation}")
                
                if step.action == "company_finder" and "error" not in result:
                    company_profile = result
                    logger.info("Company profile retrieved successfully")
                
                if step.action == "briefing_generator" and "error" not in result:
                    briefing_document = result
                    logger.info("Briefing document generated successfully")
                
            except Exception as e:
                error_msg = f"Error in ReAct iteration {iteration + 1}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                observations.append(f"Error: {error_msg}")
        
        if not briefing_document:
            logger.warning("No briefing document generated, creating fallback")
            if company_profile:
                logger.info("Generating briefing from company profile")
                result = await self.briefing_generator.generate_briefing(
                    company_profile
                )
                briefing_document = result.model_dump()
            else:
                raise ValueError("Unable to generate briefing: no company profile found")
        
        briefing_text = self._format_briefing_document(briefing_document)
        
        logger.info("Applying security redaction to briefing")
        redaction_result = self.security_redacter.redact(briefing_text, enable_logging=True)
        
        logger.info(f"Redaction complete: {redaction_result['matches_found']} sensitive items redacted")
        
        return BriefingOutput(
            company_name=company_name,
            briefing_content=redaction_result["redacted_text"],
            redaction_summary=redaction_result["sensitivity_summary"],
            research_steps=research_steps
        )
    
    def _format_briefing_document(self, briefing_doc: Dict[str, Any]) -> str:
        """Format briefing document into readable text."""
        lines = []
        lines.append("=" * 80)
        lines.append(briefing_doc.get("title", "Briefing Document"))
        lines.append("=" * 80)
        lines.append("")
        lines.append("EXECUTIVE SUMMARY")
        lines.append("-" * 80)
        lines.append(briefing_doc.get("executive_summary", ""))
        lines.append("")
        
        for section in briefing_doc.get("sections", []):
            lines.append(section.get("heading", "").upper())
            lines.append("-" * 80)
            lines.append(section.get("content", ""))
            lines.append("")
        
        lines.append("KEY FINDINGS")
        lines.append("-" * 80)
        for i, finding in enumerate(briefing_doc.get("key_findings", []), 1):
            lines.append(f"{i}. {finding}")
        lines.append("")
        
        lines.append("RECOMMENDATIONS")
        lines.append("-" * 80)
        for i, rec in enumerate(briefing_doc.get("recommendations", []), 1):
            lines.append(f"{i}. {rec}")
        lines.append("")
        
        lines.append(f"RISK LEVEL: {briefing_doc.get('risk_level', 'UNKNOWN').upper()}")
        lines.append("=" * 80)
        
        return "\n".join(lines)


if __name__ == "__main__":
    import asyncio
    import os
    
    async def main():
        log_level = os.getenv("LOG_LEVEL", "DEBUG")
        logger.logger.setLevel(logger._get_log_level(log_level))
        logger.info(f"Log level set to: {log_level}")
        
        assistant = ResearchAssistant(
            model_name="meta-llama/Llama-3.1-8B-Instruct",
            max_iterations=10
        )
        
        print("=" * 80)
        print("Research Assistant - Company Briefing Generation")
        print("=" * 80)
        print()
        
        query = "Research TechVentures Global, a technology company in the United States, San Francisco, operating in software and cloud services"
        
        print(f"Query: {query}")
        print()
        print("Starting research...")
        print()
        
        result = await assistant.research_and_generate_briefing(
            query=query,
        )
        
        print("=" * 80)
        print("RESEARCH STEPS")
        print("=" * 80)
        for step in result.research_steps:
            print(step)
            print()
        
        print("=" * 80)
        print("REDACTION SUMMARY")
        print("=" * 80)
        print(f"Sensitivity breakdown: {result.redaction_summary}")
        print()
        
        print("=" * 80)
        print("FINAL BRIEFING (REDACTED)")
        print("=" * 80)
        print(result.briefing_content)
        print()
    
    asyncio.run(main())
