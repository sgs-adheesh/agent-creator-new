from typing import Dict, Any
import os
from .base_tool import BaseTool

try:
    from google.oauth2.credentials import Credentials
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import RunReportRequest, DateRange, Dimension, Metric
    GOOGLE_ANALYTICS_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_ANALYTICS_LIBS_AVAILABLE = False


class GoogleAnalyticsApiConnector(BaseTool):
    """Tool for connecting to Google Analytics 4 (GA4) API using OAuth 2.0 to query analytics data for reporting purposes."""
    
    @classmethod
    def get_config_schema(cls):
        return [
            {
                "name": "access_token",
                "label": "Google Analytics OAuth Access Token",
                "type": "password",
                "required": True,
                "env_var": "GOOGLE_ANALYTICS_ACCESS_TOKEN",
                "description": "OAuth 2.0 access token. Get from: https://developers.google.com/oauthplayground (scope: https://www.googleapis.com/auth/analytics.readonly)"
            },
            {
                "name": "property_id",
                "label": "GA4 Property ID",
                "type": "text",
                "required": True,
                "env_var": "GOOGLE_ANALYTICS_PROPERTY_ID",
                "description": "Your GA4 Property ID (format: properties/123456789)"
            }
        ]
    
    def __init__(self):
        super().__init__(
            name="google_analytics_api",
            description="This tool connects to Google Analytics 4 (GA4) API using OAuth 2.0 to query analytics data for reporting purposes."
        )
        self.access_token = os.getenv("GOOGLE_ANALYTICS_ACCESS_TOKEN")
        self.property_id = os.getenv("GOOGLE_ANALYTICS_PROPERTY_ID")
        self.client = None
        
        if not GOOGLE_ANALYTICS_LIBS_AVAILABLE:
            self.client = None
        elif self.access_token:
            try:
                credentials = Credentials(token=self.access_token)
                self.client = BetaAnalyticsDataClient(credentials=credentials)
            except Exception as e:
                print(f"⚠️ Google Analytics API initialization error: {e}")
                self.client = None
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute Google Analytics GA4 operation to run a report
        
        Args:
            **kwargs: Operation parameters including:
                - start_date: Start date (YYYY-MM-DD)
                - end_date: End date (YYYY-MM-DD)
                - dimensions: List of dimension names (e.g., ['city', 'country'])
                - metrics: List of metric names (e.g., ['activeUsers', 'sessions'])
            
        Returns:
            Dictionary with results
        """
        if not GOOGLE_ANALYTICS_LIBS_AVAILABLE:
            return {
                "success": False,
                "error": "Google Analytics libraries not installed",
                "suggestion": "Install required packages: pip install google-analytics-data google-auth"
            }
        
        if not self.client or not self.property_id:
            return {
                "success": False,
                "error": "Google Analytics OAuth credentials or Property ID not configured",
                "suggestion": "Set GOOGLE_ANALYTICS_ACCESS_TOKEN and GOOGLE_ANALYTICS_PROPERTY_ID environment variables"
            }
        
        try:
            # Get parameters
            start_date = kwargs.get('start_date', '30daysAgo')
            end_date = kwargs.get('end_date', 'today')
            dimensions_list = kwargs.get('dimensions', ['city'])
            metrics_list = kwargs.get('metrics', ['activeUsers'])
            
            # Build request
            request = RunReportRequest(
                property=self.property_id,
                date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
                dimensions=[Dimension(name=dim) for dim in dimensions_list],
                metrics=[Metric(name=metric) for metric in metrics_list]
            )
            
            # Execute report
            response = self.client.run_report(request)
            
            # Format results
            rows = []
            for row in response.rows:
                row_data = {}
                for i, dimension_value in enumerate(row.dimension_values):
                    row_data[dimensions_list[i]] = dimension_value.value
                for i, metric_value in enumerate(row.metric_values):
                    row_data[metrics_list[i]] = metric_value.value
                rows.append(row_data)
            
            return {
                "success": True,
                "row_count": response.row_count,
                "data": rows,
                "metadata": {
                    "property_id": self.property_id,
                    "date_range": {"start": start_date, "end": end_date},
                    "dimensions": dimensions_list,
                    "metrics": metrics_list
                }
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__,
                "suggestion": "Verify OAuth token has analytics.readonly scope and Property ID is correct (format: properties/123456789)"
            }