from abc import ABC, abstractmethod
from typing import Dict, Any
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

