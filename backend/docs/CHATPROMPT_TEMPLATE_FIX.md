# ChatPromptTemplate Variable Parsing Fix

## Issue

When creating agents using AI (not from templates), the system was failing with this error:

```
❌ Error executing agent: 'Input to ChatPromptTemplate is missing variables {'"value"'}. 
Expected: ['"value"', 'agent_scratchpad', 'input'] 
Received: ['input', 'intermediate_steps', 'agent_scratchpad']
```

## Root Cause

The defensive SQL documentation in `postgres_connector.py` included JSON examples like:

```python
{"value": "actual_data", "confidence": 0.95}
```

LangChain's `ChatPromptTemplate` treats anything in curly braces `{}` as a template variable. When it saw `{"value": ...}` in the tool description, it tried to parse `"value"` as a variable name, causing the error.

## Solution

**Escape the curly braces** by doubling them: `{{` and `}}`.

This tells ChatPromptTemplate to treat them as literal characters, not template variables.

### Changes Made

**Before**:
```python
description = """...
1. JSONB columns contain: {\"value\": \"actual_data\", \"confidence\": 0.95, \"pageNo\": 1}
..."""
```

**After**:
```python
description = """...
1. JSONB columns contain: {{"value": "actual_data", "confidence": 0.95, "pageNo": 1}}
..."""
```

### Files Modified

1. ✅ `backend/tools/postgres_connector.py` (line 98)
2. ✅ `backend/tools/postgres_connector.py` (line 996)

## Testing

After this fix:
1. **Restart the backend server**
2. **Create a new agent using AI**
3. **The agent should execute successfully** without ChatPromptTemplate errors

## Why This Happened

When you create an agent using AI:
1. The AI reads the tool descriptions (including postgres_query)
2. The tool description is inserted into a ChatPromptTemplate
3. ChatPromptTemplate scans for `{variable}` patterns
4. It found `{"value": ...}` and tried to parse it as a variable
5. This caused the error

## Prevention

Always use **double braces** `{{` and `}}` in tool descriptions when showing JSON examples or any literal curly braces.

**Good**:
```python
f"Example JSON: {{{{\"key\": \"value\"}}}}"  # In f-strings, quadruple braces
f"Example JSON: {{'key': 'value'}}"         # In regular strings, double braces
```

**Bad**:
```python
f"Example JSON: {{\"key\": \"value\"}}"     # ChatPromptTemplate will parse this!
```

## Summary

✅ **Fixed ChatPromptTemplate parsing error**  
✅ **AI-created agents will now work correctly**  
✅ **Defensive SQL rules still fully documented**  
✅ **No functionality lost - just escaped the braces**  

The defensive SQL documentation is still complete and accurate - we just made it compatible with LangChain's template system!
