import psycopg2
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from langchain.tools import StructuredTool

from config import settings
from .base_tool import BaseTool 


class PostgresQueryInput(BaseModel):
    """Input schema for Postgres query tool"""
    query: str = Field(description="SQL SELECT query to execute on the PostgreSQL database. Only SELECT queries are allowed.")


class PostgresSchemaInput(BaseModel):
    """Input schema for Postgres schema inspection tool"""
    table_name: str = Field(description="Name of the table to inspect. Use semantic names like 'invoice' or 'vendor'. Leave empty to get all tables.", default="")


class PostgresConnector(BaseTool):
    """Read-only Postgres database connector tool"""
    
    def __init__(self):
        # Get database schema to include in description
        schema_info = self._get_database_schema()
        
        description = """⚠️ IMPORTANT: Call 'postgres_inspect_schema' tool FIRST before using this tool!

Execute read-only SQL queries on PostgreSQL database. Only SELECT queries are allowed.

🔴 REQUIRED FIRST STEP: Use postgres_inspect_schema(table_name='invoice') to see:
- Actual column names
- Which columns are JSONB (require ->> operator)
- Sample data structure

Available tables and columns:
{}

Use this tool to query invoice data, customer information, and other business data.

Note: Many columns are JSONB - you MUST inspect schema first or queries will fail!""".format(schema_info)
        
        super().__init__(
            name="postgres_query",
            description=description
        )
        self.connection = None
        
        # Initialize table mappings as empty dict
        self.table_mappings = {}
        
        # Track which tables have been inspected in current session
        self._inspected_tables = set()
        
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
                'invoice', 'invoice_detail', 'invoice_line_item',
                'document', 'customer', 'product', 'vendor', 
                'order', 'payment', 'user', 'line_item', 'detail'
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
    
    def _detect_implicit_relationships(self, table_name: str, all_tables: List[str]) -> Dict[str, Any]:
        """
        Detect implicit foreign key relationships based on naming conventions
        (e.g., document_id references icap_document.id, invoice_id references icap_invoice.id)
        
        Args:
            table_name: The table to analyze
            all_tables: List of all available tables in the database
            
        Returns:
            Dictionary with implicit foreign keys and related tables
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Get columns for this table
            cursor.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                ORDER BY ordinal_position;
            """, (table_name,))
            
            columns = cursor.fetchall()
            cursor.close()
            
            implicit_fks = []
            referenced_by = []
            
            # Pattern 1: Look for columns ending with '_id' (e.g., document_id, vendor_id, invoice_id)
            for col_name, col_type in columns:
                if col_name.endswith('_id') and col_type == 'uuid':
                    # Extract the referenced table name
                    # e.g., 'document_id' -> look for 'icap_document' or 'document' table
                    ref_entity = col_name[:-3]  # Remove '_id'
                    
                    # Try to find matching table
                    for potential_table in all_tables:
                        # Check if table name matches the pattern
                        # e.g., 'icap_document', 'document'
                        if (potential_table.endswith('_' + ref_entity) or 
                            potential_table == ref_entity or
                            potential_table.endswith(ref_entity)):
                            
                            implicit_fks.append({
                                "column": col_name,
                                "references_table": potential_table,
                                "references_column": "id",
                                "confidence": "high",
                                "detection_method": "naming_convention"
                            })
                            break
            
            # Pattern 2: Look for tables that might reference this table
            # e.g., if table is 'icap_invoice', look for 'invoice_id' in other tables
            
            # Extract entity name from table name
            # 'icap_invoice' -> 'invoice', 'icap_document' -> 'document'
            entity_name = table_name
            if '_' in table_name:
                # Try to extract the entity part (last part after underscore)
                parts = table_name.split('_')
                entity_name = parts[-1]  # e.g., 'invoice', 'document'
            
            expected_fk_col = f"{entity_name}_id"  # e.g., 'invoice_id', 'document_id'
            
            # Check all other tables for this column
            for other_table in all_tables:
                if other_table == table_name:
                    continue
                    
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' 
                        AND table_name = %s
                        AND column_name = %s
                        AND data_type = 'uuid';
                """, (other_table, expected_fk_col))
                
                if cursor.fetchone():
                    # This table has a column that likely references our table
                    referenced_by.append({
                        "table": other_table,
                        "column": expected_fk_col,
                        "references_column": "id",
                        "confidence": "high",
                        "detection_method": "naming_convention"
                    })
                cursor.close()
            
            return {
                "implicit_foreign_keys": implicit_fks,
                "implicit_referenced_by": referenced_by
            }
            
        except Exception as e:
            print(f"Warning: Could not detect implicit relationships: {e}")
            return {
                "implicit_foreign_keys": [],
                "implicit_referenced_by": []
            }
    
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
    
    def _extract_tables_from_query(self, query: str) -> List[str]:
        """
        Extract table names from a SQL query
        
        Args:
            query: SQL query string
            
        Returns:
            List of table names found in the query
        """
        import re
        
        tables = []
        
        # Pattern to match table names in FROM and JOIN clauses
        patterns = [
            r'\bFROM\s+([\w_]+)',
            r'\bJOIN\s+([\w_]+)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, query, re.IGNORECASE)
            tables.extend(matches)
        
        return list(set(tables))  # Remove duplicates
    
    def _auto_inspect_tables(self, query: str) -> str:
        """
        Automatically inspect tables in the query if not already inspected
        Returns helpful schema information as a string
        
        Args:
            query: SQL query to analyze
            
        Returns:
            Schema information string to help the LLM
        """
        tables = self._extract_tables_from_query(query)
        schema_info = []
        
        for table in tables:
            # Resolve semantic name to actual table name
            actual_table = self._resolve_table_name(table)
            
            # Check if we've already inspected this table in this session
            if actual_table not in self._inspected_tables:
                print(f"🔍 AUTO-INSPECT: Checking schema for table '{actual_table}'...")
                
                # Get schema for this table
                schema_result = self.get_table_schema(table_name=table)
                
                if schema_result.get('success'):
                    self._inspected_tables.add(actual_table)
                    
                    # Build helpful message
                    jsonb_cols = schema_result.get('jsonb_columns', [])
                    if jsonb_cols:
                        schema_info.append(
                            f"⚠️ Table '{actual_table}' has JSONB columns: {', '.join(jsonb_cols)}. "
                            f"Use ->> operator: (column_name->>'value')::type"
                        )
                    
                    # Show relationships
                    if schema_result.get('relationships'):
                        schema_info.append(f"🔗 {schema_result['relationships']}")
                    
                    if schema_result.get('related_tables'):
                        schema_info.append(f"📊 {schema_result['related_tables']}")
                        schema_info.append(
                            "➡️ TIP: For complete invoice data, consider joining with related tables using foreign keys!"
                        )
                    
                    # Show sample data structure
                    if schema_result.get('sample_data'):
                        schema_info.append(f"📊 Sample data from '{actual_table}': {schema_result['sample_data'][:1]}")
        
        if schema_info:
            return "\n".join(["\n🔍 AUTO-SCHEMA-CHECK:"] + schema_info + [""])
        return ""
    
    def get_table_schema(self, table_name: str = "") -> Dict[str, Any]:
        """
        Get detailed schema information for a specific table or all tables.
        This should be called BEFORE writing queries to understand the table structure.
        
        Args:
            table_name: Optional table name to inspect (can use semantic names like 'invoice')
            
        Returns:
            Dictionary with schema information including columns, data types, sample data, and relationships
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Resolve semantic table name if provided
            actual_table = None
            if table_name:
                actual_table = self._resolve_table_name(table_name)
            
            # Get schema information
            if actual_table:
                # Get columns for specific table
                cursor.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                    ORDER BY ordinal_position;
                """, (actual_table,))
                
                columns = cursor.fetchall()
                
                if not columns:
                    cursor.close()
                    return {
                        "success": False,
                        "error": f"Table '{table_name}' (resolved to '{actual_table}') not found"
                    }
                
                # Get foreign key relationships
                cursor.execute("""
                    SELECT
                        kcu.column_name,
                        ccu.table_name AS foreign_table_name,
                        ccu.column_name AS foreign_column_name
                    FROM information_schema.table_constraints AS tc
                    JOIN information_schema.key_column_usage AS kcu
                        ON tc.constraint_name = kcu.constraint_name
                        AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage AS ccu
                        ON ccu.constraint_name = tc.constraint_name
                        AND ccu.table_schema = tc.table_schema
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                        AND tc.table_name = %s
                        AND tc.table_schema = 'public';
                """, (actual_table,))
                
                foreign_keys = cursor.fetchall()
                
                # Get tables that reference this table (reverse relationships)
                cursor.execute("""
                    SELECT
                        tc.table_name AS referencing_table,
                        kcu.column_name AS referencing_column,
                        ccu.column_name AS referenced_column
                    FROM information_schema.table_constraints AS tc
                    JOIN information_schema.key_column_usage AS kcu
                        ON tc.constraint_name = kcu.constraint_name
                        AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage AS ccu
                        ON ccu.constraint_name = tc.constraint_name
                        AND ccu.table_schema = tc.table_schema
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                        AND ccu.table_name = %s
                        AND tc.table_schema = 'public';
                """, (actual_table,))
                
                referenced_by = cursor.fetchall()
                
                # Get all available tables for implicit relationship detection
                cursor.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    ORDER BY table_name;
                """)
                all_tables = [row[0] for row in cursor.fetchall()]
                
                # Detect implicit relationships based on naming conventions
                implicit_rels = self._detect_implicit_relationships(actual_table, all_tables)
                
                # Get sample data to show structure
                cursor.execute(f"SELECT * FROM {actual_table} LIMIT 3;")
                sample_rows = cursor.fetchall()
                column_names = [desc[0] for desc in cursor.description]
                
                cursor.close()
                
                # Build response
                column_info = []
                jsonb_cols = []
                uuid_cols = []
                for col_name, data_type, nullable in columns:
                    column_info.append({
                        "name": col_name,
                        "type": data_type,
                        "nullable": nullable == "YES"
                    })
                    if data_type == "jsonb":
                        jsonb_cols.append(col_name)
                    elif data_type == "uuid":
                        uuid_cols.append(col_name)
                
                response = {
                    "success": True,
                    "table_name": actual_table,
                    "columns": column_info,
                    "total_columns": len(column_info),
                    "sample_data": [dict(zip(column_names, row)) for row in sample_rows[:3]]
                }
                
                # Add foreign key relationships (both explicit and implicit)
                all_fk_info = []
                all_related_tables = set()
                
                # Add explicit foreign keys
                if foreign_keys:
                    for col, fk_table, fk_col in foreign_keys:
                        all_fk_info.append({
                            "column": col,
                            "references_table": fk_table,
                            "references_column": fk_col,
                            "type": "explicit"
                        })
                        all_related_tables.add(fk_table)
                
                # Add implicit foreign keys
                if implicit_rels.get('implicit_foreign_keys'):
                    for fk in implicit_rels['implicit_foreign_keys']:
                        all_fk_info.append({
                            "column": fk['column'],
                            "references_table": fk['references_table'],
                            "references_column": fk['references_column'],
                            "type": "implicit",
                            "confidence": fk['confidence']
                        })
                        all_related_tables.add(fk['references_table'])
                
                if all_fk_info:
                    response["foreign_keys"] = all_fk_info
                    response["relationships"] = f"This table links to: {', '.join(all_related_tables)}"
                
                # Add reverse relationships (both explicit and implicit)
                all_ref_info = []
                all_detail_tables = set()
                
                # Add explicit reverse relationships
                if referenced_by:
                    for ref_table, ref_col, this_col in referenced_by:
                        all_ref_info.append({
                            "table": ref_table,
                            "column": ref_col,
                            "references_column": this_col,
                            "type": "explicit"
                        })
                        all_detail_tables.add(ref_table)
                
                # Add implicit reverse relationships
                if implicit_rels.get('implicit_referenced_by'):
                    for ref in implicit_rels['implicit_referenced_by']:
                        all_ref_info.append({
                            "table": ref['table'],
                            "column": ref['column'],
                            "references_column": ref['references_column'],
                            "type": "implicit",
                            "confidence": ref['confidence']
                        })
                        all_detail_tables.add(ref['table'])
                
                if all_ref_info:
                    response["referenced_by"] = all_ref_info
                    response["related_tables"] = f"Related detail tables: {', '.join(all_detail_tables)}"
                
                # Add JSONB guidance if applicable
                if jsonb_cols:
                    response["jsonb_columns"] = jsonb_cols
                    response["jsonb_guidance"] = (
                        f"⚠️ The following columns are JSONB: {', '.join(jsonb_cols)}. "
                        "These store objects like {'value': <data>, 'confidence': <float>, ...}. "
                        "Use ->> operator to extract: (column_name->>'value')::numeric or (column_name->>'value')::date"
                    )
                
                return response
            else:
                # Get all tables starting with 'icap_' prefix
                cursor.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name LIKE 'icap_%'
                    ORDER BY table_name;
                """)
                
                tables = [row[0] for row in cursor.fetchall()]
                cursor.close()
                
                return {
                    "success": True,
                    "tables": tables,
                    "total_tables": len(tables),
                    "message": f"Found {len(tables)} tables starting with 'icap_'. Call this tool again with a specific table_name to see detailed column information"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
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
            jsonb_columns = {}
            for table_name, column_name, data_type in rows:
                if table_name not in tables:
                    tables[table_name] = []
                    jsonb_columns[table_name] = []
                tables[table_name].append(f"{column_name} ({data_type})")
                if data_type == 'jsonb':
                    jsonb_columns[table_name].append(column_name)
            
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
            
            # Add JSONB handling instructions if any JSONB columns exist
            has_jsonb = any(len(cols) > 0 for cols in jsonb_columns.values())
            if has_jsonb:
                schema_lines.append("")
                schema_lines.append("⚠️ IMPORTANT - JSONB Column Handling:")
                schema_lines.append("Many columns are stored as JSONB objects with the structure: {'value': <actual_value>, 'pageNo': <int>, 'confidence': <float>, ...}")
                schema_lines.append("")
                schema_lines.append("To query JSONB columns:")
                schema_lines.append("  - Extract text value: column_name->>'value' (e.g., invoice_date->>'value')")
                schema_lines.append("  - Extract as JSONB: column_name->'value' (for nested operations)")
                schema_lines.append("  - Cast to date: (invoice_date->>'value')::date")
                schema_lines.append("  - Cast to numeric: (total->>'value')::numeric")
                schema_lines.append("  - Check confidence: (column_name->>'confidence')::float")
                schema_lines.append("")
                schema_lines.append("Example queries:")
                schema_lines.append("  - SELECT (total->>'value')::numeric FROM icap_invoice WHERE (total->>'value') IS NOT NULL;")
                schema_lines.append("  - SELECT * FROM icap_invoice WHERE (invoice_date->>'value')::date BETWEEN '2023-01-01' AND '2023-12-31';")
                schema_lines.append("  - SELECT SUM((total->>'value')::numeric) FROM icap_invoice WHERE (total->>'confidence')::float > 90;")
                schema_lines.append("")
                for table_name, cols in jsonb_columns.items():
                    if cols:
                        schema_lines.append(f"  JSONB columns in {table_name}: {', '.join(cols)}")
            
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
        
        # AUTO-INSPECT: DISABLED - AI should inspect schema during query building, not execution
        # This was causing redundant schema checks after the AI already inspected tables
        auto_schema_info = None
        
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
                "row_count": len(results),
                "schema_info": auto_schema_info if auto_schema_info else None
            }
            
        except psycopg2.Error as e:
            # Rollback on error
            try:
                conn = self._get_connection()
                conn.rollback()
            except:
                pass
            
            error_msg = str(e)
            
            # Add auto-schema info to error message if available
            if auto_schema_info:
                error_msg = auto_schema_info + "\n" + error_msg
            
            # Provide better error messages for common JSONB issues
            if "jsonb" in error_msg.lower() and ("extract" in error_msg.lower() or "date_part" in error_msg.lower()):
                error_msg += "\n\n💡 TIP: The date column appears to be stored as JSONB. Try using JSONB operators like ->> to extract values.\nExample: invoice_date->>'value' to extract the value field from JSONB, then cast it: (invoice_date->>'value')::date"
            elif "does not exist" in error_msg.lower() and "column" in error_msg.lower():
                # Extract column name from error if possible
                import re
                column_match = re.search(r'column "([^"]+)" does not exist', error_msg)
                if column_match:
                    missing_col = column_match.group(1)
                    error_msg += f"\n\n💡 TIP: Column '{missing_col}' not found. Many columns are stored as JSONB objects.\n"
                    error_msg += "Common JSONB columns: invoice_date, invoice_number, total, sub_total, tax, etc.\n"
                    error_msg += "Use ->> operator to extract values: (total->>'value')::numeric, (invoice_date->>'value')::date\n"
                    error_msg += "Example: SELECT (total->>'value')::numeric AS total_amount FROM icap_invoice;"
            
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
    
    def to_langchain_schema_tool(self) -> StructuredTool:
        """Create a separate LangChain tool for schema inspection"""
        
        def schema_tool_func(table_name: str = "") -> str:
            print(f"📊 DEBUG: schema_tool_func called with table_name: {table_name}")
            result = self.get_table_schema(table_name=table_name)
            print(f"📊 DEBUG: get_table_schema returned: {result}")
            return str(result)
        
        description = """🔍 MUST USE THIS FIRST before writing SQL queries! Inspect PostgreSQL database schema.

