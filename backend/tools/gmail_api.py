from typing import Dict, Any
import os
import requests
from .base_tool import BaseTool


class GmailApiConnector(BaseTool):
    """Tool for enabling the agent to send emails through Gmail, allowing for the creation and sending of email messages programmatically."""
    
    @classmethod
    def get_config_schema(cls):
        return [
            {
                "name": "api_key",
                "label": "Gmail API Key",
                "type": "password",
                "required": True,
                "env_var": "GMAIL_API_API_KEY"
            }
        ]
    
    def __init__(self):
        super().__init__(
            name="gmail_api",
            description="This tool enables the agent to send emails through Gmail, allowing for the creation and sending of email messages programmatically."
        )
        self.api_key = os.getenv("GMAIL_API_API_KEY")
        self.api_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute Gmail operation to send an email.
        
        Args:
            **kwargs: Operation parameters including 'to', 'subject', and 'body'.
            
        Returns:
            Dictionary with results
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "Gmail API key not configured",
                "suggestion": "Set GMAIL_API_API_KEY environment variable"
            }
        
        to = kwargs.get('to')
        subject = kwargs.get('subject')
        body = kwargs.get('body')

        if not to or not subject or not body:
            return {
                "success": False,
                "error": "Missing required parameters: 'to', 'subject', and 'body' are required."
            }
        
        try:
            message = {
                'raw': self._create_message(to, subject, body)
            }
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            response = requests.post(self.api_url, headers=headers, json=message)
            response.raise_for_status()
            return {
                "success": True,
                "data": response.json()
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
    
    def _create_message(self, to: str, subject: str, body: str) -> str:
        """
        Create a raw email message.
        
        Args:
            to (str): Recipient email address.
            subject (str): Email subject.
            body (str): Email body.
        
        Returns:
            str: Base64url encoded email message.
        """
        import base64
        from email.mime.text import MIMEText
        
        message = MIMEText(body)
        message['to'] = to
        message['subject'] = subject
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        return raw_message