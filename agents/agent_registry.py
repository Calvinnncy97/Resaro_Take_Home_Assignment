from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum


class ParameterType(Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    LIST = "list"
    DICT = "dict"
    OBJECT = "object"


@dataclass
class AgentParameter:
    name: str
    type: ParameterType
    description: str
    required: bool = True
    default: Any = None


@dataclass
class AgentMetadata:
    name: str
    description: str
    parameters: List[AgentParameter]
    agent_type: str
    callable_func: Optional[Callable] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentRegistry:
    def __init__(self):
        self._agents: Dict[str, AgentMetadata] = {}
    
    def register_agent(
        self,
        name: str,
        description: str,
        parameters: List[AgentParameter],
        agent_type: str,
        callable_func: Optional[Callable],
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Register a new agent in the registry."""
        if name in self._agents:
            raise ValueError(f"Agent '{name}' is already registered")
        
        agent_metadata = AgentMetadata(
            name=name,
            description=description,
            parameters=parameters,
            agent_type=agent_type,
            callable_func=callable_func,
            metadata=metadata or {}
        )
        
        self._agents[name] = agent_metadata
    
    def unregister_agent(self, name: str) -> None:
        """Remove an agent from the registry."""
        if name in self._agents:
            del self._agents[name]
    
    def get_agent(self, name: str) -> Optional[AgentMetadata]:
        """Get agent metadata by name."""
        return self._agents.get(name)
    
    def list_agents(self, agent_type: Optional[str] = None) -> List[AgentMetadata]:
        """List all registered agents, optionally filtered by type."""
        if agent_type:
            return [agent for agent in self._agents.values() if agent.agent_type == agent_type]
        return list(self._agents.values())
    
    def get_agent_names(self) -> List[str]:
        """Get list of all registered agent names."""
        return list(self._agents.keys())
    
    def get_agent_description_for_llm(self, name: str) -> str:
        """Generate a formatted description of an agent for LLM consumption."""
        agent = self.get_agent(name)
        if not agent:
            return f"Agent '{name}' not found"
        
        params_desc = []
        for param in agent.parameters:
            required_str = "required" if param.required else "optional"
            default_str = f", default={param.default}" if param.default is not None else ""
            params_desc.append(
                f"  - {param.name} ({param.type.value}, {required_str}{default_str}): {param.description}"
            )
        
        params_text = "\n".join(params_desc) if params_desc else "  No parameters"
        
        return f"""Agent: {agent.name}
Type: {agent.agent_type}
Description: {agent.description}
Parameters:
{params_text}"""
    
    def get_all_agents_description_for_llm(self) -> str:
        """Generate a formatted description of all agents for LLM consumption."""
        descriptions = []
        for name in sorted(self._agents.keys()):
            descriptions.append(self.get_agent_description_for_llm(name))
        
        return "\n\n" + "="*80 + "\n\n".join(descriptions)
    
    async def call_agent(self, name: str, **kwargs) -> Any:
        """Call a registered agent with the provided arguments."""
        agent = self.get_agent(name)
        if not agent:
            raise ValueError(f"Agent '{name}' not found")
        
        if not agent.callable_func:
            raise ValueError(f"Agent '{name}' has no callable function registered")
        
        return await agent.callable_func(**kwargs)


def create_default_agent_registry() -> AgentRegistry:
    """Create and populate a registry with default agents."""
    registry = AgentRegistry()
    
    registry.register_agent(
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
        agent_type="search"
    )
    
    registry.register_agent(
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
        agent_type="data_retrieval"
    )
    
    registry.register_agent(
        name="document_translator",
        description="Translate documents from one language to another while preserving formatting and professional tone.",
        parameters=[
            AgentParameter(
                name="document_content",
                type=ParameterType.STRING,
                description="The document content to translate",
                required=True
            ),
            AgentParameter(
                name="target_language",
                type=ParameterType.STRING,
                description="The target language for translation",
                required=True
            ),
        ],
        agent_type="translation"
    )
    
    registry.register_agent(
        name="briefing_generator",
        description="Generate comprehensive briefing documents from company profiles. Creates executive summaries, risk assessments, and actionable recommendations.",
        parameters=[
            AgentParameter(
                name="company_profile",
                type=ParameterType.DICT,
                description="The company profile data containing all relevant information",
                required=True
            ),
            AgentParameter(
                name="briefing_type",
                type=ParameterType.STRING,
                description="Type of briefing (e.g., executive_summary, risk_assessment, due_diligence)",
                required=False,
                default="executive_summary"
            )
        ],
        agent_type="analysis"
    )
    
    return registry


if __name__ == "__main__":
    registry = create_default_agent_registry()
    
    print("=" * 80)
    print("Agent Registry - All Registered Agents")
    print("=" * 80)
    print()
    
    for agent_name in registry.get_agent_names():
        print(registry.get_agent_description_for_llm(agent_name))
        print()
        print("=" * 80)
        print()
    
    print(f"\nTotal agents registered: {len(registry.get_agent_names())}")
    
    print("\nAgents by type:")
    agent_types = set(agent.agent_type for agent in registry.list_agents())
    for agent_type in sorted(agent_types):
        agents_of_type = registry.list_agents(agent_type=agent_type)
        print(f"  {agent_type}: {len(agents_of_type)} agents")
        for agent in agents_of_type:
            print(f"    - {agent.name}")
