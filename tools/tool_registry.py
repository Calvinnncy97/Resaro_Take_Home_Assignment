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
class ToolParameter:
    name: str
    type: ParameterType
    description: str
    required: bool = True
    default: Any = None


@dataclass
class ToolMetadata:
    name: str
    description: str
    parameters: List[ToolParameter]
    category: str
    callable_func: Optional[Callable] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, ToolMetadata] = {}
    
    def register_tool(
        self,
        name: str,
        description: str,
        parameters: List[ToolParameter],
        category: str,
        callable_func: Optional[Callable] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Register a new tool in the registry."""
        if name in self._tools:
            raise ValueError(f"Tool '{name}' is already registered")
        
        tool_metadata = ToolMetadata(
            name=name,
            description=description,
            parameters=parameters,
            category=category,
            callable_func=callable_func,
            metadata=metadata or {}
        )
        
        self._tools[name] = tool_metadata
    
    def unregister_tool(self, name: str) -> None:
        """Remove a tool from the registry."""
        if name in self._tools:
            del self._tools[name]
    
    def get_tool(self, name: str) -> Optional[ToolMetadata]:
        """Get tool metadata by name."""
        return self._tools.get(name)
    
    def list_tools(self, category: Optional[str] = None) -> List[ToolMetadata]:
        """List all registered tools, optionally filtered by category."""
        if category:
            return [tool for tool in self._tools.values() if tool.category == category]
        return list(self._tools.values())
    
    def get_tool_names(self) -> List[str]:
        """Get list of all registered tool names."""
        return list(self._tools.keys())
    
    def get_tool_description_for_llm(self, name: str) -> str:
        """Generate a formatted description of a tool for LLM consumption."""
        tool = self.get_tool(name)
        if not tool:
            return f"Tool '{name}' not found"
        
        params_desc = []
        for param in tool.parameters:
            required_str = "required" if param.required else "optional"
            default_str = f", default={param.default}" if param.default is not None else ""
            params_desc.append(
                f"  - {param.name} ({param.type.value}, {required_str}{default_str}): {param.description}"
            )
        
        params_text = "\n".join(params_desc) if params_desc else "  No parameters"
        
        return f"""Tool: {tool.name}
Category: {tool.category}
Description: {tool.description}
Parameters:
{params_text}"""
    
    def get_all_tools_description_for_llm(self) -> str:
        """Generate a formatted description of all tools for LLM consumption."""
        descriptions = []
        for name in sorted(self._tools.keys()):
            descriptions.append(self.get_tool_description_for_llm(name))
        
        return "\n\n" + "="*80 + "\n\n".join(descriptions)
    
    def call_tool(self, name: str, **kwargs) -> Any:
        """Call a registered tool with the provided arguments."""
        tool = self.get_tool(name)
        if not tool:
            raise ValueError(f"Tool '{name}' not found")
        
        if not tool.callable_func:
            raise ValueError(f"Tool '{name}' has no callable function registered")
        
        return tool.callable_func(**kwargs)


def create_default_tool_registry() -> ToolRegistry:
    """Create and populate a registry with default tools."""
    registry = ToolRegistry()
    
    registry.register_tool(
        name="security_redacter",
        description="Redact sensitive and private information from text. Removes PII, credentials, API keys, and proprietary information before output.",
        parameters=[
            ToolParameter(
                name="text",
                type=ParameterType.STRING,
                description="The text to redact sensitive information from",
                required=True
            ),
            ToolParameter(
                name="enable_logging",
                type=ParameterType.BOOLEAN,
                description="Whether to log redaction details",
                required=False,
                default=True
            )
        ],
        category="security"
    )
    
    return registry


if __name__ == "__main__":
    registry = create_default_tool_registry()
    
    print("=" * 80)
    print("Tool Registry - All Registered Tools")
    print("=" * 80)
    print()
    
    for tool_name in registry.get_tool_names():
        print(registry.get_tool_description_for_llm(tool_name))
        print()
        print("=" * 80)
        print()
    
    print(f"\nTotal tools registered: {len(registry.get_tool_names())}")
    
    print("\nTools by category:")
    categories = set(tool.category for tool in registry.list_tools())
    for category in sorted(categories):
        tools_in_category = registry.list_tools(category=category)
        print(f"  {category}: {len(tools_in_category)} tools")
        for tool in tools_in_category:
            print(f"    - {tool.name}")
