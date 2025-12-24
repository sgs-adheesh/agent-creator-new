from typing import Dict, Any
import os
import requests
from .base_tool import BaseTool


class SalesforceApiConnector(BaseTool):
    """Tool for interacting with Salesforce data using OAuth 2.0, enabling operations such as querying records and retrieving information from Salesforce databases."""
    
    @classmethod
    def get_config_schema(cls):
        return [
            {
                "name": "access_token",
                "label": "Salesforce OAuth Access Token",
                "type": "password",
                "required": True,
                "env_var": "SALESFORCE_ACCESS_TOKEN",
                "description": "OAuth 2.0 access token from Salesforce Connected App"
            },
            {
                "name": "instance_url",
                "label": "Salesforce Instance URL",
                "type": "text",
                "required": True,
                "env_var": "SALESFORCE_INSTANCE_URL",
                "description": "Your Salesforce instance URL (e.g., https://yourcompany.my.salesforce.com)"
            }
        ]
    
    def __init__(self):
        super().__init__(
            name="salesforce_api",
            description="This tool allows the agent to search and interact with Salesforce data using OAuth 2.0, enabling operations such as querying records and retrieving information from Salesforce databases."
        )
        self.access_token = os.getenv("SALESFORCE_ACCESS_TOKEN")
        self.instance_url = os.getenv("SALESFORCE_INSTANCE_URL")
        # Default to latest API version if instance URL is set
        if self.instance_url:
            self.api_version = "v59.0"  # Update as needed
            self.base_url = f"{self.instance_url}/services/data/{self.api_version}"
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute Salesforce operation
        
        Args:
            **kwargs: Operation parameters including:
                - operation: 'query', 'create', 'update', 'delete'
                - query: SOQL query string (for query operation)
                - sobject: Salesforce object type (e.g., 'Account', 'Contact')
                - record_id: Record ID (for update/delete)
                - data: Record data (for create/update)
            
        Returns:
            Dictionary with results
        """
        if not self.access_token or not self.instance_url:
            return {
                "success": False,
                "error": "Salesforce OAuth credentials or Instance URL not configured",
                "suggestion": "Set SALESFORCE_ACCESS_TOKEN and SALESFORCE_INSTANCE_URL environment variables. Create a Connected App in Salesforce Setup to get OAuth credentials."
            }
        
        operation = kwargs.get('operation', 'query')
        
        try:
            if operation == 'query':
                return self._query_records(kwargs)
            elif operation == 'create':
                return self._create_record(kwargs)
            elif operation == 'update':
                return self._update_record(kwargs)
            elif operation == 'delete':
                return self._delete_record(kwargs)
            elif operation == 'describe':
                return self._describe_object(kwargs)
            else:
                return {
                    "success": False,
                    "error": f"Unsupported operation: {operation}",
                    "valid_operations": ["query", "create", "update", "delete", "describe"]
                }
        except requests.exceptions.HTTPError as http_err:
            return {
                "success": False,
                "error": f"Salesforce API error: {http_err}",
                "status_code": http_err.response.status_code if hasattr(http_err, 'response') else None,
                "response": http_err.response.text if hasattr(http_err, 'response') else None
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    def _get_headers(self) -> Dict[str, str]:
        """Get common headers for API requests"""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
    
    def _query_records(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute SOQL query"""
        query = params.get('query')
        
        if not query:
            return {
                "success": False,
                "error": "No query provided",
                "suggestion": "Provide a valid SOQL query (e.g., SELECT Id, Name FROM Account LIMIT 10)"
            }
        
        response = requests.get(
            f"{self.base_url}/query",
            headers=self._get_headers(),
            params={"q": query}
        )
        response.raise_for_status()
        
        result = response.json()
        return {
            "success": True,
            "total_size": result.get('totalSize'),
            "records": result.get('records', []),
            "done": result.get('done')
        }
    
    def _create_record(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new record"""
        sobject = params.get('sobject')
        data = params.get('data', {})
        
        if not sobject or not data:
            return {"success": False, "error": "sobject and data are required"}
        
        response = requests.post(
            f"{self.base_url}/sobjects/{sobject}",
            headers=self._get_headers(),
            json=data
        )
        response.raise_for_status()
        
        result = response.json()
        return {
            "success": result.get('success', True),
            "record_id": result.get('id'),
            "data": result
        }
    
    def _update_record(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing record"""
        sobject = params.get('sobject')
        record_id = params.get('record_id')
        data = params.get('data', {})
        
        if not sobject or not record_id or not data:
            return {"success": False, "error": "sobject, record_id, and data are required"}
        
        response = requests.patch(
            f"{self.base_url}/sobjects/{sobject}/{record_id}",
            headers=self._get_headers(),
            json=data
        )
        response.raise_for_status()
        
        return {
            "success": True,
            "message": f"Record {record_id} updated successfully"
        }
    
    def _delete_record(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a record"""
        sobject = params.get('sobject')
        record_id = params.get('record_id')
        
        if not sobject or not record_id:
            return {"success": False, "error": "sobject and record_id are required"}
        
        response = requests.delete(
            f"{self.base_url}/sobjects/{sobject}/{record_id}",
            headers=self._get_headers()
        )
        response.raise_for_status()
        
        return {
            "success": True,
            "message": f"Record {record_id} deleted successfully"
        }
    
    def _describe_object(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get object metadata"""
        sobject = params.get('sobject')
        
        if not sobject:
            return {"success": False, "error": "sobject is required"}
        
        response = requests.get(
            f"{self.base_url}/sobjects/{sobject}/describe",
            headers=self._get_headers()
        )
        response.raise_for_status()
        
        return {
            "success": True,
            "data": response.json()
        }