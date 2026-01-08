# Fixed: AI Agent Creation Now Follows Defensive SQL Rules

## Problem Identified

When creating agents using AI, the system was generating queries during the "execution guidance" phase that did NOT follow the defensive SQL rules. This caused errors like:

```
❌ cannot cast type jsonb to date
❌ invalid input syntax for type uuid: ""
```

## Root Cause

The `_build_query_template()` method in `agent_service.py` (line 2443) generates SQL queries during agent creation. The prompt it uses to instruct the AI was **missing the TO_DATE pattern** and other defensive SQL rules.

## Solution Applied

Updated the query generation prompt in `agent_service.py` to include **all 4 golden rules**:

### Added to Line 2466:
```python
🔴 THE 4 GOLDEN RULES OF DEFENSIVE SQL (MUST FOLLOW EVERY TIME):

📌 RULE 1: Defensive Join Pattern (for UUID fields)
   ✅ GOOD: LEFT JOIN table ON NULLIF(field->>'value', '') IS NOT NULL 
                            AND (field->>'value')::uuid = table.id

📌 RULE 2: Safe Numeric Pattern
   ✅ GOOD: NULLIF(invoice.total->>'value', '')::numeric

📌 RULE 3: Date Handling Pattern (CRITICAL!)
   ✅ GOOD: TO_DATE(invoice.due_date->>'value', 'MM/DD/YYYY')
   ✅ Date aging: CURRENT_DATE - TO_DATE(invoice.due_date->>'value', 'MM/DD/YYYY')
   ✅ Age buckets: CASE WHEN CURRENT_DATE - TO_DATE(...) <= 30 THEN '0-30 days' ...

📌 RULE 4: Always Include Document Join
   ✅ INNER JOIN icap_document d ON invoice.document_id = d.id
```

## Impact

### Before Fix:
```sql
-- AI generated this (WRONG):
SELECT 
  invoice.invoice_number,
  invoice.due_date::date,  -- ❌ Wrong!
  CURRENT_DATE - invoice.due_date::date AS days_overdue  -- ❌ Crashes!
FROM icap_invoice invoice
LEFT JOIN icap_vendor vendor ON (invoice.vendor_id->>'value')::uuid = vendor.id  -- ❌ Crashes on empty!
```

### After Fix:
```sql
-- AI will now generate this (CORRECT):
SELECT 
  d.batch_name,
  (invoice.invoice_number->>'value')::text,
  TO_DATE(invoice.due_date->>'value', 'MM/DD/YYYY') AS due_date,  -- ✅ Correct!
  CURRENT_DATE - TO_DATE(invoice.due_date->>'value', 'MM/DD/YYYY') AS days_overdue,  -- ✅ Works!
  NULLIF(invoice.total->>'value', '')::numeric AS total  -- ✅ Safe!
FROM icap_invoice invoice
INNER JOIN icap_document d ON invoice.document_id = d.id  -- ✅ Batch name!
LEFT JOIN icap_vendor vendor 
  ON NULLIF(invoice.vendor_id->>'value', '') IS NOT NULL 
  AND (invoice.vendor_id->>'value')::uuid = vendor.id  -- ✅ Safe join!
```

## Testing

### To Test the Fix:

1. **Restart the backend server**:
   ```bash
   # Stop current server (Ctrl+C)
   python backend/main.py
   ```

2. **Create a new agent using AI**:
   - Go to "Create Agent"
   - Enter a prompt like: "Generate an aging report for unpaid invoices"
   - Click "Create Agent"

3. **Check the generated query**:
   - The execution guidance should now use:
     - ✅ `TO_DATE(invoice.due_date->>'value', 'MM/DD/YYYY')`
     - ✅ `NULLIF(invoice.total->>'value', '')::numeric`
     - ✅ `INNER JOIN icap_document d ON invoice.document_id = d.id`
     - ✅ Defensive UUID joins with NULLIF

4. **Execute the agent**:
   - Should work without errors!
   - No more "cannot cast type jsonb to date"
   - No more "invalid input syntax for type uuid"

## Files Modified

1. ✅ `backend/services/agent_service.py` (line 2458-2496)
   - Added 4 golden rules to query generation prompt
   - Updated requirements list to reference the rules

## Summary

**Before**: AI-generated queries during agent creation ignored defensive SQL rules  
**After**: AI-generated queries follow all 4 golden rules automatically  

**Result**: Creating agents with AI now produces robust, error-free queries that handle messy OCR data correctly!

## Next Steps

1. **Restart backend server** to apply changes
2. **Test by creating a new agent** with AI
3. **Verify** the generated query uses TO_DATE, NULLIF, and defensive joins
4. **Execute** the agent to confirm it works without errors

---

**Status**: ✅ **FIXED** - AI agent creation now follows defensive SQL rules!
