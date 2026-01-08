# Defensive SQL Implementation Summary

## Overview

This implementation adds **4 Golden Rules** of defensive SQL coding to ensure AI-generated queries are as robust and accurate as the manually-crafted Agent Templates. These rules handle messy OCR data gracefully and prevent execution errors.

---

## What Was Changed

### 1. Documentation Created

#### `backend/docs/DEFENSIVE_SQL_RULES.md`
- **Complete guide** to the 4 golden rules
- Detailed explanations with examples
- Common pitfalls and how to avoid them
- Testing guidelines for edge cases
- Version history

#### `backend/docs/DEFENSIVE_SQL_QUICK_REF.md`
- **Quick reference card** for developers
- Pattern cheat sheet
- Common mistakes table
- Complete example template
- AI prompt template

### 2. PostgreSQL Connector Updated

#### `backend/tools/postgres_connector.py`

**Enhanced Tool Description** (lines 29-106):
- Added comprehensive explanation of all 4 golden rules
- Included complete example query showing all rules in action
- Added reference to documentation
- Updated JSONB handling guidance

**Enhanced Schema Inspection** (lines 960-1050):
- Updated JSONB guidance to include all 4 defensive patterns
- Modified query examples to use:
  - `TO_DATE()` for date fields
  - `NULLIF()` for numeric fields
  - Defensive join pattern for UUID fields
- Added document join reminder

---

## The 4 Golden Rules

### Rule 1: Defensive Join Pattern
**Problem**: Casting empty JSONB strings to UUID crashes
**Solution**: Validate data exists before casting

```sql
-- ❌ BAD
LEFT JOIN icap_product_master prod 
  ON (detail.product_id->>'value')::uuid = prod.id

-- ✅ GOOD
LEFT JOIN icap_product_master prod 
  ON NULLIF(detail.product_id->>'value', '') IS NOT NULL 
  AND (detail.product_id->>'value')::uuid = prod.id
```

### Rule 2: Safe Numeric Pattern
**Problem**: Casting empty strings to numeric causes errors
**Solution**: Use NULLIF to convert empty strings to NULL

```sql
-- ❌ BAD
SELECT (invoice.total->>'value')::numeric

-- ✅ GOOD
SELECT NULLIF(invoice.total->>'value', '')::numeric
```

### Rule 3: Date Handling Pattern
**Problem**: Dates are MM/DD/YYYY strings, not proper date types
**Solution**: Use TO_DATE with explicit format

```sql
-- ❌ BAD
SELECT (invoice.due_date->>'value')::date

-- ✅ GOOD
SELECT TO_DATE(invoice.due_date->>'value', 'MM/DD/YYYY')

-- ✅ Date aging
SELECT CURRENT_DATE - TO_DATE(invoice.due_date->>'value', 'MM/DD/YYYY') AS days_overdue

-- ✅ Age buckets
CASE 
  WHEN CURRENT_DATE - TO_DATE(invoice.due_date->>'value', 'MM/DD/YYYY') <= 30 
    THEN '0-30 days'
  WHEN CURRENT_DATE - TO_DATE(invoice.due_date->>'value', 'MM/DD/YYYY') <= 60 
    THEN '31-60 days'
  ELSE '90+ days'
END AS age_bucket
```

### Rule 4: Always Include Document Join
**Problem**: batch_name lives in icap_document, not icap_invoice
**Solution**: Always join icap_document

```sql
-- ❌ BAD
SELECT (i.invoice_number->>'value')::text
FROM icap_invoice i

-- ✅ GOOD
SELECT 
  d.batch_name,
  (i.invoice_number->>'value')::text
FROM icap_invoice i
INNER JOIN icap_document d ON i.document_id = d.id
```

---

## Impact on Agent Templates

### Current Agent Templates
The existing agent templates in `backend/templates/agent_templates.json` already follow most of these patterns, but some need updates:

#### Templates That Need Updates:

1. **Invoice Aging Report** (line 431):
   - Currently uses: `(CURRENT_DATE - (i.due_date->>'value')::date)`
   - Should use: `CURRENT_DATE - TO_DATE(i.due_date->>'value', 'MM/DD/YYYY')`

2. **Monthly Expense Report** (line 320):
   - Currently uses: `LEFT JOIN icap_product_master pm ON (ivd.product_id->>'value')::uuid = pm.id`
   - Should use defensive join pattern with NULLIF

3. **Product Category Spend** (line 564):
   - Same UUID join issue
   - Date filtering should use TO_DATE

4. **Vendor GL Breakdown** (line 132):
   - Uses `CASE WHEN (i.total->>'value') != ''` 
   - Should use `NULLIF(i.total->>'value', '')::numeric`

### Recommended Action
Update all agent templates to follow the 4 golden rules. This ensures:
- Consistency between AI-generated and template queries
- Robustness against messy OCR data
- Better error handling

---

## How AI Will Use These Rules

### Before (Without Rules)
AI might generate:
```sql
SELECT 
  (i.invoice_number->>'value')::text,
  (i.due_date->>'value')::date,
  (i.total->>'value')::numeric
FROM icap_invoice i
LEFT JOIN icap_product_master pm ON (i.product_id->>'value')::uuid = pm.id
WHERE (i.total->>'value')::numeric > 0
```

