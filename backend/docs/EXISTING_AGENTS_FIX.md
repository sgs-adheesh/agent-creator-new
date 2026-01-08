# Quick Fix: Clear Execution Guidance from Existing Agents

## Problem

Existing agents have **old execution guidance** generated before the defensive SQL fixes were applied. This guidance contains broken queries that don't follow the defensive SQL rules.

## Solution

You have 2 options:

### Option 1: Delete and Recreate the Agent (Recommended)

1. **Delete the existing agent**
2. **Create a new agent** with the same prompt
3. The new agent will generate correct execution guidance

### Option 2: Clear Execution Guidance (Forces Regeneration)

The agent JSON stores the execution guidance in the `execution_guidance` field. You can clear it to force regeneration.

**Manual Method**:
1. Find your agent in the database or JSON storage
2. Remove or set `execution_guidance` to `null`
3. Next execution will regenerate it with defensive SQL

**API Method** (if available):
```bash
# Update agent to clear execution guidance
curl -X PATCH http://localhost:8000/api/agents/{agent_id} \
  -H "Content-Type: application/json" \
  -d '{"execution_guidance": null}'
```

---

## Why This Happened

The execution guidance is generated **once** during agent creation and **cached** for performance. When you updated the defensive SQL rules, existing agents still had the old guidance.

### Timeline:
1. ✅ You created an agent → Generated execution guidance (without defensive SQL)
2. ✅ We fixed the code → Added defensive SQL to generation
3. ❌ You ran the old agent → Used cached old guidance (broken!)
4. ✅ Solution → Delete agent and recreate OR clear cached guidance

---

## How to Identify Affected Agents

Agents created **before** the defensive SQL fixes will have broken execution guidance.

**Check the agent's execution guidance**:
- If it contains `invoice.vendor_id->>'value'` → **BROKEN** (vendor_id is UUID, not JSONB)
- If it contains `invoice.due_date::date` → **BROKEN** (should use TO_DATE)
- If it contains direct `::numeric` without NULLIF → **BROKEN**

**Agents created AFTER the fix** will have correct guidance automatically.

---

## Prevention

Going forward, all new agents will have correct execution guidance because:
1. ✅ `_build_query_template()` now includes defensive SQL rules
2. ✅ Query correction includes defensive SQL rules
3. ✅ Tool descriptions include defensive SQL rules

---

## Quick Action

**For your current agent**:

1. **Go to the agent list**
2. **Delete the "Invoice Aging Report" agent**
3. **Create a new agent** with the same prompt:
   ```
   "Generate an aging report for unpaid invoices, categorizing them by age"
   ```
4. **Execute the new agent** → Should work perfectly!

---

## Alternative: Force Regeneration on Next Run

If you don't want to delete the agent, you can modify the code to detect and regenerate old execution guidance.

**Add this check** in `agent_service.py` before using execution guidance:

```python
# Check if execution guidance needs regeneration
if execution_guidance:
    # Check for old patterns that indicate outdated guidance
    query_template = execution_guidance.get('query_template', {})
    base_query = query_template.get('base_query', '')
    
    # Detect old patterns
    needs_regeneration = (
        '::date' in base_query or  # Old date pattern
        "->>'value')::numeric" in base_query or  # Old numeric pattern (missing NULLIF)
        "vendor_id->>'value'" in base_query  # Wrong - vendor_id is UUID, not JSONB
    )
    
    if needs_regeneration:
        logger.warning("Detected outdated execution guidance, regenerating...")
        execution_guidance = None  # Force regeneration
```

---

## Summary

✅ **Root Cause**: Existing agents have cached old execution guidance  
✅ **Quick Fix**: Delete and recreate the agent  
✅ **Long-term**: All new agents will be correct  
✅ **Prevention**: Code now generates correct guidance for all new agents  

**Action**: Delete the current agent and create a new one with the same prompt!
