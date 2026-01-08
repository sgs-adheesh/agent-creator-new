# Defensive SQL Documentation

This directory contains comprehensive documentation for writing robust SQL queries against the ICAP invoice system.

## 📚 Documentation Files

### 1. [DEFENSIVE_SQL_RULES.md](./DEFENSIVE_SQL_RULES.md)
**Complete guide** to the 4 golden rules of defensive SQL coding.

- Detailed explanations of each rule
- Why AI-generated queries fail vs. why agent templates succeed
- Complete examples with before/after comparisons
- Common pitfalls and how to avoid them
- Testing guidelines for edge cases
- Version history

**Use this when**: You need to understand the reasoning behind defensive SQL patterns.

---

### 2. [DEFENSIVE_SQL_QUICK_REF.md](./DEFENSIVE_SQL_QUICK_REF.md)
**Quick reference card** for developers and AI.

- The 4 golden rules in concise format
- Pattern cheat sheet
- Common mistakes table
- Complete example template
- AI prompt template

**Use this when**: You need a quick reminder of the correct patterns.

---

### 3. [DEFENSIVE_SQL_IMPLEMENTATION.md](./DEFENSIVE_SQL_IMPLEMENTATION.md)
**Implementation summary** of the defensive SQL system.

- What was changed in the codebase
- Impact on agent templates
- How AI will use these rules
- Testing recommendations
- Next steps

**Use this when**: You need to understand what was implemented and what needs to be done next.

---

## 🎯 Quick Start

### For Developers

1. **Read**: [DEFENSIVE_SQL_QUICK_REF.md](./DEFENSIVE_SQL_QUICK_REF.md)
2. **Reference**: Keep the quick reference open while writing queries
3. **Deep Dive**: Read [DEFENSIVE_SQL_RULES.md](./DEFENSIVE_SQL_RULES.md) for complete understanding

### For AI Systems

Use this prompt when generating SQL queries:

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

See backend/docs/DEFENSIVE_SQL_QUICK_REF.md for complete patterns.
```

---

## 🔴 The 4 Golden Rules (Summary)

### 1️⃣ Defensive Join Pattern
```sql
LEFT JOIN table ON NULLIF(field->>'value', '') IS NOT NULL 
                AND (field->>'value')::uuid = table.id
```

### 2️⃣ Safe Numeric Pattern
```sql
NULLIF(field->>'value', '')::numeric
```

### 3️⃣ Date Handling Pattern
```sql
TO_DATE(field->>'value', 'MM/DD/YYYY')
```

### 4️⃣ Always Include Document Join
```sql
INNER JOIN icap_document d ON invoice.document_id = d.id
```

---

## 📋 Pattern Cheat Sheet

| Field Type | Pattern |
|------------|---------|
| Text | `(field->>'value')::text` |
| Numeric | `NULLIF(field->>'value', '')::numeric` |
| Date | `TO_DATE(field->>'value', 'MM/DD/YYYY')` |
| UUID Join | `NULLIF(field->>'value', '') IS NOT NULL AND (field->>'value')::uuid = table.id` |
| Date Aging | `CURRENT_DATE - TO_DATE(field->>'value', 'MM/DD/YYYY')` |

---

## 🚀 Complete Example

```sql
SELECT 
    -- Rule 4: Document join
    d.batch_name,
    
    -- JSONB text
    (inv.invoice_number->>'value')::text AS invoice_number,
    
    -- Rule 3: Date handling
    TO_DATE(inv.invoice_date->>'value', 'MM/DD/YYYY') AS invoice_date,
    TO_DATE(inv.due_date->>'value', 'MM/DD/YYYY') AS due_date,
    CURRENT_DATE - TO_DATE(inv.due_date->>'value', 'MM/DD/YYYY') AS days_overdue,
    
    -- Rule 2: Safe numeric
    NULLIF(inv.total->>'value', '')::numeric AS total_amount,
    
    -- Vendor
    v.name AS vendor_name
    
FROM icap_invoice inv
INNER JOIN icap_document d ON inv.document_id = d.id
LEFT JOIN icap_vendor v ON inv.vendor_id = v.id

-- Rule 1: Defensive join
LEFT JOIN icap_invoice_detail detail ON detail.document_id = inv.document_id
LEFT JOIN icap_product_master prod 
    ON NULLIF(detail.product_id->>'value', '') IS NOT NULL 
    AND (detail.product_id->>'value')::uuid = prod.id

WHERE NULLIF(inv.balance_amount->>'value', '')::numeric > 0
ORDER BY d.batch_name, days_overdue DESC;
```

---

## 📖 Additional Resources

- **PostgreSQL Connector**: `backend/tools/postgres_connector.py` - See the tool description for inline guidance
- **Agent Templates**: `backend/templates/agent_templates.json` - Examples of queries following these patterns
- **Schema Inspection**: Use `postgres_inspect_schema` tool to get defensive SQL examples for any table

---

## 🔄 Version History

- **v1.0** (2026-01-08): Initial defensive SQL rules implementation
  - Added 4 Golden Rules
  - Updated PostgreSQL connector with defensive patterns
  - Created comprehensive documentation
  - Added TO_DATE pattern for MM/DD/YYYY dates

---

## 📞 Support

For questions or issues:
1. Check the [Quick Reference](./DEFENSIVE_SQL_QUICK_REF.md)
2. Read the [Complete Rules](./DEFENSIVE_SQL_RULES.md)
3. Review the [Implementation Summary](./DEFENSIVE_SQL_IMPLEMENTATION.md)
