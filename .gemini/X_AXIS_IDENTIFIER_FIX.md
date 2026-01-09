# X-Axis Identifier Field Fix

## 🐛 Issue
Charts were showing mixed/inappropriate values on the X-axis, including both vendor names and invoice numbers, creating cluttered and meaningless visualizations.

## 🔍 Root Cause
The LLM was sometimes generating visualization configs that used **identifier fields** (like `invoice_number`, `id`, `code`) for grouping/x-axis instead of **categorical fields** (like `vendor_name`, `category`, `status`).

### Why This Happens
- Identifier fields have many unique values (one per record)
- Using them for grouping creates one bar/point per record
- Results in cluttered, unreadable charts
- Defeats the purpose of aggregation

### Example of Bad Config
```json
{
  "type": "bar",
  "data_source": {
    "x_axis": "invoice_number",  // ❌ Identifier - creates 100 bars
    "y_axis": "total_amount"
  }
}
```

### Example of Good Config
```json
{
  "type": "bar",
  "data_source": {
    "x_axis": "vendor_name",  // ✅ Categorical - creates 5-10 bars
    "y_axis": "total_amount"
  }
}
```

---

## 🔧 The Fix

### Two-Layer Defense

#### Layer 1: Backend (LLM Guidance)
**File:** `backend/services/agent_service.py`  
**Lines:** 405-437

Added explicit rules to the LLM prompt:

```python
CRITICAL Field Selection Rules:
- **NEVER use identifier fields** (invoice_number, id, code, reference, uuid) for group_by or x_axis
- **ALWAYS use descriptive fields** (vendor_name, supplier_name, category, status, type) for grouping
- **For x_axis in bar/line charts:** Use categorical fields like vendor_name, category, or date fields
- **For group_by:** Use fields that represent meaningful categories (vendor, product, status)
- **Avoid:** Fields with "number", "id", "code", "reference" in their names for grouping
- **Prefer:** Fields with "name", "category", "type", "status" for grouping

Examples of GOOD field choices:
- group_by: "vendor_name" ✅
- x_axis: "vendor_name" ✅
- x_axis: "invoice_date" ✅
- group_by: "category" ✅

Examples of BAD field choices:
- group_by: "invoice_number" ❌ (identifier, not a category)
- x_axis: "invoice_number" ❌ (creates too many unique values)
- group_by: "id" ❌ (identifier)
- x_axis: "reference_code" ❌ (identifier)
```

#### Layer 2: Frontend (Validation & Auto-Fix)
**File:** `frontend/src/components/DataVisualization.tsx`  
**Lines:** 38-76, 267-280, 354-368, 436-450

Added validation functions and auto-correction:

```typescript
// Helper to check if a field is an identifier
function isIdentifierField(fieldName: string): boolean {
  const identifierKeywords = ['number', 'id', 'uuid', 'code', 'ref', 'reference'];
  const fieldLower = fieldName.toLowerCase();
  return identifierKeywords.some(keyword => fieldLower.includes(keyword));
}

// Helper to check if a field is good for grouping
function isGoodGroupingField(fieldName: string): boolean {
  const goodKeywords = ['name', 'category', 'type', 'status', 'group', 'class'];
  const fieldLower = fieldName.toLowerCase();
  return goodKeywords.some(keyword => fieldLower.includes(keyword)) && !isIdentifierField(fieldName);
}

// Helper to find best categorical field
function findBestCategoricalField(categoricalFields: string[]): string | null {
  // Priority 1: vendor_name or supplier_name
  // Priority 2: Other name/category fields (not identifiers)
  // Priority 3: First non-identifier field
}
```

**Validation Applied To:**
1. Pie charts with `group_by`
2. Bar/Line/Area/Scatter charts with `group_by`
3. Bar/Line/Area charts with `x_axis`

**Auto-Correction Logic:**
```typescript
// Validate group_by field
if (isIdentifierField(groupByField)) {
  console.warn(`⚠️ Chart config uses identifier field "${groupByField}" for grouping`);
  const betterField = findBestCategoricalField(categoricalFields);
  if (betterField) {
    console.log(`✅ Replaced "${groupByField}" with "${betterField}"`);
    groupByField = betterField;
  } else {
    console.warn(`⚠️ No better field found, skipping chart`);
    return; // Skip this chart
  }
}
```

---

## 📊 Impact

