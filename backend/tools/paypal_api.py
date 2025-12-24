from typing import Dict, Any
import os
import requests
import base64
from .base_tool import BaseTool


class PaypalApiConnector(BaseTool):
    """Tool for sending invoices via PayPal using OAuth 2.0, enabling users to create and send invoices to customers through the PayPal platform."""
    
    @classmethod
    def get_config_schema(cls):
        return [
            {
                "name": "client_id",
                "label": "PayPal Client ID",
                "type": "password",
                "required": True,
                "env_var": "PAYPAL_CLIENT_ID",
                "description": "Get from PayPal Developer Dashboard (https://developer.paypal.com/dashboard/applications)"
            },
            {
                "name": "client_secret",
                "label": "PayPal Client Secret",
                "type": "password",
                "required": True,
                "env_var": "PAYPAL_CLIENT_SECRET",
                "description": "Get from PayPal Developer Dashboard"
            },
            {
                "name": "sandbox_mode",
                "label": "Use Sandbox Mode",
                "type": "text",
                "required": False,
                "env_var": "PAYPAL_SANDBOX_MODE",
                "default": "true",
                "description": "Set to 'false' for production"
            }
        ]
    
    def __init__(self):
        super().__init__(
            name="paypal_api",
            description="This tool sends invoices via PayPal using OAuth 2.0, enabling users to create and send invoices to customers through the PayPal platform."
        )
        self.client_id = os.getenv("PAYPAL_CLIENT_ID")
        self.client_secret = os.getenv("PAYPAL_CLIENT_SECRET")
        self.sandbox_mode = os.getenv("PAYPAL_SANDBOX_MODE", "true").lower() == "true"
        
        # Set API base URL based on mode
        if self.sandbox_mode:
            self.base_url = "https://api-m.sandbox.paypal.com"
        else:
            self.base_url = "https://api-m.paypal.com"
        
        self.access_token = None
        self.token_type = None
    
    def _get_access_token(self) -> bool:
        """Get OAuth access token from PayPal"""
        try:
            auth_string = f"{self.client_id}:{self.client_secret}"
            auth_bytes = auth_string.encode('ascii')
            auth_base64 = base64.b64encode(auth_bytes).decode('ascii')
            
            headers = {
                "Authorization": f"Basic {auth_base64}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            data = {"grant_type": "client_credentials"}
            
            response = requests.post(
                f"{self.base_url}/v1/oauth2/token",
                headers=headers,
                data=data
            )
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data.get('access_token')
            self.token_type = token_data.get('token_type', 'Bearer')
            
            return True
        except Exception as e:
            print(f"⚠️ PayPal OAuth token error: {e}")
            return False
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute PayPal operation
        
        Args:
            **kwargs: Operation parameters including invoice details
            
        Returns:
            Dictionary with results
        """
        if not self.client_id or not self.client_secret:
            return {
                "success": False,
                "error": "PayPal Client ID and Secret not configured",
                "suggestion": "Set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET environment variables. Get from: https://developer.paypal.com/dashboard/applications"
            }
        
        # Get access token first
        if not self.access_token:
            if not self._get_access_token():
                return {
                    "success": False,
                    "error": "Failed to obtain PayPal OAuth access token",
                    "suggestion": "Verify your Client ID and Secret are correct"
                }
        
        operation = kwargs.get('operation', 'create_invoice')
        
        try:
            if operation == 'create_invoice':
                return self._create_invoice(kwargs)
            elif operation == 'send_invoice':
                return self._send_invoice(kwargs)
            elif operation == 'get_invoice':
                return self._get_invoice(kwargs)
            else:
                return {
                    "success": False,
                    "error": f"Unsupported operation: {operation}",
                    "valid_operations": ["create_invoice", "send_invoice", "get_invoice"]
                }
        except requests.exceptions.HTTPError as http_err:
            return {
                "success": False,
                "error": f"PayPal API error: {http_err}",
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
            "Content-Type": "application/json",
            "Authorization": f"{self.token_type} {self.access_token}"
        }
    
    def _create_invoice(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create a PayPal invoice"""
        invoice_data = params.get('invoice_data', {})
        
        response = requests.post(
            f"{self.base_url}/v2/invoicing/invoices",
            headers=self._get_headers(),
            json=invoice_data
        )
        response.raise_for_status()
        
        result = response.json()
        return {
            "success": True,
            "invoice_id": result.get('id'),
            "invoice_number": result.get('detail', {}).get('invoice_number'),
            "status": result.get('status'),
            "data": result
        }
    
    def _send_invoice(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send a PayPal invoice"""
        invoice_id = params.get('invoice_id')
        
        if not invoice_id:
            return {"success": False, "error": "invoice_id is required"}
        
        response = requests.post(
            f"{self.base_url}/v2/invoicing/invoices/{invoice_id}/send",
            headers=self._get_headers()
        )
        response.raise_for_status()
        
        return {
            "success": True,
            "message": f"Invoice {invoice_id} sent successfully"
        }
    
    def _get_invoice(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get invoice details"""
        invoice_id = params.get('invoice_id')
        
        if not invoice_id:
            return {"success": False, "error": "invoice_id is required"}
        
        response = requests.get(
            f"{self.base_url}/v2/invoicing/invoices/{invoice_id}",
            headers=self._get_headers()
        )
        response.raise_for_status()
        
        return {
            "success": True,
            "data": response.json()
        }