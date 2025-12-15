from typing import Dict, Any
import os
import requests
from .base_tool import BaseTool


class GoogleSheetsApiConnector(BaseTool):
    """Tool for connecting to the Google Sheets API to generate and manipulate reports in Google Sheets."""
    
    def __init__(self):
        super().__init__(
            name="google_sheets_api",
            description="This tool connects to the Google Sheets API to generate and manipulate reports in Google Sheets."
        )
        self.api_key = os.getenv("GOOGLE_SHEETS_API_API_KEY")
        if not self.api_key:
            raise ValueError("Google Sheets API key not configured. Set GOOGLE_SHEETS_API_API_KEY environment variable.")
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute Google Sheets operation
        
        Args:
            **kwargs: Operation parameters
            
        Returns:
            Dictionary with results
        """
        try:
            # Example API call to list spreadsheets
            url = "https://sheets.googleapis.com/v4/spreadsheets"
            headers = {
                "Authorization": f"Bearer {self.api_key}"
            }
            response = requests.get(url, headers=headers)
            response.raise_for_status()  # Raise an error for bad responses
            
            data = response.json()
            return {
                "success": True,
                "data": data
            }
        except requests.exceptions.HTTPError as http_err:
            return {
                "success": False,
                "error": str(http_err),
                "error_type": "HTTPError"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }