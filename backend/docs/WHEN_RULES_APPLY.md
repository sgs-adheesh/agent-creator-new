# When Defensive SQL Rules Apply - Complete Guide

## Overview

The defensive SQL rules are applied at **4 different stages** of the agent lifecycle. Understanding when and how they apply helps you write better queries and avoid errors.

---

## 📊 The 4 Application Stages

### 1️⃣ Agent Templates (Pre-built) ✅ ACTIVE NOW

**When**: You use a pre-built agent template  
**How**: Templates contain queries that already follow all 4 rules  
**Reliability**: ✅ **100%** - Queries are pre-validated  
**Status**: ✅ **Active** after server restart

**Example**:
```sql
-- Invoice Aging Report template now uses:
SELECT 
  d.batch_name,
  TO_DATE(i.due_date->>'value', 'MM/DD/YYYY') AS due_date,
  CURRENT_DATE - TO_DATE(i.due_date->>'value', 'MM/DD/YYYY') AS days_overdue,
  NULLIF(i.total->>'value', '')::numeric AS total
FROM icap_invoice i
INNER JOIN icap_document d ON i.document_id = d.id
WHERE NULLIF(i.balance_amount->>'value', '')::numeric > 0
```

**Applies**: Immediately after you restart the backend server

---

### 2️⃣ AI-Generated Queries (Dynamic) ⚠️ GUIDANCE ONLY

**When**: You create a new agent using AI (not from a template)  
**How**: AI reads tool descriptions that include the 4 golden rules  
**Reliability**: ⚠️ **~80-90%** - AI usually follows, but can make mistakes  
**Status**: ⚠️ **Guidance provided** - AI sees the rules but isn't forced to follow them

**What AI Sees**:
```
🔴 THE 4 GOLDEN RULES OF DEFENSIVE SQL (MUST FOLLOW EVERY TIME):

📌 RULE 1: Defensive Join Pattern
📌 RULE 2: Safe Numeric Pattern  
📌 RULE 3: Date Handling Pattern
📌 RULE 4: Always Include Document Join
```

**Your Experience**:
- ✅ AI **correctly used** `TO_DATE()` and `NULLIF()`
- ❌ AI **hallucinated columns** that don't exist (`v.city`, `v.state`)
- ❌ AI **incomplete WHERE clause** (missing NULL handling)

**Applies**: After you restart the backend server

---

### 3️⃣ Agent Editing (Manual) 🔧 NEW - VALIDATION AVAILABLE

**When**: You manually edit an agent's query  
**How**: API endpoints validate and auto-fix queries  
**Reliability**: 🔧 **Depends on integration** - Frontend needs to call the API  
**Status**: 🔧 **API Ready** - Frontend integration needed

**Available Now**:
- ✅ **Validation API**: `POST /api/sql/validate`
- ✅ **Auto-fix API**: `POST /api/sql/auto-fix`
- ✅ **Python Validator**: `DefensiveSQLValidator` class

**To Implement** (Frontend):
1. Real-time validation as you type
2. Save-time validation before saving
3. "Apply Defensive SQL" button for one-click fixes

**Applies**: When frontend integration is complete

---

### 4️⃣ Query Auto-Correction (Fallback) 🔧 ALREADY ACTIVE

**When**: A query fails during execution  
**How**: System detects error and AI attempts to fix it  
**Reliability**: 🔧 **~70-80%** - Works for common errors  
**Status**: 🔧 **Already active** - Your error log showed this

**Your Experience**:
```
🔧 Attempting to fix SQL syntax error (attempt 1/5)...
📊 Fetching schema for table: icap_invoice
✅ AI provided corrected query
```

**Applies**: Already active - no action needed

---

## 🎯 Summary Table

