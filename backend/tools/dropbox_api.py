from typing import Dict, Any
import os
import requests
from .base_tool import BaseTool


class DropboxApiConnector(BaseTool):
    """Tool for enabling interaction with the Dropbox service for file sharing and management. 
    It provides methods to upload files, share links, and manage Dropbox folders."""
    
    @classmethod
    def get_config_schema(cls):
        return [
            {
                "name": "api_key",
                "label": "Dropbox API Access Token",
                "type": "password",
                "required": True,
                "env_var": "DROPBOX_API_API_KEY"
            }
        ]
    
    def __init__(self):
        super().__init__(
            name="dropbox_api",
            description="This tool enables interaction with the Dropbox service for file sharing and management. It provides methods to upload files, share links, and manage Dropbox folders."
        )
        self.api_key = os.getenv("DROPBOX_API_API_KEY")
        self.base_url = "https://api.dropboxapi.com/2/"
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute Dropbox operation
        
        Args:
            **kwargs: Operation parameters
            
        Returns:
            Dictionary with results
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "Dropbox API key not configured",
                "suggestion": "Set DROPBOX_API_API_KEY environment variable"
            }
        
        operation = kwargs.get("operation")
        
        try:
            if operation == "upload":
                return self.upload_file(kwargs.get("file_path"), kwargs.get("dropbox_path"))
            elif operation == "share_link":
                return self.create_shared_link(kwargs.get("dropbox_path"))
            elif operation == "list_folder":
                return self.list_folder(kwargs.get("folder_path"))
            else:
                return {
                    "success": False,
                    "error": "Invalid operation specified",
                    "valid_operations": ["upload", "share_link", "list_folder"]
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }

    def upload_file(self, file_path: str, dropbox_path: str) -> Dict[str, Any]:
        """Uploads a file to Dropbox."""
        with open(file_path, 'rb') as f:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/octet-stream",
                "Dropbox-API-Arg": f'{{"path": "{dropbox_path}", "mode": "add", "autorename": true, "mute": false}}'
            }
            response = requests.post("https://content.dropboxapi.com/2/files/upload", headers=headers, data=f)
            if response.status_code == 200:
                return {
                    "success": True,
                    "data": response.json()
                }
            else:
                return {
                    "success": False,
                    "error": response.json().get("error_summary", "Unknown error occurred")
                }

    def create_shared_link(self, dropbox_path: str) -> Dict[str, Any]:
        """Creates a shared link for a file or folder in Dropbox."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "path": dropbox_path,
            "short_url": False
        }
        response = requests.post("https://api.dropboxapi.com/2/sharing/create_shared_link_with_settings", headers=headers, json=data)
        if response.status_code == 200:
            return {
                "success": True,
                "data": response.json()
            }
        else:
            return {
                "success": False,
                "error": response.json().get("error_summary", "Unknown error occurred")
            }

    def list_folder(self, folder_path: str) -> Dict[str, Any]:
        """Lists files in a Dropbox folder."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "path": folder_path
        }
        response = requests.post("https://api.dropboxapi.com/2/files/list_folder", headers=headers, json=data)
        if response.status_code == 200:
            return {
                "success": True,
                "data": response.json()
            }
        else:
            return {
                "success": False,
                "error": response.json().get("error_summary", "Unknown error occurred")
            }