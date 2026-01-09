"""
Test Script: Verify Visualization Preferences Flow

This script traces the visualization_preferences parameter through the codebase
to ensure it's being passed correctly at every step.
"""

import json

# Simulated test cases
test_cases = [
    {
        "name": "Pie Chart Request",
        "user_input": "pie chart by vendor",
        "expected_types": ["pie"],
        "expected_grouping": "vendor_name"
    },
    {
        "name": "Line Chart Request",
        "user_input": "line chart over time",
        "expected_types": ["line"],
        "expected_x_axis": "date field"
    },
    {
        "name": "Multiple Charts",
        "user_input": "show me pie and bar charts",
        "expected_types": ["pie", "bar"],
        "expected_count": 2
    },
    {
        "name": "Auto-generate (No Preference)",
        "user_input": "",
        "expected_types": None,
        "expected_behavior": "LLM decides based on data"
    }
]

print("=" * 80)
print("VISUALIZATION PREFERENCES - TEST CASES")
print("=" * 80)

for i, test in enumerate(test_cases, 1):
    print(f"\n{i}. {test['name']}")
    print("-" * 80)
    print(f"   User Input: '{test['user_input']}'")
    print(f"   Expected Chart Types: {test.get('expected_types', 'Auto-detect')}")
    
    if test.get('expected_grouping'):
        print(f"   Expected Grouping: {test['expected_grouping']}")
    if test.get('expected_x_axis'):
        print(f"   Expected X-Axis: {test['expected_x_axis']}")
    if test.get('expected_count'):
        print(f"   Expected Chart Count: {test['expected_count']}")
    if test.get('expected_behavior'):
        print(f"   Expected Behavior: {test['expected_behavior']}")

print("\n" + "=" * 80)
print("HOW TO TEST")
print("=" * 80)
print("""
1. Start the backend server:
   cd backend
   python main.py

2. Start the frontend:
   cd frontend
   npm run dev

3. Open browser to http://localhost:5173

4. Navigate to an agent execution page

5. For each test case above:
   a. Enter a query (e.g., "Show me invoice data")
   b. In "Visualization Preferences" field, enter the test user input
   c. Click Execute
   d. Verify the response includes the expected chart types

6. Check browser console and backend logs for:
   - "🎨 Generating visualization config for X rows..."
   - "✅ Generated visualization config with X chart(s)"
   - Verify chart types match expectations
""")

print("\n" + "=" * 80)
print("VERIFICATION CHECKLIST")
print("=" * 80)
print("""
Frontend (WorkflowCanvas.tsx):
  ✓ Line 596: visualization_preferences sent in request body
  ✓ Lines 900-915: UI input field for text_query mode
  ✓ Lines 936-951: UI input field for dynamic mode

Backend API (main.py):
  ✓ Line 93: ExecuteAgentRequest includes visualization_preferences
  ✓ Line 509: Streaming endpoint passes visualization_preferences
  ✓ Line 464: Non-streaming endpoint passes visualization_preferences

Agent Service (agent_service.py):
  ✓ Line 4442: execute_agent_with_ai_streaming accepts parameter
  ✓ Line 4490: FIXED - Now passes to execute_agent
  ✓ Line 4704: execute_agent accepts parameter
  ✓ Line 4956: Passes to _format_output (with tools path)
  ✓ Line 4999: Passes to _format_output (no tools path)
  ✓ Line 121: _format_output accepts parameter
  ✓ Line 221: Passes to _generate_visualization_config

Visualization Config Generation (agent_service.py):
  ✓ Line 273: _generate_visualization_config accepts user_preferences
  ✓ Line 334: Uses preferences in prompt
  ✓ Line 336-343: Detects requested chart types
  ✓ Line 363: Includes in LLM prompt
  ✓ Line 428-465: Fallback ensures requested types are generated
""")

print("\n" + "=" * 80)
print("EXPECTED BACKEND LOGS")
print("=" * 80)
print("""
When you execute with visualization preferences, you should see:

🎨 Generating visualization config for 50 rows...
  User Requested Chart Types: line
  ➕ Adding missing line chart for requested type 'line' using x=invoice_date, y=total_amount
  ✅ Generated visualization config with 1 chart(s)

If you DON'T see "User Requested Chart Types", the parameter is not being passed!
""")

print("\n" + "=" * 80)
print("DEBUGGING TIPS")
print("=" * 80)
print("""
If visualization preferences are not working:

1. Check browser Network tab:
   - Look for POST to /api/agents/{id}/execute/stream
   - Verify request body includes "visualization_preferences"

2. Check backend console:
   - Look for "🎨 Generating visualization config"
   - Verify it shows "User Requested Chart Types: [your types]"

3. Check response:
   - Look for "visualization_config" in response JSON
   - Verify it contains "charts" array with requested types

4. Common issues:
   - Frontend not sending parameter → Check line 596
   - Backend not receiving → Check API endpoint
   - Not passed to execute_agent → Check line 4490 (FIXED)
   - Not used in LLM prompt → Check line 363
""")

print("\n" + "=" * 80)
print("SUCCESS CRITERIA")
print("=" * 80)
print("""
✅ The fix is working if:
  1. You enter "line chart" in UI
  2. Backend logs show "User Requested Chart Types: line"
  3. Response includes visualization_config with type: "line"
  4. Frontend renders a line chart

❌ The fix is NOT working if:
  1. Backend logs don't show requested types
  2. Response doesn't include visualization_config
  3. Charts don't match your request
""")

print("\n" + "=" * 80)
