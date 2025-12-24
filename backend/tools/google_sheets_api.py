from typing import Dict, Any, List
import os
from .base_tool import BaseTool

try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False


class GoogleSheetsApiConnector(BaseTool):
    """Tool for connecting to Google Sheets API using OAuth 2.0 to generate and manipulate reports in Google Sheets."""
    
    @classmethod
    def get_config_schema(cls):
        return [
            {
                "name": "access_token",
                "label": "Google Sheets OAuth Access Token",
                "type": "password",
                "required": True,
                "env_var": "GOOGLE_SHEETS_ACCESS_TOKEN",
                "description": "OAuth 2.0 access token. Get from: https://developers.google.com/oauthplayground (scope: https://www.googleapis.com/auth/spreadsheets)"
            }
        ]
    
    def __init__(self):
        super().__init__(
            name="google_sheets_api",
            description="This tool connects to Google Sheets API using OAuth 2.0 to generate and manipulate reports in Google Sheets."
        )
        self.access_token = os.getenv("GOOGLE_SHEETS_ACCESS_TOKEN")
        self.service = None
        
        if not GOOGLE_LIBS_AVAILABLE:
            self.service = None
        elif self.access_token:
            try:
                credentials = Credentials(token=self.access_token)
                self.service = build('sheets', 'v4', credentials=credentials)
            except Exception as e:
                print(f"⚠️ Google Sheets API initialization error: {e}")
                self.service = None
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute Google Sheets operation
        
        Args:
            **kwargs: Operation parameters including:
                - operation: 'read', 'write', 'create', 'append'
                - spreadsheet_id: Spreadsheet ID (required for read/write/append)
                - range: A1 notation range (e.g., 'Sheet1!A1:D10')
                - values: Data to write (for write/append operations)
                - title: Title for new spreadsheet (for create operation)
            
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
                "error": "Google Sheets OAuth credentials not configured",
                "suggestion": "Set GOOGLE_SHEETS_ACCESS_TOKEN environment variable. Get OAuth token from: https://developers.google.com/oauthplayground (use scope: https://www.googleapis.com/auth/spreadsheets)"
            }
        
        operation = kwargs.get('operation', 'read')
        
        try:
            if operation == 'read':
                return self._read_values(kwargs)
            elif operation == 'write':
                return self._write_values(kwargs)
            elif operation == 'append':
                return self._append_values(kwargs)
            elif operation == 'create':
                return self._create_spreadsheet(kwargs)
            else:
                return {
                    "success": False,
                    "error": f"Unsupported operation: {operation}",
                    "valid_operations": ["read", "write", "append", "create"]
                }
        except HttpError as error:
            return {
                "success": False,
                "error": f"Google Sheets API error: {error}",
                "error_type": "HttpError"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    def _read_values(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Read values from a spreadsheet range"""
        spreadsheet_id = params.get('spreadsheet_id')
        range_name = params.get('range', 'Sheet1!A1:Z1000')
        
        if not spreadsheet_id:
            return {"success": False, "error": "spreadsheet_id is required for read operation"}
        
        result = self.service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_name
        ).execute()
        
        values = result.get('values', [])
        return {
            "success": True,
            "row_count": len(values),
            "data": values,
            "range": result.get('range')
        }
    
    def _write_values(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Write values to a spreadsheet range"""
        spreadsheet_id = params.get('spreadsheet_id')
        range_name = params.get('range', 'Sheet1!A1')
        values = params.get('values', [])
        
        if not spreadsheet_id or not values:
            return {"success": False, "error": "spreadsheet_id and values are required"}
        
        body = {'values': values}
        result = self.service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption='RAW',
            body=body
        ).execute()
        
        return {
            "success": True,
            "updated_cells": result.get('updatedCells'),
            "updated_range": result.get('updatedRange')
        }
    
    def _append_values(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Append values to a spreadsheet"""
        spreadsheet_id = params.get('spreadsheet_id')
        range_name = params.get('range', 'Sheet1!A1')
        values = params.get('values', [])
        
        if not spreadsheet_id or not values:
            return {"success": False, "error": "spreadsheet_id and values are required"}
        
        body = {'values': values}
        result = self.service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption='RAW',
            body=body
        ).execute()
        
        return {
            "success": True,
            "updated_cells": result.get('updates', {}).get('updatedCells'),
            "updated_range": result.get('updates', {}).get('updatedRange')
        }
    
    def _create_spreadsheet(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new spreadsheet"""
        title = params.get('title', 'New Spreadsheet')
        
        spreadsheet = {
            'properties': {
                'title': title
            }
        }
        
        result = self.service.spreadsheets().create(
            body=spreadsheet,
            fields='spreadsheetId,spreadsheetUrl'
        ).execute()
        
        return {
            "success": True,
            "spreadsheet_id": result.get('spreadsheetId'),
            "spreadsheet_url": result.get('spreadsheetUrl')
        }