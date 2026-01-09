# Implementation Plan: Query Accuracy & LLM-Generated Visualizations

## Overview
This plan addresses two major improvements:
1. **Query Accuracy**: Ensure AI considers column types and associated steps when creating/updating/correcting queries
2. **LLM-Generated Visualizations**: Generate visualization data based on agent purpose and user preferences

---

## Part 1: Improving Query Accuracy

### Problem Statement
The AI query generation, updation, and correction is not accurately considering:
- Column types (JSONB vs regular columns)
- Associated steps/relationships
- Schema validation before query generation
- Proper application of defensive SQL rules

### Root Causes Identified
1. **Schema Context Not Always Available**: Query generation sometimes happens without full schema inspection
2. **Column Type Inference**: AI doesn't always verify column types before using them
3. **Incomplete Schema Snapshot**: Schema snapshots may not include all necessary table relationships
4. **Weak Validation**: No pre-execution validation that checks column existence and types

### Solution Approach

#### 1.1 Enhanced Schema Inspection During Query Generation
**File**: `backend/services/agent_service.py`
**Method**: `_build_query_template()`

**Changes**:
- **Force schema inspection** before query generation
- **Fetch complete schema** for all tables mentioned in prompt
- **Include column types** explicitly in prompt (JSONB, UUID, VARCHAR, DATE, etc.)
- **Include foreign key relationships** with column types
- **Add validation step** that checks if generated query columns exist in schema

**Implementation Steps**:
1. Enhance `_inspect_schema_for_prompt()` to return structured schema with types
2. Modify query generation prompt to include explicit column type information
3. Add post-generation validation that verifies all columns exist
4. Add column type checking (e.g., ensure JSONB columns use `->>'value'`)

#### 1.2 Enhanced Query Correction with Type Validation
**File**: `backend/services/agent_service.py`
**Method**: `_fix_sql_syntax_error()`

**Changes**:
- **Fetch actual column types** from schema cache for all tables in query
- **Validate column types** match usage (JSONB columns use `->>'value'`, regular columns don't)
- **Check foreign key relationships** before suggesting JOINs
- **Verify data types** match operations (dates use TO_DATE, numerics use NULLIF)

**Implementation Steps**:
1. Enhance schema fetching to include detailed type information
2. Add type validation logic that checks each column usage
3. Improve error analysis to identify type mismatches
4. Add proactive checks before returning corrected query

#### 1.3 Pre-Execution Query Validation
**File**: `backend/services/agent_service.py`
**Method**: `_validate_query_before_execution()`

**New Method**:
- **Parse SQL query** to extract all column references
- **Check each column** exists in schema
- **Verify column types** match usage patterns
- **Validate JOIN conditions** match foreign key relationships
- **Check defensive SQL rules** are applied correctly

**Implementation Steps**:
1. Create new validation method
2. Integrate validation before query execution
3. Auto-fix common issues before execution
4. Log validation results for debugging

#### 1.4 Schema Snapshot Enhancement
**File**: `backend/services/agent_service.py`
**Method**: `_build_execution_guidance()`

**Changes**:
- **Store complete schema snapshot** with column types
- **Include table relationships** (foreign keys) with types
- **Cache schema information** for faster access during execution
- **Include sample data types** to help AI understand data structure

**Implementation Steps**:
1. Enhance schema snapshot to include detailed type information
2. Store schema snapshot in execution guidance
3. Use snapshot during query correction for faster access

---

## Part 2: LLM-Generated Visualizations

### Problem Statement
Current visualizations are auto-generated from data structure but don't consider:
- Agent's purpose/mission
- User-specified visualization preferences
- Contextual chart types based on data meaning
- Structured visualization JSON separate from raw data

### Solution Approach

#### 2.1 Visualization Request Handling
**File**: `backend/services/agent_service.py`
**Method**: `_generate_visualization_data()`

**New Method**:
- **Accept user visualization preferences** (optional parameter)
- **Analyze agent purpose** to suggest appropriate visualizations
- **Generate visualization configuration** using LLM
- **Return structured JSON** separate from raw data

**Input Parameters**:
- `query_result`: The data fetched from query
- `agent_purpose`: Agent's prompt/description
- `user_preferences`: Optional user-specified visualization approach
- `data_summary`: Summary of data structure (columns, types, row count)

**Output Structure**:
```json
{
  "visualization_config": {
    "charts": [
      {
        "type": "pie|bar|line|area|scatter",
        "title": "Chart Title",
        "description": "What this chart shows",
        "data": [...],
        "xAxis": "field_name",
        "yAxis": "field_name",
        "groupBy": "field_name",
        "aggregation": "sum|count|avg|max|min"
      }
    ],
    "recommended_charts": ["pie", "bar"],
    "insights": "AI-generated insights about the data"
  },
  "raw_data": {...}  // Original query result
}
```

#### 2.2 LLM Visualization Generation Prompt
**File**: `backend/services/agent_service.py`
**Method**: `_generate_visualization_config()`

**Prompt Structure**:
```
Based on the agent's purpose and the data structure, generate visualization configurations.

Agent Purpose: {agent_purpose}
Data Structure: {columns, types, sample_rows}
User Preferences: {user_preferences or "auto"}

Generate JSON configuration for visualizations that best represent this data.
Consider:
- Agent's mission (what insights are we trying to show?)
- Data types (categorical vs numeric)
- Data relationships (grouping, aggregations)
- Chart types appropriate for the data
```

#### 2.3 Backend API Changes
**File**: `backend/main.py`

**Changes**:
- Add `visualization_preferences` parameter to `ExecuteAgentRequest`
- Include `visualization_config` in `ExecuteAgentResponse`
- Generate visualization config during agent execution

**Request Model Update**:
```python
class ExecuteAgentRequest(BaseModel):
    query: Optional[str] = None
    tool_configs: Optional[Dict[str, Dict[str, str]]] = None
    visualization_preferences: Optional[str] = None  # NEW: User's visualization approach
```

**Response Model Update**:
```python
class ExecuteAgentResponse(BaseModel):
    # ... existing fields ...
    visualization_config: Optional[Dict[str, Any]] = None  # NEW: Structured visualization data
```

#### 2.4 Frontend Integration
**File**: `frontend/src/components/WorkflowCanvas.tsx`

**Changes**:
- Add optional input field for visualization preferences
- Display visualization config if provided
- Fall back to current auto-generation if no config

**File**: `frontend/src/components/DataVisualization.tsx`

**Changes**:
- Accept `visualization_config` prop
- Use config if provided, otherwise use current logic
- Render charts based on config structure

#### 2.5 Visualization Config Structure
**File**: `backend/services/agent_service.py`

**Config Schema**:
```python
{
    "charts": [
        {
            "id": "chart_1",
            "type": "pie",  # pie, bar, line, area, scatter, table
            "title": "Vendor Distribution",
            "description": "Shows distribution of invoices by vendor",
            "data_source": {
                "group_by": "vendor_name",
                "aggregate": {
                    "field": "total_amount",
                    "function": "sum"
                }
            },
            "config": {
                "colors": ["#3B82F6", "#8B5CF6", "#EC4899", ...],
                "show_legend": True,
                "show_labels": True
            }
        },
        {
            "id": "chart_2",
            "type": "bar",
            "title": "Monthly Spending",
            "description": "Total spending by month",
            "data_source": {
                "x_axis": "month",
                "y_axis": "total_amount",
                "group_by": "vendor_name"
            },
            "config": {
                "stacked": False,
                "orientation": "vertical"
            }
        }
    ],
    "insights": "AI-generated insights about the data patterns",
    "recommended_view": "dashboard"  # dashboard, single_chart, table_only
}
```

---

## Implementation Order

### Phase 1: Query Accuracy (Priority 1)
1. ✅ Enhance schema inspection with type information
2. ✅ Add column type validation to query generation
3. ✅ Improve query correction with type checking
4. ✅ Add pre-execution validation
5. ✅ Test with various query scenarios

### Phase 2: Visualization Generation (Priority 2)
1. ✅ Create visualization config generation method
2. ✅ Add LLM prompt for visualization generation
3. ✅ Update backend API models
4. ✅ Integrate into agent execution flow
5. ✅ Update frontend to use visualization config
6. ✅ Add fallback to current visualization

---

## Files to Modify

### Backend
1. `backend/services/agent_service.py`
   - `_build_query_template()` - Add type validation
   - `_fix_sql_syntax_error()` - Enhance with type checking
   - `_inspect_schema_for_prompt()` - Return structured types
   - `_validate_query_before_execution()` - NEW method
   - `_generate_visualization_config()` - NEW method
   - `_execute_with_guidance()` - Add visualization generation
   - `execute_agent_with_ai_streaming()` - Include visualization config

2. `backend/main.py`
   - `ExecuteAgentRequest` - Add visualization_preferences
   - `ExecuteAgentResponse` - Add visualization_config

3. `backend/tools/postgres_connector.py`
   - `get_table_schema()` - Ensure returns column types clearly

### Frontend
1. `frontend/src/components/WorkflowCanvas.tsx`
   - Add visualization preferences input
   - Pass preferences to API
   - Handle visualization_config in response

2. `frontend/src/components/DataVisualization.tsx`
   - Accept visualization_config prop
   - Use config if provided
   - Fallback to current logic

3. `frontend/src/services/api.ts`
   - Update ExecuteAgentRequest interface
   - Update ExecuteAgentResponse interface

---

## Testing Strategy

### Query Accuracy
1. Test query generation with various column types
2. Test query correction with type mismatches
3. Test pre-execution validation catches errors
4. Test with complex queries (multiple joins, aggregations)

### Visualization Generation
1. Test with user preferences provided
2. Test without preferences (auto-generation)
3. Test with different data types (numeric, categorical, dates)
4. Test visualization config structure is valid
5. Test frontend renders config correctly

---

## Success Criteria

### Query Accuracy
- ✅ All generated queries use correct column types
- ✅ Query correction fixes type mismatches
- ✅ Pre-execution validation catches errors before execution
- ✅ No more "column does not exist" or "cannot cast" errors

### Visualization Generation
- ✅ Visualization config generated based on agent purpose
- ✅ User preferences are respected when provided
- ✅ Falls back to current visualization when no config
- ✅ Visualization JSON is structured and separate from raw data
- ✅ Frontend renders visualizations correctly

---

## Estimated Effort
- **Query Accuracy**: 6-8 hours
- **Visualization Generation**: 8-10 hours
- **Total**: 14-18 hours
