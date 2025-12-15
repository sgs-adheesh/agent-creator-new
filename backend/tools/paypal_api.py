from typing import Dict, Any
import os
import requests
from .base_tool import BaseTool


class PaypalApiConnector(BaseTool):
    """Tool for sending invoices via PayPal, enabling users to create and send invoices to customers through the PayPal platform."""
    
    def __init__(self):
        super().__init__(
            name="paypal_api",
            description="This tool sends invoices via PayPal, enabling users to create and send invoices to customers through the PayPal platform."
        )
        self.api_key = os.getenv("PAYPAL_API_API_KEY")
        self.api_url = "https://api.paypal.com/v1/invoicing/invoices"  # Example endpoint
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute PayPal operation
        
        Args:
            **kwargs: Operation parameters including invoice details
            
        Returns:
            Dictionary with results
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "PayPal API key not configured",
                "suggestion": "Set PAYPAL_API_API_KEY environment variable"
            }
        
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            response = requests.post(self.api_url, json=kwargs, headers=headers)
            response_data = response.json()
            
            if response.status_code == 201:
                return {
                    "success": True,
                    "data": response_data
                }
            else:
                return {
                    "success": False,
                    "error": response_data.get("message", "Failed to send invoice"),
                    "error_details": response_data
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }