from typing import Dict, Any, List, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from config import settings
from .base_tool import BaseTool


class QdrantConnector(BaseTool):
    """Qdrant vector database connector tool"""
    
    def __init__(self):
        super().__init__(
            name="qdrant_search",
            description="Search and query data from Qdrant vector database. Use this to perform vector similarity searches, filter queries, and retrieve data from the configured collection."
        )
        self.client = None
        self.collection_name = settings.qdrant_collection
    
    def _get_client(self):
        """Get or create Qdrant client with timeout"""
        if self.client is None:
            self.client = QdrantClient(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key if hasattr(settings, 'qdrant_api_key') and settings.qdrant_api_key else None,
                timeout=5  # 5 second timeout
            )
        return self.client
    
    def execute(self, query: Optional[str] = None, query_vector: Optional[str] = None, limit: int = 10, filter_field: Optional[str] = None, filter_value: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute a vector search or query on Qdrant
        
        Args:
            query: Text description of what to search for (for info queries)
            query_vector: Vector embedding as comma-separated string or JSON array string for similarity search
            limit: Maximum number of results to return (default: 10)
            filter_field: Optional field name to filter by
            filter_value: Optional field value to filter by
            
        Returns:
            Dictionary with search results or error message
        """
        try:
            client = self._get_client()
            
            # Parse query_vector if provided as string
            vector_list = None
            if query_vector:
                try:
                    import json
                    # Try parsing as JSON array
                    if query_vector.startswith('['):
                        vector_list = json.loads(query_vector)
                    else:
                        # Try parsing as comma-separated values
                        vector_list = [float(x.strip()) for x in query_vector.split(',')]
                except:
                    return {
                        "success": False,
                        "error": "Invalid query_vector format. Provide as JSON array string or comma-separated floats."
                    }
            
            # Build filter if conditions provided
            filter_obj = None
            if filter_field and filter_value:
                try:
                    filter_obj = Filter(
                        must=[FieldCondition(key=filter_field, match=MatchValue(value=filter_value))]
                    )
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Failed to create filter: {str(e)}"
                    }
            
            # If no query vector provided, try to get collection info or perform a scroll
            if vector_list is None and query is None:
                # Get collection info with sample data
                try:
                    import socket
                    from qdrant_client.http.exceptions import UnexpectedResponse
                    
                    collection_info = client.get_collection(self.collection_name)
                    
                    # Also get a few sample points to show what data is available
                    scroll_result = client.scroll(
                        collection_name=self.collection_name,
                        limit=3,
                        with_payload=True,
                        with_vectors=False
                    )
                    
                    sample_data = []
                    for point in scroll_result[0]:
                        sample_data.append({
                            "id": str(point.id),
                            "payload": point.payload
                        })
                    
                    return {
                        "success": True,
                        "message": f"Collection '{self.collection_name}' has {collection_info.points_count} records",
                        "collection_name": self.collection_name,
                        "points_count": collection_info.points_count,
                        "sample_records": sample_data,
                        "suggestion": "Use specific search criteria or provide a query to find relevant records. Available fields: " + ", ".join(sample_data[0]["payload"].keys() if sample_data and sample_data[0].get("payload") else [])
                    }
                except (socket.timeout, TimeoutError) as e:
                    return {
                        "success": False,
                        "error": "Qdrant database connection timed out. Please ensure the database is running and accessible.",
                        "error_type": "timeout_error",
                        "suggestion": "Check if Qdrant service is running at " + settings.qdrant_url
                    }
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Unable to connect to Qdrant: {str(e)}",
                        "error_type": "connection_error",
                        "suggestion": "Verify Qdrant configuration and network connectivity"
                    }
            
            # Perform vector search
            if vector_list:
                search_results = client.search(
                    collection_name=self.collection_name,
                    query_vector=vector_list,
                    limit=limit,
                    query_filter=filter_obj
                )
                
                results = []
                for result in search_results:
                    results.append({
                        "id": result.id,
                        "score": result.score,
                        "payload": result.payload
                    })
                
                return {
                    "success": True,
                    "results": results,
                    "count": len(results),
                    "collection": self.collection_name
                }
            elif query and query.lower() in ["info", "information", "count", "stats"]:
                # Return collection info
                collection_info = client.get_collection(self.collection_name)
                return {
                    "success": True,
                    "message": "Collection information",
                    "collection_name": self.collection_name,
                    "points_count": collection_info.points_count,
                    "vectors_count": collection_info.vectors_count if hasattr(collection_info, 'vectors_count') else None
                }
            else:
                # Perform scroll to get points
                scroll_result = client.scroll(
                    collection_name=self.collection_name,
                    limit=limit,
                    scroll_filter=filter_obj,
                    with_payload=True,
                    with_vectors=False
                )
                
                points = []
                for point in scroll_result[0]:
                    points.append({
                        "id": str(point.id),
                        "payload": point.payload
                    })
                
                return {
                    "success": True,
                    "results": points,
                    "count": len(points),
                    "collection": self.collection_name,
                    "message": f"Retrieved {len(points)} records from {self.collection_name}"
                }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    def scroll(self, limit: int = 10, offset: Optional[str] = None, filter_conditions: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Scroll through collection points
        
        Args:
            limit: Maximum number of points to return
            offset: Offset for pagination
            filter_conditions: Optional filter conditions
            
        Returns:
            Dictionary with scroll results
        """
        try:
            client = self._get_client()
            
            # Build filter if conditions provided
            filter_obj = None
            if filter_conditions:
                conditions = []
                for key, value in filter_conditions.items():
                    conditions.append(
                        FieldCondition(key=key, match=MatchValue(value=value))
                    )
                if conditions:
                    filter_obj = Filter(must=conditions)
            
            scroll_result = client.scroll(
                collection_name=self.collection_name,
                limit=limit,
                offset=offset,
                scroll_filter=filter_obj
            )
            
            points = []
            for point in scroll_result[0]:  # scroll_result is a tuple (points, next_page_offset)
                points.append({
                    "id": point.id,
                    "vector": point.vector if hasattr(point, 'vector') else None,
                    "payload": point.payload
                })
            
            return {
                "success": True,
                "points": points,
                "count": len(points),
                "next_offset": scroll_result[1] if len(scroll_result) > 1 else None
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }

