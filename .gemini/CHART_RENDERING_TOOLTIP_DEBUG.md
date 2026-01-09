# Chart Rendering and Tooltip Data Issues - Debugging Guide

## 🐛 Issues Reported

1. **Bar chart showing when not requested** - User requested 5 charts but seeing bar chart as 6th
2. **Tooltip modal missing proper data** - Some charts don't show complete data in tooltip

## 🔍 Debugging Steps

### Step 1: Check Console for Chart Rendering Config

Look for this log message:
```
📊 Chart rendering config: {
  hasConfig: true,
  requestedChartTypes: ['area', 'scatter', 'radar', 'radialbar', ...],
  chartsToShow: {
    pie: false,
    bar: false,     // ❌ Should be false if not requested
    line: false,
    area: true,     // ✅ Should be true if requested
    scatter: true,  // ✅ Should be true if requested
    radar: true,    // ✅ Should be true if requested
    radialBar: true // ✅ Should be true if requested
  }
}
```

**What to check:**
- Is `bar: false` when you didn't request bar chart?
- Are all your requested charts showing as `true`?

### Step 2: Check Requested Chart Types from Backend

Look for this log:
```
🎨 Using LLM-generated visualization config: {
  charts: [
    { type: 'area', ... },
    { type: 'scatter', ... },
    { type: 'radar', ... },
    { type: 'radialbar', ... },
    { type: 'bar', ... }  // ❌ If you see this and didn't request it, backend issue
  ]
}
```

**What to check:**
- Does the backend config include chart types you didn't request?
- Count the charts - should match what you requested

### Step 3: Check Data Deduplication

Look for this log:
```
✅ Generated chart data from config: {
  barDataCountRaw: 22,      // Before deduplication
  barDataCountUnique: 11,   // After deduplication
  barDataSample: [
    { name: 'Acme', keys: ['total', 'duplicate_count'] },
    { name: 'Tech Inc', keys: ['total', 'duplicate_count'] }
  ]
}
```

**What to check:**
- Is `barDataCountUnique` less than `barDataCountRaw`? (Should be if duplicates existed)
- Do the keys look correct for your data?

---

## 🔧 Fixes Applied

### Fix 1: Improved Deduplication with Details Merging

**Problem:** Simple deduplication was losing the `details` array needed for tooltips

**Old Code:**
```typescript
// Lost details from duplicate entries
const uniqueBarData = Array.from(
  new Map(barData.map(item => [item.name, item])).values()
);
```

**New Code:**
```typescript
// Merges details arrays from all duplicates
const barDataMap = new Map<string, typeof barData[0]>();
barData.forEach(item => {
  const existing = barDataMap.get(item.name);
  if (existing) {
    // Merge details arrays
    if (existing.details && item.details) {
      existing.details = [...existing.details, ...item.details];
    }
    // Keep max value for numeric fields
    Object.keys(item).forEach(key => {
      if (key !== 'name' && key !== 'details' && typeof item[key] === 'number') {
        existing[key] = Math.max(existing[key], item[key]);
      }
    });
  } else {
    barDataMap.set(item.name, { ...item });
  }
});
```

**Benefits:**
- ✅ Preserves all detail rows for tooltips
- ✅ Merges data from duplicate entries
- ✅ Uses max value for numeric fields (avoids double-counting)

### Fix 2: Added Chart Rendering Debug Logging

**File:** `frontend/src/components/RE-Chart.tsx`

Added logging to show exactly which charts are being rendered and why.

---

## 🎯 Expected Behavior

### Scenario 1: User Requests Specific Charts

**Input:**
```
Visualization Preferences: "area chart, scatter plot, radar chart, radial bar"
```

**Expected Console:**
```
📊 Chart rendering config: {
  requestedChartTypes: ['area', 'scatter', 'radar', 'radialbar'],
  chartsToShow: {
    pie: false,      // ✅ Not requested
    bar: false,      // ✅ Not requested
    area: true,      // ✅ Requested
    scatter: true,   // ✅ Requested
    radar: true,     // ✅ Requested
    radialBar: true  // ✅ Requested
  }
}
```

**Expected Result:** 4 charts shown (area, scatter, radar, radialbar)

### Scenario 2: Bar Chart Appearing Unexpectedly

**If you see:**
```
chartsToShow: {
  bar: true  // ❌ But you didn't request it!
}
```

**Possible causes:**
1. Backend LLM added 'bar' to the config (check backend logs)
2. Your visualization preferences included 'bar' keyword accidentally
3. Bug in chart type detection

---

## 🐛 Tooltip Data Issues

### Problem: Missing Details in Tooltip

**Symptom:** Click on chart element, modal shows "No details available"

**Cause:** The `details` array is missing or empty

**Check:**
```javascript
// In console, inspect barData:
console.log(barData[0]);

// Should see:
{
  name: "Acme Corp",
  total: 15000,
  duplicate_count: 3,
  details: [        // ✅ Should have array of rows
    { vendor_name: "Acme Corp", total: "5000", ... },
    { vendor_name: "Acme Corp", total: "10000", ... }
  ]
}

// If details is missing or empty:
{
  name: "Acme Corp",
  total: 15000,
  duplicate_count: 3,
  details: []  // ❌ Empty!
}
```

**Fix:** The improved deduplication now merges all `details` arrays

---

## 🧪 Testing Steps

### Test 1: Verify Requested Charts Only

1. Request: `"area chart, radar chart"`
2. Check console for `chartsToShow`
3. Verify: `area: true, radar: true, bar: false, pie: false`
4. Count charts on page: Should be 2

### Test 2: Verify Tooltip Data

1. Click on any chart element
2. Modal should open with data
3. Check that all fields are shown
4. Verify multiple rows if aggregated data

### Test 3: Verify No Duplicates

1. Check X-axis labels
2. Each category should appear once
3. Check console: `barDataCountUnique` should equal number of unique categories

---

## 📞 If Issues Persist

### Collect This Information:

1. **Console logs:**
   - `📊 Chart rendering config`
   - `🎨 Using LLM-generated visualization config`
   - `✅ Generated chart data from config`

2. **Your input:**
   - Exact visualization preferences text
   - What charts you expected
   - What charts you're seeing

3. **Tooltip issue:**
   - Which chart has the problem?
   - What data shows in tooltip?
   - What data should show?

---

## ✅ Quick Checklist

- [ ] Console shows correct `requestedChartTypes`
- [ ] `chartsToShow` matches your request
- [ ] Number of charts on page matches request
- [ ] No bar chart if you didn't request it
- [ ] Tooltips show data when clicking charts
- [ ] No duplicate X-axis labels
- [ ] `barDataCountUnique` ≤ `barDataCountRaw`

---

**Next Step:** Run your agent and share the console output for the three key log messages above!
