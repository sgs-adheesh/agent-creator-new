# Visualization Preferences - Test Cases

## 🧪 Complete Test Suite for All Chart Types

Copy and paste these into the "Visualization Preferences" field to test each chart type.

---

## 📊 Individual Chart Type Tests

### Test 1: Pie Chart
```
pie chart
```
**Expected:** Distribution pie chart (donut style)  
**Best for:** Categorical data with numeric values

---

### Test 2: Bar Chart
```
bar chart
```
**Expected:** Vertical bar chart for comparisons  
**Best for:** Comparing categories

---

### Test 3: Line Chart
```
line chart
```
**Expected:** Line chart showing trends  
**Best for:** Time-series or sequential data

---

### Test 4: Area Chart
```
area chart
```
**Expected:** Filled area chart  
**Best for:** Cumulative trends

---

### Test 5: Scatter Chart
```
scatter plot
```
**Expected:** Scatter plot showing correlations  
**Best for:** Two numeric variables

---

### Test 6: Radar Chart ✨ NEW
```
radar chart
```
**Expected:** Spider/web chart for multi-metric comparison  
**Best for:** Comparing multiple metrics across categories  
**Requires:** 2+ numeric fields

---

### Test 7: Radial Bar Chart ✨ NEW
```
radial bar
```
**Alternative:**
```
circular progress
```
**Expected:** Semi-circular progress bars  
**Best for:** Rankings, progress visualization

---

### Test 8: Composed Chart ✨ NEW
```
composed chart
```
**Alternative:**
```
mixed chart
```
**Expected:** Bar + Line + Area combined  
**Best for:** Multiple metrics in one view  
**Requires:** 2+ numeric fields

---

### Test 9: Funnel Chart ✨ NEW
```
funnel chart
```
**Alternative:**
```
conversion funnel
```
**Expected:** Funnel showing conversion stages  
**Best for:** Pipeline/conversion analysis

---

### Test 10: Treemap Chart ✨ NEW
```
treemap
```
**Alternative:**
```
hierarchical view
```
**Expected:** Nested rectangles showing proportions  
**Best for:** Hierarchical data, budget breakdown

---

## 🎯 Combination Tests

### Test 11: All Basic Charts
```
show me pie, bar, line, area, and scatter charts
```
**Expected:** All 5 basic chart types

---

### Test 12: All New Charts
```
show me radar, radial bar, composed, funnel, and treemap charts
```
**Expected:** All 5 new chart types

---

### Test 13: All Charts (Complete Dashboard)
```
show me pie, bar, line, area, scatter, radar, radial bar, composed, funnel, and treemap charts
```
**Expected:** All 10 chart types in one dashboard

---

### Test 14: Mixed Selection
```
radar and funnel charts
```
**Expected:** Radar + Funnel charts

---

### Test 15: Business Analysis Mix
```
show me pie chart for distribution, funnel for conversion, and radar for comparison
```
**Expected:** Pie + Funnel + Radar charts

---

## 🔥 Advanced Test Cases

### Test 16: Alias Test (Radial)
```
radial
```
**Expected:** Radial bar chart (alias for radialbar)

---

### Test 17: Alias Test (Mixed)
```
mixed
```
**Expected:** Composed chart (alias for composed)

---

### Test 18: Natural Language
```
I want to see a radar chart comparing metrics and a funnel showing conversion
```
**Expected:** Radar + Funnel charts

---

### Test 19: Descriptive Request
```
show trends with line chart and distribution with pie chart
```
**Expected:** Line + Pie charts

---

### Test 20: Auto-Generation (No Preference)
```
(leave empty)
```
**Expected:** AI automatically selects best chart types based on data

---

## 📋 Quick Copy-Paste List

For quick testing, here are one-liners for each chart:

```
pie chart
bar chart
line chart
area chart
scatter plot
radar chart
radial bar
composed chart
funnel chart
treemap
```

---

## 🎨 Themed Test Scenarios

### Sales Analysis Dashboard
```
pie chart for sales distribution, line chart for trends, and funnel for pipeline
```

### Vendor Performance Dashboard
```
radar chart for vendor comparison, bar chart for rankings, and treemap for breakdown
```

### Financial Dashboard
```
area chart for cumulative revenue, composed chart for metrics, and pie chart for categories
```

### Conversion Analysis
```
funnel chart for conversion stages, bar chart for comparisons, and line chart for trends
```

---

## ✅ Validation Checklist

After each test, verify:
- [ ] Chart renders correctly
- [ ] Chart has appropriate title
- [ ] Hover tooltip works
- [ ] Click opens detail modal
- [ ] Colors match theme
- [ ] Data is accurate
- [ ] No console errors

---

## 🚀 Recommended Test Order

1. **Start Simple:** Test individual charts (Tests 1-10)
2. **Test Combinations:** Try 2-3 charts together (Tests 14-15)
3. **Test Aliases:** Verify "radial" and "mixed" work (Tests 16-17)
4. **Test Natural Language:** Use descriptive requests (Tests 18-19)
5. **Test Auto-Generation:** Leave empty to see AI selection (Test 20)
6. **Full Dashboard:** Request all charts together (Test 13)

---

## 💡 Pro Tips

1. **Case Insensitive:** `"RADAR CHART"` works same as `"radar chart"`
2. **Flexible Wording:** `"show me a radar"` works same as `"radar chart"`
3. **Multiple Requests:** Separate with commas or "and"
4. **Partial Matches:** `"rad"` won't work, but `"radar"` will
5. **Data Dependent:** Some charts need specific data (e.g., radar needs 2+ numeric fields)

---

## 🎯 Expected Results Summary

| Test | Input | Expected Charts |
|------|-------|----------------|
| 1 | `pie chart` | 1 Pie |
| 2 | `bar chart` | 1 Bar |
| 3 | `line chart` | 1 Line |
| 4 | `area chart` | 1 Area |
| 5 | `scatter plot` | 1 Scatter |
| 6 | `radar chart` | 1 Radar |
| 7 | `radial bar` | 1 RadialBar |
| 8 | `composed chart` | 1 Composed |
| 9 | `funnel chart` | 1 Funnel |
| 10 | `treemap` | 1 Treemap |
| 11 | `pie, bar, line, area, scatter` | 5 Basic |
| 12 | `radar, radial, composed, funnel, treemap` | 5 New |
| 13 | All types | 10 Total |
| 20 | (empty) | AI Selected |

---

## 🐛 Troubleshooting

**Chart not appearing?**
- Check if data has required fields (e.g., radar needs 2+ numeric)
- Check browser console for errors
- Verify backend is running
- Check backend logs for "User Requested Chart Types"

**Wrong chart type?**
- Ensure spelling is correct
- Try alternative keywords (e.g., "radial bar" vs "radialbar")
- Check if LLM substituted due to data incompatibility

**No charts at all?**
- Check if agent execution succeeded
- Verify `visualization_config` in response
- Check if `table_data` exists in response

---

## 📞 Need Help?

If charts aren't working:
1. Check backend logs for: `🎨 Generating visualization config`
2. Look for: `User Requested Chart Types: [your types]`
3. Verify response includes `visualization_config`
4. Check browser console for errors

---

**Happy Testing! 🎉**

Try them all and see your data come to life with 10 different visualization types!
