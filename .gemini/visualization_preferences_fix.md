# Visualization Preferences Bug Fix

## Issue
User-specified visualization preferences from the UI were being ignored during agent execution.

## Root Cause
In `backend/services/agent_service.py`, the `execute_agent_with_ai_streaming()` method was receiving the `visualization_preferences` parameter from the API endpoint but **failing to pass it** to the underlying `execute_agent()` method.

### Code Location
**File:** `backend/services/agent_service.py`  
**Method:** `execute_agent_with_ai_streaming()` (line 4442)  
**Problem Line:** 4489-4491

### Before (Broken)
```python
def execute_in_thread():
    try:
        result_container['result'] = self.execute_agent(
            agent_id, user_query, tool_configs, input_data, capturing_callback
            # ❌ Missing: visualization_preferences parameter!
        )
```

### After (Fixed)
```python
def execute_in_thread():
    try:
        result_container['result'] = self.execute_agent(
            agent_id, user_query, tool_configs, input_data, capturing_callback, visualization_preferences
            # ✅ Now passing visualization_preferences
        )
```

## Data Flow (Now Working)

```
Frontend (WorkflowCanvas.tsx)
  ↓ Line 596: visualization_preferences sent in request body
  
API Endpoint (main.py)
  ↓ Line 509: Receives visualization_preferences from request
  ↓ Line 509: Calls execute_agent_with_ai_streaming(... visualization_preferences)
  
Agent Service (agent_service.py)
  ↓ Line 4442: execute_agent_with_ai_streaming receives visualization_preferences
  ✅ Line 4490: NOW passes it to execute_agent()
  ↓ Line 4704: execute_agent receives visualization_preferences
  ↓ Line 4737: Passes to _execute_with_guidance()
  ↓ Eventually reaches _format_output()
  ↓ Line 221-229: Generates visualization_config using user preferences
  
Response
  ↓ Returns visualization_config to frontend
  ↓ Frontend renders charts according to user preferences
```

## Testing
To verify the fix works:

1. **Open the agent execution UI**
2. **Enter a query** (e.g., "Show me invoice data")
3. **In the "Visualization Preferences" field**, enter:
   - "line chart over time"
   - "pie chart by vendor"
   - "bar chart comparison"
4. **Execute the agent**
5. **Verify** that the response includes a `visualization_config` with the requested chart types

## Example User Preferences

| User Input | Expected Result |
|------------|----------------|
| "pie chart by vendor" | Generates pie chart grouped by vendor_name |
| "line chart over time" | Generates line chart with date on x-axis |
| "bar chart comparison" | Generates bar chart for comparisons |
| "show trends" | Generates line/area charts for trend analysis |

## Related Files

### Frontend
- `frontend/src/components/WorkflowCanvas.tsx` (lines 596, 900-915, 936-951)
  - Captures user input for visualization preferences
  - Sends to backend in execute request

### Backend
- `backend/main.py` (line 509)
  - API endpoint receives visualization_preferences
  
- `backend/services/agent_service.py`
  - Line 4442: `execute_agent_with_ai_streaming()` - **FIXED HERE**
  - Line 4704: `execute_agent()` - Accepts parameter
  - Line 273: `_generate_visualization_config()` - Uses preferences
  - Line 121: `_format_output()` - Calls visualization generation

## Impact
✅ Users can now specify their preferred chart types  
✅ LLM will honor user requests (e.g., "show me a line chart")  
✅ Fallback auto-generation still works if no preferences specified  
✅ System guarantees requested chart types are included in response
