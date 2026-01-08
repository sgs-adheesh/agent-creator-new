# SQL Validation During Agent Editing - Implementation Guide

## Overview

The defensive SQL validator is now available as an API endpoint that can be called during agent editing to validate and auto-fix queries in real-time.

## API Endpoints

### 1. Validate SQL Query

**Endpoint**: `POST /api/sql/validate`

**Request**:
```json
{
  "query": "SELECT ... FROM icap_invoice ...",
  "auto_fix": false
}
```

**Response**:
```json
{
  "is_valid": false,
  "issues": [
    {
      "rule": "Rule 3: Date Handling Pattern",
      "severity": "critical",
      "message": "Using ::date cast - will fail with MM/DD/YYYY format",
      "location": "(i.due_date->>'value')::date",
      "suggestion": "Use TO_DATE(field->>'value', 'MM/DD/YYYY')"
    }
  ],
  "fixes_applied": [],
  "fixed_query": null,
  "original_query": "..."
}
```

### 2. Auto-Fix SQL Query

**Endpoint**: `POST /api/sql/auto-fix`

**Request**:
```json
{
  "query": "SELECT ... FROM icap_invoice ..."
}
```

**Response**:
```json
{
  "success": true,
  "original_query": "...",
  "fixed_query": "...",
  "fixes_applied": [
    "Replaced ::date with TO_DATE for i.due_date",
    "Added NULLIF for numeric field i.total"
  ],
  "remaining_issues": []
}
```

---

## Integration Points

### Scenario 1: Real-Time Validation (Recommended)

**When**: User types in the query editor  
**How**: Call `/api/sql/validate` on debounced input (e.g., 500ms after user stops typing)

**Frontend Implementation**:
```javascript
// In your agent editor component
const [query, setQuery] = useState('');
const [validationIssues, setValidationIssues] = useState([]);

// Debounced validation
useEffect(() => {
  const timer = setTimeout(async () => {
    if (query) {
      const response = await fetch('/api/sql/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, auto_fix: false })
      });
      const result = await response.json();
      setValidationIssues(result.issues);
    }
  }, 500);
  
  return () => clearTimeout(timer);
}, [query]);

// Display issues in the UI
{validationIssues.map(issue => (
  <div className={`alert alert-${issue.severity}`}>
    <strong>{issue.rule}</strong>: {issue.message}
    <br />
    <small>Suggestion: {issue.suggestion}</small>
  </div>
))}
```

### Scenario 2: Save-Time Validation

**When**: User clicks "Save" button  
**How**: Call `/api/sql/validate` before saving

**Frontend Implementation**:
```javascript
const handleSave = async () => {
  // Validate before saving
  const response = await fetch('/api/sql/validate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, auto_fix: false })
  });
  
  const result = await response.json();
  
  if (!result.is_valid) {
    // Show warning dialog
    const shouldContinue = confirm(
      `Found ${result.issues.length} issues. Do you want to auto-fix them?`
    );
    
    if (shouldContinue) {
      // Auto-fix and use the fixed query
      const fixResponse = await fetch('/api/sql/auto-fix', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
      });
      
      const fixResult = await fixResponse.json();
      setQuery(fixResult.fixed_query);
      
      // Show what was fixed
      alert(`Applied ${fixResult.fixes_applied.length} fixes:\n${fixResult.fixes_applied.join('\n')}`);
    }
  }
  
  // Proceed with save
  await saveAgent({ ...agentData, query });
};
```

### Scenario 3: "Apply Defensive SQL" Button

**When**: User clicks a button to auto-fix their query  
**How**: Call `/api/sql/auto-fix`

**Frontend Implementation**:
```javascript
const handleApplyDefensiveSQL = async () => {
  const response = await fetch('/api/sql/auto-fix', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query })
  });
  
  const result = await response.json();
  
  if (result.success) {
    setQuery(result.fixed_query);
    
    // Show notification
    toast.success(
      `Applied ${result.fixes_applied.length} defensive SQL patterns!`,
      { description: result.fixes_applied.join(', ') }
    );
  }
};

// In your UI
<button onClick={handleApplyDefensiveSQL}>
  🛡️ Apply Defensive SQL Patterns
</button>
```

