# Defensive SQL Quick Reference Card

## 🔴 THE 4 GOLDEN RULES - Always Apply These!

### 1️⃣ Defensive Join Pattern (UUID fields)
```sql
-- ❌ BAD - Crashes on empty strings
LEFT JOIN icap_product_master prod 
  ON (detail.product_id->>'value')::uuid = prod.id

-- ✅ GOOD - Validates first
LEFT JOIN icap_product_master prod 
  ON NULLIF(detail.product_id->>'value', '') IS NOT NULL 
  AND (detail.product_id->>'value')::uuid = prod.id
```

### 2️⃣ Safe Numeric Pattern
```sql
-- ❌ BAD - Crashes on empty strings
SELECT (invoice.total->>'value')::numeric

-- ✅ GOOD - Handles empty strings
SELECT NULLIF(invoice.total->>'value', '')::numeric

-- ✅ BETTER - With default value
SELECT COALESCE(NULLIF(invoice.total->>'value', '')::numeric, 0)
```

### 3️⃣ Date Handling Pattern (MM/DD/YYYY)
```sql
-- ❌ BAD - Wrong format
SELECT (invoice.due_date->>'value')::date

-- ✅ GOOD - Correct format
SELECT TO_DATE(invoice.due_date->>'value', 'MM/DD/YYYY')

-- ✅ Date aging
SELECT CURRENT_DATE - TO_DATE(invoice.due_date->>'value', 'MM/DD/YYYY') AS days_overdue

-- ✅ Date filtering
WHERE TO_DATE(invoice.invoice_date->>'value', 'MM/DD/YYYY') 
  BETWEEN TO_DATE('01/01/2024', 'MM/DD/YYYY') 
  AND TO_DATE('12/31/2024', 'MM/DD/YYYY')

-- ✅ Age buckets
CASE 
  WHEN CURRENT_DATE - TO_DATE(invoice.due_date->>'value', 'MM/DD/YYYY') <= 30 
    THEN '0-30 days'
  WHEN CURRENT_DATE - TO_DATE(invoice.due_date->>'value', 'MM/DD/YYYY') <= 60 
    THEN '31-60 days'
  ELSE '90+ days'
END AS age_bucket
```

### 4️⃣ Always Include Document Join
```sql
-- ❌ BAD - Missing batch_name
SELECT 
  (i.invoice_number->>'value')::text
FROM icap_invoice i

-- ✅ GOOD - Includes batch_name
SELECT 
  d.batch_name,
  (i.invoice_number->>'value')::text
FROM icap_invoice i
INNER JOIN icap_document d ON i.document_id = d.id
```

---

## 📋 Pattern Cheat Sheet

| Field Type | Pattern | Example |
|------------|---------|---------|
| **Text** | `(field->>'value')::text` | `(invoice_number->>'value')::text` |
| **Numeric** | `NULLIF(field->>'value', '')::numeric` | `NULLIF(total->>'value', '')::numeric` |
| **Date** | `TO_DATE(field->>'value', 'MM/DD/YYYY')` | `TO_DATE(invoice_date->>'value', 'MM/DD/YYYY')` |
| **UUID Join** | `NULLIF(field->>'value', '') IS NOT NULL AND (field->>'value')::uuid = table.id` | See Rule 1 |
| **Date Aging** | `CURRENT_DATE - TO_DATE(field->>'value', 'MM/DD/YYYY')` | See Rule 3 |

---

## ⚡ Common Mistakes to Avoid

| ❌ Don't Do This | ✅ Do This Instead |
|------------------|-------------------|
| `(field->>'value')::int` | `NULLIF(field->>'value', '')::numeric` |
| `(field->>'value')::date` | `TO_DATE(field->>'value', 'MM/DD/YYYY')` |
| `(field->>'value')::uuid = table.id` | `NULLIF(field->>'value', '') IS NOT NULL AND (field->>'value')::uuid = table.id` |
| Missing document join | `INNER JOIN icap_document d ON i.document_id = d.id` |
| `WHERE field->>'value' LIKE '01/%/2024'` | `WHERE TO_DATE(field->>'value', 'MM/DD/YYYY') BETWEEN ...` |

---

## 🎯 Complete Example Template

```sql
SELECT 
    -- Rule 4: Document join for batch_name
    d.batch_name,
    d.status,
    d.sub_status,
    
    -- JSONB text extraction
    (inv.invoice_number->>'value')::text AS invoice_number,
    
    -- Rule 3: Date handling
    TO_DATE(inv.invoice_date->>'value', 'MM/DD/YYYY') AS invoice_date,
    TO_DATE(inv.due_date->>'value', 'MM/DD/YYYY') AS due_date,
    
    -- Rule 3: Date aging
    CURRENT_DATE - TO_DATE(inv.due_date->>'value', 'MM/DD/YYYY') AS days_overdue,
    
    -- Rule 3: Age bucket
    CASE 
        WHEN CURRENT_DATE - TO_DATE(inv.due_date->>'value', 'MM/DD/YYYY') <= 30 
            THEN '0-30 days'
        WHEN CURRENT_DATE - TO_DATE(inv.due_date->>'value', 'MM/DD/YYYY') <= 60 
            THEN '31-60 days'
        ELSE '90+ days'
    END AS age_bucket,
    
    -- Rule 2: Safe numeric
    NULLIF(inv.total->>'value', '')::numeric AS total_amount,
    NULLIF(inv.balance_amount->>'value', '')::numeric AS balance_due,
    
    -- Vendor info
    v.name AS vendor_name,
    v.email AS vendor_email

FROM icap_invoice inv

-- Rule 4: INNER JOIN with document
INNER JOIN icap_document d ON inv.document_id = d.id

-- Regular LEFT JOIN
LEFT JOIN icap_vendor v ON inv.vendor_id = v.id

-- Rule 1: Defensive join with product (if needed)
LEFT JOIN icap_invoice_detail detail ON detail.document_id = inv.document_id
LEFT JOIN icap_product_master prod 
    ON NULLIF(detail.product_id->>'value', '') IS NOT NULL 
    AND (detail.product_id->>'value')::uuid = prod.id

-- Rule 2: Safe numeric filtering
WHERE NULLIF(inv.balance_amount->>'value', '')::numeric > 0

ORDER BY d.batch_name, days_overdue DESC;
```

---

## 🚀 AI Prompt Template

When asking AI to generate a query, use this prompt:

```
Generate a SQL query for the ICAP invoice system following these defensive coding rules:

1. Defensive Join: Use NULLIF(..., '') IS NOT NULL before casting UUIDs in JOINs
2. Safe Numeric: Use NULLIF(..., '')::numeric for all money/number fields
3. Date Handling: Use TO_DATE(field->>'value', 'MM/DD/YYYY') for all date operations
4. Document Join: Always INNER JOIN icap_document d ON invoice.document_id = d.id

All JSONB fields use ->>'value' to extract text.
Dates are stored as MM/DD/YYYY strings.
Never use ::int (use ::numeric instead).
Never use simple ::date (use TO_DATE instead).

This prevents execution errors on empty strings and missing data.
```

---

## 📚 Full Documentation

See `DEFENSIVE_SQL_RULES.md` for complete documentation with examples and explanations.