⚠️ CRITICAL: Always call this tool BEFORE postgres_query to see:
- Exact column names (many are JSONB, not simple columns!)
- Data types and structure
- Sample data with actual values
- How to properly extract JSONB fields
- **Foreign key relationships to related tables**
- **Related detail tables (e.g., invoice_detail, document)**

Usage:
- Call with table_name='invoice' to see invoice table structure AND related tables
- Call with table_name='vendor' to see vendor table structure  
- Call with empty string to list all available tables

Without calling this first, your queries WILL FAIL because you won't know:
- Which columns exist
- Which columns are JSONB (need ->> operator)
- The correct syntax to extract values
- **Which related tables to JOIN for complete data**

Example: postgres_inspect_schema(table_name='invoice') returns:
- Column list + sample data
- Foreign keys showing links to document, vendor tables
- Related detail tables like icap_invoice_detail"""
        
        try:
            return StructuredTool.from_function(
                func=schema_tool_func,
                name="postgres_inspect_schema",
                description=description,
                args_schema=PostgresSchemaInput
            )
        except Exception as e:
            print(f"Error creating schema StructuredTool: {e}")
            # Fallback to basic tool without schema
            return StructuredTool.from_function(
                func=schema_tool_func,
                name="postgres_inspect_schema",
                description=description
            )