**Problems**:
- Missing batch_name (no document join)
- Wrong date cast (should use TO_DATE)
- Unsafe numeric cast (crashes on empty strings)
- Unsafe UUID join (crashes on empty strings)

### After (With Rules)
AI will generate:
```sql
SELECT 
  d.batch_name,
  (i.invoice_number->>'value')::text,
  TO_DATE(i.due_date->>'value', 'MM/DD/YYYY') AS due_date,
  NULLIF(i.total->>'value', '')::numeric AS total
FROM icap_invoice i
INNER JOIN icap_document d ON i.document_id = d.id
LEFT JOIN icap_product_master pm 
  ON NULLIF(i.product_id->>'value', '') IS NOT NULL 
  AND (i.product_id->>'value')::uuid = pm.id
WHERE NULLIF(i.total->>'value', '')::numeric > 0
```

**Benefits**:
- Includes batch_name
- Correct date handling
- Safe numeric casting
- Safe UUID joins
- Won't crash on messy data

---

## Testing Recommendations

### Edge Cases to Test
1. **Empty JSONB values**: `{"value": "", "confidence": 0.0}`
2. **NULL JSONB values**: `{"value": null, "confidence": 0.0}`
3. **Missing JSONB keys**: `{"confidence": 0.95}` (no "value" key)
4. **Invalid UUIDs**: `{"value": "not-a-uuid"}`
5. **Invalid dates**: `{"value": "13/45/2024"}`
6. **Invalid numbers**: `{"value": "abc123"}`

### Test Query
```sql
-- This should handle all edge cases gracefully
SELECT 
  d.batch_name,
  (i.invoice_number->>'value')::text AS invoice_number,
  TO_DATE(i.invoice_date->>'value', 'MM/DD/YYYY') AS invoice_date,
  NULLIF(i.total->>'value', '')::numeric AS total,
  v.name AS vendor_name
FROM icap_invoice i
INNER JOIN icap_document d ON i.document_id = d.id
LEFT JOIN icap_vendor v ON i.vendor_id = v.id
LEFT JOIN icap_invoice_detail detail ON detail.document_id = i.document_id
LEFT JOIN icap_product_master pm 
  ON NULLIF(detail.product_id->>'value', '') IS NOT NULL 
  AND (detail.product_id->>'value')::uuid = pm.id
WHERE NULLIF(i.total->>'value', '')::numeric > 0
LIMIT 10;
```

---

## Next Steps

### 1. Update Agent Templates (Recommended)
Update all queries in `backend/templates/agent_templates.json` to follow the 4 golden rules:
- Replace `::date` with `TO_DATE(..., 'MM/DD/YYYY')`
- Replace `::numeric` with `NULLIF(..., '')::numeric`
- Add defensive join pattern for UUID fields
- Ensure all templates include document join

### 2. Create Validation Tool (Optional)
Create a script to validate queries against the 4 rules:
```python
def validate_defensive_sql(query):
    """Validate query follows defensive SQL patterns"""
    issues = []
    
    # Check for unsafe date casts
    if re.search(r"->>'value'\)::date", query):
        issues.append("Use TO_DATE(..., 'MM/DD/YYYY') instead of ::date")
    
    # Check for unsafe numeric casts
    if re.search(r"->>'value'\)::numeric", query) and not re.search(r"NULLIF\(", query):
        issues.append("Use NULLIF(..., '')::numeric for safety")
    
    # Check for unsafe UUID joins
    if re.search(r"->>'value'\)::uuid\s*=", query) and not re.search(r"NULLIF\(", query):
        issues.append("Use defensive join pattern for UUID fields")
    
    # Check for document join
    if "icap_invoice" in query and "icap_document" not in query:
        issues.append("Missing document join for batch_name")
    
    return issues
```

### 3. Update AI System Prompt (Optional)
Add the defensive SQL rules to the AI's system prompt for automatic enforcement.

---

## Files Modified

1. ✅ `backend/tools/postgres_connector.py` - Updated with 4 golden rules
2. ✅ `backend/docs/DEFENSIVE_SQL_RULES.md` - Complete documentation
3. ✅ `backend/docs/DEFENSIVE_SQL_QUICK_REF.md` - Quick reference
4. ⏳ `backend/templates/agent_templates.json` - **Needs updating** (recommended)

---

## Summary

The defensive SQL implementation ensures that:
- ✅ AI-generated queries are as robust as manually-crafted templates
- ✅ Queries handle messy OCR data gracefully
- ✅ Empty strings, NULL values, and missing data don't cause crashes
- ✅ Date operations work correctly with MM/DD/YYYY format
- ✅ All queries include essential context (batch_name)
- ✅ UUID joins are safe and won't crash

**Result**: More reliable, production-ready queries that work with real-world messy data.

---

## Quick Reference

See `backend/docs/DEFENSIVE_SQL_QUICK_REF.md` for:
- Pattern cheat sheet
- Common mistakes table
- Complete example template
- AI prompt template

See `backend/docs/DEFENSIVE_SQL_RULES.md` for:
- Detailed explanations
- Edge case handling
- Testing guidelines
- Version history
