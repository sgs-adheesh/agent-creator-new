from typing import Dict, Any
import os
import stripe
from .base_tool import BaseTool


class StripeApiConnector(BaseTool):
    """Tool for processing payments through Stripe, allowing for secure transactions and payment handling."""
    
    def __init__(self):
        super().__init__(
            name="stripe_api",
            description="This tool processes payments through Stripe, allowing for secure transactions and payment handling."
        )
        self.api_key = os.getenv("STRIPE_API_API_KEY")
        if self.api_key:
            stripe.api_key = self.api_key
        else:
            raise ValueError("Stripe API key not configured. Set STRIPE_API_API_KEY environment variable.")
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute Stripe operation
        
        Args:
            **kwargs: Operation parameters
            
        Returns:
            Dictionary with results
        """
        if not self.api_key:
            return {
                "success": False,
                "error": "Stripe API key not configured",
                "suggestion": "Set STRIPE_API_API_KEY environment variable"
            }
        
        try:
            # Example operation: Create a payment intent
            amount = kwargs.get("amount")
            currency = kwargs.get("currency", "usd")
            payment_intent = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                payment_method=kwargs.get("payment_method"),
                confirmation_method='manual',
                confirm=True,
            )
            return {
                "success": True,
                "data": payment_intent
            }
        except stripe.error.StripeError as e:
            return {
                "success": False,
                "error": str(e.user_message),
                "error_type": type(e).__name__
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }