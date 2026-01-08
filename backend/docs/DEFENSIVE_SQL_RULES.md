# Defensive SQL Coding Rules for ICAP Invoice System

## Overview
This document outlines the **4 Golden Rules** for writing robust, error-free SQL queries against the ICAP invoice database. These rules ensure queries handle messy OCR data gracefully and prevent execution errors.

---

## The Problem: AI vs Agent Template Queries

### Why AI-Generated Queries Fail
- **Assumption**: Data is clean and complete
- **Reality**: OCR data contains empty strings, missing values, and inconsistent formats
- **Result**: Runtime errors from invalid casts and missing data

### Why Agent Templates Succeed
- **Assumption**: Data is messy and incomplete
- **Approach**: Defensive coding with validation at every step
- **Result**: Robust queries that handle edge cases gracefully

---

## The 4 Golden Rules

### Rule 1: The "Defensive Join" Pattern

**Problem**: Casting JSONB fields to UUID or Numeric directly in JOIN/WHERE clauses crashes on empty strings.

**❌ BAD (Crashes on empty strings)**:
```sql
LEFT JOIN icap_product_master prod 
  ON (detail.product_id->>'value')::uuid = prod.id
```

**✅ GOOD (Validates data first)**:
```sql
LEFT JOIN icap_product_master prod 
  ON NULLIF(detail.product_id->>'value', '') IS NOT NULL 
  AND (detail.product_id->>'value')::uuid = prod.id
```

**Why It Works**:
- `NULLIF(field, '')` converts empty strings to NULL
- NULL check prevents casting empty strings
- JOIN only executes when data is valid

---

### Rule 2: The "Safe Numeric" Pattern

**Problem**: OCR data often contains empty strings `''` instead of NULL. Casting `''` to numeric causes errors.

**❌ BAD (Crashes on empty strings)**:
```sql
SELECT (invoice.total->>'value')::numeric AS total
```

**✅ GOOD (Handles empty strings)**:
```sql
SELECT NULLIF(invoice.total->>'value', '')::numeric AS total
```

**Alternative (with default value)**:
```sql
SELECT COALESCE(NULLIF(invoice.total->>'value', '')::numeric, 0) AS total
```

**Why It Works**:
- `NULLIF(field, '')` converts empty strings to NULL
- NULL can be safely cast to numeric (returns NULL)
- `COALESCE` provides a fallback value if needed

---

### Rule 3: The "Date Aging" Calculation Pattern

**Problem**: PostgreSQL cannot subtract a string from a date. JSONB values must be cast to date type using the correct format.

**Date Format**: All dates in ICAP are stored as **MM/DD/YYYY** strings in JSONB.

**❌ BAD (Wrong - uses simple cast)**:
```sql
SELECT CURRENT_DATE - (invoice.due_date->>'value')::date AS days_overdue
```

**❌ BAD (Wrong - treats as string)**:
```sql
SELECT CURRENT_DATE - invoice.due_date->>'value' AS days_overdue
```

**✅ GOOD (Uses TO_DATE with correct format)**:
```sql
SELECT CURRENT_DATE - TO_DATE(invoice.due_date->>'value', 'MM/DD/YYYY') AS days_overdue
```

**Date Comparison Example**:
```sql
-- Filtering by date range
WHERE TO_DATE(invoice.invoice_date->>'value', 'MM/DD/YYYY') 
  BETWEEN TO_DATE('01/01/2024', 'MM/DD/YYYY') 
  AND TO_DATE('12/31/2024', 'MM/DD/YYYY')

-- Age bucket calculation
CASE 
  WHEN CURRENT_DATE - TO_DATE(invoice.due_date->>'value', 'MM/DD/YYYY') <= 30 
    THEN '0-30 days'
  WHEN CURRENT_DATE - TO_DATE(invoice.due_date->>'value', 'MM/DD/YYYY') <= 60 
    THEN '31-60 days'
  ELSE '90+ days'
END AS age_bucket
```

**Why It Works**:
- `TO_DATE(value, 'MM/DD/YYYY')` explicitly parses the date format
- Avoids locale-dependent parsing issues
- Handles date arithmetic correctly

---

### Rule 4: Always Include the Document Join

**Problem**: The `batch_name` field lives in `icap_document`, not `icap_invoice`. Forgetting this join means missing critical context.

**❌ BAD (Missing batch_name)**:
```sql
SELECT 
  (i.invoice_number->>'value')::text AS invoice_number,
  v.name AS vendor_name
FROM icap_invoice i
LEFT JOIN icap_vendor v ON i.vendor_id = v.id
```

**✅ GOOD (Includes document join)**:
```sql
SELECT 
  d.batch_name,
  (i.invoice_number->>'value')::text AS invoice_number,
  v.name AS vendor_name
FROM icap_invoice i
INNER JOIN icap_document d ON i.document_id = d.id
LEFT JOIN icap_vendor v ON i.vendor_id = v.id
```

**Why It Matters**:
- `batch_name` provides essential context for invoice grouping
- `status` and `sub_status` fields are in `icap_document`
- `accuracy` scores are in `icap_document`

---

## Complete Example: Aging Report with All Rules Applied

```sql
SELECT 
    -- Rule 4: Always include document join for batch_name
    d.batch_name,
    
    -- JSONB extraction (always use ->> 'value')
    (inv.invoice_number->>'value')::text AS invoice_number,
    
    -- Rule 3: Use TO_DATE for date formatting
    TO_DATE(inv.invoice_date->>'value', 'MM/DD/YYYY') AS formatted_invoice_date,
    TO_DATE(inv.due_date->>'value', 'MM/DD/YYYY') AS formatted_due_date,
    
    -- Rule 3: Date aging calculation
    CURRENT_DATE - TO_DATE(inv.due_date->>'value', 'MM/DD/YYYY') AS days_overdue,
    
    -- Age bucket with date calculation
    CASE 
        WHEN CURRENT_DATE - TO_DATE(inv.due_date->>'value', 'MM/DD/YYYY') <= 30 
            THEN '0-30 days'
        WHEN CURRENT_DATE - TO_DATE(inv.due_date->>'value', 'MM/DD/YYYY') <= 60 
            THEN '31-60 days'
        ELSE '90+ days'
    END AS age_bucket,
    
    -- Rule 2: Safe numeric casting
    NULLIF(inv.total->>'value', '')::numeric AS total_amount,
    
    -- Vendor information
    v.name AS vendor_name
    
FROM icap_invoice inv

-- Rule 4: INNER JOIN with document for batch_name
INNER JOIN icap_document d ON inv.document_id = d.id

-- Regular LEFT JOIN for vendor
LEFT JOIN icap_vendor v ON inv.vendor_id = v.id

-- Rule 2: Safe numeric filtering
WHERE NULLIF(inv.balance_amount->>'value', '')::numeric > 0

ORDER BY d.batch_name, days_overdue DESC;
```

---

## System Prompt for AI Query Generation

When asking an AI to write a query for the ICAP system, use this instruction:

```
Use the icap_invoice table as the base. Always join icap_document on document_id to include batch_name. 

For all JSONB fields, use ->>'value' to extract text. 

Apply these defensive patterns:
1. Defensive Join: Use NULLIF(..., '') IS NOT NULL before casting UUIDs in JOINs
2. Safe Numeric: Use NULLIF(..., '')::numeric for money fields
3. Date Handling: Use TO_DATE(field->>'value', 'MM/DD/YYYY') for all date operations
4. Document Join: Always INNER JOIN icap_document d ON invoice.document_id = d.id

This prevents execution errors on empty strings and missing data.
```

---

## Quick Reference Table

| Pattern | Bad ❌ | Good ✅ |
|---------|--------|---------|
| **UUID Join** | `ON (field->>'value')::uuid = table.id` | `ON NULLIF(field->>'value', '') IS NOT NULL AND (field->>'value')::uuid = table.id` |
| **Numeric Cast** | `(field->>'value')::numeric` | `NULLIF(field->>'value', '')::numeric` |
| **Date Format** | `(field->>'value')::date` | `TO_DATE(field->>'value', 'MM/DD/YYYY')` |
| **Date Aging** | `CURRENT_DATE - field->>'value'` | `CURRENT_DATE - TO_DATE(field->>'value', 'MM/DD/YYYY')` |
| **Document Join** | *(missing)* | `INNER JOIN icap_document d ON i.document_id = d.id` |

---

## Common Pitfalls to Avoid

### ❌ Don't hardcode values
```sql
-- Bad: Hardcoded table names or column names
SELECT invoice_number FROM invoices WHERE total > 1000
```

### ❌ Don't assume data exists
```sql
-- Bad: Direct cast without validation
SELECT (total->>'value')::numeric FROM icap_invoice
```

### ❌ Don't use simple date casts
```sql
-- Bad: Locale-dependent parsing
SELECT (invoice_date->>'value')::date FROM icap_invoice
```

### ✅ Do validate and use defensive patterns
```sql
-- Good: Defensive coding
SELECT 
  NULLIF(total->>'value', '')::numeric AS total,
  TO_DATE(invoice_date->>'value', 'MM/DD/YYYY') AS invoice_date
FROM icap_invoice
WHERE NULLIF(total->>'value', '') IS NOT NULL
```

---

## Testing Your Queries

Before deploying a query, test it with these edge cases:

1. **Empty JSONB values**: `{"value": "", "confidence": 0.0}`
2. **NULL JSONB values**: `{"value": null, "confidence": 0.0}`
3. **Missing JSONB keys**: `{"confidence": 0.95}` (no "value" key)
4. **Invalid UUIDs**: `{"value": "not-a-uuid"}`
5. **Invalid dates**: `{"value": "13/45/2024"}`
6. **Invalid numbers**: `{"value": "abc123"}`

Your query should either:
- Handle these gracefully (return NULL or skip the row)
- Or provide a clear, actionable error message

---

## Version History

- **v1.0** (2026-01-08): Initial defensive SQL rules documentation
- Added 4 Golden Rules
- Added TO_DATE pattern for MM/DD/YYYY dates
- Added complete aging report example
