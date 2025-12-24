from typing import Dict, Any
import os
from .base_tool import BaseTool

try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False


class GoogleDriveApiConnector(BaseTool):
    """Tool for backing up files to Google Drive using OAuth 2.0, enabling file upload, download, and management within Google Drive."""
    
    @classmethod
    def get_config_schema(cls):
        return [
            {
                "name": "access_token",
                "label": "Google Drive OAuth Access Token",
                "type": "password",
                "required": True,
                "env_var": "GOOGLE_DRIVE_ACCESS_TOKEN",
                "description": "OAuth 2.0 access token. Get from: https://developers.google.com/oauthplayground (scope: https://www.googleapis.com/auth/drive.file)"
            }
        ]
    
    def __init__(self):
        super().__init__(
            name="google_drive_api",
            description="Allows the agent to back up files to Google Drive using OAuth 2.0, enabling file upload, download, and management within Google Drive."
        )
        self.access_token = os.getenv("GOOGLE_DRIVE_ACCESS_TOKEN")
        self.service = None
        
        if not GOOGLE_LIBS_AVAILABLE:
            self.service = None
        elif self.access_token:
            try:
                credentials = Credentials(token=self.access_token)
                self.service = build('drive', 'v3', credentials=credentials)
            except Exception as e:
                print(f"⚠️ Google Drive API initialization error: {e}")
                self.service = None
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute Google Drive operation
        
        Args:
            **kwargs: Operation parameters including:
                - operation: 'upload', 'download', 'list', 'delete'
                - file_path: Local file path (for upload/download)
                - file_id: Google Drive file ID (for download/delete)
                - folder_id: Parent folder ID (optional, for upload)
                - file_name: Name for the file in Drive
            
        Returns:
            Dictionary with results
        """
        if not GOOGLE_LIBS_AVAILABLE:
            return {
                "success": False,
                "error": "Google API libraries not installed",
                "suggestion": "Install required packages: pip install google-auth google-api-python-client"
            }
        
        if not self.service:
            return {
                "success": False,
                "error": "Google Drive OAuth credentials not configured",
                "suggestion": "Set GOOGLE_DRIVE_ACCESS_TOKEN environment variable. Get OAuth token from: https://developers.google.com/oauthplayground (use scope: https://www.googleapis.com/auth/drive.file)"
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
        except HttpError as error:
            return {
                "success": False,
                "error": f"Google Drive API error: {error}",
                "error_type": "HttpError"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    def _upload_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Upload a file to Google Drive"""
        file_path = params.get('file_path')
        file_name = params.get('file_name', os.path.basename(file_path) if file_path else 'untitled')
        folder_id = params.get('folder_id')
        
        if not file_path:
            return {"success": False, "error": "file_path is required for upload"}
        
        file_metadata = {'name': file_name}
        if folder_id:
            file_metadata['parents'] = [folder_id]
        
        media = MediaFileUpload(file_path, resumable=True)
        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name, webViewLink'
        ).execute()
        
        return {
            "success": True,
            "file_id": file.get('id'),
            "file_name": file.get('name'),
            "web_view_link": file.get('webViewLink')
        }
    
    def _list_files(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """List files in Google Drive"""
        page_size = params.get('page_size', 10)
        folder_id = params.get('folder_id')
        
        query = f"'{folder_id}' in parents" if folder_id else None
        
        results = self.service.files().list(
            pageSize=page_size,
            q=query,
            fields="files(id, name, mimeType, modifiedTime)"
        ).execute()
        
        files = results.get('files', [])
        return {
            "success": True,
            "file_count": len(files),
            "files": files
        }
    
    def _download_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Download a file from Google Drive"""
        file_id = params.get('file_id')
        file_path = params.get('file_path')
        
        if not file_id or not file_path:
            return {"success": False, "error": "file_id and file_path are required"}
        
        request = self.service.files().get_media(fileId=file_id)
        with open(file_path, 'wb') as f:
            from googleapiclient.http import MediaIoBaseDownload
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
        
        return {
            "success": True,
            "message": f"File downloaded to {file_path}"
        }
    
    def _delete_file(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a file from Google Drive"""
        file_id = params.get('file_id')
        
        if not file_id:
            return {"success": False, "error": "file_id is required"}
        
        self.service.files().delete(fileId=file_id).execute()
        return {
            "success": True,
            "message": f"File {file_id} deleted successfully"
        }