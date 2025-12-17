import psycopg2
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from langchain.tools import StructuredTool

from config import settings
from .base_tool import BaseTool 


class PostgresQueryInput(BaseModel):
    """Input schema for Postgres query tool"""
    query: str = Field(description="SQL SELECT query to execute on the PostgreSQL database. Only SELECT queries are allowed.")


class PostgresConnector(BaseTool):
    """Read-only Postgres database connector tool"""
    
    def __init__(self):
        # Get database schema to include in description
        schema_info = self._get_database_schema()
        
        description = """Execute read-only SQL queries on PostgreSQL database. Only SELECT queries are allowed.
        
Available tables and columns:
{}

Use this tool to query invoice data, customer information, and other business data.""".format(schema_info)
        
        super().__init__(
            name="postgres_query",
            description=description
        )
        self.connection = None
        
        # Initialize table mappings as empty dict
        self.table_mappings = {}
        
        # Try to generate semantic table mappings based on database schema
        try:
            self.table_mappings = self._generate_semantic_mappings()
        except Exception as e:
            print(f"Warning: Could not generate table mappings: {e}")
            self.table_mappings = {}
    
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
    
    def _generate_semantic_mappings(self) -> Dict[str, List[str]]:
        """
        Dynamically generate semantic table mappings by analyzing database schema
        
        Returns:
            Dictionary mapping semantic names to possible actual table names
        """
        try:
            # Get available tables from database
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            
            available_tables = [row[0] for row in cursor.fetchall()]
            cursor.close()
            
            # Generate semantic mappings dynamically
            mappings = {}
            
            # Common semantic categories
            semantic_categories = [
                'invoice', 'invoice_detail', 'document', 'customer', 
                'product', 'vendor', 'order', 'payment', 'user'
            ]
            
            # For each semantic category, find matching tables
            for category in semantic_categories:
                matches = []
                
                # Look for tables that contain the category name
                for table in available_tables:
                    # Exact match
                    if table.lower() == category.lower():
                        matches.append(table)
                    # Prefixed match (e.g., icap_invoice)
                    elif table.lower().endswith('_' + category.lower()) or table.lower().startswith(category.lower() + '_'):
                        matches.append(table)
                    # Plural form match
                    elif table.lower() == category.lower() + 's' or table.lower() + 's' == category.lower():
                        matches.append(table)
                
                # Sort by preference (prefixed versions first, then exact matches)
                matches.sort(key=lambda x: (not x.startswith('icap_'), x))
                
                if matches:
                    mappings[category] = matches
            
            return mappings
            
        except Exception as e:
            # Return empty mappings on error
            return {}
    
    def _resolve_table_name(self, semantic_name: str) -> str:
        """
        Resolve semantic table name to actual table name by checking existence
        
        Args:
            semantic_name: User-friendly table name (e.g., 'invoice')
            
        Returns:
            Actual table name that exists in database
        """
        # Get available table names from database
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            
            available_tables = [row[0] for row in cursor.fetchall()]
            cursor.close()
            
            # Regenerate current mappings to ensure they're up-to-date
            current_mappings = self._generate_semantic_mappings()
            
            # Check if semantic name has mappings
            if semantic_name.lower() in current_mappings:
                # Try each possible actual name in order
                for actual_name in current_mappings[semantic_name.lower()]:
                    if actual_name in available_tables:
                        return actual_name
            
            # Handle common plural forms
            singular_form = semantic_name.lower()
            if singular_form.endswith('s') and len(singular_form) > 1:
                singular_form = singular_form[:-1]  # Remove trailing 's'
                if singular_form in current_mappings:
                    for actual_name in current_mappings[singular_form]:
                        if actual_name in available_tables:
                            return actual_name
            
            # If no mapping found, check if semantic name itself exists
            if semantic_name.lower() in available_tables:
                return semantic_name.lower()
                
            # Return original if no match found
            return semantic_name
            
        except Exception as e:
            # Fallback to original name if error occurs
            return semantic_name
    
    def _resolve_semantic_table_names(self, query: str) -> str:
        """
        Replace semantic table names in query with actual table names
        
        Args:
            query: Original SQL query
            
        Returns:
            Query with semantic table names replaced
        """
        resolved_query = query
        
        # Get available table names from database
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            
            available_tables = [row[0] for row in cursor.fetchall()]
            cursor.close()
            
            # Regenerate current mappings to ensure they're up-to-date
            current_mappings = self._generate_semantic_mappings()
            
            # Replace semantic table names with actual ones
            import re
            
            # Pattern to match table names in FROM and JOIN clauses
            patterns = [
                r'\bFROM\s+([\w_]+)',
                r'\bJOIN\s+([\w_]+)'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, resolved_query, re.IGNORECASE)
                for match in matches:
                    # For each word in the query that might be a table name,
                    # check if we can resolve it to an actual table
                    resolved_name = self._resolve_table_name(match)
                    if resolved_name != match:
                        # Replace in query
                        resolved_query = re.sub(r'\b' + re.escape(match) + r'\b', 
                                              resolved_name, resolved_query, flags=re.IGNORECASE)
                        
        except Exception as e:
            # If error occurs, return original query
            print(f"Error in _resolve_semantic_table_names: {e}")
            pass
            
        return resolved_query
    
    def _enhance_query_for_jsonb_dates(self, query: str) -> str:
        """
        Enhance query to properly handle JSONB date columns by providing better error guidance
        
        Args:
            query: SQL query that may contain date operations on JSONB columns
            
        Returns:
            Same query (unchanged) but with improved error handling guidance
        """
        # For now, return the query as-is but we could enhance it in the future
        # The main enhancement is in the error handling in the execute method
        return query
    
    def _get_database_schema(self) -> str:
        """
        Retrieve database schema information (tables and columns)
        
        Returns:
            Formatted string with table and column information
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Query to get tables and their columns from information_schema
            query = """
            SELECT 
                table_name,
                column_name,
                data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position;
            """
            
            cursor.execute(query)
            rows = cursor.fetchall()
            cursor.close()
            
            # Organize data by table
            tables = {}
            for table_name, column_name, data_type in rows:
                if table_name not in tables:
                    tables[table_name] = []
                tables[table_name].append(f"{column_name} ({data_type})")
            
            # Format as string
            if not tables:
                return "No tables found in the database."
            
            schema_lines = []
            schema_lines.append("Table mappings (you can use semantic names like 'invoice' which will automatically resolve to actual table names like 'icap_invoice'):")
            
            # Regenerate semantic mappings to ensure they're up-to-date
            current_mappings = self._generate_semantic_mappings()
            
            # Add semantic mappings info
            for semantic_name, possible_names in current_mappings.items():
                matched_actual = [name for name in possible_names if name in tables]
                if matched_actual:
                    schema_lines.append(f"  - '{semantic_name}' maps to: {', '.join(matched_actual)}")
            
            schema_lines.append("")
            schema_lines.append("Actual tables and columns:")
            for table_name, columns in tables.items():
                schema_lines.append(f"  - {table_name}: {', '.join(columns)}")
            
            return "\n".join(schema_lines)
            
        except Exception as e:
            return f"Unable to retrieve schema: {str(e)}"
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute a read-only SQL query
        
        Args:
            query: SQL SELECT query string (passed as keyword argument)
            
        Returns:
            Dictionary with query results or error message
        """
        print(f"🔍 DEBUG: execute() called with kwargs: {kwargs}")
        
        # Extract query from kwargs
        query = kwargs.get('query', '')
        
        print(f"🔍 DEBUG: extracted query: '{query}'")
        
        if not query:
            return {
                "success": False,
                "error": "No query provided. Please provide a SQL SELECT query."
            }
        
        # Resolve semantic table names to actual table names
        resolved_query = self._resolve_semantic_table_names(query)
        print(f"🔍 DEBUG: resolved query: '{resolved_query}'")
        
        # Enhance query for JSONB date handling
        enhanced_query = self._enhance_query_for_jsonb_dates(resolved_query)
        print(f"🔍 DEBUG: enhanced query: '{enhanced_query}'")
        
        try:
            # Validate query is read-only
            query_upper = enhanced_query.strip().upper()
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
            
            # Rollback any pending transactions to ensure clean state
            try:
                conn.rollback()
            except:
                pass
            
            cursor = conn.cursor()
            
            cursor.execute(enhanced_query)
            
            # Fetch column names
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            
            # Fetch all results
            rows = cursor.fetchall()
            
            # Convert to list of dictionaries
            results = [dict(zip(columns, row)) for row in rows]
            
            cursor.close()
            
            # Commit the read transaction
            conn.commit()
            
            return {
                "success": True,
                "columns": columns,
                "rows": results,
                "row_count": len(results)
            }
            
        except psycopg2.Error as e:
            # Rollback on error
            try:
                conn = self._get_connection()
                conn.rollback()
            except:
                pass
            
            error_msg = str(e)
            
            # Provide better error messages for common JSONB issues
            if "jsonb" in error_msg.lower() and ("extract" in error_msg.lower() or "date_part" in error_msg.lower()):
                error_msg += "\n\n💡 TIP: The date column appears to be stored as JSONB. Try using JSONB operators like ->> to extract values.\nExample: invoice_date->>'date' to extract a 'date' field from JSONB."
            
            return {
                "success": False,
                "error": error_msg,
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
    
    def to_langchain_tool(self) -> StructuredTool:
        """Convert to LangChain tool format with proper argument schema"""
        
        def tool_func(query: str) -> str:
            print(f"🔍 DEBUG: tool_func called with query: {query}")
            result = self.execute(query=query)
            print(f"🔍 DEBUG: execute returned: {result}")
            return str(result)
        
        try:
            return StructuredTool.from_function(
                func=tool_func,
                name=self.name,
                description=self.description,
                args_schema=PostgresQueryInput
            )
        except Exception as e:
            print(f"Error creating StructuredTool: {e}")
            # Fallback to basic tool without schema
            return StructuredTool.from_function(
                func=tool_func,
                name=self.name,
                description=self.description
            )

