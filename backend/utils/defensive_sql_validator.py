"""
Defensive SQL Validator and Auto-Fixer
Validates and automatically fixes SQL queries to follow the 4 Golden Rules
"""
import re
from typing import Dict, List, Tuple


class DefensiveSQLValidator:
    """Validates and fixes SQL queries to follow defensive SQL patterns"""
    
    def __init__(self):
        self.issues = []
        self.fixes_applied = []
    
    def validate_and_fix(self, query: str, auto_fix: bool = False) -> Dict:
        """
        Validate a SQL query and optionally auto-fix issues
        
        Args:
            query: SQL query string to validate
            auto_fix: If True, automatically apply fixes
            
        Returns:
            Dictionary with validation results and optionally fixed query
        """
        self.issues = []
        self.fixes_applied = []
        
        fixed_query = query
        
        # Check Rule 1: Defensive Join Pattern
        uuid_join_issues = self._check_uuid_joins(query)
        if uuid_join_issues:
            self.issues.extend(uuid_join_issues)
            if auto_fix:
                fixed_query = self._fix_uuid_joins(fixed_query)
        
        # Check Rule 2: Safe Numeric Pattern
        numeric_issues = self._check_numeric_casts(query)
        if numeric_issues:
            self.issues.extend(numeric_issues)
            if auto_fix:
                fixed_query = self._fix_numeric_casts(fixed_query)
        
        # Check Rule 3: Date Handling Pattern
        date_issues = self._check_date_handling(query)
        if date_issues:
            self.issues.extend(date_issues)
            if auto_fix:
                fixed_query = self._fix_date_handling(fixed_query)
        
        # Check Rule 4: Document Join
        doc_join_issues = self._check_document_join(query)
        if doc_join_issues:
            self.issues.extend(doc_join_issues)
            if auto_fix:
                fixed_query = self._fix_document_join(fixed_query)
        
        return {
            'is_valid': len(self.issues) == 0,
            'issues': self.issues,
            'fixes_applied': self.fixes_applied if auto_fix else [],
            'fixed_query': fixed_query if auto_fix else None,
            'original_query': query
        }
    
    def _check_uuid_joins(self, query: str) -> List[Dict]:
        """Check for unsafe UUID joins"""
        issues = []
        
        # Pattern: LEFT JOIN table ON (field->>'value')::uuid = table.id
        # Without NULLIF check
        pattern = r"(LEFT|INNER)\s+JOIN\s+(\w+)\s+(\w+)\s+ON\s+\(([a-z_]+\.)?\w+->>\'value\'\)::uuid\s*=\s*\3\.id"
        matches = re.finditer(pattern, query, re.IGNORECASE)
        
        for match in matches:
            # Check if NULLIF is present before this join
            join_text = match.group(0)
            if 'NULLIF' not in join_text:
                issues.append({
                    'rule': 'Rule 1: Defensive Join Pattern',
                    'severity': 'high',
                    'message': 'UUID join without NULLIF validation - will crash on empty strings',
                    'location': match.group(0),
                    'suggestion': 'Add NULLIF check before casting to UUID'
                })
        
        return issues
    
    def _check_numeric_casts(self, query: str) -> List[Dict]:
        """Check for unsafe numeric casts"""
        issues = []
        
        # Pattern 1: Direct ::numeric without NULLIF
        pattern1 = r"\([a-z_]+\.[a-z_]+->>\'value\'\)::numeric"
        matches1 = re.finditer(pattern1, query, re.IGNORECASE)
        
        for match in matches1:
            cast_text = match.group(0)
            # Check if NULLIF is present
            if 'NULLIF' not in cast_text:
                issues.append({
                    'rule': 'Rule 2: Safe Numeric Pattern',
                    'severity': 'high',
                    'message': 'Numeric cast without NULLIF - will crash on empty strings',
                    'location': cast_text,
                    'suggestion': 'Use NULLIF(field->>\'value\', \'\')::numeric'
                })
        
        # Pattern 2: CASE WHEN pattern (old style)
        pattern2 = r"CASE\s+WHEN\s+\([a-z_]+\.[a-z_]+->>\'value\'\)\s*!=\s*\'\'\s+THEN\s+\([a-z_]+\.[a-z_]+->>\'value\'\)::numeric\s+ELSE\s+NULL\s+END"
        matches2 = re.finditer(pattern2, query, re.IGNORECASE)
        
        for match in matches2:
            issues.append({
                'rule': 'Rule 2: Safe Numeric Pattern',
                'severity': 'medium',
                'message': 'Using old CASE WHEN pattern - can be simplified with NULLIF',
                'location': match.group(0),
                'suggestion': 'Replace with NULLIF pattern for cleaner code'
            })
        
        return issues
    
    def _check_date_handling(self, query: str) -> List[Dict]:
        """Check for unsafe date handling"""
        issues = []
        
        # Pattern 1: Simple ::date cast
        pattern1 = r"\([a-z_]+\.[a-z_]+->>\'value\'\)::date"
        matches1 = re.finditer(pattern1, query, re.IGNORECASE)
        
        for match in matches1:
            issues.append({
                'rule': 'Rule 3: Date Handling Pattern',
                'severity': 'critical',
                'message': 'Using ::date cast - will fail with MM/DD/YYYY format',
                'location': match.group(0),
                'suggestion': 'Use TO_DATE(field->>\'value\', \'MM/DD/YYYY\')'
            })
        
        # Pattern 2: Date arithmetic without TO_DATE
        pattern2 = r"CURRENT_DATE\s*-\s*\([a-z_]+\.[a-z_]+->>\'value\'\)::date"
        matches2 = re.finditer(pattern2, query, re.IGNORECASE)
        
        for match in matches2:
            issues.append({
                'rule': 'Rule 3: Date Handling Pattern',
                'severity': 'critical',
                'message': 'Date arithmetic without TO_DATE - will fail',
                'location': match.group(0),
                'suggestion': 'Use CURRENT_DATE - TO_DATE(field->>\'value\', \'MM/DD/YYYY\')'
            })
        
        return issues
    
    def _check_document_join(self, query: str) -> List[Dict]:
        """Check for missing or incorrect document join"""
        issues = []
        
        # Check if query uses icap_invoice
        if 'icap_invoice' in query.lower():
            # Check if icap_document join exists
            if 'icap_document' not in query.lower():
                issues.append({
                    'rule': 'Rule 4: Document Join',
                    'severity': 'medium',
                    'message': 'Missing icap_document join - batch_name will not be available',
                    'location': 'Query uses icap_invoice but no document join',
                    'suggestion': 'Add: INNER JOIN icap_document d ON invoice.document_id = d.id'
                })
            else:
                # Check if it's LEFT JOIN instead of INNER JOIN
                pattern = r"LEFT\s+JOIN\s+icap_document"
                if re.search(pattern, query, re.IGNORECASE):
                    issues.append({
                        'rule': 'Rule 4: Document Join',
                        'severity': 'low',
                        'message': 'Using LEFT JOIN for document - should be INNER JOIN',
                        'location': 'LEFT JOIN icap_document',
                        'suggestion': 'Change to INNER JOIN for guaranteed batch_name'
                    })
        
        return issues
    
    def _fix_uuid_joins(self, query: str) -> str:
        """Fix unsafe UUID joins"""
        # Pattern: LEFT JOIN table ON (field->>'value')::uuid = table.id
        # Fix: LEFT JOIN table ON NULLIF(field->>'value', '') IS NOT NULL AND (field->>'value')::uuid = table.id
        
        pattern = r"(LEFT|INNER)\s+JOIN\s+(\w+)\s+(\w+)\s+ON\s+\(([a-z_]+\.)?(\w+)->>\'value\'\)::uuid\s*=\s*\3\.id"
        
        def replacement(match):
            join_type = match.group(1)
            table_name = match.group(2)
            alias = match.group(3)
            prefix = match.group(4) or ''
            field = match.group(5)
            
            self.fixes_applied.append(f"Added NULLIF check for UUID join on {prefix}{field}")
            
            return (f"{join_type} JOIN {table_name} {alias} ON "
                   f"NULLIF({prefix}{field}->>'value', '') IS NOT NULL "
                   f"AND ({prefix}{field}->>'value')::uuid = {alias}.id")
        
        return re.sub(pattern, replacement, query, flags=re.IGNORECASE)
    
    def _fix_numeric_casts(self, query: str) -> str:
        """Fix unsafe numeric casts"""
        # Pattern 1: Replace direct ::numeric with NULLIF
        pattern1 = r"\(([a-z_]+\.)([a-z_]+)->>\'value\'\)::numeric"
        
        def replacement1(match):
            prefix = match.group(1)
            field = match.group(2)
            self.fixes_applied.append(f"Added NULLIF for numeric field {prefix}{field}")
            return f"NULLIF({prefix}{field}->>'value', '')::numeric"
        
        query = re.sub(pattern1, replacement1, query, flags=re.IGNORECASE)
        
        # Pattern 2: Replace CASE WHEN with NULLIF
        pattern2 = r"CASE\s+WHEN\s+\(([a-z_]+\.)([a-z_]+)->>\'value\'\)\s*!=\s*\'\'\s+THEN\s+\(\1\2->>\'value\'\)::numeric\s+ELSE\s+NULL\s+END"
        
        def replacement2(match):
            prefix = match.group(1)
            field = match.group(2)
            self.fixes_applied.append(f"Simplified CASE WHEN to NULLIF for {prefix}{field}")
            return f"NULLIF({prefix}{field}->>'value', '')::numeric"
        
        query = re.sub(pattern2, replacement2, query, flags=re.IGNORECASE)
        
        return query
    
    def _fix_date_handling(self, query: str) -> str:
        """Fix unsafe date handling"""
        # Pattern 1: Replace ::date with TO_DATE
        pattern1 = r"\(([a-z_]+\.)([a-z_]+)->>\'value\'\)::date"
        
        def replacement1(match):
            prefix = match.group(1)
            field = match.group(2)
            self.fixes_applied.append(f"Replaced ::date with TO_DATE for {prefix}{field}")
            return f"TO_DATE({prefix}{field}->>'value', 'MM/DD/YYYY')"
        
        query = re.sub(pattern1, replacement1, query, flags=re.IGNORECASE)
        
        # Pattern 2: Fix date arithmetic
        pattern2 = r"CURRENT_DATE\s*-\s*\(([a-z_]+\.)([a-z_]+)->>\'value\'\)::date"
        
        def replacement2(match):
            prefix = match.group(1)
            field = match.group(2)
            self.fixes_applied.append(f"Fixed date arithmetic for {prefix}{field}")
            return f"CURRENT_DATE - TO_DATE({prefix}{field}->>'value', 'MM/DD/YYYY')"
        
        query = re.sub(pattern2, replacement2, query, flags=re.IGNORECASE)
        
        return query
    
    def _fix_document_join(self, query: str) -> str:
        """Fix document join issues"""
        # Change LEFT JOIN to INNER JOIN for icap_document
        pattern = r"LEFT\s+JOIN\s+icap_document"
        
        if re.search(pattern, query, re.IGNORECASE):
            self.fixes_applied.append("Changed LEFT JOIN to INNER JOIN for icap_document")
            query = re.sub(pattern, "INNER JOIN icap_document", query, flags=re.IGNORECASE)
        
        return query


