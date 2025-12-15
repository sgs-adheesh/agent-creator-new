import psycopg2
from typing import Dict, Any, List, Optional

from config import settings
from .base_tool import BaseTool 


class PostgresConnector(BaseTool):
    """Read-only Postgres database connector tool"""
    
    def __init__(self):
        super().__init__(
            name="postgres_query",
            description="Execute read-only SQL queries on PostgreSQL database. Use this to query data from tables. Only SELECT queries are allowed."
        )
        self.connection = None
    
    def _get_connection(self):
        """Get or create database connection"""
        if self.connection is None or self.connection.closed:
            self.connection = psycopg2.connect(
                host=settings.postgres_host,
                port=settings.postgres_port,
                database=settings.postgres_database,
                user=settings.postgres_user,
                password=settings.postgres_password
            )
        return self.connection
    
    def execute(self, query: str) -> Dict[str, Any]:
        """
        Execute a read-only SQL query
        
        Args:
            query: SQL SELECT query string
            
        Returns:
            Dictionary with query results or error message
        """
        try:
            # Validate query is read-only
            query_upper = query.strip().upper()
            if not query_upper.startswith("SELECT"):
                return {
                    "error": "Only SELECT queries are allowed. This is a read-only connector.",
                    "success": False
                }
            
            # Check for dangerous keywords
            dangerous_keywords = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE", "TRUNCATE"]
            if any(keyword in query_upper for keyword in dangerous_keywords):
                return {
                    "error": "Query contains dangerous keywords. Only SELECT queries are allowed.",
                    "success": False
                }
            
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute(query)
            
            # Fetch column names
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            
            # Fetch all results
            rows = cursor.fetchall()
            
            # Convert to list of dictionaries
            results = [dict(zip(columns, row)) for row in rows]
            
            cursor.close()
            
            return {
                "success": True,
                "columns": columns,
                "rows": results,
                "row_count": len(results)
            }
            
        except psycopg2.Error as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": "database_error"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": "unknown_error"
            }
    
    def close(self):
        """Close database connection"""
        if self.connection and not self.connection.closed:
            self.connection.close()

