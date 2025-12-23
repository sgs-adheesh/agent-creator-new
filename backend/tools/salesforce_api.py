from typing import Dict, Any
import os
import requests
from .base_tool import BaseTool


class SalesforceApiConnector(BaseTool):
    """Tool for interacting with Salesforce data, enabling operations such as querying records and retrieving information from Salesforce databases."""
    
    @classmethod
    def get_config_schema(cls):
        return [
            {
                "name": "api_key",
                "label": "Salesforce API Key",
                "type": "password",
                "required": True,
                "env_var": "SALESFORCE_API_API_KEY"
            }
        ]
    
    def __init__(self):
        super().__init__(
            name="salesforce_api",
            description="This tool allows the agent to search and interact with Salesforce data, enabling operations such as querying records and retrieving information from Salesforce databases."
        )
        self.api_key = os.getenv("SALESFORCE_API_API_KEY")
        self.base_url = "https://your_instance.salesforce.com/services/data/vXX.X/"  # Replace with your Salesforce instance and API version
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute Salesforce operation
        
        Args:
            **kwargs: Operation parameters
            
        Returns:
            Dictionary with results
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "Salesforce API key not configured",
                "suggestion": "Set SALESFORCE_API_API_KEY environment variable"
            }
        
        try:
            # Example operation: querying records
            query = kwargs.get("query")
            if not query:
                return {
                    "success": False,
                    "error": "No query provided",
                    "suggestion": "Provide a valid SOQL query as a parameter"
                }
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            response = requests.get(f"{self.base_url}query?q={query}", headers=headers)
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": response.json().get("message", "Failed to retrieve data from Salesforce"),
                    "status_code": response.status_code
                }
            
            return {
                "success": True,
                "data": response.json()
            }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }