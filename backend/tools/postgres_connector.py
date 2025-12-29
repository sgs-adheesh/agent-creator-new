import psycopg2
from typing import Dict, Any, List, Optional
from langchain.tools import StructuredTool
import json
import os
from datetime import datetime

from config import settings
from .base_tool import BaseTool 


class PostgresConnector(BaseTool):
    """Read-only Postgres database connector tool"""
    
    # Class-level cache (shared across all instances)
    _SCHEMA_CACHE = None
    _MAPPING_CACHE = None
    _FK_CACHE = None  # Cache for foreign key relationships
    _CACHE_TIMESTAMP = None
    _CACHE_FILE = "postgres_schema_cache.json"
    
    def __init__(self):
        # LAZY LOADING: Don't fetch schema during init
        # Schema will be loaded on first use
        
        description = """⚠️⚠️⚠️ MANDATORY FIRST STEP: Call 'postgres_inspect_schema' BEFORE writing ANY query!

Execute read-only SQL queries on PostgreSQL database. Only SELECT queries are allowed.

🔴 REQUIRED WORKFLOW:
1. ALWAYS call postgres_inspect_schema(table_name='your_table') FIRST
2. Read the 'ready_to_use_query' template (auto-generated from postgres_schema_cache)
3. Copy the template and modify it for your specific needs
4. Execute the query using this tool

🔴 WHY SCHEMA INSPECTION IS MANDATORY:
- Column names are NOT hardcoded anywhere - they're discovered from postgres_schema_cache
- Column types (jsonb vs regular) determine the query syntax
- JSONB columns require special ->>'value' extraction
- The schema cache contains the ONLY source of truth for table structure

🔴 CRITICAL JSONB RULES (MUST FOLLOW FOR EVERY JSONB COLUMN):

1. JSONB columns contain: {{\"value\": \"actual_data\", \"confidence\": 0.95, \"pageNo\": 1}}

2. NEVER select the column directly - you'll get the entire JSON object
   ❌ WRONG: SELECT invoice_number, invoice_date, total FROM invoice
   ✅ CORRECT: SELECT (invoice_number->>'value')::text, (invoice_date->>'value')::text FROM invoice

3. EVERY JSONB column MUST use this pattern:
   - Extract value: column_name->>'value'
   - Cast to text: (column_name->>'value')::text
   - For math only: (column_name->>'value')::numeric

4. Treat ALL JSONB values as TEXT (including dates, numbers for display):
   ✅ (invoice_number->>'value')::text
   ✅ (invoice_date->>'value')::text  -- Dates are MM/DD/YYYY text
   ✅ (quantity->>'value')::text  -- Display as text
   ✅ (total->>'value')::numeric  -- Only for SUM, calculations

5. Date filtering uses LIKE on text:
   ✅ WHERE invoice_date->>'value' LIKE '02/%/2025'
   ❌ WRONG: WHERE invoice_date LIKE '02/%/2025'  -- Missing ->>'value'
   ❌ WRONG: WHERE (invoice_date->>'value')::date >= '2025-01-01'  -- Not date type

6. NEVER use ::int (causes overflow), NEVER use ::date (data is text):
   ❌ WRONG: (quantity->>'value')::int
   ❌ WRONG: (invoice_date->>'value')::date
   ✅ CORRECT: (quantity->>'value')::text or ::numeric for calculations

📘 EXAMPLE WORKFLOW:
Step 1: result = postgres_inspect_schema(table_name='invoice')
Step 2: Copy result['ready_to_use_query']:
  SELECT
    id,
    vendor_id,
    (invoice_number->>'value')::text AS invoice_number,
    (invoice_date->>'value')::text AS invoice_date,
    (total->>'value')::text AS total
  FROM icap_invoice
  LIMIT 10;

Step 3: Modify for your needs:
  SELECT
    (i.invoice_number->>'value')::text,
    (i.invoice_date->>'value')::text,
    (i.total->>'value')::numeric,
    v.name
  FROM icap_invoice i
  LEFT JOIN icap_vendor v ON i.vendor_id = v.id
  WHERE i.invoice_date->>'value' LIKE '02/%/2025';

Step 4: Execute with postgres_query(query='...')

Note: NEVER guess column names or types - ALWAYS inspect schema first!"""
        
        super().__init__(
            name="postgres_query",
            description=description
        )
        self.connection = None
        
        # Track which tables have been inspected in current session
        self._inspected_tables = set()
    
    @classmethod
    def _load_cache_from_file(cls):
        """Load schema cache from file if it exists and is recent"""
        if not os.path.exists(cls._CACHE_FILE):
            return False
        
        try:
            with open(cls._CACHE_FILE, 'r') as f:
                cache_data = json.load(f)
            
            # Check if cache is less than 24 hours old
            cache_time = datetime.fromisoformat(cache_data.get('timestamp', ''))
            age_hours = (datetime.now() - cache_time).total_seconds() / 3600
            
            if age_hours < 24:
                cls._SCHEMA_CACHE = cache_data.get('schema')
                cls._MAPPING_CACHE = cache_data.get('mappings')
                cls._FK_CACHE = cache_data.get('foreign_keys', {})
                cls._CACHE_TIMESTAMP = cache_time
                print(f"✅ Loaded schema cache from file (age: {age_hours:.1f} hours)")
                return True
            else:
                print(f"⏰ Cache file is {age_hours:.1f} hours old, will refresh")
        except Exception as e:
            print(f"⚠️ Could not load cache file: {e}")
        
        return False
    
    @classmethod
    def _save_cache_to_file(cls):
        """Save schema cache to file"""
        try:
            cache_data = {
                'timestamp': cls._CACHE_TIMESTAMP.isoformat(),
                'schema': cls._SCHEMA_CACHE,
                'mappings': cls._MAPPING_CACHE,
                'foreign_keys': cls._FK_CACHE
            }
            with open(cls._CACHE_FILE, 'w') as f:
                json.dump(cache_data, f, indent=2, default=str)
            print("💾 Saved schema cache to file")
        except Exception as e:
            print(f"⚠️ Could not save cache file: {e}")
    
    @classmethod
    def initialize_cache(cls, force_refresh: bool = True):
        """
        Initialize cache on application startup (call this from main.py)
        
        Args:
            force_refresh: If True, always fetch fresh data from database on app restart.
                          If False, try to load from cache file if available.
        """
        if cls._SCHEMA_CACHE is not None:
            print("✅ Schema cache already initialized in this session")
            return
        
        # If force_refresh is False, try loading from file first
        if not force_refresh:
            if cls._load_cache_from_file():
                return
        else:
            print("🔄 Force refresh enabled - rebuilding cache from database...")
        
        print("🔄 Initializing schema cache from database...")
        try:
            # Create temporary connection
            conn = psycopg2.connect(
                host=settings.postgres_host,
                port=settings.postgres_port,
                database=settings.postgres_database,
                user=settings.postgres_user,
                password=settings.postgres_password
            )
            
            cursor = conn.cursor()
            
            # Use fast system catalogs instead of information_schema
            cursor.execute("""
                SELECT 
                    c.relname AS table_name,
                    a.attname AS column_name,
                    t.typname AS data_type,
                    a.attnotnull AS not_null
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                JOIN pg_attribute a ON a.attrelid = c.oid
                JOIN pg_type t ON t.oid = a.atttypid
                WHERE n.nspname = 'public'
                    AND c.relkind = 'r'
                    AND a.attnum > 0
                    AND NOT a.attisdropped
                ORDER BY c.relname, a.attnum;
            """)
            
            rows = cursor.fetchall()
            
            # Organize by table
            schema = {}
            for table_name, column_name, data_type, not_null in rows:
                if table_name not in schema:
                    schema[table_name] = []
                schema[table_name].append({
                    'name': column_name,
                    'type': data_type,
                    'nullable': not not_null
                })
            
            cls._SCHEMA_CACHE = schema
            cls._CACHE_TIMESTAMP = datetime.now()
            
            # Get table list for mappings
            available_tables = list(schema.keys())
            
            # Generate semantic mappings
            mappings: Dict[str, List[str]] = {}
            
            # 1) Built-in semantic categories for common business entities
            semantic_categories = [
                'invoice', 'invoice_detail', 'invoice_line_item',
                'document', 'customer', 'product', 'vendor', 
                'order', 'payment', 'user', 'line_item', 'detail'
            ]
            
            for category in semantic_categories:
                matches: List[str] = []
                for table in available_tables:
                    tl = table.lower()
                    cl = category.lower()
                    if (
                        tl == cl or
                        tl.endswith('_' + cl) or
                        tl.startswith(cl + '_') or
                        tl == cl + 's' or
                        tl + 's' == cl
                    ):
                        matches.append(table)
                
                matches.sort(key=lambda x: (not x.startswith('icap_'), x))
                if matches:
                    mappings[category] = matches
            
            # 2) Auto-generate mappings from table names so more tables are discoverable
            #    Examples:
            #      icap_invoice          -> 'invoice'
            #      icap_invoice_detail   -> 'invoice_detail', 'detail'
            #      icap_payment_plan     -> 'payment_plan', 'payment', 'plan'
            for table in available_tables:
                parts = table.lower().split('_')
                # Heuristic: treat leading known prefixes as non-semantic
                prefixes_to_ignore = {'icap', 'tbl', 't'}
                tokens = [p for p in parts if p not in prefixes_to_ignore] or parts
                
                # Last token as base entity (e.g. 'invoice', 'detail', 'plan')
                base_entity = tokens[-1]
                mappings.setdefault(base_entity, []).append(table)
                
                # Last two tokens as compound entity (e.g. 'invoice_detail', 'payment_plan')
                if len(tokens) >= 2:
                    compound = '_'.join(tokens[-2:])
                    mappings.setdefault(compound, []).append(table)
                
                # Also map each token (except very short ones) to all tables containing it
                for tok in tokens:
                    if len(tok) >= 3:  # avoid noise from very short tokens
                        mappings.setdefault(tok, []).append(table)
            
            # Ensure deterministic ordering and de-duplicate table lists
            for key, vals in mappings.items():
                unique_vals = sorted(set(vals), key=lambda x: (not x.startswith('icap_'), x))
                mappings[key] = unique_vals
            
            cls._MAPPING_CACHE = mappings
            
            # Cache foreign key relationships for all tables
            print("📊 Caching foreign key relationships...")
            fk_cache = {}
            
            # Get all explicit foreign keys at once
            cursor.execute("""
                SELECT
                    tc.table_name,
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
                    AND tc.table_schema = 'public'
                ORDER BY tc.table_name;
            """)
            
            fk_rows = cursor.fetchall()
            
            # Organize explicit FKs by table
            for table_name, col_name, fk_table, fk_col in fk_rows:
                if table_name not in fk_cache:
                    fk_cache[table_name] = {'outgoing': [], 'incoming': []}
                
                fk_cache[table_name]['outgoing'].append({
                    'column': col_name,
                    'references_table': fk_table,
                    'references_column': fk_col,
                    'type': 'explicit'
                })
                
                # Add incoming relationship to referenced table
                if fk_table not in fk_cache:
                    fk_cache[fk_table] = {'outgoing': [], 'incoming': []}
                
                fk_cache[fk_table]['incoming'].append({
                    'table': table_name,
                    'column': col_name,
                    'references_column': fk_col,
                    'type': 'explicit'
                })
            
            # Now compute and cache IMPLICIT foreign keys for all tables
            print("🔍 Computing implicit foreign key relationships...")
            
            for table_name in available_tables:
                if table_name not in fk_cache:
                    fk_cache[table_name] = {'outgoing': [], 'incoming': []}
                
                columns = schema[table_name]
                
                # Pattern 1: Look for columns ending with '_id' (outgoing FKs)
                for col_data in columns:
                    col_name = col_data['name']
                    
                    if col_name.endswith('_id'):
                        ref_entity = col_name[:-3]
                        
                        # Find matching table
                        for potential_table in available_tables:
                            if (
                                potential_table.endswith('_' + ref_entity) or 
                                potential_table == ref_entity or
                                potential_table.endswith(ref_entity)
                            ):
                                # Check if not already in explicit FKs
                                already_exists = any(
                                    fk['column'] == col_name and fk['references_table'] == potential_table
                                    for fk in fk_cache[table_name]['outgoing']
                                )
                                
                                if not already_exists:
                                    fk_cache[table_name]['outgoing'].append({
                                        'column': col_name,
                                        'references_table': potential_table,
                                        'references_column': 'id',
                                        'type': 'implicit',
                                        'confidence': 'high',
                                        'detection_method': 'naming_convention'
                                    })
                                break
                
                # Pattern 2: Look for tables that reference this table (incoming FKs)
                entity_name = table_name
                if '_' in table_name:
                    parts = table_name.split('_')
                    entity_name = parts[-1]
                
                expected_fk_col = f"{entity_name}_id"
                
                for other_table in available_tables:
                    if other_table == table_name:
                        continue
                    
                    other_columns = schema[other_table]
                    
                    for col_data in other_columns:
                        if col_data['name'] == expected_fk_col:
                            # Check if not already in explicit FKs
                            already_exists = any(
                                fk['table'] == other_table and fk['column'] == expected_fk_col
                                for fk in fk_cache[table_name]['incoming']
                            )
                            
                            if not already_exists:
                                fk_cache[table_name]['incoming'].append({
                                    'table': other_table,
                                    'column': expected_fk_col,
                                    'references_column': 'id',
                                    'type': 'implicit',
                                    'confidence': 'high',
                                    'detection_method': 'naming_convention'
                                })
                            break
            
            cls._FK_CACHE = fk_cache
            
            # Count stats
            total_explicit = sum(len(v['outgoing']) for v in fk_cache.values() if v['outgoing'] and any(fk['type'] == 'explicit' for fk in v['outgoing']))
            total_implicit = sum(len([fk for fk in v['outgoing'] if fk['type'] == 'implicit']) for v in fk_cache.values())
            print(f"✅ Cached {total_explicit} explicit + {total_implicit} implicit FK relationships")
            
            cursor.close()
            conn.close()
            
            # Save to file
            cls._save_cache_to_file()
            
            print(f"✅ Schema cache initialized with {len(schema)} tables")
            
        except Exception as e:
            print(f"❌ Failed to initialize schema cache: {e}")
            cls._SCHEMA_CACHE = {}
            cls._MAPPING_CACHE = {}
            cls._FK_CACHE = {}
    
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
        Get semantic table mappings from cache
        
        Returns:
            Dictionary mapping semantic names to possible actual table names
        """
        # Ensure cache is initialized
        if self.__class__._MAPPING_CACHE is None:
            self.__class__.initialize_cache()
        
        return self.__class__._MAPPING_CACHE or {}
    
    def _resolve_table_name(self, semantic_name: str) -> str:
        """
        Resolve semantic table name to actual table name using cache
        
        Args:
            semantic_name: User-friendly table name (e.g., 'invoice')
            
        Returns:
            Actual table name that exists in database
        """
        # Ensure cache is initialized
        if self.__class__._SCHEMA_CACHE is None:
            self.__class__.initialize_cache()
        
        available_tables = list(self.__class__._SCHEMA_CACHE.keys())
        current_mappings = self._generate_semantic_mappings()
        
        # Check if semantic name has mappings
        if semantic_name.lower() in current_mappings:
            for actual_name in current_mappings[semantic_name.lower()]:
                if actual_name in available_tables:
                    return actual_name
        
        # Handle common plural forms
        singular_form = semantic_name.lower()
        if singular_form.endswith('s') and len(singular_form) > 1:
            singular_form = singular_form[:-1]
            if singular_form in current_mappings:
                for actual_name in current_mappings[singular_form]:
                    if actual_name in available_tables:
                        return actual_name
        
        # If no mapping found, check if semantic name itself exists
        if semantic_name.lower() in available_tables:
            return semantic_name.lower()
        
        return semantic_name
    
    def _resolve_semantic_table_names(self, query: str) -> str:
        """
        Replace semantic table names in query with actual table names
        
        Args:
            query: Original SQL query
            
        Returns:
            Query with semantic table names replaced
        """
        import re
        
        resolved_query = query
        
        try:
            # Pattern to match table names in FROM and JOIN clauses
            patterns = [
                r'\bFROM\s+([\w_]+)',
                r'\bJOIN\s+([\w_]+)'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, resolved_query, re.IGNORECASE)
                for match in matches:
                    resolved_name = self._resolve_table_name(match)
                    if resolved_name != match:
                        resolved_query = re.sub(r'\b' + re.escape(match) + r'\b', 
                                              resolved_name, resolved_query, flags=re.IGNORECASE)
        except Exception as e:
            print(f"Error in _resolve_semantic_table_names: {e}")
            
        return resolved_query
    
    def _detect_implicit_relationships(self, table_name: str, all_tables: List[str]) -> Dict[str, Any]:
        """
        Detect implicit foreign key relationships based on naming conventions
        (e.g., document_id references icap_document.id, invoice_id references icap_invoice.id)
        Uses cache for column information.
        
        Args:
            table_name: The table to analyze
            all_tables: List of all available tables in the database
            
        Returns:
            Dictionary with implicit foreign keys and related tables
        """
        try:
            # Get columns from cache
            if self.__class__._SCHEMA_CACHE is None:
                self.__class__.initialize_cache()
            
            if table_name not in self.__class__._SCHEMA_CACHE:
                return {"implicit_foreign_keys": [], "implicit_referenced_by": []}
            
            columns = self.__class__._SCHEMA_CACHE[table_name]
            
            implicit_fks = []
            referenced_by = []
            
            # Pattern 1: Look for columns ending with '_id'
            for col_data in columns:
                col_name = col_data['name']
                col_type = col_data['type']
                
                # Do NOT require UUID type here – many schemas use integer/string IDs
                if col_name.endswith('_id'):
                    ref_entity = col_name[:-3]
                    
                    for potential_table in all_tables:
                        if (
                            potential_table.endswith('_' + ref_entity) or 
                            potential_table == ref_entity or
                            potential_table.endswith(ref_entity)
                        ):
                            implicit_fks.append({
                                "column": col_name,
                                "references_table": potential_table,
                                "references_column": "id",
                                "confidence": "high",
                                "detection_method": "naming_convention"
                            })
                            break
            
            # Pattern 2: Look for tables that might reference this table
            entity_name = table_name
            if '_' in table_name:
                parts = table_name.split('_')
                entity_name = parts[-1]
            
            expected_fk_col = f"{entity_name}_id"
            
            for other_table in all_tables:
                if other_table == table_name:
                    continue
                
                if other_table in self.__class__._SCHEMA_CACHE:
                    other_columns = self.__class__._SCHEMA_CACHE[other_table]
                    
                    for col_data in other_columns:
                        # Again, do NOT require UUID type so we can pick up integer/string FKs
                        if col_data['name'] == expected_fk_col:
                            referenced_by.append({
                                "table": other_table,
                                "column": expected_fk_col,
                                "references_column": "id",
                                "confidence": "high",
                                "detection_method": "naming_convention"
                            })
                            break
            
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
        Uses cache for ALL operations - no database queries for metadata!
        
        Args:
            table_name: Optional table name to inspect (can use semantic names like 'invoice')
            
        Returns:
            Dictionary with schema information including columns, data types, sample data, and relationships
        """
        try:
            # Ensure cache is initialized
            if self.__class__._SCHEMA_CACHE is None:
                self.__class__.initialize_cache()
            
            # Resolve semantic table name if provided
            actual_table = None
            if table_name:
                actual_table = self._resolve_table_name(table_name)
            
            # Get schema information
            if actual_table:
                # Get columns from cache
                if actual_table not in self.__class__._SCHEMA_CACHE:
                    return {
                        "success": False,
                        "error": f"Table '{table_name}' (resolved to '{actual_table}') not found"
                    }
                
                columns_info = self.__class__._SCHEMA_CACHE[actual_table]
                
                # Get foreign key relationships from cache (no DB query!)
                fk_data = self.__class__._FK_CACHE.get(actual_table, {'outgoing': [], 'incoming': []})
                foreign_keys = fk_data.get('outgoing', [])
                referenced_by_fks = fk_data.get('incoming', [])
                
                # Get all available tables for implicit relationship detection
                all_tables = list(self.__class__._SCHEMA_CACHE.keys())
                
                # Detect implicit relationships (uses cache only)
                implicit_rels = self._detect_implicit_relationships(actual_table, all_tables)
                
                # Get sample data (ONLY database query - for actual data)
                conn = self._get_connection()
                cursor = conn.cursor()
                cursor.execute(f"SELECT * FROM {actual_table} LIMIT 1;")
                sample_rows = cursor.fetchall()
                column_names = [desc[0] for desc in cursor.description]
                cursor.close()
                
                # Build response
                column_info = []
                jsonb_cols = []
                uuid_cols = []
                for col_data in columns_info:
                    col_name = col_data['name']
                    data_type = col_data['type']
                    nullable = col_data['nullable']
                    
                    column_info.append({
                        "name": col_name,
                        "type": data_type,
                        "nullable": nullable
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
                    "sample_data": [dict(zip(column_names, row)) for row in sample_rows[:1]]
                }
                
                # Build a ready-to-use SELECT template showing correct syntax for ALL columns
                # This template is dynamically generated from the actual schema - NO hardcoded column names
                select_parts = []
                for col_data in columns_info:
                    col_name = col_data['name']
                    col_type = col_data['type']
                    
                    if col_type == "jsonb":
                        # JSONB columns MUST extract value and cast to text
                        select_parts.append(f"  ({col_name}->>'value')::text AS {col_name}")
                    else:
                        # Regular columns can be selected directly
                        select_parts.append(f"  {col_name}")
                
                ready_query = f"SELECT\n" + ",\n".join(select_parts) + f"\nFROM {actual_table}\nLIMIT 10;"
                response["ready_to_use_query"] = ready_query
                response["query_template_note"] = (
                    "⚠️ This query template is AUTO-GENERATED from postgres_schema_cache - "
                    "all column names and types are discovered dynamically. "
                    "Copy this template and modify the WHERE/JOIN clauses as needed."
                )
                
                # Add foreign key relationships (both explicit from cache and implicit)
                all_fk_info = []
                all_related_tables = set()
                
                # Add explicit foreign keys from cache
                for fk in foreign_keys:
                    all_fk_info.append(fk)
                    all_related_tables.add(fk['references_table'])
                
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
                
                # Add reverse relationships (both explicit from cache and implicit)
                all_ref_info = []
                all_detail_tables = set()
                
                # Add explicit reverse relationships from cache
                for ref in referenced_by_fks:
                    all_ref_info.append(ref)
                    all_detail_tables.add(ref['table'])
                
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
                
                # Add JSONB guidance with specific query syntax
                if jsonb_cols:
                    response["jsonb_columns"] = jsonb_cols
                    response["WARNING"] = f"⚠️⚠️⚠️ CRITICAL: {len(jsonb_cols)} columns are JSONB type - MUST use ->>'value' extraction!"
                    
                    # Show first 3 JSONB columns as examples (don't hardcode specific names)
                    example_cols = jsonb_cols[:3]
                    
                    # Build correct syntax examples (can't use backslash in f-string)
                    correct_examples = [f"({col}->>'value')::text" for col in example_cols]
                    correct_examples_str = ', '.join(correct_examples)
                    
                    response["jsonb_guidance"] = (
                        f"❌ WRONG - DO NOT DO THIS (returns entire JSON object):\n"
                        f"  SELECT {', '.join(example_cols)} FROM {actual_table};\n\n"
                        f"✅ CORRECT - ALWAYS extract 'value' and cast to ::text:\n"
                        f"  SELECT {correct_examples_str} FROM {actual_table};\n\n"
                        f"MANDATORY Rules for ALL {len(jsonb_cols)} JSONB columns:\n"
                        f"  1. Structure: {{\"value\": \"actual_data\", \"confidence\": 0.95, \"pageNo\": 1}}\n"
                        f"  2. ALWAYS extract: column_name->>'value'\n"
                        f"  3. ALWAYS cast to ::text for display/filtering\n"
                        f"  4. Use ::numeric ONLY for SUM/math (NEVER ::int)\n"
                        f"  5. Dates are TEXT (MM/DD/YYYY), use LIKE for filtering\n\n"
                        f"Query Patterns:\n"
                        f"  • Text/ID: (column_name->>'value')::text\n"
                        f"  • Date: (column_name->>'value')::text  (stored as MM/DD/YYYY)\n"
                        f"  • Number display: (column_name->>'value')::text\n"
                        f"  • Number math: (column_name->>'value')::numeric\n"
                        f"  • Date filter: WHERE column_name->>'value' LIKE '02/%/2025'\n\n"
                        f"JSONB columns in this table: {', '.join(jsonb_cols)}\n\n"
                        f"USE THE 'ready_to_use_query' FIELD - it shows correct syntax for EVERY column!"
                    )
                    
                    # Add query examples for each JSONB column
                    response["jsonb_query_examples"] = {}
                    for jcol in jsonb_cols:
                        # Infer likely data type from column name
                        if any(keyword in jcol.lower() for keyword in ['date', 'time', 'day', 'month', 'year']):
                            response["jsonb_query_examples"][jcol] = {
                                "type": "text (date stored as MM/DD/YYYY)",
                                "select": f"({jcol}->>'value')::text",
                                "where": f"WHERE {jcol}->>'value' LIKE '02/%/2025'",
                                "example": f"SELECT ({jcol}->>'value')::text AS {jcol}_value FROM {actual_table} WHERE {jcol}->>'value' LIKE '01/%/2024'"
                            }
                        elif any(keyword in jcol.lower() for keyword in ['total', 'amount', 'price', 'cost', 'tax', 'sum', 'balance']):
                            response["jsonb_query_examples"][jcol] = {
                                "type": "numeric",
                                "select": f"({jcol}->>'value')::numeric",
                                "where": f"WHERE ({jcol}->>'value')::numeric > 0",
                                "example": f"SELECT ({jcol}->>'value')::numeric AS {jcol}_value FROM {actual_table}"
                            }
                        elif any(keyword in jcol.lower() for keyword in ['qty', 'quantity', 'count', 'number']):
                            # Quantity should be numeric for calculations but can be text if not calculating
                            response["jsonb_query_examples"][jcol] = {
                                "type": "text or numeric (use ::numeric only for calculations)",
                                "select": f"({jcol}->>'value')::text",
                                "where": f"WHERE ({jcol}->>'value')::numeric > 0",
                                "example": f"SELECT ({jcol}->>'value')::text AS {jcol}_value FROM {actual_table}"
                            }
                        else:
                            response["jsonb_query_examples"][jcol] = {
                                "type": "text",
                                "select": f"({jcol}->>'value')::text",
                                "where": f"WHERE {jcol}->>'value' IS NOT NULL",
                                "example": f"SELECT ({jcol}->>'value')::text AS {jcol}_value FROM {actual_table}"
                            }
                
                return response
            else:
                # Get all tables from cache
                all_tables = list(self.__class__._SCHEMA_CACHE.keys())
                icap_tables = [t for t in all_tables if t.startswith('icap_')]
                
                return {
                    "success": True,
                    "tables": icap_tables,
                    "total_tables": len(icap_tables),
                    "message": f"Found {len(icap_tables)} tables starting with 'icap_'. Call this tool again with a specific table_name to see detailed column information"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _get_database_schema(self) -> str:
        """
        Retrieve database schema information (tables and columns) from cache
        
        Returns:
            Formatted string with table and column information
        """
        try:
            # Ensure cache is initialized
            if self.__class__._SCHEMA_CACHE is None:
                self.__class__.initialize_cache()
            
            schema = self.__class__._SCHEMA_CACHE
            
            if not schema:
                return "No tables found in the database."
            
            schema_lines = []
            schema_lines.append("Table mappings (you can use semantic names like 'invoice' which will automatically resolve to actual table names like 'icap_invoice'):")
            
            # Get semantic mappings
            current_mappings = self._generate_semantic_mappings()
            
            # Add semantic mappings info
            for semantic_name, possible_names in current_mappings.items():
                matched_actual = [name for name in possible_names if name in schema]
                if matched_actual:
                    schema_lines.append(f"  - '{semantic_name}' maps to: {', '.join(matched_actual)}")
            
            schema_lines.append("")
            schema_lines.append("Actual tables and columns:")
            
            # Organize JSONB columns
            jsonb_columns = {}
            
            for table_name, columns in schema.items():
                col_strs = []
                jsonb_columns[table_name] = []
                
                for col_data in columns:
                    col_name = col_data['name']
                    col_type = col_data['type']
                    col_strs.append(f"{col_name} ({col_type})")
                    
                    if col_type == 'jsonb':
                        jsonb_columns[table_name].append(col_name)
                
                schema_lines.append(f"  - {table_name}: {', '.join(col_strs)}")
            
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
            
            # Fetch all results (capped at 50 rows)
            rows = cursor.fetchmany(50)
            
            # Check if there are more rows
            has_more = cursor.fetchone() is not None
            
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
                "has_more": has_more,
                "note": "Results capped at 50 rows for performance" if has_more else None,
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
        """Convert to LangChain tool format"""
        
        def tool_func(query: str) -> str:
            print(f"🔍 DEBUG: tool_func called with query: {query}")
            result = self.execute(query=query)
            print(f"🔍 DEBUG: execute returned: {result}")
            return str(result)
        
        # Use simple from_function without args_schema for Python 3.14 compatibility
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
        
        # Use simple from_function without args_schema for Python 3.14 compatibility
        return StructuredTool.from_function(
            func=schema_tool_func,
            name="postgres_inspect_schema",
            description=description
        )