# Convenience function for quick validation
def validate_sql(query: str, auto_fix: bool = False) -> Dict:
    """
    Validate a SQL query against defensive SQL rules
    
    Args:
        query: SQL query string
        auto_fix: If True, automatically fix issues
        
    Returns:
        Validation results dictionary
    """
    validator = DefensiveSQLValidator()
    return validator.validate_and_fix(query, auto_fix=auto_fix)


# Example usage
if __name__ == "__main__":
    # Test query with issues
    test_query = """
    SELECT 
        (i.invoice_number->>'value')::text,
        (i.due_date->>'value')::date,
        (i.total->>'value')::numeric,
        CURRENT_DATE - (i.due_date->>'value')::date AS days_overdue
    FROM icap_invoice i
    LEFT JOIN icap_vendor v ON (i.vendor_id->>'value')::uuid = v.id
    LEFT JOIN icap_document d ON i.document_id = d.id
    """
    
    # Validate without fixing
    print("=" * 80)
    print("VALIDATION RESULTS (without auto-fix):")
    print("=" * 80)
    result = validate_sql(test_query, auto_fix=False)
    print(f"Valid: {result['is_valid']}")
    print(f"\nIssues found: {len(result['issues'])}")
    for issue in result['issues']:
        print(f"\n  [{issue['severity'].upper()}] {issue['rule']}")
        print(f"  Message: {issue['message']}")
        print(f"  Location: {issue['location']}")
        print(f"  Suggestion: {issue['suggestion']}")
    
    # Validate with auto-fix
    print("\n" + "=" * 80)
    print("VALIDATION RESULTS (with auto-fix):")
    print("=" * 80)
    result = validate_sql(test_query, auto_fix=True)
    print(f"Valid: {result['is_valid']}")
    print(f"\nFixes applied: {len(result['fixes_applied'])}")
    for fix in result['fixes_applied']:
        print(f"  ✓ {fix}")
    
    print("\n" + "=" * 80)
    print("FIXED QUERY:")
    print("=" * 80)
    print(result['fixed_query'])
