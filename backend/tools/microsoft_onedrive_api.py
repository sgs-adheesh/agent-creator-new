from typing import Dict, Any
import os
import requests
from .base_tool import BaseTool


class MicrosoftOnedriveApiConnector(BaseTool):
    """Tool for syncing files with Microsoft OneDrive using Microsoft Graph API, allowing for file upload, download, and management within OneDrive."""
    
    @classmethod
    def get_config_schema(cls):
        return [
            {
                "name": "access_token",
                "label": "Microsoft Graph OAuth Access Token",
                "type": "password",
                "required": True,
                "env_var": "MICROSOFT_ONEDRIVE_ACCESS_TOKEN",
                "description": "OAuth 2.0 access token from Microsoft Graph. Get from Azure AD app registration (scope: Files.ReadWrite)"
            }
        ]
    
    def __init__(self):
        super().__init__(
            name="microsoft_onedrive_api",
            description="Enables the agent to sync files with Microsoft OneDrive using Microsoft Graph API, allowing for file upload, download, and management within OneDrive."
        )
        self.access_token = os.getenv("MICROSOFT_ONEDRIVE_ACCESS_TOKEN")
        self.graph_url = "https://graph.microsoft.com/v1.0"
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute Microsoft OneDrive operation using Graph API
        
        Args:
            **kwargs: Operation parameters including:
                - operation: 'upload', 'download', 'list', 'delete'
                - file_path: Local file path (for upload/download)
                - file_name: Name for the file in OneDrive
                - item_id: OneDrive item ID (for download/delete)
                - folder_path: Path to folder (optional)
            
        Returns:
            Dictionary with results
        """
        if not self.access_token:
            return {
                "success": False,
                "error": "Microsoft OneDrive OAuth access token not configured",
                "suggestion": "Set MICROSOFT_ONEDRIVE_ACCESS_TOKEN environment variable. Register an Azure AD app and get OAuth token with Files.ReadWrite scope"
            }
        
        operation = kwargs.get('operation', 'upload')
        
        try:
            if operation == 'upload':
                return self._upload_file(kwargs)
            elif operation == 'list':
                return self._list_files(kwargs)
            elif operation == 'download':
                return self._download_file(kwargs)
            elif operation == 'delete':
                return self._delete_file(kwargs)
            else:
                return {
                    "success": False,
                    "error": f"Unsupported operation: {operation}",
                    "valid_operations": ["upload", "list", "download", "delete"]
                }
        except requests.exceptions.HTTPError as http_err:
            return {
                "success": False,
                "error": f"Microsoft Graph API error: {http_err}",
                "error_type": "HTTPError",
                "response": http_err.response.text if hasattr(http_err, 'response') else None
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    def _get_headers(self) -> Dict[str, str]:
        """Get common headers for Graph API requests"""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
    
    def _upload_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Upload a file to OneDrive"""
        file_path = params.get('file_path')
        file_name = params.get('file_name', os.path.basename(file_path) if file_path else 'untitled')
        folder_path = params.get('folder_path', '/')
        
        if not file_path:
            return {"success": False, "error": "file_path is required"}
        
        # Read file content
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        # Upload to OneDrive
        upload_url = f"{self.graph_url}/me/drive/root:{folder_path}/{file_name}:/content"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        response = requests.put(upload_url, headers=headers, data=file_content)
        response.raise_for_status()
        
        result = response.json()
        return {
            "success": True,
            "item_id": result.get('id'),
            "file_name": result.get('name'),
            "web_url": result.get('webUrl'),
            "size": result.get('size')
        }
    
    def _list_files(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List files in OneDrive"""
        folder_path = params.get('folder_path', '/')
        
        if folder_path == '/':
            list_url = f"{self.graph_url}/me/drive/root/children"
        else:
            list_url = f"{self.graph_url}/me/drive/root:{folder_path}:/children"
        
        response = requests.get(list_url, headers=self._get_headers())
        response.raise_for_status()
        
        result = response.json()
        items = result.get('value', [])
        
        return {
            "success": True,
            "file_count": len(items),
            "files": [
                {
                    "id": item.get('id'),
                    "name": item.get('name'),
                    "type": "folder" if 'folder' in item else "file",
                    "size": item.get('size'),
                    "modified": item.get('lastModifiedDateTime')
                }
                for item in items
            ]
        }
    
    def _download_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Download a file from OneDrive"""
        item_id = params.get('item_id')
        file_path = params.get('file_path')
        
        if not item_id or not file_path:
            return {"success": False, "error": "item_id and file_path are required"}
        
        download_url = f"{self.graph_url}/me/drive/items/{item_id}/content"
        response = requests.get(download_url, headers={"Authorization": f"Bearer {self.access_token}"})
        response.raise_for_status()
        
        with open(file_path, 'wb') as f:
            f.write(response.content)
        
        return {
            "success": True,
            "message": f"File downloaded to {file_path}",
            "size": len(response.content)
        }
    
    def _delete_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a file from OneDrive"""
        item_id = params.get('item_id')
        
        if not item_id:
            return {"success": False, "error": "item_id is required"}
        
        delete_url = f"{self.graph_url}/me/drive/items/{item_id}"
        response = requests.delete(delete_url, headers=self._get_headers())
        response.raise_for_status()
        
        return {
            "success": True,
            "message": f"Item {item_id} deleted successfully"
        }