# Quick Reference: All Recharts Chart Types

## 🎯 Quick Chart Selection Guide

| Your Need | Chart Type | User Input Example |
|-----------|------------|-------------------|
| Show distribution | **Pie** | `"pie chart by vendor"` |
| Compare categories | **Bar** | `"bar chart comparison"` |
| Show trends | **Line** | `"line chart over time"` |
| Show cumulative | **Area** | `"area chart trends"` |
| Show correlation | **Scatter** | `"scatter plot"` |
| Compare metrics | **Radar** | `"radar chart"` |
| Show progress | **RadialBar** | `"radial bar"` or `"circular progress"` |
| Mix chart types | **Composed** | `"composed chart"` or `"mixed chart"` |
| Show funnel | **Funnel** | `"funnel chart"` or `"conversion funnel"` |
| Show hierarchy | **Treemap** | `"treemap"` or `"hierarchical view"` |

---

## 📊 Chart Type Details

### 1. Pie Chart 🥧
**When to use:** Distribution analysis  
**Data needed:** 1 categorical + 1 numeric field  
**Example:** Sales by vendor  
**Input:** `"pie chart by vendor"`

### 2. Bar Chart 📊
**When to use:** Comparisons  
**Data needed:** 1 categorical + 1+ numeric fields  
**Example:** Revenue by product  
**Input:** `"bar chart"`

### 3. Line Chart 📈
**When to use:** Trends over time  
**Data needed:** 1 date/categorical + 1+ numeric fields  
**Example:** Sales over months  
**Input:** `"line chart over time"`

### 4. Area Chart 📉
**When to use:** Cumulative trends  
**Data needed:** 1 date/categorical + 1+ numeric fields  
**Example:** Cumulative revenue  
**Input:** `"area chart"`

### 5. Scatter Chart 🔵
**When to use:** Correlations  
**Data needed:** 2+ numeric fields  
**Example:** Price vs Quality  
**Input:** `"scatter plot"`

### 6. Radar Chart 🕸️ **NEW!**
**When to use:** Multi-metric comparison  
**Data needed:** 2+ numeric fields, 1 categorical  
**Example:** Vendor performance across KPIs  
**Input:** `"radar chart"`  
**Requires:** At least 2 numeric fields

### 7. Radial Bar Chart 🎯 **NEW!**
**When to use:** Circular progress/ranking  
**Data needed:** 1 categorical + 1 numeric field  
**Example:** Top performers ranking  
**Input:** `"radial bar"` or `"circular chart"`

### 8. Composed Chart 🎨 **NEW!**
**When to use:** Multiple metrics in one view  
**Data needed:** 2+ numeric fields  
**Example:** Sales (bar) + Trend (line) + Forecast (area)  
**Input:** `"composed chart"` or `"mixed chart"`  
**Requires:** At least 2 numeric fields

### 9. Funnel Chart 🔻 **NEW!**
**When to use:** Conversion/pipeline analysis  
**Data needed:** 1 categorical + 1 numeric field  
**Example:** Sales pipeline stages  
**Input:** `"funnel chart"` or `"conversion funnel"`

### 10. Treemap Chart 🗂️ **NEW!**
**When to use:** Hierarchical/proportional data  
**Data needed:** 1 categorical + 1 numeric field  
**Example:** Budget by department  
**Input:** `"treemap"` or `"hierarchical view"`

---

## 💡 Usage Examples

### Single Chart Request
```
Query: "Show me invoice data"
Visualization Preferences: "radar chart"
Result: One radar chart
```

### Multiple Charts Request
```
Query: "Show me sales analysis"
Visualization Preferences: "show me pie and funnel charts"
Result: Both pie and funnel charts
```

### Auto-Generation (No Preference)
```
Query: "Show me vendor data"
Visualization Preferences: (leave empty)
Result: AI selects best chart types
```

---

## 🎨 Color Themes

| Chart | Colors |
|-------|--------|
| Pie | Indigo → Purple |
| Bar | Purple → Pink |
| Line | Blue → Sky |
| Area | Emerald → Teal |
| Scatter | Amber → Orange |
| Radar | Green → Emerald |
| RadialBar | Violet → Purple |
| Composed | Cyan → Blue |
| Funnel | Orange → Red |
| Treemap | Rose → Pink |

---

## ⚡ Quick Tips

1. **Be specific:** `"radar chart"` is better than `"chart"`
2. **Use aliases:** `"radial"` works for `"radialbar"`, `"mixed"` works for `"composed"`
3. **Combine types:** `"show me pie and bar charts"` requests both
4. **Let AI decide:** Leave preferences empty for auto-selection
5. **Check data:** Some charts need specific data (e.g., radar needs 2+ numeric fields)

---

## 🚀 Testing Commands

```bash
# Start backend
cd backend && python main.py

# Start frontend
cd frontend && npm run dev

# Open browser
http://localhost:5173
```

---

## ✅ Supported Keywords

| Keyword | Chart Type |
|---------|------------|
| `pie` | Pie Chart |
| `bar` | Bar Chart |
| `line` | Line Chart |
| `area` | Area Chart |
| `scatter` | Scatter Chart |
| `radar` | Radar Chart |
| `radial`, `radialbar` | Radial Bar Chart |
| `composed`, `mixed` | Composed Chart |
| `funnel` | Funnel Chart |
| `treemap` | Treemap Chart |

---

## 📞 Need Help?

Check these docs:
- `COMPLETE_RECHARTS_IMPLEMENTATION.md` - Full implementation details
- `RECHARTS_CAPABILITY_ANALYSIS.md` - Capability analysis
- `VISUALIZATION_GUIDE.md` - Complete guide
- `test_visualization_preferences.py` - Test script

---

**Total Chart Types:** 10  
**Coverage:** 71% of Recharts library  
**Status:** ✅ Ready to use!
