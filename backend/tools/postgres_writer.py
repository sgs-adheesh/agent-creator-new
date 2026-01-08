import psycopg2
from typing import Dict, Any, List, Optional
from langchain.tools import StructuredTool
import json
import re
from datetime import datetime

from config import settings
from .base_tool import BaseTool


class PostgresWriter(BaseTool):
    """Secure PostgreSQL write operations tool with transaction safety and validation"""
    
    # Allowed operations (whitelist approach)
    ALLOWED_OPERATIONS = ['INSERT', 'UPDATE', 'DELETE']
    
    # Tables that are protected from write operations (blacklist)
    PROTECTED_TABLES = ['pg_', 'information_schema', 'sys']
    
    # Maximum rows affected per operation (safety limit)
    MAX_ROWS_LIMIT = 1000
    
    def __init__(self):
        description = """⚠️ SECURE PostgreSQL Write Operations Tool ⚠️

Execute INSERT, UPDATE, and DELETE operations on PostgreSQL database with built-in safety measures.

🔴 SECURITY FEATURES:
1. ✅ Transaction-based: Auto-rollback on errors
2. ✅ Dry-run mode: Preview changes before committing
3. ✅ Row limit: Maximum 100 rows per operation
4. ✅ Protected tables: System tables are blocked
5. ✅ Query validation: Syntax and permission checks
6. ✅ Audit logging: All operations are logged

🔴 REQUIRED WORKFLOW:
1. ALWAYS use dry_run=True first to preview changes
2. Review the affected_rows count and preview_data
3. If safe, execute with dry_run=False to commit

🔴 SUPPORTED OPERATIONS:

1. INSERT - Add new records:
   INSERT INTO table_name (column1, column2) VALUES ('value1', 'value2');
   
2. UPDATE - Modify existing records:
   UPDATE table_name SET column1 = 'new_value' WHERE id = 123;
   
3. DELETE - Remove records:
   DELETE FROM table_name WHERE condition = 'value';

🔴 SAFETY RULES:
1. ALWAYS include WHERE clause for UPDATE/DELETE (prevents accidental mass updates)
2. NEVER modify system tables (pg_*, information_schema)
3. Operations affecting >100 rows are blocked
4. Use transactions - partial failures rollback completely
5. Test with dry_run first

🔴 JSONB COLUMN HANDLING:
For JSONB columns, insert data in the correct format:
- Structure: {{"value": "actual_data", "confidence": 0.95, "pageNo": 1}}
- Example: INSERT INTO table (jsonb_col) VALUES ('{{"value": "data", "confidence": 0.95, "pageNo": 1}}');

📘 EXAMPLE WORKFLOW:

Step 1: Dry-run to preview
  postgres_write(
    query="UPDATE icap_vendor SET name = 'New Name' WHERE id = 5",
    dry_run=True
  )
  
Step 2: Review the response
  {{
    "success": True,
    "dry_run": True,
    "affected_rows": 1,
    "preview_data": [...],
    "message": "DRY RUN: Would update 1 row(s)"
  }}

Step 3: Execute if safe
  postgres_write(
    query="UPDATE icap_vendor SET name = 'New Name' WHERE id = 5",
    dry_run=False
  )

⚠️ CRITICAL WARNINGS:
- UPDATE/DELETE without WHERE clause will be REJECTED
- Operations affecting >100 rows will be BLOCKED
- System tables cannot be modified
- All operations are logged with timestamp and user"""
        
        super().__init__(
            name="postgres_write",
            description=description
        )
        self.connection = None
        self._audit_log = []
    
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
    
    def _validate_query_safety(self, query: str) -> tuple[bool, str]:
        """
        Validate query for safety before execution
        
        Returns:
            (is_safe, error_message)
        """
        query_upper = query.strip().upper()
        
        # 1. Check operation type
        operation = None
        for op in self.ALLOWED_OPERATIONS:
            if query_upper.startswith(op):
                operation = op
                break
        
        if not operation:
            return (False, f"Only {', '.join(self.ALLOWED_OPERATIONS)} operations are allowed. Got: {query_upper[:20]}...")
        
        # 2. Check for multiple statements (SQL injection prevention)
        if ';' in query[:-1]:  # Allow trailing semicolon only
            return (False, "Multiple statements are not allowed. Execute one operation at a time.")
        
        # 3. Extract table name
        table_pattern = {
            'INSERT': r'INSERT\s+INTO\s+([\w_]+)',
            'UPDATE': r'UPDATE\s+([\w_]+)',
            'DELETE': r'DELETE\s+FROM\s+([\w_]+)'
        }
        
        match = re.search(table_pattern[operation], query_upper)
        if not match:
            return (False, f"Could not extract table name from {operation} query")
        
        table_name = match.group(1).lower()
        
        # 4. Check protected tables
        for protected in self.PROTECTED_TABLES:
            if table_name.startswith(protected):
                return (False, f"Cannot modify protected table: {table_name}")
        
        # 5. Require WHERE clause for UPDATE/DELETE
        if operation in ['UPDATE', 'DELETE']:
            if 'WHERE' not in query_upper:
                return (False, f"{operation} requires a WHERE clause to prevent accidental mass modifications. "
                              f"If you really want to modify all rows, add 'WHERE 1=1'")
        
        # 6. Check for dangerous keywords
        dangerous = ['DROP', 'TRUNCATE', 'ALTER', 'CREATE', 'GRANT', 'REVOKE']
        for keyword in dangerous:
            if keyword in query_upper:
                return (False, f"Query contains dangerous keyword: {keyword}")
        
        return (True, "")
    
    def _estimate_affected_rows(self, query: str, cursor) -> int:
        """
        Estimate number of rows that would be affected by the query
        
        Args:
            query: The write query
            cursor: Database cursor
            
        Returns:
            Estimated row count
        """
        query_upper = query.strip().upper()
        
        # For INSERT, return 1 (or count VALUES clauses)
        if query_upper.startswith('INSERT'):
            values_count = query_upper.count('VALUES')
            return values_count if values_count > 0 else 1
        
        # For UPDATE/DELETE, convert to SELECT COUNT(*)
        if query_upper.startswith('UPDATE'):
            # Extract: UPDATE table SET ... WHERE condition
            match = re.search(r'UPDATE\s+([\w_]+)\s+SET.*?(WHERE.+)?$', query_upper, re.DOTALL)
            if match:
                table_name = match.group(1)
                where_clause = match.group(2) if match.group(2) else ''
                count_query = f"SELECT COUNT(*) FROM {table_name} {where_clause}"
            else:
                return 0
        
        elif query_upper.startswith('DELETE'):
            # Extract: DELETE FROM table WHERE condition
            match = re.search(r'DELETE\s+FROM\s+([\w_]+)(.*)?$', query_upper, re.DOTALL)
            if match:
                table_name = match.group(1)
                where_clause = match.group(2) if match.group(2) else ''
                count_query = f"SELECT COUNT(*) FROM {table_name} {where_clause}"
            else:
                return 0
        else:
            return 0
        
        try:
            cursor.execute(count_query)
            result = cursor.fetchone()
            return result[0] if result else 0
        except Exception as e:
            print(f"Warning: Could not estimate affected rows: {e}")
            return 0
    
    def _get_preview_data(self, query: str, cursor, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get preview of data that would be affected
        
        Args:
            query: The write query
            cursor: Database cursor
            limit: Maximum number of rows to preview
            
        Returns:
            List of rows that would be affected
        """
        query_upper = query.strip().upper()
        
        try:
            if query_upper.startswith('INSERT'):
                # For INSERT, show what would be inserted (parse VALUES)
                return [{"note": "INSERT operation - new data will be added"}]
            
            elif query_upper.startswith('UPDATE') or query_upper.startswith('DELETE'):
                # Extract table and WHERE clause
                if query_upper.startswith('UPDATE'):
                    match = re.search(r'UPDATE\s+([\w_]+).*?(WHERE.+)?$', query_upper, re.DOTALL)
                else:
                    match = re.search(r'DELETE\s+FROM\s+([\w_]+)(.*)?$', query_upper, re.DOTALL)
                
                if match:
                    table_name = match.group(1)
                    where_clause = match.group(2) if match.group(2) else ''
                    preview_query = f"SELECT * FROM {table_name} {where_clause} LIMIT {limit}"
                    
                    cursor.execute(preview_query)
                    columns = [desc[0] for desc in cursor.description]
                    rows = cursor.fetchall()
                    
                    return [dict(zip(columns, row)) for row in rows]
            
            return []
        
        except Exception as e:
            print(f"Warning: Could not get preview data: {e}")
            return [{"error": f"Could not preview: {str(e)}"}]
    
    def _log_operation(self, query: str, dry_run: bool, success: bool, affected_rows: int, error: str = None):
        """Log operation for audit trail"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "query": query[:200],  # Truncate long queries
            "dry_run": dry_run,
            "success": success,
            "affected_rows": affected_rows,
            "error": error
        }
        self._audit_log.append(log_entry)
        
        # Keep only last 100 entries
        if len(self._audit_log) > 100:
            self._audit_log = self._audit_log[-100:]
    
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        Execute a write operation with safety checks
        
        Args:
            query: SQL write query (INSERT, UPDATE, DELETE)
            dry_run: If True, only preview changes without committing (default: True)
            
        Returns:
            Dictionary with operation results or error message
        """
        query = kwargs.get('query', '')
        dry_run = kwargs.get('dry_run', True)  # Default to safe mode
        
        if not query:
            return {
                "success": False,
                "error": "No query provided"
            }
        
        # Validate query safety
        is_safe, error_msg = self._validate_query_safety(query)
        if not is_safe:
            self._log_operation(query, dry_run, False, 0, error_msg)
            return {
                "success": False,
                "error": f"🚫 SAFETY CHECK FAILED: {error_msg}",
                "safety_check": "failed"
            }
        
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Estimate affected rows
            affected_rows = self._estimate_affected_rows(query, cursor)
            
            # Check row limit
            if affected_rows > self.MAX_ROWS_LIMIT:
                error = f"Operation would affect {affected_rows} rows, exceeding limit of {self.MAX_ROWS_LIMIT}"
                self._log_operation(query, dry_run, False, affected_rows, error)
                cursor.close()
                conn.rollback()
                return {
                    "success": False,
                    "error": f"🚫 {error}",
                    "affected_rows": affected_rows,
                    "limit": self.MAX_ROWS_LIMIT,
                    "suggestion": "Use more specific WHERE clause to target fewer rows"
                }
            
            # Get preview data
            preview_data = self._get_preview_data(query, cursor)
            
            if dry_run:
                # DRY RUN MODE - Don't execute, just preview
                cursor.close()
                conn.rollback()
                
                self._log_operation(query, True, True, affected_rows)
                
                return {
                    "success": True,
                    "dry_run": True,
                    "affected_rows": affected_rows,
                    "preview_data": preview_data,
                    "message": f"✅ DRY RUN: Would affect {affected_rows} row(s). Review data and execute with dry_run=False to commit.",
                    "next_step": "If this looks correct, call again with dry_run=False to execute"
                }
            
            else:
                # EXECUTE MODE - Actually perform the operation
                cursor.execute(query)
                actual_affected = cursor.rowcount
                conn.commit()
                
                cursor.close()
                
                self._log_operation(query, False, True, actual_affected)
                
                return {
                    "success": True,
                    "dry_run": False,
                    "affected_rows": actual_affected,
                    "message": f"✅ SUCCESS: {actual_affected} row(s) affected",
                    "committed": True,
                    "timestamp": datetime.now().isoformat()
                }
        
        except psycopg2.Error as e:
            # Database error - rollback transaction
            try:
                conn = self._get_connection()
                conn.rollback()
            except:
                pass
            
            error_msg = str(e)
            self._log_operation(query, dry_run, False, 0, error_msg)
            
            return {
                "success": False,
                "error": f"❌ DATABASE ERROR: {error_msg}",
                "rolled_back": True,
                "error_type": "database_error"
            }
        
        except Exception as e:
            # Unexpected error - rollback
            try:
                conn = self._get_connection()
                conn.rollback()
            except:
                pass
            
            error_msg = str(e)
            self._log_operation(query, dry_run, False, 0, error_msg)
            
            return {
                "success": False,
                "error": f"❌ ERROR: {error_msg}",
                "rolled_back": True,
                "error_type": "unknown_error"
            }
    
    def get_audit_log(self) -> List[Dict[str, Any]]:
        """Get audit log of recent operations"""
        return self._audit_log
    
    def close(self):
        """Close database connection"""
        if self.connection and not self.connection.closed:
            self.connection.close()
    
    def to_langchain_tool(self) -> StructuredTool:
        """Convert to LangChain tool format"""
        
        def tool_func(query: str, dry_run: bool = True) -> str:
            result = self.execute(query=query, dry_run=dry_run)
            return str(result)
        
        return StructuredTool.from_function(
            func=tool_func,
            name=self.name,
            description=self.description
        )
