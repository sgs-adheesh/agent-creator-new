from typing import Dict, Any
import os
import boto3
from botocore.exceptions import ClientError
from .base_tool import BaseTool


class AwsS3ApiConnector(BaseTool):
    """Tool for uploading files to Amazon S3, a scalable storage service. 
    It provides methods for file upload, retrieval, and management within S3 buckets."""
    
    def __init__(self):
        super().__init__(
            name="aws_s3_api",
            description="This tool allows for uploading files to Amazon S3, a scalable storage service. It provides methods for file upload, retrieval, and management within S3 buckets."
        )
        self.api_key = os.getenv("AWS_S3_API_API_KEY")
        self.secret_key = os.getenv("AWS_S3_API_SECRET_KEY")
        self.region_name = os.getenv("AWS_S3_REGION_NAME", "us-east-1")
        
        if not self.api_key or not self.secret_key:
            raise ValueError("AWS S3 API key and secret key must be configured in environment variables.")
        
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=self.api_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region_name
        )
    
    def execute(self, operation: str, **kwargs) -> Dict[str, Any]:
        """
        Execute Amazon S3 operation
        
        Args:
            operation (str): The S3 operation to perform (e.g., 'upload', 'retrieve').
            **kwargs: Operation parameters
            
        Returns:
            Dictionary with results
        """
        try:
            if operation == "upload":
                bucket_name = kwargs.get("bucket_name")
                file_name = kwargs.get("file_name")
                object_name = kwargs.get("object_name", file_name)

                if not bucket_name or not file_name:
                    return {
                        "success": False,
                        "error": "Bucket name and file name are required for upload operation."
                    }

                self.s3_client.upload_file(file_name, bucket_name, object_name)
                return {
                    "success": True,
                    "message": f"File '{file_name}' uploaded to bucket '{bucket_name}' as '{object_name}'."
                }

            elif operation == "retrieve":
                bucket_name = kwargs.get("bucket_name")
                object_name = kwargs.get("object_name")
                file_name = kwargs.get("file_name")

                if not bucket_name or not object_name or not file_name:
                    return {
                        "success": False,
                        "error": "Bucket name, object name, and file name are required for retrieve operation."
                    }

                self.s3_client.download_file(bucket_name, object_name, file_name)
                return {
                    "success": True,
                    "message": f"File '{object_name}' retrieved from bucket '{bucket_name}' and saved as '{file_name}'."
                }

            else:
                return {
                    "success": False,
                    "error": "Unsupported operation. Please use 'upload' or 'retrieve'."
                }

        except ClientError as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }