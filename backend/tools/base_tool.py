from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from langchain.tools import StructuredTool


class BaseTool(ABC):
    """Base class for all custom tools"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the tool with given parameters"""
        pass
    
    @classmethod
    def get_config_schema(cls) -> List[Dict[str, Any]]:
        """Return configuration schema for this tool.
        Override this method in subclasses to define required configuration fields.
        
        Returns:
            List of config field definitions, e.g.:
            [
                {
                    "name": "api_key",
                    "label": "API Key",
                    "type": "password",
                    "required": True,
                    "env_var": "STRIPE_API_API_KEY"
                }
            ]
        """
        return []  # Default: no configuration needed
    
    def to_langchain_tool(self) -> StructuredTool:
        """Convert to LangChain tool format"""
        def tool_func(**kwargs) -> str:
            result = self.execute(**kwargs)
            return str(result)
        
        return StructuredTool.from_function(
            func=tool_func,
            name=self.name,
            description=self.description
        )