### Before Fix
```
X-Axis Values:
INV-001, INV-002, INV-003, INV-004, INV-005, INV-006, ...
Acme Corp, Tech Inc, Global Ltd, ...

Result: Cluttered, mixed values, unreadable ❌
```

### After Fix
```
X-Axis Values:
Acme Corp, Tech Inc, Global Ltd, Innovate Co, Supply Plus

Result: Clean, aggregated, meaningful ✅
```

---

## 🎯 Field Classification

### Identifier Fields (❌ Bad for Grouping)
- `invoice_number`
- `id`
- `uuid`
- `reference_code`
- `transaction_id`
- `order_number`

**Why bad:** Each record has a unique value, no aggregation possible

### Categorical Fields (✅ Good for Grouping)
- `vendor_name`
- `supplier_name`
- `category`
- `status`
- `type`
- `product_name`

**Why good:** Limited unique values, enables meaningful aggregation

### Date Fields (✅ Good for Time Series)
- `invoice_date`
- `created_at`
- `order_date`

**Why good:** Natural grouping by time periods

---

## 🔍 Detection Logic

### Identifier Keywords
```typescript
['number', 'id', 'uuid', 'code', 'ref', 'reference']
```

If field name contains any of these → **Identifier**

### Good Grouping Keywords
```typescript
['name', 'category', 'type', 'status', 'group', 'class']
```

If field name contains any of these AND not an identifier → **Good for Grouping**

---

## 🚀 Priority Order for Field Selection

1. **vendor_name** or **supplier_name** (highest priority)
2. Other **name** fields (product_name, customer_name)
3. **category** fields
4. **type** or **status** fields
5. First non-identifier categorical field

---

## ✅ Validation Examples

### Example 1: Pie Chart
```typescript
// LLM generates:
{
  type: "pie",
  data_source: {
    group_by: "invoice_number",  // ❌ Identifier
    aggregate: "total_amount"
  }
}

// Frontend validates and fixes:
⚠️ Chart config uses identifier field "invoice_number" for grouping
✅ Replaced "invoice_number" with "vendor_name"

// Result:
{
  type: "pie",
  data_source: {
    group_by: "vendor_name",  // ✅ Fixed
    aggregate: "total_amount"
  }
}
```

### Example 2: Bar Chart
```typescript
// LLM generates:
{
  type: "bar",
  data_source: {
    x_axis: "id",  // ❌ Identifier
    y_axis: "quantity"
  }
}

// Frontend validates and fixes:
⚠️ Chart config uses identifier field "id" for x-axis
✅ Replaced "id" with "vendor_name"

// Result:
{
  type: "bar",
  data_source: {
    x_axis: "vendor_name",  // ✅ Fixed
    y_axis: "quantity"
  }
}
```

---

## 🐛 Debugging

### Console Messages

**When identifier detected:**
```
⚠️ Chart config uses identifier field "invoice_number" for grouping. Finding better field...
✅ Replaced "invoice_number" with "vendor_name" for grouping
```

**When no better field found:**
```
⚠️ Chart config uses identifier field "id" for x-axis. Finding better field...
⚠️ No better field found, skipping chart
```

### How to Check
1. Open browser console
2. Execute agent with visualization
3. Look for warning/success messages
4. Verify X-axis shows proper categorical values

---

## 📈 Benefits

1. **Clean Charts** - No cluttered axes with hundreds of values
2. **Meaningful Aggregation** - Data grouped by actual categories
3. **Better Insights** - See patterns across vendors, categories, etc.
4. **Auto-Correction** - Works even if LLM makes mistakes
5. **Defensive** - Two-layer protection (backend + frontend)

---

## 🎯 Test Cases

### Test 1: Invoice Data
```
Data: 100 invoices from 5 vendors
Bad Config: x_axis = "invoice_number"
Result: 100 bars (one per invoice) ❌
Fixed Config: x_axis = "vendor_name"
Result: 5 bars (aggregated by vendor) ✅
```

### Test 2: Product Data
```
Data: 200 products in 10 categories
Bad Config: group_by = "product_id"
Result: 200 slices (unreadable) ❌
Fixed Config: group_by = "category"
Result: 10 slices (clear distribution) ✅
```

---

## ✅ Status

**Backend Fix:** ✅ LLM guidance updated  
**Frontend Fix:** ✅ Validation & auto-correction added  
**Testing:** ✅ Ready to test  

---

**Summary:** Charts now automatically detect and replace identifier fields with proper categorical fields, ensuring clean, meaningful visualizations with proper aggregation.