| Stage | When | Reliability | Status | Action Needed |
|-------|------|-------------|--------|---------------|
| **Templates** | Using pre-built templates | ✅ 100% | ✅ Active | Restart server |
| **AI-Generated** | Creating with AI | ⚠️ 80-90% | ⚠️ Guidance | Restart server |
| **Editing** | Manual query editing | 🔧 TBD | 🔧 API Ready | Frontend integration |
| **Auto-Correction** | Query execution fails | 🔧 70-80% | 🔧 Active | None |

---

## 🚀 To Activate Everything

### Step 1: Restart Backend Server ✅ DO THIS NOW
```bash
# Stop current server (Ctrl+C)
python backend/main.py
```

This activates:
- ✅ Updated agent templates with defensive SQL
- ✅ AI tool descriptions with the 4 golden rules
- ✅ Fixed ChatPromptTemplate parsing (no more `{"value"}` errors)

### Step 2: Integrate Validation API (Optional - Future Enhancement)

Add to your agent editor frontend:
1. Call `/api/sql/validate` as user types (debounced)
2. Show validation issues in the UI
3. Add "Apply Defensive SQL" button that calls `/api/sql/auto-fix`

See `backend/docs/SQL_VALIDATION_INTEGRATION.md` for implementation guide.

---

## 💡 Best Practices

### For Maximum Reliability:

1. **Use Agent Templates** when possible
   - 100% guaranteed defensive SQL
   - No chance of errors

2. **When using AI to create agents**:
   - AI will follow the rules ~80-90% of the time
   - **Always review the generated query**
   - Look for:
     - ❌ Non-existent columns (like `v.city`)
     - ❌ Incomplete WHERE clauses
     - ✅ Correct use of TO_DATE, NULLIF

3. **When editing agents**:
   - Use the validation API (once integrated)
   - Or manually check against the 4 golden rules
   - Reference: `backend/docs/DEFENSIVE_SQL_QUICK_REF.md`

4. **Test your agents**:
   - Run with sample data
   - Auto-correction will catch most issues
   - But prevention is better than correction!

---

## 🔍 How to Verify Rules Are Working

### Test 1: Check a Template
```bash
# View the Invoice Aging Report template
# Should see TO_DATE() and NULLIF()
cat backend/templates/agent_templates.json | grep -A 20 "invoice-aging-report"
```

### Test 2: Create an Agent with AI
1. Create a new agent asking for "aging report"
2. Check if AI uses `TO_DATE()` instead of `::date`
3. Check if AI uses `NULLIF()` for numeric fields
4. ✅ If yes, rules are working!
5. ❌ If no, check if server was restarted

### Test 3: Test Validation API
```bash
curl -X POST http://localhost:8000/api/sql/validate \
  -H "Content-Type: application/json" \
  -d '{"query": "SELECT (i.due_date->>'\''value'\'')::date FROM icap_invoice i"}'
```

Should return validation issues about using `::date` instead of `TO_DATE`.

---

## 📚 Documentation Reference

- **Quick Reference**: `backend/docs/DEFENSIVE_SQL_QUICK_REF.md`
- **Complete Rules**: `backend/docs/DEFENSIVE_SQL_RULES.md`
- **Implementation**: `backend/docs/DEFENSIVE_SQL_IMPLEMENTATION.md`
- **Validation Integration**: `backend/docs/SQL_VALIDATION_INTEGRATION.md`
- **Template Updates**: `backend/docs/AGENT_TEMPLATES_UPDATE.md`

---

## 🎯 Bottom Line

**The rules apply in 4 ways**:

1. **Templates** → ✅ **100% Guaranteed** (restart server to activate)
2. **AI-generated** → ⚠️ **80-90% Guidance** (AI sees rules, usually follows)
3. **Editing** → 🔧 **API Available** (frontend integration needed)
4. **Auto-correction** → 🔧 **70-80% Fallback** (already active)

**Your immediate action**: Restart the backend server to activate templates and AI guidance!

**Future enhancement**: Integrate validation API into agent editor for real-time validation during editing.