---

## Current Limitations & Next Steps

### ✅ What's Validated Now

1. **Rule 1**: UUID joins without NULLIF
2. **Rule 2**: Numeric casts without NULLIF
3. **Rule 3**: Date operations without TO_DATE
4. **Rule 4**: Missing document join

### ⚠️ What's NOT Validated Yet

1. **Column existence** - AI might reference columns that don't exist
2. **NULL handling completeness** - WHERE clause might miss NULL checks
3. **Table existence** - AI might reference non-existent tables

### 🔜 Recommended Enhancements

#### Enhancement 1: Schema-Aware Validation

Add column/table existence checking:

```python
def _check_column_existence(self, query: str, schema_cache: Dict) -> List[Dict]:
    """Check if referenced columns actually exist in the schema"""
    issues = []
    
    # Extract table.column references
    pattern = r"([a-z_]+)\.([a-z_]+)"
    matches = re.finditer(pattern, query, re.IGNORECASE)
    
    for match in matches:
        table_alias = match.group(1)
        column = match.group(2)
        
        # Resolve alias to actual table name
        actual_table = resolve_table_from_alias(query, table_alias)
        
        # Check if column exists
        if actual_table in schema_cache:
            columns = [col['name'] for col in schema_cache[actual_table]]
            if column not in columns:
                issues.append({
                    'rule': 'Schema Validation',
                    'severity': 'critical',
                    'message': f'Column {column} does not exist in table {actual_table}',
                    'location': f'{table_alias}.{column}',
                    'suggestion': f'Available columns: {", ".join(columns[:5])}'
                })
    
    return issues
```

#### Enhancement 2: NULL Handling Validation

Check for incomplete NULL handling:

```python
def _check_null_handling(self, query: str) -> List[Dict]:
    """Check if WHERE clauses properly handle NULL values"""
    issues = []
    
    # Pattern: WHERE field > 0 (without NULL check)
    pattern = r"WHERE\s+NULLIF\([^)]+\)::numeric\s*>\s*0"
    
    # Should also check for NULL/empty:
    # WHERE (field IS NULL OR field = '' OR NULLIF(field, '')::numeric > 0)
    
    if re.search(pattern, query, re.IGNORECASE):
        # Check if there's also a NULL check
        if "IS NULL" not in query.upper() and "= ''" not in query:
            issues.append({
                'rule': 'NULL Handling',
                'severity': 'medium',
                'message': 'WHERE clause might exclude NULL/empty values unintentionally',
                'location': 'WHERE clause',
                'suggestion': 'Add: (field IS NULL OR field = \'\' OR NULLIF(...) > 0)'
            })
    
    return issues
```

---

## Testing

### Test the Validator

```bash
# Test validation endpoint
curl -X POST http://localhost:8000/api/sql/validate \
  -H "Content-Type: application/json" \
  -d '{
    "query": "SELECT (i.due_date->>'\''value'\'')::date FROM icap_invoice i",
    "auto_fix": false
  }'

# Test auto-fix endpoint
curl -X POST http://localhost:8000/api/sql/auto-fix \
  -H "Content-Type: application/json" \
  -d '{
    "query": "SELECT (i.due_date->>'\''value'\'')::date FROM icap_invoice i"
  }'
```

---

## Summary

### ✅ Implemented

1. **Defensive SQL Validator** - Python class that validates all 4 rules
2. **API Endpoints** - `/api/sql/validate` and `/api/sql/auto-fix`
3. **Auto-fix Capability** - Automatically applies defensive SQL patterns

### 🔜 To Implement (Frontend)

1. **Real-time validation** in agent editor
2. **Save-time validation** before saving agents
3. **"Apply Defensive SQL" button** for one-click fixes

### 🎯 Next Steps

1. **Add API endpoints to main.py** (register the router)
2. **Integrate into frontend** agent editor
3. **Add schema-aware validation** (column existence checking)
4. **Add NULL handling validation** (complete WHERE clauses)

This will ensure defensive SQL rules are applied **during editing**, not just during execution!
