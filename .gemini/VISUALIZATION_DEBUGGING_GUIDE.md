# Visualization Not Showing - Debugging Guide

## 🐛 Issue
Visualizations are not showing any content.

## 🔍 Debugging Steps

### Step 1: Check Browser Console

Open browser DevTools (F12) and look for these log messages:

#### Expected Logs (Successful Flow)
```
🗃️ Extracted dataArray: [...]
🔑 First row keys: [...]
📊 First row data: {...}
🎨 Using LLM-generated visualization config: {...}
📊 Processing chart 1/3: { type: 'pie', data_source: {...} }
📊 Processing chart 2/3: { type: 'bar', data_source: {...} }
✅ Generated chart data from config: { pieDataCount: 1, barDataCount: 1, ... }
```

#### Problem Indicators

**No data extracted:**
```
🗃️ Extracted dataArray: []
```
**Solution:** Check if agent execution returned `table_data` or `json_data`

**No visualization config:**
```
(No "🎨 Using LLM-generated visualization config" message)
```
**Solution:** Check if backend generated `visualization_config`

**Charts skipped:**
```
⚠️ visualization_config pie chart missing valid aggregate field, skipping
```
**Solution:** Check LLM-generated config structure

**No chart data generated:**
```
✅ Generated chart data from config: { pieDataCount: 0, barDataCount: 0 }
```
**Solution:** Check if data processing logic is working

---

### Step 2: Check Backend Response

Look at the API response in Network tab:

#### Required Structure
```json
{
  "success": true,
  "table_data": {
    "rows": [...],  // ✅ Must have rows
    "columns": [...]
  },
  "visualization_config": {  // ✅ Must be present
    "charts": [
      {
        "type": "pie",
        "data_source": {
          "group_by": "vendor_name",  // ✅ Must be valid field
          "aggregate": {
            "field": "total_amount",  // ✅ Must be valid field
            "function": "sum"
          }
        }
      }
    ]
  }
}
```

#### Common Issues

**Missing `table_data`:**
```json
{
  "success": true,
  "result": "Some text..."  // ❌ No table_data
}
```
**Solution:** Agent needs to return structured data

**Missing `visualization_config`:**
```json
{
  "success": true,
  "table_data": {...}  // ❌ No visualization_config
}
```
**Solution:** Check if backend `_generate_visualization_config` was called

**Invalid field names:**
```json
{
  "data_source": {
    "group_by": "nonexistent_field"  // ❌ Field doesn't exist in data
  }
}
```
**Solution:** LLM is hallucinating field names

---

### Step 3: Check Data Structure

Verify data has the expected structure:

#### Good Data Structure
```javascript
dataArray = [
  {
    vendor_name: { value: "Acme Corp" },  // JSONB wrapped
    total_amount: { value: 15000 },
    invoice_number: { value: "INV-001" }
  },
  {
    vendor_name: "Tech Inc",  // Or plain value
    total_amount: 23000,
    invoice_number: "INV-002"
  }
]
```

#### Bad Data Structure
```javascript
dataArray = []  // ❌ Empty
dataArray = null  // ❌ Null
dataArray = [{ message: "No data" }]  // ❌ Wrong structure
```

---

### Step 4: Check Field Names

Verify fields in config match fields in data:

```javascript
// In console:
console.log('Available fields:', Object.keys(dataArray[0]));
console.log('Config group_by:', visualization_config.charts[0].data_source.group_by);

// They should match!
```

---

## 🔧 Common Fixes

### Fix 1: No Data Returned

**Problem:** Agent returns text instead of structured data

**Solution:** Update agent to return table data
```python
# In agent template:
return {
    "table_data": {
        "rows": query_results,
        "columns": ["vendor_name", "total_amount"]
    }
}
```

### Fix 2: No Visualization Config

**Problem:** Backend not generating visualization config

**Check:** Backend logs for:
```
🎨 Generating visualization config for X rows...
✅ Generated visualization config with X chart(s)
```

**If missing:** Check if `_format_output` is being called with `visualization_preferences`

### Fix 3: Field Mismatch

**Problem:** Config uses fields that don't exist in data

**Solution:** Add field validation in frontend (already implemented)

**Or:** Improve LLM prompt to use correct field names

### Fix 4: Empty Chart Data

**Problem:** Data processing returns empty arrays

**Debug:**
```javascript
// Add breakpoint in DataVisualization.tsx
// Check values of:
- groupByField
- aggregateField
- dataArray
- aggregated object
```

**Common causes:**
- JSONB unwrapping failing
- Field name case mismatch
- Null/undefined values

---

## 🎯 Quick Diagnostic Checklist

Run through this checklist:

- [ ] Backend returns `table_data` with `rows`
- [ ] Backend returns `visualization_config` with `charts`
- [ ] `dataArray` is not empty (check console)
- [ ] Field names in config match field names in data
- [ ] At least one chart is being processed (check console)
- [ ] Chart data arrays are not empty (check console)
- [ ] No errors in browser console
- [ ] No errors in backend logs

---

## 🧪 Test Cases

### Test 1: Minimal Working Example

**Backend Response:**
```json
{
  "success": true,
  "table_data": {
    "rows": [
      { "category": "A", "value": 100 },
      { "category": "B", "value": 200 }
    ]
  },
  "visualization_config": {
    "charts": [{
      "type": "pie",
      "data_source": {
        "group_by": "category",
        "aggregate": "value"
      }
    }]
  }
}
```

**Expected:** Pie chart with 2 slices (A: 100, B: 200)

### Test 2: With JSONB Wrapping

**Backend Response:**
```json
{
  "table_data": {
    "rows": [
      { 
        "vendor_name": { "value": "Acme" }, 
        "total": { "value": 1000 } 
      }
    ]
  },
  "visualization_config": {
    "charts": [{
      "type": "bar",
      "data_source": {
        "group_by": "vendor_name",
        "aggregate": { "field": "total", "function": "sum" }
      }
    }]
  }
}
```

**Expected:** Bar chart with 1 bar (Acme: 1000)

---

## 🚨 Emergency Fallback

If visualizations still don't work, try **auto-generation mode**:

1. **Remove** `visualization_preferences` from request
2. **Let** the system auto-generate charts
3. **Check** if auto-generated charts work

If auto-generated works but LLM-config doesn't:
- Problem is in LLM config generation
- Check backend logs for LLM response
- Check if LLM is returning valid JSON

---

## 📞 Still Not Working?

Collect this information:

1. **Browser console logs** (all messages)
2. **Backend logs** (especially visualization generation)
3. **Network response** (full JSON)
4. **Agent purpose** (what is the agent supposed to do?)
5. **Sample data** (first few rows)

Then check:
- Is `visualization_preferences` being passed correctly?
- Is LLM generating valid configs?
- Are field names matching?
- Is data being extracted correctly?

---

## ✅ Success Indicators

You know it's working when you see:

```
✅ Generated chart data from config: { 
  pieDataCount: 1,  // > 0
  barDataCount: 1,  // > 0
  pieData: [{ name: "Acme Corp", value: 15000, ... }],
  barData: [{ name: "Acme Corp", total_amount: 15000, ... }]
}
```

And charts render on the page! 🎉
