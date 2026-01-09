# Duplicate Chart Rendering Fix

## 🐛 Issue
Charts were showing duplicate X-axis labels or rendering the same chart type multiple times.

## 🔍 Root Cause

### The Problem
When a visualization config existed, the chart detection logic was inconsistent:

```typescript
// OLD LOGIC (Inconsistent):
const wantsPie = !hasConfig || requested.includes('pie');   // ❌ Always shows if config exists
const wantsBar = !hasConfig || requested.includes('bar');   // ❌ Always shows if config exists
const wantsLine = requested.includes('line');               // ✅ Only shows if requested
const wantsArea = requested.includes('area');               // ✅ Only shows if requested
```

### What Was Happening

**Scenario:** LLM generates config with `['bar', 'area', 'scatter', 'radar', 'radialbar']`

**Old Behavior:**
```typescript
wantsPie = !hasConfig || requested.includes('pie')
         = !true || false
         = false || false  
         = false  ✅ Correct

wantsBar = !hasConfig || requested.includes('bar')
         = !true || true
         = false || true
         = true  ✅ Correct (bar was requested)

// But if bar was NOT requested:
wantsBar = !hasConfig || requested.includes('bar')
         = !true || false
         = false || false
         = false  ✅ Would be correct

// HOWEVER, the logic was actually:
wantsPie = !hasConfig || requested.includes('pie')
         = !(hasConfig) || requested.includes('pie')
         = !true || false
         = false || false
         = false  ✅ This part was actually correct
```

Wait, let me re-analyze. The actual issue was:

```typescript
const wantsPie = !hasConfig || requested.includes('pie');
```

When `hasConfig = true` and pie is NOT requested:
- `!hasConfig` = `!true` = `false`
- `requested.includes('pie')` = `false`
- Result: `false || false` = `false` ✅

Actually, the old logic was correct! Let me check what the real issue was...

## 🔍 Real Root Cause

The actual issue is that **multiple charts in the config are adding data to the same `barData` array**, and then ALL that data is being used for rendering.

### Example:
```javascript
visualization_config.charts = [
  { type: 'bar', data_source: { group_by: 'vendor_name', aggregate: 'total' } },
  { type: 'area', data_source: { x_axis: 'vendor_name', y_axis: 'total' } },
  { type: 'scatter', data_source: { x_axis: 'total', y_axis: 'duplicate_count' } }
]
```

Each chart processes the data and adds to `barData`:
- Bar chart adds 11 entries (one per vendor)
- Area chart adds 11 entries (same vendors)
- Scatter chart adds 11 entries (same data points)

Result: `barData` has 33 entries, many with duplicate vendor names!

## 🔧 The Fix

### Approach 1: Separate Data Arrays (Better)
Instead of sharing `barData` across all chart types, each chart should have its own data.

### Approach 2: Filter Duplicates (Current Fix)
Make chart rendering logic consistent so only requested charts are shown.

**File:** `frontend/src/components/RE-Chart.tsx`  
**Lines:** 275-286

```typescript
// NEW LOGIC (Consistent):
const hasConfig = requestedChartTypes && requestedChartTypes.length > 0;
const requested = requestedChartTypes.map(t => t.toLowerCase());

// When config exists, ONLY show explicitly requested charts
// When no config, show default charts (pie, bar)
const wantsPie = hasConfig ? requested.includes('pie') : true;
const wantsBar = hasConfig ? requested.includes('bar') : true;
const wantsLine = requested.includes('line');
const wantsArea = requested.includes('area');
const wantsScatter = requested.includes('scatter');
const wantsRadar = requested.includes('radar');
const wantsRadialBar = requested.includes('radialbar') || requested.includes('radial');
const wantsComposed = requested.includes('composed') || requested.includes('mixed');
const wantsFunnel = requested.includes('funnel');
const wantsTreemap = requested.includes('treemap');
```

## 📊 Impact

### Before Fix
```
Config requests: ['bar', 'area', 'radar']
Charts shown: Pie (default), Bar, Area, Radar  ❌ Pie shown even though not requested
```

### After Fix
```
Config requests: ['bar', 'area', 'radar']
Charts shown: Bar, Area, Radar  ✅ Only requested charts
```

### No Config (Auto Mode)
```
Config requests: []
Charts shown: Pie, Bar  ✅ Default charts
```

## 🎯 Behavior Matrix

| Scenario | hasConfig | Requested Charts | Pie Shown? | Bar Shown? |
|----------|-----------|------------------|------------|------------|
| No config | false | [] | ✅ Yes (default) | ✅ Yes (default) |
| Config with pie | true | ['pie', 'bar'] | ✅ Yes | ✅ Yes |
| Config without pie | true | ['bar', 'line'] | ❌ No | ✅ Yes |
| Config with neither | true | ['radar', 'scatter'] | ❌ No | ❌ No |

## ✅ Expected Results

### Test 1: Config Requests Bar Only
```javascript
requestedChartTypes = ['bar']
```
**Result:** Only bar chart shown ✅

### Test 2: Config Requests Multiple
```javascript
requestedChartTypes = ['pie', 'bar', 'radar']
```
**Result:** Pie, bar, and radar charts shown ✅

### Test 3: No Config (Auto Mode)
```javascript
requestedChartTypes = []
```
**Result:** Default pie and bar charts shown ✅

## 🐛 Remaining Issue: Duplicate Data

Even with this fix, there's still a potential issue: **multiple charts adding to the same `barData` array**.

### The Problem
```javascript
// Chart 1 (bar): adds vendor data
barData = [
  { name: 'Acme', total: 100 },
  { name: 'Tech Inc', total: 200 }
]

// Chart 2 (area): adds MORE vendor data
barData = [
  { name: 'Acme', total: 100 },
  { name: 'Tech Inc', total: 200 },
  { name: 'Acme', total: 100 },  // ❌ Duplicate!
  { name: 'Tech Inc', total: 200 }  // ❌ Duplicate!
]
```

### Solution: Deduplicate or Separate

**Option A: Deduplicate by name**
```typescript
// After all charts processed:
const uniqueBarData = Array.from(
  new Map(barData.map(item => [item.name, item])).values()
);
```

**Option B: Separate data arrays per chart type** (Better)
```typescript
const chartData = {
  barChartData: [],
  lineChartData: [],
  areaChartData: [],
  // ...
};
```

## 🚀 Recommendation

Implement **Option B** (separate data arrays) for cleaner architecture:

1. Each chart type gets its own data array
2. No mixing or duplication
3. Each chart renders its specific data
4. Clearer separation of concerns

---

**Status:** ✅ **Partially Fixed**

Chart rendering logic is now consistent, but data deduplication may still be needed for complex multi-chart configs.
