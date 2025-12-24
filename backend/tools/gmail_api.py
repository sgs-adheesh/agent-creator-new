from typing import Dict, Any
import os
import base64
from email.mime.text import MIMEText
from .base_tool import BaseTool

try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False


class GmailApiConnector(BaseTool):
    """Tool for enabling the agent to send emails through Gmail using OAuth 2.0, allowing for the creation and sending of email messages programmatically."""
    
    @classmethod
    def get_config_schema(cls):
        return [
            {
                "name": "access_token",
                "label": "Gmail OAuth Access Token",
                "type": "password",
                "required": True,
                "env_var": "GMAIL_ACCESS_TOKEN",
                "description": "OAuth 2.0 access token from Google. Get it from: https://developers.google.com/oauthplayground"
            },
            {
                "name": "refresh_token",
                "label": "Gmail OAuth Refresh Token (Optional)",
                "type": "password",
                "required": False,
                "env_var": "GMAIL_REFRESH_TOKEN",
                "description": "Optional refresh token for automatic token renewal"
            }
        ]
    
    def __init__(self):
        super().__init__(
            name="gmail_api",
            description="This tool enables the agent to send emails through Gmail using OAuth 2.0, allowing for the creation and sending of email messages programmatically."
        )
        self.access_token = os.getenv("GMAIL_ACCESS_TOKEN")
        self.refresh_token = os.getenv("GMAIL_REFRESH_TOKEN")
        self.service = None
        
        if not GOOGLE_LIBS_AVAILABLE:
            self.service = None
        elif self.access_token:
            try:
                # Create credentials from access token
                credentials = Credentials(token=self.access_token)
                if self.refresh_token:
                    credentials.refresh_token = self.refresh_token
                
                self.service = build('gmail', 'v1', credentials=credentials)
            except Exception as e:
                print(f"⚠️ Gmail API initialization error: {e}")
                self.service = None
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute Gmail operation to send an email.
        
        Args:
            **kwargs: Operation parameters including 'to', 'subject', and 'body'.
            
        Returns:
            Dictionary with results
        """
        if not GOOGLE_LIBS_AVAILABLE:
            return {
                "success": False,
                "error": "Google API libraries not installed",
                "suggestion": "Install required packages: pip install google-auth google-auth-oauthlib google-api-python-client"
            }
        
        if not self.service:
            return {
                "success": False,
                "error": "Gmail OAuth credentials not configured",
                "suggestion": "Set GMAIL_ACCESS_TOKEN environment variable. Get OAuth token from: https://developers.google.com/oauthplayground (use scope: https://www.googleapis.com/auth/gmail.send)"
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
            message = self._create_message(to, subject, body)
            send_message = {'raw': message}
            
            result = self.service.users().messages().send(
                userId='me',
                body=send_message
            ).execute()
            
            return {
                "success": True,
                "message_id": result.get('id'),
                "thread_id": result.get('threadId'),
                "data": result
            }
        except HttpError as error:
            return {
                "success": False,
                "error": f"Gmail API error: {error}",
                "error_type": "HttpError",
                "suggestion": "Check if access token is valid and has gmail.send scope"
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
        message = MIMEText(body)
        message['to'] = to
        message['subject'] = subject
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        return raw_message