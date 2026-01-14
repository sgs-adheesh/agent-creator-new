import uuid
from datetime import datetime
from typing import Dict, Any, List
import os
import sys
import importlib
import csv
import io
import json
import base64
import logging
from pathlib import Path
from config import settings
from langchain.agents import create_openai_functions_agent, AgentExecutor
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_models import ChatOllama
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from storage import AgentStorage

logger = logging.getLogger(__name__)

# Import ToolAnalyzer (with error handling to avoid circular imports)
try:
    from services.tool_analyzer import ToolAnalyzer
    TOOL_ANALYZER_AVAILABLE = True
except ImportError:
    ToolAnalyzer = None
    TOOL_ANALYZER_AVAILABLE = False

try:
    from services.semantic_service import SemanticService
    SEMANTIC_SERVICE_AVAILABLE = True
except ImportError:
    SemanticService = None
    SEMANTIC_SERVICE_AVAILABLE = False


class AgentService:
    """Service for creating and executing agents"""
    
    def __init__(self):
        self.storage = AgentStorage()
        
        # Initialize LLM based on configuration
        if settings.use_openai and settings.openai_api_key:
            self.llm = ChatOpenAI(
                model=settings.openai_model,
                api_key=settings.openai_api_key,
                temperature=0.7
            )
            # Store OpenAI config for streaming
            self.use_openai = True
            self.openai_api_key = settings.openai_api_key
            self.openai_model = settings.openai_model
        else:
            self.llm = ChatOllama(
                base_url=settings.ollama_base_url,
                model=settings.ollama_model,
                temperature=0.7
            )
        
        # Load all available tools dynamically
        self.tools = self._load_all_tools()
        
        # Initialize semantic service
        if SEMANTIC_SERVICE_AVAILABLE:
            try:
                self.semantic_service = SemanticService()
            except Exception as e:
                logger.warning(f"Failed to initialize SemanticService: {e}")
                self.semantic_service = None
        else:
            self.semantic_service = None
    
    def _load_all_tools(self) -> List:
        """
        Dynamically load all tools from the tools directory
        
        Returns:
            List of LangChain tools
        """
        tools = []
        tools_dir = Path(__file__).parent.parent / "tools"
        
        # Get all .py files in tools directory
        for tool_file in tools_dir.glob("*.py"):
            # Skip __init__.py and base_tool.py
            if tool_file.name.startswith("__") or tool_file.name == "base_tool.py":
                continue
            
            try:
                # Import the module
                module_name = f"tools.{tool_file.stem}"
                
                # Clear from cache to force reimport
                if module_name in sys.modules:
                    importlib.reload(sys.modules[module_name])
                else:
                    module = importlib.import_module(module_name)
                
                module = sys.modules.get(module_name) or importlib.import_module(module_name)
                
                # Find the tool class (should end with 'Connector' or 'Writer')
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    # Check if it's a class and has the required methods
                    if (isinstance(attr, type) and 
                        (attr_name.endswith('Connector') or attr_name.endswith('Writer')) and
                        hasattr(attr, 'to_langchain_tool')):
                        # Instantiate and convert to LangChain tool
                        tool_instance = attr()
                        tools.append(tool_instance.to_langchain_tool())
                        print(f"✅ Loaded tool: {attr_name}")
                        
                        # Check if this tool also has a schema inspection tool
                        if hasattr(tool_instance, 'to_langchain_schema_tool'):
                            schema_tool = tool_instance.to_langchain_schema_tool()
                            tools.append(schema_tool)
                            print(f"📊 Loaded schema tool: {schema_tool.name}")
                        
                        break
                        
            except ModuleNotFoundError as e:
                print(f"⚠️ Could not load tool from {tool_file.name}: {e}")
                dep_name = str(e).split("'")[1] if "'" in str(e) else "unknown"
                print(f"   💡 Install missing dependency: pip install {dep_name}")
            except Exception as e:
                print(f"⚠️ Could not load tool from {tool_file.name}: {e}")
        
        print(f"\nTotal tools loaded: {len(tools)}\n")
        return tools

    def _get_agent_templates_summary(self) -> str:
        """
        Load and summarize existing agent templates to use as reference for the LLM
        """
        try:
            # Path relative to backend/services/agent_service.py -> backend/templates/agent_templates.json
            templates_file = Path(__file__).parent.parent / "templates" / "agent_templates.json"
            
            if not templates_file.exists():
                logger.warning(f"Templates file not found at {templates_file}")
                return ""
            
            with open(templates_file, 'r', encoding='utf-8') as f:
                templates = json.load(f)
            
            summary_parts = []
            for t in templates:
                template_data = t.get("template", {})
                summary = (
                    f"Template Name: {t.get('name')}\n"
                    f"Description: {t.get('description')}\n"
                    f"Prompt: {template_data.get('prompt')}\n"
                    f"Tools: {', '.join(template_data.get('tools', []))}\n"
                )
                summary_parts.append(summary)
            
            return "\n---\n".join(summary_parts)
        except Exception as e:
            logger.error(f"Error loading agent templates summary: {e}")
            return ""

    def _get_agent_templates(self) -> List[Dict[str, Any]]:
        """
        Load raw agent templates list
        """
        try:
            templates_file = Path(__file__).parent.parent / "templates" / "agent_templates.json"
            if not templates_file.exists():
                return []
            
            with open(templates_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading agent templates: {e}")
            return []
    
    def reload_tools(self):
        """Reload all tools from directory (useful after generating new tools)"""
        self.tools = self._load_all_tools()
    
    def _format_output(self, output: str, output_format: str, intermediate_steps: List, agent_data: Dict[str, Any] = None, visualization_preferences: str = None) -> Dict[str, Any]:
        """
        Format agent output based on the specified output_format
        
        Args:
            output: Raw output from agent
            output_format: Desired format (text, json, csv, table)
            intermediate_steps: Execution steps from LangChain (list of tuples)
            agent_data: Full agent metadata (name, description, use_cases, etc.)
            
        Returns:
            Formatted response dictionary
        """
        print(f"\n🔧 _format_output called with {len(intermediate_steps)} intermediate steps")
        
        # Convert LangChain intermediate_steps tuples to serializable dictionaries
        serialized_steps = []
        if intermediate_steps:
            for idx, step in enumerate(intermediate_steps):
                print(f"  Step {idx}: type={type(step)}, is_tuple={isinstance(step, tuple)}, is_dict={isinstance(step, dict)}")
                
                # Handle tuple format (standard LangChain execution)
                if isinstance(step, tuple) and len(step) >= 2:
                    action, result = step[0], step[1]
                    step_dict = {
                        "action": {
                            "tool": getattr(action, 'tool', None),
                            "tool_input": getattr(action, 'tool_input', None),
                            "log": getattr(action, 'log', None)
                        },
                        "result": str(result)
                    }
                    serialized_steps.append(step_dict)
                    print(f"    ✓ Serialized tuple - tool: {step_dict['action']['tool']}")
                
                # Handle dict format (fast path execution guidance)
                elif isinstance(step, dict):
                    # Already in dict format from fast path
                    tool_name = step.get('tool_name') or step.get('action', {}).get('tool')
                    result_data = step.get('result', '')
                    
                    # Keep result as-is if it's already a dict, otherwise convert to string
                    if isinstance(result_data, dict):
                        # Keep dict structure for query results
                        result_value = result_data
                    else:
                        result_value = str(result_data)
                    
                    step_dict = {
                        "action": {
                            "tool": tool_name,
                            "tool_input": step.get('tool_input'),
                            "log": step.get('log')
                        },
                        "result": result_value
                    }
                    serialized_steps.append(step_dict)
                    print(f"    ✓ Serialized dict - tool: {tool_name}, result type: {type(result_value)}")
                
                else:
                    logger.debug(f"Skipped - unknown format")
        
        print(f"  → Serialized {len(serialized_steps)} steps")
        
        base_response = {
            "success": True,
            "output": output,
            "intermediate_steps": serialized_steps,
            "output_format": output_format
        }
        
        # Generate summary from query results
        summary = self._generate_summary_from_results(intermediate_steps, agent_data=agent_data)
        if summary:
            base_response["summary"] = summary
            print(f"\n📊 Summary Generated:")
            print(f"  - Total records: {summary.get('total_records', 'N/A')}")
            print(f"  - Has numeric analysis: {'numeric_analysis' in summary}")
            print(f"  - Has date analysis: {'date_analysis' in summary}")
            print(f"  - Has categorical analysis: {'categorical_analysis' in summary}")
            if 'ai_summary' in summary:
                print(f"  - Has AI summary: YES ({len(summary.get('ai_summary', ''))} chars)")
            if 'full_summary' in summary:
                print(f"\n  Full Summary Preview:")
                print(f"  {summary['full_summary'][:500]}...")
        else:
            print(f"\n⚠️ No summary generated (no query results found)")
            print(f"  🔍 Intermediate steps count: {len(intermediate_steps)}")
            print(f"  🔍 Steps preview: {[type(s).__name__ for s in intermediate_steps[:3]]}")
        
        # 🎨 ALWAYS extract table_data for visualization (regardless of output_format)
        table_data = self._extract_table_from_output(output, intermediate_steps)
        if table_data:
            base_response["table_data"] = table_data
            print(f"\n📊 Table data extracted for visualization: {table_data.get('row_count', 0)} rows")
            print(f"  📋 Columns: {table_data.get('columns', [])}")
            
            # Generate visualization config if agent data is available
            if agent_data:
                print(f"  🎯 Agent data available, generating visualization config...")
                print(f"  📝 Visualization preferences: {visualization_preferences}")
                agent_purpose = agent_data.get('prompt', '') or agent_data.get('description', '')
                
                # Note: streaming_callback is not available in _format_output context
                # Visualization streaming will be handled in execute_agent_with_ai_streaming
                try:
                    visualization_config = self._generate_visualization_config(
                        query_result=base_response,
                        agent_purpose=agent_purpose,
                        user_preferences=visualization_preferences,
                        streaming_callback=None  # Will be set in streaming context
                    )
                    
                    if visualization_config:
                        # 🐍 Python data formation step to ensure robustness
                        visualization_config = self._form_visualization_data(table_data, visualization_config)
                        base_response["visualization_config"] = visualization_config
                        print(f"  ✅ Visualization config generated and added to response")
                    else:
                        print(f"  ⚠️ _generate_visualization_config returned None")
                except Exception as e:
                    print(f"  ❌ Error in _generate_visualization_config: {e}")
                    import traceback
                    traceback.print_exc()
                    visualization_config = None
                
                if not visualization_config:
                    # Fallback: Create basic visualization config from table_data
                    print(f"  ⚠️ Visualization config generation returned None, creating fallback config...")
                    if table_data and table_data.get('rows'):
                        # Extract requested types from preferences
                        # Parse chart types from visualization preferences (same logic as _generate_visualization_config)
                        requested_types = []
                        if visualization_preferences:
                            prefs_lower = visualization_preferences.lower().strip()
                            
                            # Try comma-separated parsing first (checkbox format)
                            parts = [p.strip() for p in prefs_lower.split(',')]
                            supported_types = {
                                "pie": "pie", "bar": "bar", "line": "line", "area": "area",
                                "scatter": "scatter", "radar": "radar", "radialbar": "radialbar",
                                "radial": "radialbar", "composed": "composed", "mixed": "composed",
                                "funnel": "funnel", "treemap": "treemap"
                            }
                            
                            for part in parts:
                                for chart_key, chart_type in supported_types.items():
                                    if chart_key == part or part.startswith(chart_key + " ") or part == chart_key + "chart":
                                        normalized_type = supported_types[chart_key]
                                        if normalized_type not in requested_types:
                                            requested_types.append(normalized_type)
                                        break
                            
                            # Fallback to substring search if no matches
                            if not requested_types:
                                for chart_key, chart_type in supported_types.items():
                                    if chart_key in prefs_lower:
                                        normalized_type = supported_types[chart_key]
                                        if normalized_type not in requested_types:
                                            requested_types.append(normalized_type)
                        
                        # Limit to 4 chart types (matching frontend limit)
                        if len(requested_types) > 4:
                            print(f"  ⚠️ Limiting requested chart types from {len(requested_types)} to 4")
                            requested_types = requested_types[:4]
                        
                        # Create minimal fallback config
                        fallback_config = {
                            "charts": [],
                            "insights": "Visualization configuration generated from data structure.",
                            "recommended_view": "dashboard"
                        }
                        
                        # Add at least pie and bar if no preferences specified
                        if not requested_types:
                            requested_types = ["pie", "bar"]
                        
                        # Try to create charts from requested types
                        rows = table_data.get('rows', [])
                        columns = table_data.get('columns', [])
                        if rows and columns:
                            # Analyze fields
                            first_row = rows[0]
                            numeric_fields = []
                            categorical_fields = []
                            
                            for col in columns:
                                if col in first_row:
                                    value = first_row[col]
                                    if isinstance(value, dict) and 'value' in value:
                                        value = value['value']
                                    if isinstance(value, (int, float)) or (isinstance(value, str) and value.replace('.', '').replace('-', '').isdigit()):
                                        if 'date' not in col.lower() and 'time' not in col.lower():
                                            numeric_fields.append(col)
                                    elif isinstance(value, str) and 'date' not in col.lower() and 'time' not in col.lower():
                                        categorical_fields.append(col)
                            
                            # Create charts for requested types
                            chart_id = 1
                            for chart_type in requested_types[:5]:  # Limit to 5 charts
                                if chart_type == 'pie' and categorical_fields and numeric_fields:
                                    fallback_config["charts"].append({
                                        "id": f"fallback_{chart_id}",
                                        "type": "pie",
                                        "title": f"{numeric_fields[0]} by {categorical_fields[0]}",
                                        "description": "Distribution analysis",
                                        "data_source": {
                                            "group_by": categorical_fields[0],
                                            "aggregate": {"field": numeric_fields[0], "function": "sum"}
                                        },
                                        "config": {"colors": ["#6366f1", "#8b5cf6", "#ec4899"]}
                                    })
                                    chart_id += 1
                                elif chart_type == 'bar' and categorical_fields and numeric_fields:
                                    fallback_config["charts"].append({
                                        "id": f"fallback_{chart_id}",
                                        "type": "bar",
                                        "title": f"{numeric_fields[0]} by {categorical_fields[0]}",
                                        "description": "Comparison analysis",
                                        "data_source": {
                                            "group_by": categorical_fields[0],
                                            "aggregate": {"field": numeric_fields[0], "function": "sum"}
                                        },
                                        "config": {"colors": ["#10b981", "#3b82f6"], "orientation": "vertical"}
                                    })
                                    chart_id += 1
                                elif chart_type == 'line' and categorical_fields and numeric_fields:
                                    fallback_config["charts"].append({
                                        "id": f"fallback_{chart_id}",
                                        "type": "line",
                                        "title": f"{numeric_fields[0]} over {categorical_fields[0]}",
                                        "description": "Trend analysis",
                                        "data_source": {
                                            "x_axis": categorical_fields[0],
                                            "y_axis": numeric_fields[0]
                                        },
                                        "config": {"colors": ["#2563EB"]}
                                    })
                                    chart_id += 1
                                elif chart_type == 'area' and categorical_fields and numeric_fields:
                                    fallback_config["charts"].append({
                                        "id": f"fallback_{chart_id}",
                                        "type": "area",
                                        "title": f"{numeric_fields[0]} over {categorical_fields[0]}",
                                        "description": "Accumulation analysis",
                                        "data_source": {
                                            "x_axis": categorical_fields[0],
                                            "y_axis": numeric_fields[0]
                                        },
                                        "config": {"colors": ["#8B5CF6"]}
                                    })
                                    chart_id += 1
                                elif chart_type == 'scatter' and len(numeric_fields) >= 2:
                                    fallback_config["charts"].append({
                                        "id": f"fallback_{chart_id}",
                                        "type": "scatter",
                                        "title": f"{numeric_fields[1]} vs {numeric_fields[0]}",
                                        "description": "Relationship analysis",
                                        "data_source": {
                                            "x_axis": numeric_fields[0],
                                            "y_axis": numeric_fields[1]
                                        },
                                        "config": {"colors": ["#F59E0B"]}
                                    })
                                    chart_id += 1
                            
                            if fallback_config["charts"]:
                                base_response["visualization_config"] = fallback_config
                                print(f"  ✅ Created fallback visualization config with {len(fallback_config['charts'])} chart(s)")
                            else:
                                print(f"  ⚠️ Could not create fallback charts - insufficient data fields")
                                # Create minimal config with at least one chart if possible
                                if numeric_fields and categorical_fields:
                                    base_response["visualization_config"] = {
                                        "charts": [{
                                            "id": "minimal_1",
                                            "type": "bar",
                                            "title": f"{numeric_fields[0]} by {categorical_fields[0]}",
                                            "description": "Basic visualization",
                                            "data_source": {
                                                "group_by": categorical_fields[0],
                                                "aggregate": {"field": numeric_fields[0], "function": "sum"}
                                            },
                                            "config": {"colors": ["#6366f1"]}
                                        }],
                                        "insights": "Basic visualization generated from available data.",
                                        "recommended_view": "dashboard"
                                    }
                                    print(f"  ✅ Created minimal visualization config")
                    else:
                        print(f"  ⚠️ No table_data rows available for fallback visualization")
                
                # Final check: ensure visualization_config is always present if we have table_data
                if table_data and table_data.get('rows') and 'visualization_config' not in base_response:
                    print(f"  ⚠️ WARNING: visualization_config missing despite having table_data - this should not happen!")
                    # Last resort: create absolute minimal config
                    rows = table_data.get('rows', [])
                    columns = table_data.get('columns', [])
                    if rows and columns:
                        first_row = rows[0]
                        # Find any numeric and categorical field
                        for col in columns:
                            if col in first_row:
                                value = first_row[col]
                                if isinstance(value, dict) and 'value' in value:
                                    value = value['value']
                                if isinstance(value, (int, float)) or (isinstance(value, str) and value.replace('.', '').replace('-', '').isdigit()):
                                    numeric_field = col
                                    break
                        for col in columns:
                            if col in first_row and col != numeric_field:
                                categorical_field = col
                                break
                        
                        if 'numeric_field' in locals() and 'categorical_field' in locals():
                            base_response["visualization_config"] = {
                                "charts": [{
                                    "id": "emergency_1",
                                    "type": "bar",
                                    "title": f"Data visualization",
                                    "description": "Emergency fallback visualization",
                                    "data_source": {
                                        "group_by": categorical_field,
                                        "aggregate": {"field": numeric_field, "function": "sum"}
                                    },
                                    "config": {"colors": ["#6366f1"]}
                                }],
                                "insights": "Visualization generated from data structure.",
                                "recommended_view": "dashboard"
                            }
                            print(f"  ✅ Created emergency visualization config")
        
        # TEXT format (default) - return as-is
        if output_format == "text":
            return base_response
        
        # JSON format - try to parse output as JSON
        elif output_format == "json":
            try:
                # Try to extract JSON from output
                json_data = json.loads(output)
                base_response["json_data"] = json_data
                base_response["output"] = json.dumps(json_data, indent=2)
            except:
                # If output is not valid JSON, wrap it
                base_response["json_data"] = {"result": output}
                base_response["output"] = json.dumps({"result": output}, indent=2)
            return base_response
        
        # CSV format - generate downloadable CSV
        elif output_format == "csv":
            csv_data = self._generate_csv_from_output(output, intermediate_steps)
            if csv_data:
                # Encode CSV as base64 for download
                csv_base64 = base64.b64encode(csv_data.encode('utf-8')).decode('utf-8')
                base_response["csv_data"] = csv_base64
                base_response["csv_filename"] = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                base_response["download_link"] = f"data:text/csv;base64,{csv_base64}"
                print(f"\n📥 CSV Response:")
                print(f"  - csv_filename: {base_response['csv_filename']}")
                print(f"  - download_link length: {len(base_response['download_link'])} characters")
                print(f"  - output_format: {base_response['output_format']}")
            else:
                print(f"\n⚠️ CSV data is None - no download link created")
            return base_response
        
        # TABLE format - table_data already extracted above
        elif output_format == "table":
            return base_response
        
        # Unknown format - return as text
        else:
            return base_response
    
    def _form_visualization_data(self, table_data: Dict[str, Any], visualization_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Form structured data for visualization charts using Python aggregation
        
        Args:
            table_data: Raw query result data with rows and columns
            visualization_config: The visualization configuration from LLM
            
        Returns:
            Updated visualization configuration with populated data
        """
        if not table_data or not table_data.get('rows') or not visualization_config or not visualization_config.get('charts'):
            return visualization_config
            
        rows = table_data.get('rows', [])
        print(f"  📊 Python Data Formation: Processing {len(rows)} rows for {len(visualization_config.get('charts', []))} charts")
        
        for chart in visualization_config.get('charts', []):
            try:
                data_source = chart.get('data_source', {})
                chart_type = chart.get('type')
                
                # Settle on a label for the chart
                # Grouping Logic (for Pie, Bar, Treemap, etc.)
                if 'group_by' in data_source and 'aggregate' in data_source:
                    group_field = data_source['group_by']
                    agg_config = data_source['aggregate'] # {field, function}
                    
                    if isinstance(agg_config, dict):
                        agg_field = agg_config.get('field')
                        agg_func = agg_config.get('function', 'sum').lower()
                    else:
                        # Handle case where aggregate might be just a string
                        agg_field = str(agg_config)
                        agg_func = 'sum'
                    
                    if not group_field or not agg_field:
                        continue
                        
                    # Perform aggregation
                    groups = {}
                    for row in rows:
                        # Get group key
                        key = row.get(group_field, 'Unknown')
                        if key is None: key = 'Unknown'
                        if isinstance(key, dict): key = str(key)
                        
                        # Get value
                        val = row.get(agg_field, 0)
                        try:
                            val = float(val) if val is not None else 0
                        except (ValueError, TypeError):
                            val = 0
                            
                        if key not in groups:
                            groups[key] = []
                        groups[key].append(val)
                    
                    # Compute final values
                    chart_data = []
                    for key, values in groups.items():
                        if agg_func == 'sum':
                            result_val = sum(values)
                        elif agg_func in ['avg', 'mean', 'average']:
                            result_val = sum(values) / len(values) if values else 0
                        elif agg_func == 'count':
                            result_val = len(values)
                        elif agg_func == 'min':
                            result_val = min(values) if values else 0
                        elif agg_func == 'max':
                            result_val = max(values) if values else 0
                        else:
                            result_val = sum(values) 
                            
                        chart_data.append({
                            "name": str(key),
                            "value": result_val,
                            agg_field: result_val # Include original field name too
                        })
                    
                    # Sort by value desc for better viz
                    chart_data.sort(key=lambda x: x['value'], reverse=True)
                    
                    # Limit to top 20 for readability
                    if len(chart_data) > 20:
                        chart_data = chart_data[:20]
                        
                    chart['data'] = chart_data
                    print(f"    ✓ Formed data for chart {chart.get('id')} ({chart_type}): {len(chart_data)} points")

                # XY Logic (for Scatter, Line over time)
                elif 'x_axis' in data_source and 'y_axis' in data_source:
                    x_field = data_source['x_axis']
                    y_field = data_source['y_axis']
                    
                    chart_data = []
                    for row in rows:
                        # Only include rows that have the fields
                        if x_field in row or y_field in row:
                            x_val = row.get(x_field, '')
                            y_val = row.get(y_field, 0)
                            
                            # Clean Y value
                            try:
                                y_val = float(y_val) if y_val is not None else 0
                            except:
                                y_val = 0
                            
                            # 🏷️ Smart Naming Logic: prioritize Batch Name > Invoice Number > Vendor Name
                            display_name = str(x_val) # Default to X value
                            
                            # Check for specific identifier fields
                            if row.get('batch_name'):
                                display_name = str(row['batch_name'])
                            elif row.get('invoice_number'):
                                display_name = str(row['invoice_number'])
                            elif row.get('inv_num'):
                                display_name = str(row['inv_num'])
                            elif row.get('vendor_name') and chart_type == 'scatter':
                                # For scatter plots, vendor name is often a good label if no invoice/batch info
                                display_name = str(row['vendor_name'])
                                
                            item = {
                                "name": display_name,
                                x_field: x_val,
                                y_field: y_val,
                                "value": y_val # Fallback
                            }
                            # Copy other fields for tooltip context (careful not to copy huge objects)
                            for k, v in row.items():
                                if k not in item and isinstance(v, (str, int, float, bool, type(None))):
                                    item[k] = v
                                    
                            chart_data.append(item)
                            
                    # Sort line/area charts by X axis if possible (dates)
                    if chart_type in ['line', 'area', 'candlestick']:
                        try:
                            # Try to sort, assuming comparable types
                            chart_data.sort(key=lambda x: x.get(x_field) or '')
                        except:
                            pass
                            
                    chart['data'] = chart_data
                    print(f"    ✓ Formed data for chart {chart.get('id')} ({chart_type}): {len(chart_data)} points")
                    
                 # Radar/Radial Logic (Group by + Metrics)
                elif 'group_by' in data_source and 'metrics' in data_source:
                    group_field = data_source['group_by']
                    metrics = data_source['metrics']
                    
                    if not isinstance(metrics, list):
                        metrics = [metrics]
                    
                    chart_data = []
                    # For Radar, take top 12 items
                    for row in rows[:12]: 
                        # Use group field, but can fallback to friendly names if group field is just an ID?
                        # For now, stick to group_field as that's what the chart expects for axes
                        item = {"name": str(row.get(group_field, 'Unknown'))}
                        
                        for m in metrics:
                            val = row.get(m, 0)
                            try: val = float(val) 
                            except: val = 0
                            item[m] = val
                            
                        # Pass through other numeric fields for flexibility
                        for k, v in row.items():
                            if k not in item and isinstance(v, (int, float)):
                                item[k] = v
                                
                        chart_data.append(item)
                        
                    chart['data'] = chart_data
                    print(f"    ✓ Formed data for chart {chart.get('id')} ({chart_type}) with metrics: {len(chart_data)} points")
                
                # Fallback: if data is missing, just populate strictly from rows (dumb copy)
                elif 'data' not in chart or not chart['data']:
                    print(f"    ℹ️ No specific data_source for chart {chart.get('id')}, copying raw rows")
                    # Smart copy: limit rows and simplify
                    simple_rows = []
                    for r in rows[:50]:
                        new_r = {}
                        for k, v in r.items():
                            if isinstance(v, (str, int, float, bool, type(None))): 
                                new_r[k] = v
                                # heuristic for 'value' if not present
                                if isinstance(v, (int, float)) and 'value' not in new_r:
                                     new_r['value'] = v
                        
                        # 🏷️ Smart Naming Logic for Fallback
                        if 'name' not in new_r:
                            if new_r.get('batch_name'):
                                new_r['name'] = str(new_r['batch_name'])
                            elif new_r.get('invoice_number'):
                                new_r['name'] = str(new_r['invoice_number'])
                            elif new_r.get('inv_num'):
                                new_r['name'] = str(new_r['inv_num'])
                            elif new_r.get('vendor_name'):
                                new_r['name'] = str(new_r['vendor_name'])
                            else:
                                # Pick first string field
                                for k, v in new_r.items():
                                    if isinstance(v, str):
                                        new_r['name'] = v
                                        break
                                if 'name' not in new_r:
                                    new_r['name'] = f"Item {len(simple_rows)+1}"
                        
                        simple_rows.append(new_r)
                    chart['data'] = simple_rows

            except Exception as e:
                print(f"    ⚠️ Error forming data for chart {chart.get('id')}: {e}")
                import traceback
                traceback.print_exc()
                
        return visualization_config

    def _generate_visualization_config(self, query_result: Dict[str, Any], agent_purpose: str, user_preferences: str = None, streaming_callback = None) -> Dict[str, Any]:
        """
        Generate visualization configuration using LLM based on agent purpose and data structure
        
        Args:
            query_result: Query result data (table_data with rows, columns, etc.)
            agent_purpose: Agent's prompt/description
            user_preferences: Optional user-specified visualization approach
            streaming_callback: Optional callback for streaming visualization generation steps
            
        Returns:
            Visualization configuration dictionary
        """
        try:
            from langchain_core.messages import HumanMessage
            
            if streaming_callback:
                streaming_callback({
                    "type": "ai_thinking",
                    "step": "visualization_analysis",
                    "message": "Analyzing data structure for visualization generation...",
                    "detail": "Examining columns, field types, and data patterns"
                })
            
            # Extract data structure
            table_data = query_result.get('table_data', {})
            rows = table_data.get('rows', [])
            columns = table_data.get('columns', [])
            row_count = table_data.get('row_count', len(rows))
            
            if not rows or len(rows) == 0:
                print("  ⚠️ No data available for visualization generation")
                if streaming_callback:
                    streaming_callback({
                        "type": "ai_thinking",
                        "step": "visualization_analysis",
                        "message": "⚠️ No data available for visualization",
                        "detail": "Skipping visualization generation"
                    })
                return None
            
            if streaming_callback:
                streaming_callback({
                    "type": "ai_thinking",
                    "step": "visualization_analysis",
                    "message": f"Found {row_count} rows with {len(columns)} columns",
                    "detail": f"Columns: {', '.join(columns[:5])}{'...' if len(columns) > 5 else ''}"
                })
            
            # Analyze data structure
            numeric_fields = []
            categorical_fields = []
            date_fields = []
            
            if rows:
                first_row = rows[0]
                for col in columns:
                    if col in first_row:
                        value = first_row[col]
                        # Handle JSONB structure
                        if isinstance(value, dict) and 'value' in value:
                            value = value['value']
                        
                        # Classify field type
                        if isinstance(value, (int, float)) or (isinstance(value, str) and value.replace('.', '').replace('-', '').isdigit()):
                            if 'date' not in col.lower() and 'time' not in col.lower():
                                numeric_fields.append(col)
                        elif isinstance(value, str):
                            # Check if it's a date string
                            if any(keyword in col.lower() for keyword in ['date', 'time', 'created', 'updated']):
                                date_fields.append(col)
                            else:
                                categorical_fields.append(col)
            
            # Build data summary - include actual data for LLM to process
            # Limit rows to prevent token overflow, but include enough for meaningful aggregation
            max_rows_for_prompt = min(100, len(rows))  # Include up to 100 rows for LLM processing
            data_rows_for_prompt = rows[:max_rows_for_prompt]
            
            data_summary = {
                "row_count": row_count,
                "columns": columns,
                "numeric_fields": numeric_fields[:8],  # More fields for better selection
                "categorical_fields": categorical_fields[:8],
                "date_fields": date_fields[:5],
                "sample_row": dict(list(first_row.items())[:10]) if rows else {},
                "all_data": data_rows_for_prompt  # Include actual data for LLM to process
            }
            
            if streaming_callback:
                streaming_callback({
                    "type": "ai_thinking",
                    "step": "visualization_analysis",
                    "message": "Classified data fields",
                    "detail": f"Numeric: {len(numeric_fields)}, Categorical: {len(categorical_fields)}, Date: {len(date_fields)}"
                })
            
            # Build LLM prompt
            preferences_text = user_preferences if user_preferences else "auto-generate appropriate visualizations"

            # Detect explicitly requested chart types from user preferences
            # Handle both checkbox format (comma-separated: "pie, bar, line") and text format
            requested_types = []
            if user_preferences:
                prefs_lower = user_preferences.lower().strip()
                
                # First, try to parse as comma-separated list (from checkbox selections)
                # Split by comma and clean each part
                parts = [p.strip() for p in prefs_lower.split(',')]
                
                # All supported chart types from Recharts
                supported_types = {
                    "pie": "pie",
                    "bar": "bar",
                    "stacked_bar": "stacked_bar",
                    "line": "line",
                    "area": "area",
                    "scatter": "scatter",
                    "bubble": "bubble", # Bubble is distinct (scatter + size)
                    "radar": "radar",
                    "radialbar": "radialbar",
                    "radial": "radialbar",
                    "composed": "composed",
                    "mixed": "composed",
                    "funnel": "funnel",
                    "treemap": "treemap",
                    "sankey": "sankey",
                    "heatmap": "heatmap",
                    "waterfall": "waterfall",
                    "candlestick": "candlestick",
                    "table": "table"
                }
                
                # Check each part for chart type matches
                for part in parts:
                    # Direct match (e.g., "pie", "bar chart", "line chart")
                    for chart_key, chart_type in supported_types.items():
                        # Match whole word or at start of string to avoid false matches
                        if chart_key == part or part.startswith(chart_key + " ") or part == chart_key + "chart":
                            normalized_type = supported_types[chart_key]
                            if normalized_type not in requested_types:
                                requested_types.append(normalized_type)
                            break
                
                # If no matches found from comma-separated parsing, fall back to substring search
                # (for text-based preferences like "I want a pie chart and bar chart")
                if not requested_types:
                    for chart_key, chart_type in supported_types.items():
                        if chart_key in prefs_lower:
                            normalized_type = supported_types[chart_key]
                            if normalized_type not in requested_types:
                                requested_types.append(normalized_type)
                
                # Limit to 4 chart types (matching frontend limit)
                if len(requested_types) > 4:
                    print(f"  ⚠️ Limiting requested chart types from {len(requested_types)} to 4 (frontend limit)")
                    requested_types = requested_types[:4]
                
                print(f"  📊 Detected chart types from preferences: {requested_types}")
            
            requested_types_str = ", ".join(requested_types) if requested_types else "none explicitly requested"
            
            # Helper functions for chart creation (defined before try block for use in exception handler)
            def pick_first_or_fallback(preferred_names, available):
                for name in preferred_names:
                    if name in available:
                        return name
                return available[0] if available else None
            
            def create_chart_for_type(chart_type: str, chart_id: str, cat_fields: list, num_fields: list, date_fields_list: list) -> dict:
                """Create a chart configuration for a missing chart type"""
                # Determine data source based on chart type
                if chart_type in ['pie', 'bar', 'radialbar', 'treemap']:
                    # Use group_by + aggregate
                    group_by_field = pick_first_or_fallback(
                        ['vendor_name', 'supplier_name', 'category', 'status', 'type'],
                        cat_fields
                    )
                    aggregate_field = pick_first_or_fallback(
                        ['duplicate_count', 'total', 'amount', 'count', 'quantity'],
                        num_fields
                    )
                    if group_by_field and aggregate_field:
                        return {
                            "id": chart_id,
                            "type": chart_type,
                            "title": f"{aggregate_field} by {group_by_field}",
                            "description": f"Auto-generated {chart_type} chart added to honor user preference.",
                            "data_source": {
                                "group_by": group_by_field,
                                "aggregate": {"field": aggregate_field, "function": "sum"}
                            },
                            "config": {"colors": ["#2563EB", "#10B981", "#F59E0B"]}
                        }
                elif chart_type in ['line', 'area']:
                    # Use x_axis + y_axis
                    x_axis_field = pick_first_or_fallback(
                        ['invoice_date', 'created_at', 'updated_at', 'vendor_name', 'category'],
                        date_fields_list + cat_fields
                    )
                    y_axis_field = pick_first_or_fallback(
                        ['duplicate_count', 'total', 'amount', 'count'],
                        num_fields
                    )
                    if x_axis_field and y_axis_field:
                        return {
                            "id": chart_id,
                            "type": chart_type,
                            "title": f"{y_axis_field} over {x_axis_field}",
                            "description": f"Auto-generated {chart_type} chart added to honor user preference.",
                            "data_source": {
                                "x_axis": x_axis_field,
                                "y_axis": y_axis_field
                            },
                            "config": {"colors": ["#2563EB"], "orientation": "horizontal"}
                        }
                elif chart_type == 'scatter':
                    # CRITICAL: Scatter MUST use x_axis + y_axis (both numeric), NEVER group_by
                    # Scatter charts need individual data points, not aggregated groups
                    if len(num_fields) >= 2:
                        return {
                            "id": chart_id,
                            "type": "scatter",
                            "title": f"{num_fields[1]} vs {num_fields[0]}",
                            "description": "Auto-generated scatter chart showing relationship between two numeric variables. Each point represents an individual data row.",
                            "data_source": {
                                "x_axis": num_fields[0],  # First numeric field
                                "y_axis": num_fields[1]   # Second numeric field
                            },
                            "config": {"colors": ["#F59E0B"]}
                        }
                    else:
                        print(f"    ⚠️ Cannot create scatter chart - need at least 2 numeric fields, found {len(num_fields)}")
                        return None
                elif chart_type == 'radar':
                    # Use group_by + metrics
                    group_by_field = pick_first_or_fallback(
                        ['vendor_name', 'supplier_name', 'category'],
                        cat_fields
                    )
                    if group_by_field and len(num_fields) >= 2:
                        return {
                            "id": chart_id,
                            "type": "radar",
                            "title": f"Multi-metric comparison by {group_by_field}",
                            "description": "Auto-generated radar chart added to honor user preference.",
                            "data_source": {
                                "group_by": group_by_field,
                                "metrics": num_fields[:5]
                            },
                            "config": {"colors": ["#8B5CF6"]}
                        }
                return None

            # Helper text for when specific types are requested
            required_charts_text = ""
            if requested_types:
                # e.g. "You MUST include at least one 'line' chart and one 'bar' chart"
                type_list = "', '".join(requested_types)
                required_charts_text = f"You MUST include at least one chart for EACH of these types: '{type_list}'.\n"
            
            visualization_prompt = f"""You are a Recharts specialist and expert data visualization analyst. Your job is to generate PERFECT visualization configurations that work flawlessly with Recharts library.

🎯 AGENT PURPOSE (CRITICAL - STRICTLY FOLLOW THIS):
{agent_purpose}

⚠️ MANDATORY REQUIREMENT: Every chart you generate MUST directly relate to and support the agent's purpose above. 
- If the agent is for "duplicate finder" → visualizations MUST show duplicate-related insights (duplicate counts, duplicate patterns, etc.)
- If the agent is for "invoice analysis" → visualizations MUST show invoice-related insights (totals, vendors, dates, etc.)
- If the agent is for "vendor management" → visualizations MUST show vendor-related insights
- The chart titles, descriptions, and field selections MUST align with the agent's purpose
- DO NOT create generic visualizations - make them purpose-specific

DATA STRUCTURE ANALYSIS:
- Total rows: {row_count}
- Available columns: {', '.join(columns[:15])}
- Numeric fields (for aggregations): {', '.join(numeric_fields[:8]) if numeric_fields else 'None'}
- Categorical fields (for grouping): {', '.join(categorical_fields[:8]) if categorical_fields else 'None'}
- Date/time fields (for trends): {', '.join(date_fields[:5]) if date_fields else 'None'}

USER VISUALIZATION PREFERENCES:
{preferences_text}

EXPLICITLY REQUESTED CHART TYPES: {requested_types_str}

QUERY RESULT DATA (use this to build actual chart data):
{json.dumps(data_summary.get('all_data', [])[:50], indent=2)}  // First 50 rows for processing

SAMPLE DATA (first row for reference):
{json.dumps(data_summary.get('sample_row', {}), indent=2)}

YOUR TASK:
Generate a comprehensive JSON visualization configuration that:
1. **STRICTLY follows the agent's purpose** - every chart must relate directly to what the agent does
2. Honors ALL user-requested chart types ({requested_types_str if requested_types_str != "none explicitly requested" else "auto-select based on data"})
3. Uses appropriate fields from the available data structure that align with agent purpose
4. Provides meaningful insights that support the agent's purpose
5. **CRITICAL: Follow Recharts data format requirements exactly**
6. Chart titles and descriptions must be purpose-specific (e.g., "Duplicate Invoices by Vendor" for duplicate finder, not generic "Data by Category")

REQUIRED JSON STRUCTURE:
{{
  "charts": [
    {{
      "id": "chart_1",
      "type": "pie|bar|stacked_bar|line|area|scatter|bubble|radar|radialbar|composed|funnel|treemap|sankey|heatmap|waterfall|candlestick|table",
      "title": "Descriptive title aligned with agent purpose",
      "description": "What this chart shows (purpose-specific)",
      "data": [
        // ⚠️ CRITICAL: You MUST include the actual processed data array here
        // Process the QUERY RESULT DATA above to build this array
        // For pie: [{{ "name": "Category1", "value": 100 }}, {{ "name": "Category2", "value": 200 }}]
        // For bar/line/area: [{{ "name": "X1", "field_name": 100 }}, {{ "name": "X2", "field_name": 200 }}]
        // For scatter/bubble: [{{ "name": "Point1", "x": 10, "y": 20, "z": 5 }}, ...] (z is size for bubble)
        // For heatmap: [{{ "x": "CategoryA", "y": "Monday", "value": 50 }}, ...]
        // For waterfall: [{{ "name": "Start", "value": [0, 100] }}, {{ "name": "Change", "value": [100, 150] }}] (value is [start, end] range)
        // For candlestick: [{{ "name": "2023-01-01", "open": 100, "close": 110, "high": 115, "low": 95 }}]
        // For sankey: {{ "nodes": [{{ "name": "Input" }}, {{ "name": "Process" }}], "links": [{{ "source": 0, "target": 1, "value": 100 }}] }} NOTE: Sankey data is an OBJECT with nodes/links arrays
        // For scatter: [{{"name": "Point1", "x_field": 10, "y_field": 20}}, ...]
        // For radar: [{{"name": "Category1", "metric1": 10, "metric2": 20}}, ...]
      ],
      "data_source": {{
        // Include for reference: which fields were used
        "group_by": "vendor_name",  // or x_axis/y_axis for line/area/scatter
        "aggregate": {{"field": "total", "function": "sum"}}  // or metrics array for radar
      }},
      "config": {{"colors": ["#4CAF50", "#2196F3"], "orientation": "vertical"}}
    }}
  ],
  "insights": "2-3 sentences about data patterns aligned with agent purpose",
  "recommended_view": "dashboard"
}}

⚠️ CRITICAL: You MUST process the QUERY RESULT DATA and build the actual "data" array for each chart.
DO NOT just specify data_source - you must include the processed data array!

🎯 RECHARTS DATA FORMAT REQUIREMENTS (CRITICAL - FOLLOW EXACTLY):

1. **PIE CHART** (type: "pie"):
   - REQUIRED: group_by (categorical) + aggregate (numeric field)
   - Data format: Array of {{name: string, value: number}}
   - Example: {{"group_by": "vendor_name", "aggregate": {{"field": "total", "function": "sum"}}}}
   - ❌ NEVER use x_axis/y_axis for pie charts

2. **BAR CHART** (type: "bar"):
   - OPTION A: group_by (categorical) + aggregate (numeric) - creates grouped bars
   - OPTION B: x_axis (categorical) + y_axis (numeric) - creates sequential bars
   - Data format: Array of {{name: string, [field]: number}}
   - Example A: {{"group_by": "vendor_name", "aggregate": {{"field": "total", "function": "sum"}}}}
   - Example B: {{"x_axis": "vendor_name", "y_axis": "total"}}
   - ✅ Prefer group_by + aggregate for better aggregation

3. **LINE CHART** (type: "line"):
   - REQUIRED: x_axis (categorical or date) + y_axis (numeric)
   - Data format: Array of {{name: string, [field]: number}}
   - Example: {{"x_axis": "vendor_name", "y_axis": "total"}}
   - ✅ Use date fields for x_axis if available for trends

4. **AREA CHART** (type: "area"):
   - REQUIRED: x_axis (categorical or date) + y_axis (numeric)
   - Data format: Array of {{name: string, [field]: number}}
   - Example: {{"x_axis": "vendor_name", "y_axis": "total"}}
   - ✅ Use date fields for x_axis if available for cumulative trends

5. **SCATTER CHART** (type: "scatter"):
   - REQUIRED: x_axis (NUMERIC field) + y_axis (NUMERIC field)
   - ⚠️ CRITICAL: BOTH axes MUST be numeric fields from the raw data
   - ⚠️ NEVER use group_by for scatter - it needs individual data points
   - Data format: Array of {{name: string, [x_field]: number, [y_field]: number}}
   - Example: {{"x_axis": "duplicate_count", "y_axis": "total"}}
   - ✅ Both fields must exist in numeric_fields list above
   - ❌ NEVER use: group_by for scatter charts

6. **RADAR CHART** (type: "radar"):
   - REQUIRED: group_by (categorical) + metrics (array of numeric fields)
   - Data format: Array of {{name: string, [metric1]: number, [metric2]: number, ...}}
   - Example: {{"group_by": "vendor_name", "metrics": ["total", "duplicate_count"]}}
   - ✅ Use 2-5 metrics for best visualization

7. **RADIALBAR CHART** (type: "radialbar"):
   - REQUIRED: group_by (categorical) + aggregate (numeric)
   - Data format: Array of {{name: string, value: number}}
   - Example: {{"group_by": "vendor_name", "aggregate": {{"field": "total", "function": "sum"}}}}
   - ✅ Similar to pie chart structure

8. **TREEMAP** (type: "treemap"):
   - REQUIRED: group_by (categorical) + aggregate (numeric)
   - Data format: Array of {{name: string, value: number}}
   - Example: {{"group_by": "vendor_name", "aggregate": {{"field": "total", "function": "sum"}}}}
   - ✅ Shows proportional distribution

CRITICAL RULES:
1. {required_charts_text if required_charts_text else "If user specified chart types, you MUST include at least one chart for EACH requested type."}
2. **NEVER use identifier fields** (invoice_number, id, uuid, code, reference, batch_names) for group_by or x_axis
3. **ALWAYS prefer descriptive fields** (vendor_name, supplier_name, category, status, type, name)
4. **For scatter charts:** 
   - MUST use x_axis + y_axis (both numeric)
   - NEVER use group_by (scatter needs individual points, not aggregated groups)
   - Both fields must be in the numeric_fields list
5. **For pie/bar/radialbar/treemap:** 
   - MUST use group_by (categorical) + aggregate (numeric)
   - aggregate.field must be a numeric field that makes sense to sum/count/avg
6. **For line/area:** 
   - MUST use x_axis + y_axis
   - Prefer date fields for x_axis if available
7. **Field validation:** Check that ALL fields you use actually exist in the columns list above

COMMON MISTAKES TO AVOID:
❌ Scatter chart with group_by → Use x_axis + y_axis instead
❌ Using identifier fields (invoice_number, id) for grouping → Use vendor_name, category, etc.
❌ Using non-numeric fields for scatter axes → Both must be numeric
❌ Missing aggregate field for pie/bar/radialbar/treemap → Always include aggregate
❌ Using wrong data_source pattern for chart type → Follow the patterns above exactly

FIELD SELECTION EXAMPLES:
✅ GOOD: 
  - Pie: {{"group_by": "vendor_name", "aggregate": {{"field": "total", "function": "sum"}}}}
  - Scatter: {{"x_axis": "duplicate_count", "y_axis": "total"}}
  - Bar: {{"group_by": "vendor_name", "aggregate": {{"field": "total", "function": "sum"}}}}
  - Line: {{"x_axis": "vendor_name", "y_axis": "total"}}

❌ BAD:
  - Scatter: {{"group_by": "vendor_name", "aggregate": {{"field": "total", "function": "sum"}}}} → Wrong pattern!
  - Pie: {{"x_axis": "vendor_name", "y_axis": "total"}} → Wrong pattern!
  - Any chart: {{"group_by": "invoice_number"}} → Identifier field!

ANALYSIS APPROACH (FOLLOW STRICTLY):
1. **FIRST: Read the agent purpose VERY carefully** - identify the key theme (duplicate finder, invoice analysis, vendor management, etc.)
2. **SECOND: Select fields that directly relate to the agent purpose**:
   - For duplicate finder: prioritize duplicate_count, invoice_number, vendor_name (fields that show duplicates)
   - For invoice analysis: prioritize total, amount, invoice_date, vendor_name (fields that show invoice data)
   - For vendor management: prioritize vendor_name, supplier_name, category (fields that show vendor data)
3. **THIRD: Create chart titles and descriptions that reflect the agent purpose**:
   - ✅ GOOD: "Duplicate Invoices by Vendor" (for duplicate finder)
   - ✅ GOOD: "Invoice Totals Over Time" (for invoice analysis)
   - ❌ BAD: "Data Distribution" (too generic, doesn't reflect purpose)
   - ❌ BAD: "Category Analysis" (unless agent is specifically for category analysis)
4. Analyze the user preferences - what chart types are explicitly requested?
5. For EACH requested chart type, select the CORRECT data_source pattern from above
6. Match available fields to chart requirements (check numeric_fields, categorical_fields lists)
7. Generate charts that provide meaningful insights that DIRECTLY support the agent's purpose
8. If user requested specific types, ensure ALL are included with correct data_source patterns
9. **VERIFY: Every chart title/description mentions or implies the agent's purpose**

Return ONLY valid JSON (no markdown, no code blocks, no explanations). The JSON must be parseable.

Visualization Configuration JSON:"""
            
            print(f"\n🎨 Generating visualization config for {row_count} rows...")
            
            if streaming_callback:
                streaming_callback({
                    "type": "ai_thinking",
                    "step": "visualization_generation",
                    "message": "🤖 Generating visualization configuration with AI...",
                    "detail": f"Analyzing agent purpose and user preferences: {preferences_text[:100]}"
                })
            
            response = self.llm.invoke([HumanMessage(content=visualization_prompt)])
            config_text = response.content.strip()
            
            if streaming_callback:
                streaming_callback({
                    "type": "ai_thinking",
                    "step": "visualization_generation",
                    "message": "✅ AI generated visualization configuration",
                    "detail": "Parsing and validating chart configurations..."
                })
            
            # Remove markdown code blocks if present
            if '```' in config_text:
                import re
                code_match = re.search(r'```(?:json)?\n(.*?)\n```', config_text, re.DOTALL)
                if code_match:
                    config_text = code_match.group(1).strip()
            
            # Clean up common JSON issues
            import re
            # Fix escaped quotes - LLM sometimes returns \"key" instead of "key"
            # The pattern shows: { \"charts": [ which means escaped quotes in property names
            # Replace all instances of \" with " (unescape quotes globally)
            config_text = config_text.replace('\\"', '"')
            
            # Remove trailing commas before closing braces/brackets
            config_text = re.sub(r',(\s*[}\]])', r'\1', config_text)
            
            # Remove any comments
            config_text = re.sub(r'//.*?$', '', config_text, flags=re.MULTILINE)
            config_text = re.sub(r'/\*.*?\*/', '', config_text, flags=re.DOTALL)
            
            print(f"  🔍 Cleaned JSON preview (first 300 chars): {config_text[:300]}")
            
            # Parse JSON
            try:
                visualization_config = json.loads(config_text)
                
                # Ensure base structure
                charts = visualization_config.get('charts') or []
                insights = visualization_config.get('insights')
                recommended_view = visualization_config.get('recommended_view')
                
                if not isinstance(charts, list):
                    charts = []
                visualization_config['charts'] = charts
                if not insights:
                    visualization_config['insights'] = "Data visualization generated successfully."
                if not recommended_view:
                    visualization_config['recommended_view'] = "dashboard"

                print(f"\n📊 FINAL VISUALIZATION CONFIG ({len(charts)} charts):")
                print(json.dumps(visualization_config, indent=2))
                print("-" * 50)

                # ✅ Guarantee ALL user-requested chart types are present
                existing_types = {str(c.get('type', '')).lower() for c in charts}

                # Check for missing chart types and add them
                missing_types = [t for t in requested_types if t not in existing_types]
                # Limit missing types to 4 total (including existing)
                max_additional = max(0, 4 - len(existing_types))
                if missing_types and max_additional > 0:
                    missing_types = missing_types[:max_additional]
                    print(f"  ➕ Adding {len(missing_types)} missing chart type(s): {', '.join(missing_types)}")
                    chart_counter = len(charts) + 1
                    for missing_type in missing_types:
                        chart_id = f"auto_{missing_type}_{chart_counter}"
                        new_chart = create_chart_for_type(missing_type, chart_id, categorical_fields, numeric_fields, date_fields)
                        if new_chart:
                            charts.append(new_chart)
                            print(f"    ✅ Added {missing_type} chart: {new_chart.get('title')}")
                            chart_counter += 1
                        else:
                            print(f"    ⚠️ Could not create {missing_type} chart - insufficient data fields")

                visualization_config['charts'] = charts
                
                chart_count = len(visualization_config.get('charts', []))
                chart_types = [c.get('type', 'unknown') for c in visualization_config.get('charts', [])]
                
                print(f"  ✅ Generated visualization config with {chart_count} chart(s)")
                
                if streaming_callback:
                    streaming_callback({
                        "type": "ai_thinking",
                        "step": "visualization_complete",
                        "message": f"✅ Visualization configuration complete",
                        "detail": f"Generated {chart_count} chart(s): {', '.join(chart_types)}"
                    })
                
                return visualization_config
                
            except json.JSONDecodeError as e:
                print(f"  ⚠️ Failed to parse visualization config JSON: {e}")
                print(f"  Response preview: {config_text[:500]}...")
                print(f"  Error at position: {e.pos if hasattr(e, 'pos') else 'unknown'}")
                
                # Try to recover by creating charts from requested types
                if requested_types:
                    print(f"  🔧 Attempting to recover from JSON error by creating charts from requested types...")
                    # Create a minimal valid config with requested chart types
                    # Limit to 4 chart types (matching frontend limit)
                    limited_types = requested_types[:4] if len(requested_types) > 4 else requested_types
                    if len(requested_types) > 4:
                        print(f"  ⚠️ Limiting recovery to 4 chart types (frontend limit)")
                    recovered_charts = []
                    chart_id = 1
                    for chart_type in limited_types:
                        chart_config = create_chart_for_type(chart_type, f"recovered_{chart_type}_{chart_id}", categorical_fields, numeric_fields, date_fields)
                        if chart_config:
                            recovered_charts.append(chart_config)
                            chart_id += 1
                    
                    if recovered_charts:
                        visualization_config = {
                            "charts": recovered_charts,
                            "insights": "Visualization configuration recovered after JSON parsing error.",
                            "recommended_view": "dashboard"
                        }
                        print(f"  ✅ Recovered {len(recovered_charts)} chart(s) from requested types")
                        if streaming_callback:
                            streaming_callback({
                                "type": "ai_thinking",
                                "step": "visualization_recovered",
                                "message": "✅ Recovered visualization config",
                                "detail": f"Created {len(recovered_charts)} chart(s) from requested types"
                            })
                        return visualization_config
                
                if streaming_callback:
                    streaming_callback({
                        "type": "ai_thinking",
                        "step": "visualization_error",
                        "message": "⚠️ JSON parsing error in visualization config",
                        "detail": f"Error: {str(e)}. Attempting recovery..."
                    })
                
                return None
                
        except Exception as e:
            print(f"  ❌ Error generating visualization config: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _generate_csv_from_output(self, output: str, intermediate_steps: List) -> str:
        """
        Generate CSV from agent output, extracting data from query results
        
        Args:
            output: Agent output text
            intermediate_steps: Execution steps containing tool results
            
        Returns:
            CSV string
        """
        try:
            logger.debug(f"CSV Generation: Total intermediate steps: {len(intermediate_steps)}")
            
            # Try to find postgres_query results in intermediate steps
            for i, step in enumerate(intermediate_steps):
                # Handle both tuple format (action, result) and dict format {"action": ..., "result": ...}
                if isinstance(step, dict):
                    # Dictionary format (from cached execution)
                    action = step.get('action', {})
                    result = step.get('result', '')
                    tool_name = action.get('tool') if isinstance(action, dict) else None
                    logger.debug(f"Step {i}: tool = {tool_name} (dict format)")
                elif len(step) >= 2:
                    # Tuple format (from regular execution)
                    action, result = step[0], step[1]
                    tool_name = getattr(action, 'tool', None)
                    logger.debug(f"Step {i}: tool = {tool_name} (tuple format)")
                else:
                    continue
                
                if tool_name == 'postgres_query':
                    logger.debug(f"Found postgres_query result!")
                    # Try to parse result as dict
                    if isinstance(result, str):
                        try:
                            result_dict = eval(result)  # or json.loads if result is JSON
                            logger.debug(f"Parsed result as dict")
                        except Exception as e:
                            logger.debug(f"Failed to parse result: {e}")
                            result_dict = result
                    else:
                        result_dict = result
                    
                    if isinstance(result_dict, dict) and 'rows' in result_dict:
                        rows = result_dict['rows']
                        columns = result_dict.get('columns', [])
                        print(f"  - Found {len(rows)} rows with columns: {columns}")
                        
                        if rows and len(rows) > 0:
                            # Generate CSV
                            output_stream = io.StringIO()
                            if columns:
                                writer = csv.DictWriter(output_stream, fieldnames=columns)
                                writer.writeheader()
                                writer.writerows(rows)
                            else:
                                # Infer columns from first row
                                if isinstance(rows[0], dict):
                                    writer = csv.DictWriter(output_stream, fieldnames=rows[0].keys())
                                    writer.writeheader()
                                    writer.writerows(rows)
                            
                            csv_result = output_stream.getvalue()
                            print(f"  - ✅ Generated CSV: {len(csv_result)} characters")
                            return csv_result
            
            print(f"  - ⚠️ No postgres_query results found in intermediate_steps")
            # Fallback: create simple CSV from output text
            output_stream = io.StringIO()
            writer = csv.writer(output_stream)
            writer.writerow(["Result"])
            writer.writerow([output])
            return output_stream.getvalue()
            
        except Exception as e:
            print(f"❌ Error generating CSV: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to simple text output
            return f"Result\n{output}"
    
    def _extract_table_from_output(self, output: str, intermediate_steps: List) -> Dict[str, Any]:
        """
        Extract table data from agent output
        
        Args:
            output: Agent output text
            intermediate_steps: Execution steps containing tool results
            
        Returns:
            Dictionary with columns and rows
        """
        from decimal import Decimal
        import json
        
        try:
            print(f"\n🔍 Extracting table data from {len(intermediate_steps)} intermediate steps")
            
            # Try to find postgres_query results in intermediate steps
            for i, step in enumerate(intermediate_steps):
                # Handle both tuple format (action, result) and dict format {"action": ..., "result": ...}
                if isinstance(step, dict):
                    # Dictionary format (from cached execution)
                    action = step.get('action', {})
                    result = step.get('result', '')
                    tool_name = action.get('tool') if isinstance(action, dict) else None
                    logger.debug(f"Step {i}: dict format, tool={tool_name}")
                elif len(step) >= 2:
                    # Tuple format (from regular execution)
                    action, result = step[0], step[1]
                    tool_name = getattr(action, 'tool', None)
                    logger.debug(f"Step {i}: tuple format, tool={tool_name}")
                else:
                    logger.debug(f"Step {i}: unknown format, skipping")
                    continue
                
                if tool_name == 'postgres_query':
                    logger.debug(f"Found postgres_query at step {i}")
                    logger.debug(f"Result type: {type(result).__name__}")
                    
                    # Parse result - handle string, dict, and direct dict results
                    result_dict = None
                    if isinstance(result, dict):
                        result_dict = result
                        logger.debug(f"Result is already dict with keys: {list(result.keys())}")
                    elif isinstance(result, str):
                        # Try JSON first (safest)
                        try:
                            result_dict = json.loads(result)
                            logger.debug(f"Parsed result from JSON string")
                        except:
                            # Try eval with Decimal in scope
                            try:
                                # Safe eval with Decimal available
                                result_dict = eval(result, {"__builtins__": {}, "Decimal": Decimal}, {})
                                logger.debug(f"Parsed result from eval()")
                            except Exception as parse_err:
                                logger.debug(f"Failed to parse string result: {parse_err}")
                                result_dict = None
                    
                    if result_dict and isinstance(result_dict, dict) and 'rows' in result_dict:
                        rows = result_dict.get('rows', [])
                        columns = result_dict.get('columns', [])
                        
                        # Convert Decimal types to float for JSON serialization
                        serialized_rows = []
                        for row in rows:
                            serialized_row = {}
                            for key, value in row.items():
                                if isinstance(value, Decimal):
                                    serialized_row[key] = float(value)
                                else:
                                    serialized_row[key] = value
                            serialized_rows.append(serialized_row)
                        
                        table_data = {
                            "columns": columns,
                            "rows": serialized_rows,
                            "row_count": result_dict.get('row_count', len(serialized_rows))
                        }
                        
                        print(f"  ✅ Extracted table: {len(columns)} columns, {len(serialized_rows)} rows")
                        return table_data
            
            # No table data found
            print(f"  ⚠️ No postgres_query results found in intermediate steps")
            return None
            
        except Exception as e:
            print(f"❌ Error extracting table: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _generate_summary_from_results(self, intermediate_steps: List, agent_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Generate an elaborated summary of query results from intermediate steps
        
        Args:
            intermediate_steps: Execution steps containing tool results
            
        Returns:
            Dictionary with detailed summary statistics and human-readable insights
        """
        try:
            logger.debug(f"Generating summary from {len(intermediate_steps)} steps")
            
            # 🔧 FIX: Check ALL steps and use the LAST successful postgres_query with rows
            last_successful_summary = None
            
            # Find postgres_query results
            for idx, step in enumerate(intermediate_steps):
                print(f"  Step {idx}: type={type(step)}, is_dict={isinstance(step, dict)}, is_tuple={isinstance(step, tuple)}")
                
                # Handle both tuple format (action, result) and dict format {"action": ..., "result": ...}
                if isinstance(step, dict):
                    # Dictionary format (from cached execution)
                    action = step.get('action', {})
                    result = step.get('result', '')
                    tool_name = action.get('tool') if isinstance(action, dict) else None
                    print(f"    Dict format: tool_name={tool_name}")
                elif isinstance(step, tuple) and len(step) >= 2:
                    # Tuple format (from regular execution)
                    action, result = step[0], step[1]
                    tool_name = getattr(action, 'tool', None)
                    print(f"    Tuple format: tool_name={tool_name}, result_type={type(result)}")
                else:
                    print(f"    Unknown format, skipping")
                    continue
                
                if tool_name == 'postgres_query':
                    logger.debug(f"Found postgres_query step!")
                    # Parse result
                    if isinstance(result, str):
                        logger.debug(f"Result is string, attempting to parse...")
                        try:
                            # Try JSON loads first (safer than eval)
                            import json
                            result_dict = json.loads(result)
                            print(f"      ✅ JSON parse successful, type={type(result_dict)}")
                        except json.JSONDecodeError:
                            # Fallback to eval with Decimal support
                            try:
                                from decimal import Decimal
                                result_dict = eval(result)
                                print(f"      ✅ Eval successful (with Decimal), type={type(result_dict)}")
                            except Exception as eval_err:
                                print(f"      ❌ Parse failed: {eval_err}")
                                continue
                    else:
                        print(f"      Result is already dict: {type(result)}")
                        result_dict = result
                    
                    print(f"      Checking if result_dict has 'rows'... has_rows={'rows' in result_dict if isinstance(result_dict, dict) else False}")
                    if isinstance(result_dict, dict) and 'rows' in result_dict:
                        rows = result_dict.get('rows', [])
                        columns = result_dict.get('columns', [])
                        print(f"      🎉 Found rows! row_count={len(rows)}, columns={len(columns)}")
                        
                        # Skip if no rows, but continue checking other steps
                        if not rows:
                            print(f"      ⚠️ No rows in this step, continuing to next step...")
                            continue
                        
                        summary = {
                            "total_records": len(rows),
                            "columns": columns,
                            "description": f"Query returned {len(rows)} record(s) with {len(columns)} column(s)."
                        }
                        
                        # Detailed breakdown sections
                        numeric_summary = {}
                        date_summary = {}
                        categorical_summary = {}
                        text_summary = {}  # For text/description fields
                        invoice_breakdown = {}  # Per-invoice analysis
                        
                        # Check if we have invoice-level data for breakdown
                        invoice_number_col = None
                        for col in columns:
                            if 'invoice' in col.lower() and 'number' in col.lower():
                                invoice_number_col = col
                                break
                        
                        # Generate per-invoice breakdown if invoice_number exists
                        if invoice_number_col:
                            try:
                                # Group rows by invoice number
                                invoices = {}
                                for row in rows:
                                    inv_num = row.get(invoice_number_col)
                                    if inv_num:
                                        # Convert to string to handle dict/JSONB values
                                        inv_num_str = str(inv_num) if not isinstance(inv_num, dict) else inv_num.get('value', str(inv_num))
                                        if inv_num_str not in invoices:
                                            invoices[inv_num_str] = []
                                        invoices[inv_num_str].append(row)
                                
                                # Analyze each invoice
                                for inv_num, inv_rows in invoices.items():
                                    invoice_data = {
                                        "invoice_number": inv_num,
                                        "line_items": len(inv_rows),
                                    }
                                    
                                    # Extract invoice-level fields (from first row since they're duplicated)
                                    first_row = inv_rows[0]
                                    
                                    # Get invoice date
                                    for col in columns:
                                        if 'invoice' in col.lower() and 'date' in col.lower():
                                            date_val = first_row.get(col)
                                            invoice_data["date"] = str(date_val) if not isinstance(date_val, dict) else date_val.get('value', str(date_val))
                                        elif 'invoice' in col.lower() and 'total' in col.lower():
                                            try:
                                                total_val = first_row.get(col, 0)
                                                total_str = str(total_val) if not isinstance(total_val, dict) else total_val.get('value', '0')
                                                invoice_data["total"] = float(total_str.replace('$', '').replace(',', ''))
                                            except:
                                                pass
                                        elif 'vendor' in col.lower() and 'name' in col.lower():
                                            vendor_val = first_row.get(col)
                                            invoice_data["vendor"] = str(vendor_val) if not isinstance(vendor_val, dict) else vendor_val.get('value', str(vendor_val))
                                    
                                    # Calculate line-level totals
                                    line_totals = []
                                    quantities = []
                                    for row in inv_rows:
                                        for col in columns:
                                            if 'line' in col.lower() and 'total' in col.lower():
                                                try:
                                                    line_val = row.get(col, 0)
                                                    line_str = str(line_val) if not isinstance(line_val, dict) else line_val.get('value', '0')
                                                    val = float(line_str.replace('$', '').replace(',', ''))
                                                    if val > 0:
                                                        line_totals.append(val)
                                                except:
                                                    pass
                                            elif 'quantity' in col.lower():
                                                try:
                                                    qty_val = row.get(col, 0)
                                                    qty_str = str(qty_val) if not isinstance(qty_val, dict) else qty_val.get('value', '0')
                                                    val = float(qty_str.replace('$', '').replace(',', ''))
                                                    if val > 0:
                                                        quantities.append(val)
                                                except:
                                                    pass
                                    
                                    if line_totals:
                                        invoice_data["line_items_total"] = sum(line_totals)
                                    if quantities:
                                        invoice_data["total_quantity"] = sum(quantities)
                                    
                                    invoice_breakdown[inv_num] = invoice_data
                                
                            except Exception as e:
                                print(f"Error generating invoice breakdown: {e}")
                                import traceback
                                traceback.print_exc()
                        
                        # Analyze EACH column in detail
                        for col in columns:
                            col_lower = col.lower()
                            
                            # Get all non-null values for this column
                            values = [row.get(col) for row in rows if row.get(col) and str(row.get(col)).strip() not in ['', 'None', 'null']]
                            
                            if not values:
                                continue
                            
                            # NUMERIC ANALYSIS - for any numeric-like columns
                            # BUT exclude ID and number fields that are identifiers, not values
                            is_identifier = any(keyword in col_lower for keyword in ['_id', 'id_', '_number', 'number_']) and not any(keyword in col_lower for keyword in ['phone_number', 'account_number'])
                            is_numeric_keyword = any(keyword in col_lower for keyword in ['total', 'amount', 'quantity', 'price', 'count', 'sum', 'cost', 'fee', 'tax', 'discount', 'balance', 'payment'])
                            
                            if (is_numeric_keyword and not is_identifier) or col_lower in ['line_total', 'subtotal', 'grand_total']:
                                try:
                                    # Try to parse as numeric
                                    numeric_values = []
                                    for val in values:
                                        try:
                                            numeric_values.append(float(str(val).replace('$', '').replace(',', '')))
                                        except:
                                            pass
                                    
                                    if numeric_values and len(numeric_values) > 0:
                                        col_sum = sum(numeric_values)
                                        col_avg = col_sum / len(numeric_values)
                                        col_min = min(numeric_values)
                                        col_max = max(numeric_values)
                                        
                                        # Detect if this is a duplicated header field (like invoice_total repeated per line item)
                                        unique_count = len(set(numeric_values))
                                        is_duplicated_header = unique_count < len(numeric_values) * 0.3  # If <30% unique, likely duplicated header
                                        
                                        # Determine if this is a currency field or quantity/count field
                                        is_currency = any(keyword in col_lower for keyword in ['total', 'amount', 'price', 'cost', 'fee', 'tax', 'discount', 'balance', 'payment'])
                                        is_quantity = any(keyword in col_lower for keyword in ['quantity', 'count', 'qty', 'num'])
                                        
                                        if is_duplicated_header:
                                            # For duplicated headers (like invoice_total), show unique values instead of sum
                                            unique_values_list = sorted(set(numeric_values), reverse=True)
                                            numeric_summary[col] = {
                                                "unique_values": [round(v, 2) for v in unique_values_list[:5]],
                                                "unique_count": unique_count,
                                                "total_entries": len(numeric_values),
                                                "min": round(col_min, 2),
                                                "max": round(col_max, 2),
                                                "is_header_field": True,
                                                "description": f"**{col}** (Header Field): {unique_count} unique values across {len(numeric_values)} entries. Range: ${col_min:,.2f} - ${col_max:,.2f}"
                                            }
                                        else:
                                            # Regular numeric field - calculate totals
                                            if is_currency:
                                                numeric_summary[col] = {
                                                    "sum": round(col_sum, 2),
                                                    "average": round(col_avg, 2),
                                                    "min": round(col_min, 2),
                                                    "max": round(col_max, 2),
                                                    "count": len(numeric_values),
                                                    "is_currency": True,
                                                    "description": f"**{col}**: Total = ${col_sum:,.2f}, Average = ${col_avg:,.2f}, Range = ${col_min:,.2f} - ${col_max:,.2f}"
                                                }
                                            elif is_quantity:
                                                numeric_summary[col] = {
                                                    "sum": round(col_sum, 2),
                                                    "average": round(col_avg, 2),
                                                    "min": round(col_min, 2),
                                                    "max": round(col_max, 2),
                                                    "count": len(numeric_values),
                                                    "is_quantity": True,
                                                    "description": f"**{col}**: Total = {col_sum:,.0f}, Average = {col_avg:,.1f}, Range = {col_min:,.0f} - {col_max:,.0f}"
                                                }
                                            else:
                                                numeric_summary[col] = {
                                                    "sum": round(col_sum, 2),
                                                    "average": round(col_avg, 2),
                                                    "min": round(col_min, 2),
                                                    "max": round(col_max, 2),
                                                    "count": len(numeric_values),
                                                    "description": f"**{col}**: Total = {col_sum:,.2f}, Average = {col_avg:,.2f}, Range = {col_min:,.2f} - {col_max:,.2f}"
                                                }
                                        continue
                                except:
                                    pass
                            
                            # DATE ANALYSIS - for date columns
                            if 'date' in col_lower or 'time' in col_lower:
                                try:
                                    date_values = [str(val) for val in values]
                                    min_date = min(date_values)
                                    max_date = max(date_values)
                                    unique_dates = len(set(date_values))
                                    
                                    date_summary[col] = {
                                        "from": min_date,
                                        "to": max_date,
                                        "count": len(date_values),
                                        "unique_count": unique_dates,
                                        "description": f"**{col}**: From *{min_date}* to *{max_date}* ({len(date_values)} entries, {unique_dates} unique dates)"
                                    }
                                    continue
                                except:
                                    pass
                            
                            # CATEGORICAL ANALYSIS - for name, type, status, category, number fields
                            # Prioritize identifier fields (invoice_number, order_number, etc.)
                            if any(keyword in col_lower for keyword in ['_number', 'number_', '_name', 'name_', 'type', 'status', 'category', '_code', 'code_']) and 'id' not in col_lower:
                                try:
                                    unique_values = set(str(val) for val in values)
                                    total_entries = len(values)
                                    
                                    categorical_summary[col] = {
                                        "unique_count": len(unique_values),
                                        "total_entries": total_entries,
                                        "description": f"**{col}**: {len(unique_values)} unique value(s) across {total_entries} entries"
                                    }
                                    
                                    # Add top values if reasonable number
                                    if len(unique_values) <= 20:
                                        value_counts = {}
                                        for val in values:
                                            val_str = str(val)
                                            value_counts[val_str] = value_counts.get(val_str, 0) + 1
                                        # Sort by frequency
                                        top_values = sorted(value_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                                        categorical_summary[col]["top_values"] = [{"value": v, "count": c} for v, c in top_values]
                                    continue
                                except:
                                    pass
                            
                            # TEXT/DESCRIPTION ANALYSIS - for description, notes, comment fields
                            if any(keyword in col_lower for keyword in ['description', 'note', 'comment', 'detail', 'remark']):
                                try:
                                    unique_values = set(str(val) for val in values)
                                    total_entries = len(values)
                                    
                                    # Calculate average text length
                                    text_lengths = [len(str(val)) for val in values]
                                    avg_length = sum(text_lengths) / len(text_lengths) if text_lengths else 0
                                    
                                    text_summary[col] = {
                                        "unique_count": len(unique_values),
                                        "total_entries": total_entries,
                                        "avg_length": round(avg_length, 1),
                                        "description": f"**{col}**: {len(unique_values)} unique entries (avg length: {avg_length:.0f} chars)"
                                    }
                                    
                                    # Show sample values (first 3 unique)
                                    if len(unique_values) <= 10:
                                        samples = list(unique_values)[:3]
                                        text_summary[col]["samples"] = samples
                                    continue
                                except:
                                    pass
                            
                            # GENERAL CATEGORICAL - catch-all for any other columns
                            try:
                                unique_values = set(str(val) for val in values)
                                if len(unique_values) <= 50:  # Only if reasonable number of unique values
                                    categorical_summary[col] = {
                                        "unique_count": len(unique_values),
                                        "total_entries": len(values),
                                        "description": f"**{col}**: {len(unique_values)} unique value(s)"
                                    }
                                    
                                    if len(unique_values) <= 10:
                                        value_counts = {}
                                        for val in values:
                                            val_str = str(val)
                                            value_counts[val_str] = value_counts.get(val_str, 0) + 1
                                        top_values = sorted(value_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                                        categorical_summary[col]["top_values"] = [{"value": v, "count": c} for v, c in top_values]
                            except:
                                pass
                        
                        # Add summaries to main summary
                        if invoice_breakdown:
                            summary["invoice_breakdown"] = invoice_breakdown
                            # Create readable invoice summary
                            invoice_summaries = []
                            for inv_num, data in sorted(invoice_breakdown.items()):
                                parts = [f"**{inv_num}**"]
                                if data.get('vendor'):
                                    parts.append(f"Vendor: {data['vendor']}")
                                if data.get('date'):
                                    parts.append(f"Date: {data['date']}")
                                if data.get('total'):
                                    parts.append(f"Invoice Total: ${data['total']:,.2f}")
                                parts.append(f"Line Items: {data['line_items']}")
                                if data.get('total_quantity'):
                                    parts.append(f"Total Quantity: {data['total_quantity']:,.0f} units")
                                if data.get('line_items_total'):
                                    parts.append(f"Line Items Total: ${data['line_items_total']:,.2f}")
                                invoice_summaries.append(" | ".join(parts))
                            summary["invoice_summary_text"] = "\n".join(invoice_summaries)
                        
                        if numeric_summary:
                            summary["numeric_analysis"] = numeric_summary
                            # Create human-readable summary text
                            numeric_descriptions = [item["description"] for item in numeric_summary.values()]
                            summary["numeric_summary_text"] = "\n".join(numeric_descriptions)
                        
                        if date_summary:
                            summary["date_analysis"] = date_summary
                            date_descriptions = [item["description"] for item in date_summary.values()]
                            summary["date_summary_text"] = "\n".join(date_descriptions)
                        
                        if categorical_summary:
                            summary["categorical_analysis"] = categorical_summary
                            categorical_descriptions = [item["description"] for item in categorical_summary.values()]
                            summary["categorical_summary_text"] = "\n".join(categorical_descriptions)
                        
                        if text_summary:
                            summary["text_analysis"] = text_summary
                            text_descriptions = [item["description"] for item in text_summary.values()]
                            summary["text_summary_text"] = "\n".join(text_descriptions)
                        
                        # Create comprehensive human-readable markdown summary
                        full_summary_parts = [
                            f"# 📊 Query Results Summary\n",
                            f"**{len(rows)}** records found with **{len(columns)}** columns\n",
                        ]
                        
                        # Add invoice breakdown section if available
                        if invoice_breakdown:
                            full_summary_parts.append("## 📎 Invoices\n")
                            
                            for inv_num, data in sorted(invoice_breakdown.items(), key=lambda x: x[1].get('date', ''), reverse=True):
                                full_summary_parts.append(f"**{inv_num}** - {data.get('vendor', 'Unknown')} ({data.get('date', 'No date')})")
                                full_summary_parts.append(f"  └ {data['line_items']} items, {data.get('total_quantity', 0):,.0f} units")
                                if data.get('total'):
                                    full_summary_parts.append(f"  └ Total: ${data['total']:,.2f}")
                                full_summary_parts.append("")
                        
                        if numeric_summary:
                            full_summary_parts.append("## 💰 Numbers\n")
                            for col, data in numeric_summary.items():
                                # Handle header fields (duplicated values)
                                if data.get('is_header_field'):
                                    unique_vals = data.get('unique_values', [])
                                    if unique_vals:
                                        vals_str = ', '.join([f"${v:,.2f}" for v in unique_vals[:3]])
                                        full_summary_parts.append(f"**{col}:** {data.get('unique_count', 0)} unique values ({vals_str})")
                                # Handle regular numeric fields
                                elif data.get('is_quantity'):
                                    full_summary_parts.append(f"**{col}:** {data.get('sum', 0):,.0f} total, {data.get('average', 0):,.1f} avg ({data.get('min', 0):,.0f} - {data.get('max', 0):,.0f})")
                                elif data.get('is_currency'):
                                    full_summary_parts.append(f"**{col}:** ${data.get('sum', 0):,.2f} total, ${data.get('average', 0):,.2f} avg")
                                else:
                                    full_summary_parts.append(f"**{col}:** {data.get('average', 0):,.2f} avg ({data.get('min', 0):,.2f} - {data.get('max', 0):,.2f})")
                            full_summary_parts.append("")
                        
                        if date_summary:
                            full_summary_parts.append("## 📅 Dates\n")
                            for col, data in date_summary.items():
                                full_summary_parts.append(f"**{col}:** {data['unique_count']} unique dates from {data['from']} to {data['to']}")
                            full_summary_parts.append("")
                        
                        if categorical_summary:
                            full_summary_parts.append("## 🏷️ Categories\n")
                            for col, data in categorical_summary.items():
                                if 'top_values' in data and data['top_values']:
                                    top_3 = data['top_values'][:3]
                                    values_str = ', '.join([f"{item['value']} ({item['count']})" for item in top_3])
                                    full_summary_parts.append(f"**{col}:** {values_str}")
                            full_summary_parts.append("")
                        
                        if text_summary:
                            full_summary_parts.append("## 📝 Text Fields\n")
                            for col, data in text_summary.items():
                                full_summary_parts.append(f"**{col}:** {data['unique_count']} unique entries, avg {data['avg_length']} chars")
                            full_summary_parts.append("")
                        
                        summary["full_summary"] = "\n".join(full_summary_parts)
                        
                        # Generate AI-powered summary if LLM is available
                        print(f"\n🤖 Attempting to generate AI summary...")
                        try:
                            ai_summary = self._generate_ai_summary(rows, columns, summary, agent_data=agent_data)
                            if ai_summary and ai_summary.strip():
                                # 🧹 CLEAN: Remove code block wrappers from AI summary too
                                import re
                                if '```markdown' in ai_summary or '```' in ai_summary:
                                    print("  🧹 Removing code block wrapper from AI summary...")
                                    code_match = re.search(r'```(?:markdown)?\n(.*)\n```', ai_summary, re.DOTALL)
                                    if code_match:
                                        ai_summary = code_match.group(1).strip()
                                        print(f"  ✅ Extracted clean markdown from AI summary ({len(ai_summary)} chars)")
                                
                                summary["ai_summary"] = ai_summary
                                # Prepend AI summary to full summary
                                summary["full_summary"] = f"# 🤖 AI-Generated Insights\n\n{ai_summary}\n\n---\n\n{summary['full_summary']}"
                                print(f"✅ AI summary successfully added to response ({len(ai_summary)} chars)")
                            else:
                                print(f"⚠️ AI summary returned None or empty - using fallback")
                                # Create fallback AI summary from full_summary
                                fallback_summary = f"## Query Results\n\n{full_summary_parts[1] if len(full_summary_parts) > 1 else 'Data retrieved successfully.'}"
                                summary["ai_summary"] = fallback_summary
                                print(f"✅ Using fallback AI summary")
                        except Exception as e:
                            print(f"❌ Could not generate AI summary: {e}")
                            import traceback
                            traceback.print_exc()
                            # Always provide SOME ai_summary even if generation fails
                            fallback_summary = f"## Query Results\n\n**{len(rows)}** records found with **{len(columns)}** columns.\n\nData retrieved successfully."
                            summary["ai_summary"] = fallback_summary
                            print(f"✅ Using emergency fallback AI summary")
                        
                        # 🔧 FIX: Save this summary and continue checking other steps
                        # We want the LAST successful query with data
                        last_successful_summary = summary
                        print(f"      💾 Saved summary from step {idx}, will use this if no later steps have data")
            
            # Return the last successful summary found
            if last_successful_summary:
                print(f"\n✅ Returning summary with {last_successful_summary.get('total_records', 0)} records")
                return last_successful_summary
            
            print(f"\n⚠️ No postgres_query steps with rows found in any step")
            print(f"  📝 Debug Info:")
            print(f"    - Total steps processed: {len(intermediate_steps)}")
            print(f"    - Step types: {[type(s).__name__ for s in intermediate_steps]}")
            if intermediate_steps:
                # Show first step structure
                first_step = intermediate_steps[0]
                if isinstance(first_step, dict):
                    print(f"    - First step keys: {list(first_step.keys())}")
                    print(f"    - First step action: {first_step.get('action', 'N/A')}")
                elif isinstance(first_step, tuple):
                    print(f"    - First step tuple length: {len(first_step)}")
            return None
            
        except Exception as e:
            print(f"Error generating summary: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _generate_ai_summary(self, rows: List[Dict], columns: List[str], summary: Dict[str, Any], agent_data: Dict[str, Any] = None) -> str:
        """
        Generate AI-powered natural language summary from query results
        
        Args:
            rows: Query result rows
            columns: Column names
            summary: Statistical summary data
            agent_data: Full agent metadata (name, description, use_cases, prompt, category)
            
        Returns:
            AI-generated markdown summary text
        """
        try:
            # Prepare data snapshot for AI analysis (limit to first 10 rows for context)
            sample_rows = rows[:10] if len(rows) > 10 else rows
            
            # 🎯 Build context from agent metadata (NO hardcoded instructions!)
            agent_context = ""
            if agent_data:
                agent_name = agent_data.get('name', '')
                agent_desc = agent_data.get('description', '')
                use_cases = agent_data.get('use_cases', [])
                agent_category = agent_data.get('category', '')
                
                agent_context = f"""\n\n🎯 AGENT CONTEXT:
- Name: {agent_name}
- Description: {agent_desc}
- Category: {agent_category}
- Use Cases: {', '.join(use_cases)}

⚠️ CRITICAL: Analyze the data according to THIS SPECIFIC agent's purpose and use cases.
"""
            
            # Build prompt for AI summary generation
            analysis_prompt = f"""Analyze the following database query results and provide a concise, business-focused summary.

**Dataset Overview:**
- Total Records: {len(rows)}
- Columns: {', '.join(columns)}

**Statistical Summary:**
{self._format_summary_for_ai(summary)}

**Sample Data (first {len(sample_rows)} records):**
{self._format_sample_data(sample_rows, columns)}
{agent_context}

**Instructions:**
Provide a detailed, insightful summary using **STRICT MARKDOWN FORMATTING**:

**Required Format:**
1. Start with a ## Main Heading
2. Use **bold** for important terms (vendors, amounts, invoice numbers)
3. Use bullet points (- or *) for lists
4. Use numbered lists (1., 2., 3.) for sequential findings
5. Use ### subheadings to organize sections
6. Use > blockquotes for key insights or warnings

**Content Requirements:**
1. Identify key findings and patterns in the data
2. Highlight notable trends, concentrations, or anomalies
3. Provide business-relevant observations and actionable insights
4. Mention specific numbers, vendors, or amounts when relevant
5. Use natural, professional language suitable for business stakeholders

**Do NOT:**
- Write plain paragraphs without markdown formatting
- Simply repeat raw statistics without interpretation
- Use overly technical jargon
- Make assumptions or recommendations beyond the data

**Example Format:**
```markdown
## Duplicate Invoice Analysis

### Key Findings
- Found **10 duplicate groups** affecting **30 invoices**
- Vendor **meat Hub** has invoice **#328** duplicated **4 times** (Total: **$1.00**)

### Business Impact
> ⚠️ High-priority duplicates detected in vendor payments

### Recommendations
1. Review invoices with 4+ duplicates first
2. Implement validation checks
```

Provide a comprehensive markdown-formatted analysis:"""
            
            # Use the LLM to generate summary
            from langchain_core.messages import HumanMessage
            
            response = self.llm.invoke([HumanMessage(content=analysis_prompt)])
            ai_summary = response.content.strip()
            
            print(f"\n🤖 AI Summary Generated: {len(ai_summary)} characters")
            
            return ai_summary
            
        except Exception as e:
            print(f"Error generating AI summary: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _generate_ai_summary_streaming(self, rows: List[Dict], columns: List[str], summary: Dict[str, Any], agent_data: Dict[str, Any] = None):
        """
        Generate AI-powered summary with streaming (generator for real-time display)
        
        Yields:
            String tokens as they arrive from the AI
        """
        try:
            # Prepare data snapshot
            sample_rows = rows[:10] if len(rows) > 10 else rows
            
            # Build agent context
            agent_context = ""
            if agent_data:
                agent_name = agent_data.get('name', '')
                agent_desc = agent_data.get('description', '')
                use_cases = agent_data.get('use_cases', [])
                agent_category = agent_data.get('category', '')
                
                agent_context = f"""\n\n🎯 AGENT CONTEXT:
- Name: {agent_name}
- Description: {agent_desc}
- Category: {agent_category}
- Use Cases: {', '.join(use_cases)}

⚠️ CRITICAL: Analyze the data according to THIS SPECIFIC agent's purpose and use cases.
"""
            
            # Build prompt
            analysis_prompt = f"""Analyze the following database query results and provide a concise, business-focused summary.

**Dataset Overview:**
- Total Records: {len(rows)}
- Columns: {', '.join(columns)}

**Statistical Summary:**
{self._format_summary_for_ai(summary)}

**Sample Data (first {len(sample_rows)} records):**
{self._format_sample_data(sample_rows, columns)}
{agent_context}

**Instructions:**
Provide a detailed, insightful summary using **STRICT MARKDOWN FORMATTING**:

**Required Format:**
1. Start with a ## Main Heading
2. Use **bold** for important terms (vendors, amounts, invoice numbers)
3. Use bullet points (- or *) for lists
4. Use numbered lists (1., 2., 3.) for sequential findings
5. Use ### subheadings to organize sections
6. Use > blockquotes for key insights or warnings

**Content Requirements:**
1. Identify key findings and patterns in the data
2. Highlight notable trends, concentrations, or anomalies
3. Provide business-relevant observations and actionable insights
4. Mention specific numbers, vendors, or amounts when relevant
5. Use natural, professional language suitable for business stakeholders

**Do NOT:**
- Write plain paragraphs without markdown formatting
- Simply repeat raw statistics without interpretation
- Use overly technical jargon
- Make assumptions or recommendations beyond the data

Provide a comprehensive markdown-formatted analysis:"""
            
            # Stream AI response
            messages = [
                {"role": "user", "content": analysis_prompt}
            ]
            
            for token in self._stream_ai_response(messages):
                yield token
                
        except Exception as e:
            print(f"Error generating AI summary (streaming): {e}")
            import traceback
            traceback.print_exc()
            yield f"\n\n_Error generating summary: {str(e)}_"
    
    def _format_summary_for_ai(self, summary: Dict[str, Any]) -> str:
        """
        Format statistical summary for AI consumption
        """
        parts = []
        
        # Invoice breakdown
        if summary.get('invoice_breakdown'):
            parts.append("Invoice Breakdown:")
            for inv_num, data in sorted(summary['invoice_breakdown'].items()):
                inv_parts = [f"  - {inv_num}"]
                if data.get('vendor'):
                    inv_parts.append(f"Vendor: {data['vendor']}")
                if data.get('total'):
                    inv_parts.append(f"Total: ${data['total']:,.2f}")
                if data.get('line_items'):
                    inv_parts.append(f"{data['line_items']} items")
                if data.get('total_quantity'):
                    inv_parts.append(f"{data['total_quantity']:,.0f} units")
                parts.append(", ".join(inv_parts))
        
        if summary.get('numeric_analysis'):
            parts.append("\nNumeric Fields:")
            for col, data in summary['numeric_analysis'].items():
                if data.get('is_header_field'):
                    parts.append(f"  - {col} (Header): {data['unique_count']} unique values, Range=${data['min']:,.2f}-${data['max']:,.2f}")
                elif data.get('is_quantity'):
                    parts.append(f"  - {col}: Total={data['sum']:,.0f} units, Avg={data['average']:,.1f}, Range={data['min']:,.0f}-{data['max']:,.0f}")
                else:
                    parts.append(f"  - {col}: Total=${data['sum']:,.2f}, Avg=${data['average']:,.2f}, Range=${data['min']:,.2f}-${data['max']:,.2f}")
        
        if summary.get('date_analysis'):
            parts.append("\nDate Fields:")
            for col, data in summary['date_analysis'].items():
                parts.append(f"  - {col}: {data['from']} to {data['to']} ({data['unique_count']} unique dates)")
        
        if summary.get('categorical_analysis'):
            parts.append("\nCategorical Fields:")
            for col, data in summary['categorical_analysis'].items():
                parts.append(f"  - {col}: {data['unique_count']} unique values")
                if data.get('top_values'):
                    top = data['top_values'][:3]
                    top_str = ', '.join([f"{v['value']}({v['count']})" for v in top])
                    parts.append(f"    Top: {top_str}")
        
        return '\n'.join(parts)
    
    def _format_sample_data(self, rows: List[Dict], columns: List[str]) -> str:
        """
        Format sample rows for AI analysis
        """
        if not rows:
            return "No data available"
        
        # Create a simple table format
        lines = []
        lines.append(" | ".join(columns))
        lines.append("-" * 80)
        
        for row in rows[:5]:  # Only show first 5 for brevity
            values = []
            for col in columns:
                val = str(row.get(col, ''))[:30]  # Truncate long values
                values.append(val)
            lines.append(" | ".join(values))
        
        if len(rows) > 5:
            lines.append(f"... ({len(rows) - 5} more rows)")
        
        return '\n'.join(lines)
    
    def _ensure_markdown_format(self, text: str) -> str:
        """
        Ensure text output is properly formatted as markdown
        If the LLM returns plain text, convert it to markdown
        Also removes markdown code block wrappers if present
        
        Args:
            text: Raw text output from LLM
            
        Returns:
            Markdown-formatted text
        """
        try:
            # 🧹 CLEAN: Remove markdown code block wrappers if present
            # LLM sometimes wraps markdown in ```markdown...``` which breaks rendering
            import re
            if '```markdown' in text or '```' in text:
                print("  🧹 Removing markdown code block wrapper...")
                # Extract content from ```markdown\n...\n``` or ```\n...\n```
                code_match = re.search(r'```(?:markdown)?\n(.*)\n```', text, re.DOTALL)
                if code_match:
                    text = code_match.group(1).strip()
                    print(f"  ✅ Extracted markdown from code block ({len(text)} chars)")
            
            # Check if text already has markdown formatting
            has_headers = any(line.strip().startswith('#') for line in text.split('\n'))
            has_bold = '**' in text
            has_lists = any(line.strip().startswith(('-', '*', '1.', '2.', '3.')) for line in text.split('\n'))
            
            # If it has any markdown, assume it's properly formatted
            if has_headers or (has_bold and has_lists):
                print("  ✅ Output already has markdown formatting")
                return text
            
            # Text is plain - use LLM to convert to markdown
            print("  🎨 Converting plain text output to markdown...")
            
            from langchain_core.messages import HumanMessage
            
            conversion_prompt = f"""Convert the following plain text response into proper markdown format.

Original Text:
{text}

IMPORTANT REQUIREMENTS:
1. Start with a ## main heading
2. Use ### for subheadings
3. Use **bold** for important terms (amounts, names, invoice numbers, dates)
4. Use bullet points (-) for lists
5. Use numbered lists (1., 2., 3.) for sequential items
6. Use > for important warnings or highlights
7. Keep the original content and meaning EXACTLY - just add markdown formatting
8. Do NOT add new information or change the facts

Return ONLY the markdown-formatted version:"""
            
            response = self.llm.invoke([HumanMessage(content=conversion_prompt)])
            markdown_text = response.content.strip()
            
            # Remove any markdown code blocks if present
            if '```' in markdown_text:
                import re
                code_match = re.search(r'```(?:markdown)?\n(.*?)\n```', markdown_text, re.DOTALL)
                if code_match:
                    markdown_text = code_match.group(1).strip()
            
            print(f"  ✅ Converted to markdown ({len(markdown_text)} chars)")
            return markdown_text
            
        except Exception as e:
            print(f"  ⚠️ Error converting to markdown: {e}")
            # Fallback: return original text
            return text
    
    def _execute_with_guidance(self, agent_data: Dict, user_query: str, input_data: Dict = None, progress_callback = None, visualization_preferences: str = None) -> Dict[str, Any]:
        """
        Execute agent using pre-built execution guidance (FAST PATH)
        Includes automatic SQL error correction with retry logic (max 5 attempts)
        Falls back to AI-based query generation if template fails
        
        Args:
            agent_data: Agent configuration with execution_guidance
            user_query: User query string
            input_data: Optional input data from frontend (month, year, dates, etc.)
            progress_callback: Optional callback for progress updates
            
        Returns:
            Execution results or None to trigger fallback
        """
        try:
            if progress_callback:
                progress_callback(1, 'completed', 'Preparing execution', 'Loading agent configuration')
            
            print("\n⚡ FAST PATH: Using pre-built execution guidance")
            
            execution_guidance = agent_data.get('execution_guidance')
            if not execution_guidance or execution_guidance.get('error'):
                print("⚠️ No valid execution guidance available - falling back to traditional execution")
                return None
            
            query_template = execution_guidance.get('query_template', {})
            execution_plan = execution_guidance.get('execution_plan', {})
            write_query_template = execution_guidance.get('write_query_template', '')
            workflow_config = agent_data.get('workflow_config', {})
            
            # Step 1: Extract parameters from input_data or user_query
            params = {}
            parameters_needed = query_template.get('parameters', [])
            
            print(f"  Parameters needed: {parameters_needed}")
            print(f"  Input data: {input_data}")
            
            # Priority 1: Extract from structured input_data (from frontend)
            if input_data and isinstance(input_data, dict) and len(input_data) > 0:
                print("  🎯 Using structured input_data from frontend")
                for param in parameters_needed:
                    if param in input_data:
                        value = input_data[param]
                        # Format month with leading zero if needed
                        if param == 'month' and isinstance(value, (int, str)):
                            params[param] = str(value).zfill(2)
                        else:
                            params[param] = str(value)
            
            # Priority 2: Try to parse from user_query string (fallback)
            if not params and parameters_needed:
                print("  🔍 Attempting to extract parameters from user_query string")
                params = self._extract_query_parameters(user_query, workflow_config)
            
            if not params and parameters_needed:
                print(f"⚠️ Could not extract required parameters: {parameters_needed}")
                return None
            
            print(f"  Extracted parameters: {params}")
            
            # Step 2: Fill template with parameters
            full_query = query_template.get('full_template', '')
            
            try:
                filled_query = full_query.format(**params)
                print(f"  ✅ Query filled: {filled_query[:150]}...")
            except KeyError as e:
                print(f"⚠️ Missing parameter {e} in template")
                return None
            
            # Step 3: Execute query with retry logic (max 3 attempts)
            if progress_callback:
                progress_callback(2, 'in_progress', 'Running tools', 'Executing database query')
            
            from tools.postgres_connector import PostgresConnector
            pg_connector = PostgresConnector()
            
            max_retries = 5
            current_query = filled_query
            last_error = None
            query_was_corrected = False  # Track if we corrected the query
            
            # 🔍 PRE-EXECUTION VALIDATION: Check and fix common errors BEFORE attempting execution
            validated_query, was_fixed = self._validate_and_fix_query(current_query, execution_guidance.get('schema_snapshot', {}))
            if was_fixed:
                print("  ✅ Query was proactively fixed before execution")
                current_query = validated_query
                query_was_corrected = True  # Mark that we made changes
            
            # 🔒 CONFIRMATION CHECK & WRITE DELEGATION
            import re
            # Check for common write keywords at the start of the query
            # Check for common write keywords at the start of the query
            write_pattern = re.compile(r'^\s*(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|REPLACE|MERGE)', re.IGNORECASE)
            
            # Remove comments to avoid false positives (simple check)
            clean_query = re.sub(r'--.*', '', current_query)
            clean_query = re.sub(r'/\*.*?\*/', '', clean_query, flags=re.DOTALL)
            clean_query = clean_query.strip()
            
            match = write_pattern.match(clean_query)
            is_write_op = bool(match)
            
            print(f"  🔍 Query Operation Check:")
            if write_query_template:
                 print(f"  📝 Write Query Template Available: {write_query_template[:50]}...")
            print(f"  - Clean start: '{clean_query[:50]}...'")
            print(f"  - Detected Operation: {'WRITE (' + match.group(1).upper() + ')' if match else 'READ/OTHER'}")
            print(f"  - Is Write Op: {is_write_op}")

            
            if is_write_op:
                print("  🔒 Write operation detected - Delegating to PostgresWriter")
                try:
                    from tools.postgres_writer import PostgresWriter
                    writer = PostgresWriter()
                    
                    # Check for confirmation
                    is_confirmed = False
                    if input_data and isinstance(input_data, dict):
                         val = input_data.get('confirmation_approved')
                         if val is True or str(val).lower() == 'true':
                             is_confirmed = True
                    
                    if not is_confirmed:
                        # Run DRY RUN to check safety and preview
                        print("  🔒 executing dry run for safety...")
                        dry_run_result = writer.execute(query=current_query, dry_run=True)
                        
                        if not dry_run_result.get('success'):
                             # Safety check failed or error
                             print(f"  ❌ Dry run failed: {dry_run_result.get('error')}")
                             return dry_run_result # Return error directly
                        
                        # Return confirmation request with preview details
                        affected = dry_run_result.get('affected_rows', 0)
                        msg = f"This action involves a write operation that will affect approximately {affected} row(s)."
                        if dry_run_result.get('preview_data'):
                            msg += f"\nPreview: {str(dry_run_result['preview_data'])}"
                            
                        return {
                             "success": True, 
                             "requires_confirmation": True,
                             "confirmation_message": msg,
                             "pending_action": current_query,
                             "preview_data": dry_run_result.get('preview_data', [])
                         }
                    
                    else:
                        # Execute REAL WRITE
                        print("  🚀 executing confirmed write operation...")
                        result = writer.execute(query=current_query, dry_run=False)
                        
                        if result.get('success'):
                             # Standardize result format for the next steps
                             # Writer returns {success, affected_rows, message, ...}
                             # We need to reshape it to look like a query result (rows/columns)
                             # Writes usually don't return rows unless RETURNING is used
                             result['row_count'] = result.get('affected_rows', 0)
                             result['rows'] = [] 
                             result['columns'] = []
                             
                             print(f"  ✅ Write executed successfully: {result.get('message')}")
                             if progress_callback:
                                progress_callback(2, 'completed', 'Running tools', result.get('message'))
                             
                             # We skip the standard read loop by breaking or wrapping? 
                             # The code below triggers output formatting. Let's return the result now 
                             # formatted as if it came from the connector, so downstream logic works?
                             # Downstream expects 'result' to be defined in the loop. 
                             # Since we are outside the loop, we must adapt.
                             
                             # Actually, we should just continue to output formatting using this result.
                             # But the loop below handles READs. We need to prevent the read loop from running.
                             # Create intermediate steps in DICTIONARY format
                             intermediate_steps = [{
                                 "action": {
                                     "tool": "postgres_writer",
                                     "tool_input": {"query": current_query, "dry_run": False},
                                     "log": result.get('message')
                                 },
                                 "result": str(result)
                             }]
                             
                             output_format = workflow_config.get('output_format', 'text')
                             
                             # Generate simple output message
                             output_msg = result.get('message')
                             
                             # Use _format_output to handle standardization
                             formatted_result = self._format_output(output_msg, output_format, intermediate_steps, agent_data=agent_data, visualization_preferences=visualization_preferences)
                             formatted_result['success'] = True
                             
                             return formatted_result
 
                        else:
                             return result # Return failure

                except ImportError:
                    print("  ⚠️ PostgresWriter tool not found - failing safely")
                    return {"success": False, "error": "PostgresWriter tool required for write operations is missing"}
            
            # Executing Loop (Read or Fallback)
            if not is_write_op or (is_write_op and not result.get('success')): # Only if not already successful
                # If we just executed a write successfully, we should NOT enter this loop unless we need to?
                # Actually, the logic below is structured as:
                # for attempt... result = ...
                # We need to restructure slightly to handle the "already executed" case.
                pass 
                
            # RESTRUCTURED FLOW:
            # If write and confirmed -> result is already set.
            # If read -> result needs to be fetched in loop.
            
            # If we successfully executed a write, we will return from inside the write block.
            # Otherwise, we proceed to this generic retry loop.
            
            for attempt in range(1, max_retries + 1):
                print(f"\n  🔄 Attempt {attempt}/{max_retries}: Executing query...")
                result = pg_connector.execute(query=current_query)
                
                if result.get('success'):
                    print(f"  ✅ Query executed successfully: {result.get('row_count', 0)} rows returned")
                    
                    if progress_callback:
                        progress_callback(2, 'completed', 'Running tools', f"Query executed: {result.get('row_count', 0)} rows")
                    
                    # 💾 SAVE CORRECTED QUERY to agent JSON if it was fixed
                    if query_was_corrected and attempt > 1:
                        print(f"\n💾 Saving corrected query template to agent JSON...")
                        self._save_corrected_query_template(
                            agent_data=agent_data,
                            corrected_query=current_query,
                            original_query=filled_query,
                            attempt_number=attempt
                        )
                    
                    # Step 4: Format based on output_format
                    if progress_callback:
                        progress_callback(3, 'in_progress', 'Processing data', 'Analyzing results')
                    
                    output_format = workflow_config.get('output_format', 'text')
                    
                    # 🎯 Generate purpose-driven output message using agent's prompt
                    agent_prompt = agent_data.get('prompt', '')
                    rows = result.get('rows', [])
                    columns = result.get('columns', [])
                    row_count = result.get('row_count', 0)
                    
                    if progress_callback:
                        progress_callback(3, 'in_progress', 'Processing data', None, substeps=[
                            {
                                "id": "ai-output-generation",
                                "label": "AI is generating output message...",
                                "status": "in_progress"
                            }
                        ])
                    
                    print("\n🤖 Generating purpose-driven output based on agent's mission...")
                    purpose_output = self._generate_cached_query_output(
                        agent_data=agent_data,
                        output_format=output_format,
                        row_count=row_count,
                        rows=rows,
                        columns=columns
                    )
                    
                    if progress_callback:
                        progress_callback(3, 'in_progress', 'Processing data', None, substeps=[
                            {
                                "id": "ai-output-generation",
                                "label": "Output message generated",
                                "status": "completed",
                                "detail": f"Generated {len(purpose_output)} character message"
                            }
                        ])
                    
                    if progress_callback:
                        progress_callback(3, 'completed', 'Processing data', 'Data analyzed successfully')
                    
                    # 🎨 FORCE MARKDOWN: Convert output to markdown format (same as traditional execution)
                    if progress_callback:
                        progress_callback(4, 'in_progress', 'Generating output', 'Formatting results')
                    
                    print("🎨 Converting output to markdown format...")
                    markdown_output = self._ensure_markdown_format(purpose_output)
                    
                    # Create intermediate_steps format for _format_output
                    intermediate_steps = [{
                        "action": {
                            "tool": "postgres_query",
                            "tool_input": {"query": current_query},
                            "log": f"Used pre-built query template with parameters: {params}. Succeeded on attempt {attempt}/{max_retries}"
                        },
                        "result": result
                    }]
                    
                    # Use existing _format_output method with markdown output
                    formatted_result = self._format_output(
                        output=markdown_output,  # Use markdown-formatted output
                        output_format=output_format,
                        intermediate_steps=intermediate_steps,
                        agent_data=agent_data,  # Pass full agent data for context-aware summaries
                        visualization_preferences=visualization_preferences
                    )
                    
                    formatted_result['used_guidance'] = True
                    formatted_result['execution_time'] = f'Fast (pre-built template, attempt {attempt})'
                    formatted_result['query_attempts'] = attempt
                    if query_was_corrected:
                        formatted_result['query_corrected'] = True
                        formatted_result['correction_saved'] = True
                    
                    if progress_callback:
                        progress_callback(4, 'completed', 'Generating output', 'Output formatted successfully')
                        progress_callback(5, 'completed', 'Complete', 'Execution completed successfully')
                    
                    print("✅ Fast path execution completed successfully!")
                    return formatted_result
                
                else:
                    # Query failed - attempt to fix it
                    error_msg = result.get('error', 'Unknown error')
                    last_error = error_msg
                    print(f"  ❌ Query execution failed: {error_msg}")
                    print(f"  🔍 Failed query: {current_query[:200]}...")
                    print(f"  🔍 Parameters used: {params}")
                    
                    if attempt < max_retries:
                        print(f"  🔧 Attempting to fix SQL syntax error (attempt {attempt}/{max_retries})...")
                        
                        # Show AI query correction substep
                        if progress_callback:
                            progress_callback(2, 'in_progress', 'Running tools', None, substeps=[
                                {
                                    "id": "ai-query-fix",
                                    "label": "AI is fixing SQL query...",
                                    "status": "in_progress"
                                }
                            ])
                        
                        # Use LLM to fix the query
                        corrected_query = self._fix_sql_syntax_error(
                            query=current_query,
                            error=error_msg,
                            schema_context=execution_guidance.get('schema_snapshot', {})
                        )
                        
                        if corrected_query and corrected_query != current_query:
                            print(f"  ✅ Query corrected by AI")
                            print(f"  Original: {current_query[:100]}...")
                            print(f"  Corrected: {corrected_query[:100]}...")
                            current_query = corrected_query
                            query_was_corrected = True  # Mark that we made a correction
                            
                            # Show success substep
                            if progress_callback:
                                progress_callback(2, 'in_progress', 'Running tools', None, substeps=[
                                    {
                                        "id": "ai-query-fix",
                                        "label": "Query corrected successfully",
                                        "status": "completed",
                                        "detail": f"Retry attempt {attempt}/{max_retries}"
                                    }
                                ])
                        else:
                            print(f"  ⚠️ AI could not suggest a fix - breaking retry loop")
                            if progress_callback:
                                progress_callback(2, 'in_progress', 'Running tools', None, substeps=[
                                    {
                                        "id": "ai-query-fix",
                                        "label": "Could not fix query",
                                        "status": "error"
                                    }
                                ])
                            break
                    else:
                        print(f"  ❌ Max retries ({max_retries}) reached")
            
            # If we got here, all retries failed
            print(f"\n⚠️ Pre-built query template failed after {max_retries} attempts")
            print(f"  Last error: {last_error}")
            print(f"  🔄 Falling back to AI-based query generation during execution...")
            
            # Show fallback substep
            if progress_callback:
                progress_callback(2, 'in_progress', 'Running tools', None, substeps=[
                    {
                        "id": "ai-fallback",
                        "label": "Query correction failed, using AI to generate new query...",
                        "status": "in_progress"
                    }
                ])
            
            return None  # Signal to use traditional execution
            
        except Exception as e:
            print(f"❌ Error in fast path execution: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _fix_sql_syntax_error(self, query: str, error: str, schema_context: Dict) -> str:
        """
        Use LLM to fix SQL syntax errors with full schema cache context
        Dynamically fetches actual column types from schema to provide accurate correction guidance
        
        Args:
            query: The failing SQL query
            error: Error message from PostgreSQL
            schema_context: Schema information for context
            
        Returns:
            Corrected SQL query or empty string if cannot fix
        """
        try:
            from langchain_core.messages import HumanMessage
            from tools.postgres_connector import PostgresConnector
            
            # 🔍 Extract table names from the failing query to get relevant schema
            import re
            # First, identify CTEs (Common Table Expressions) to exclude them
            # CTEs are defined in WITH clauses: WITH cte_name AS (...) or WITH cte1 AS (...), cte2 AS (...)
            # Match: WITH cte_name AS or WITH cte_name AS( (with or without space before parenthesis)
            cte_pattern = r'WITH\s+(\w+)\s+AS\s*\('
            cte_names = set(re.findall(cte_pattern, query, re.IGNORECASE))
            
            # Also handle multiple CTEs separated by commas: WITH cte1 AS (...), cte2 AS (...)
            # Match pattern: , cte_name AS ( or ,cte_name AS (
            additional_ctes = re.findall(r',\s*(\w+)\s+AS\s*\(', query, re.IGNORECASE)
            cte_names.update(additional_ctes)
            
            # Extract table names from FROM and JOIN clauses
            table_pattern = r'(?:FROM|JOIN)\s+([\w_]+)'
            tables_in_query = re.findall(table_pattern, query, re.IGNORECASE)
            
            # Filter out CTEs - they're not real tables, just temporary result sets
            cte_names_lower = [c.lower() for c in cte_names]
            real_tables = [t for t in tables_in_query if t.lower() not in cte_names_lower]
            
            if cte_names:
                logger.debug(f"  🔍 Detected CTEs (excluding from schema fetch): {list(cte_names)}")
            
            print(f"  🔍 Detected tables in query: {real_tables}")
            if len(tables_in_query) != len(real_tables):
                print(f"  ⚠️ Filtered out {len(tables_in_query) - len(real_tables)} CTE(s) from table list")
            
            # 📦 Fetch schema details for each table from schema cache
            pg_connector = PostgresConnector()
            schema_details = []
            all_columns_info = {}  # Store column info for all tables: {table.column: {type, is_jsonb}}
            
            for table_name in real_tables:
                print(f"  📊 Fetching schema for table: {table_name}")
                table_schema = pg_connector.get_table_schema(table_name)
                
                if table_schema.get('success'):
                    columns = table_schema.get('columns', [])
                    jsonb_cols = table_schema.get('jsonb_columns', [])
                    foreign_keys = table_schema.get('foreign_keys', [])
                    
                    # Build detailed column list with types and operators
                    column_details = []
                    for col in columns[:30]:  # Show more columns with types
                        col_name = col['name']
                        col_type = col.get('data_type', col.get('type', 'unknown'))
                        is_jsonb = col_name in jsonb_cols
                        
                        # Store for later reference
                        all_columns_info[f"{table_name}.{col_name}"] = {
                            'type': col_type,
                            'is_jsonb': is_jsonb
                        }
                        
                        # Build column description with appropriate operator guidance
                        if is_jsonb:
                            column_details.append(f"{col_name} ({col_type}, JSONB - use ->>'value')")
                        elif col_type.lower() in ['varchar', 'text', 'character varying']:
                            column_details.append(f"{col_name} ({col_type}, TEXT - access directly, NO ->>)")
                        elif col_type.lower() in ['uuid', 'int4', 'int8', 'numeric', 'bool', 'timestamp', 'date']:
                            column_details.append(f"{col_name} ({col_type}, {col_type.upper()} - access directly)")
                        else:
                            column_details.append(f"{col_name} ({col_type})")
                    
                    # Separate JSONB and non-JSONB for clarity
                    jsonb_list = [col['name'] for col in columns if col['name'] in jsonb_cols]
                    non_jsonb_list = [col['name'] for col in columns[:15] if col['name'] not in jsonb_cols]
                    
                    schema_info = f"""\nTable: {table_name}
  Total columns: {len(columns)}
  Column details: {', '.join(column_details)}
  ⚠️ JSONB columns (MUST use ->>'value'): {', '.join(jsonb_list) if jsonb_list else 'None'}
  ⚠️ Regular columns (NO ->> operator): {', '.join(non_jsonb_list[:10]) if non_jsonb_list else 'None'}
  Foreign keys: {', '.join([f"{fk['column']} → {fk['references_table']}.{fk['references_column']}" for fk in foreign_keys[:5]]) if foreign_keys else 'None'}"""
                    schema_details.append(schema_info)
                else:
                    print(f"  ⚠️ Could not fetch schema for {table_name}")
            
            schema_context_str = "\n".join(schema_details) if schema_details else "Schema information not available"
            
            # 🎯 Analyze the error to provide specific guidance
            error_guidance = ""
            
            # Extract specific error line if available
            line_info = ""
            if "LINE" in error:
                line_match = re.search(r'LINE (\d+):\s*(.+?)(?:\n|$)', error)
                if line_match:
                    line_num = line_match.group(1)
                    line_content = line_match.group(2).strip()
                    line_info = f"\n**ERROR ON LINE {line_num}:** {line_content}"
            
            if "operator does not exist" in error.lower() and "->" in error:
                # Try to extract the specific column causing the issue
                col_match = re.search(r'(\w+)\.(\w+)->>', error)
                problematic_col = f"{col_match.group(1)}.{col_match.group(2)}" if col_match else "unknown"
                
                # Print debug info about the problematic column
                if col_match:
                    table_alias = col_match.group(1)
                    col_name = col_match.group(2)
                    print(f"  📍 Problematic column: {table_alias}.{col_name}")
                    
                    # Try to find the actual column info
                    for key, info in all_columns_info.items():
                        if col_name in key:
                            print(f"    Column info: {key} - Type: {info['type']}, Is JSONB: {info['is_jsonb']}")
                
                error_guidance = f"""\n⚠️ ERROR ANALYSIS: Operator issue detected!{line_info}
  - The ->> operator ONLY works on JSONB columns
  - **Problematic column: {problematic_col}**
  - Check the schema above: Is this column JSONB or a regular type (UUID, VARCHAR, etc.)?
  - If it's UUID/VARCHAR/INT: Access directly WITHOUT ->>'value'
  - If it's JSONB: Use ->>'value' to extract the string value
  - The LIKE operator does NOT work on DATE/TIMESTAMP types
  - For DATE filtering: Use string comparison BEFORE casting: invoice_date->>'value' LIKE 'MM/%/YYYY'
  - Example WRONG: cat.id (UUID) ->> 'value' ❌
  - Example CORRECT: (jsonb_field->>'value')::uuid = cat.id ✅
  
  **STEP-BY-STEP FIX:**
  1. Find the column mentioned in the error in the schema above
  2. Check if it's listed under 'JSONB columns' or 'Regular columns'
  3. If Regular: Remove ->>'value' and access directly
  4. If JSONB: Keep ->>'value' but ensure proper casting"""
            elif "column" in error.lower() and "does not exist" in error.lower():
                # Extract column name from error if possible
                col_match = re.search(r'column "([^"]+)"', error)
                missing_col = col_match.group(1) if col_match else "unknown"
                error_guidance = f"""\n⚠️ ERROR ANALYSIS: Column '{missing_col}' doesn't exist!
  - Check the exact column names in the schema above
  - This column is NOT in any of the tables in your query
  - Look for typos or wrong table aliases (i. vs v.)
  - DO NOT invent columns - use ONLY what's in the schema
  - If you need nested data, check if it exists in JSONB columns"""
            elif "must appear in the group by" in error.lower():
                error_guidance = """\n⚠️ ERROR ANALYSIS: GROUP BY clause incomplete!
  - All non-aggregated columns in SELECT must be in GROUP BY
  - Add missing columns to GROUP BY clause
  - Or use aggregate functions (COUNT, SUM, MAX, etc.) for those columns"""
            elif "foreign key" in error.lower() or "violates" in error.lower():
                error_guidance = """\n⚠️ ERROR ANALYSIS: JOIN condition issue!
  - Check the "Foreign keys" section in the schema above
  - Verify your JOIN conditions match the actual foreign key relationships
  - Example: If schema shows "vendor_id → icap_vendor.id", use: ON i.vendor_id = v.id
  - For JSONB foreign keys: Cast the JSONB value: (detail.product_id->>'value')::uuid = prod.id
  - DO NOT guess JOIN conditions - use exact relationships from schema"""
            
            fix_prompt = f"""You are a PostgreSQL expert. Fix this SQL query that is causing an error.

FAILING QUERY:
{query}

ERROR MESSAGE:
{error}{error_guidance}

DATABASE SCHEMA CONTEXT:
{schema_context_str}

🔴 THE 4 GOLDEN RULES OF DEFENSIVE SQL (MUST FOLLOW EVERY TIME):

📌 RULE 1: Defensive Join Pattern (for UUID fields)
   Never cast JSONB to UUID directly in JOIN. Always verify data exists first.
   ❌ BAD: LEFT JOIN icap_product_master prod ON (detail.product_id->>'value')::uuid = prod.id
   ✅ GOOD: LEFT JOIN icap_product_master prod ON NULLIF(detail.product_id->>'value', '') IS NOT NULL AND (detail.product_id->>'value')::uuid = prod.id

📌 RULE 2: Safe Numeric Pattern
   OCR data contains empty strings ''. Casting '' to numeric causes errors.
   ❌ BAD: (invoice.total->>'value')::numeric
   ✅ GOOD: NULLIF(invoice.total->>'value', '')::numeric
   Alternative: COALESCE(NULLIF(invoice.total->>'value', '')::numeric, 0)

📌 RULE 3: Date Handling Pattern (CRITICAL!)
   Dates are stored as MM/DD/YYYY strings. Use TO_DATE for all date operations.
   ❌ BAD: (invoice.due_date->>'value')::date
   ❌ BAD: invoice.due_date::date
   ❌ BAD: CURRENT_DATE - invoice.due_date
   ✅ GOOD: TO_DATE(invoice.due_date->>'value', 'MM/DD/YYYY')
   
   Date aging calculation:
   ✅ CURRENT_DATE - TO_DATE(invoice.due_date->>'value', 'MM/DD/YYYY') AS days_overdue
   
   Date filtering:
   ✅ WHERE TO_DATE(invoice.invoice_date->>'value', 'MM/DD/YYYY') BETWEEN TO_DATE('01/01/2024', 'MM/DD/YYYY') AND TO_DATE('12/31/2024', 'MM/DD/YYYY')
   
   Age buckets:
   ✅ CASE 
        WHEN CURRENT_DATE - TO_DATE(invoice.due_date->>'value', 'MM/DD/YYYY') <= 30 THEN '0-30 days'
        WHEN CURRENT_DATE - TO_DATE(invoice.due_date->>'value', 'MM/DD/YYYY') <= 60 THEN '31-60 days'
        ELSE '90+ days'
      END AS age_bucket

📌 RULE 4: Always Include Document Join
   batch_name lives in icap_document, not icap_invoice. Always join it.
   ✅ INNER JOIN icap_document d ON invoice.document_id = d.id
   This provides: batch_name, status, sub_status, accuracy

IMPORTANT RULES (Based on Actual Schema):
1. **CHECK COLUMN TYPES FIRST** - Look at the schema above to see each column's data type
2. **ONLY USE COLUMNS THAT EXIST** - DO NOT invent or assume columns exist
   - Cross-reference EVERY column with the schema above
   - If a column doesn't appear in schema, DO NOT use it
3. **JSONB Columns**: Use ->>'value' operator (listed in schema as "JSONB")
   Example: i.invoice_date->>'value' (if invoice_date is JSONB)
4. **Apply RULE 2 (NULLIF) for ALL numeric JSONB fields**
5. **Apply RULE 3 (TO_DATE) for ALL date JSONB fields**
6. **Apply RULE 1 (defensive join) for ALL UUID JSONB fields in JOIN conditions**
7. **VARCHAR/TEXT Columns**: Access directly, NO ->> operator
   Example: v.name, v.address (if these are VARCHAR/TEXT)
   If VARCHAR contains JSON: Cast first: (v.address::jsonb)->>'street'
8. **Other Types** (uuid, int, numeric, bool, timestamp, date): Access directly
   Example: i.id, v.tenant_id, i.created_on
9. Use LEFT JOIN for optional relationships (vendor, product, category)
10. Use INNER JOIN for required relationships (document)
11. **NEVER EXPOSE ID COLUMNS** - ID columns must NEVER appear in SELECT:
   - ❌ WRONG: SELECT d.id, v.vendor_id, cat.id
   - ✅ CORRECT: SELECT d.description, v.name, cat.name
   - If you need to reference an entity, JOIN its table and show the name/description column
   - ID columns are: id, document_id, vendor_id, product_id, category_id, tenant_id, user_id, etc.
   - **CRITICAL**: Remove ALL id/ID columns from SELECT, even if they were in the original query
12. Use column names EXACTLY as shown in schema
13. **USE SCHEMA FOREIGN KEYS FOR JOINS** - DO NOT hallucinate JOIN conditions:
   - Look at "Foreign keys" section in schema above
   - Use ONLY the foreign key relationships shown in schema
   - Example from schema: "vendor_id → icap_vendor.id" means JOIN icap_vendor v ON i.vendor_id = v.id
   - ❌ WRONG: Guessing JOIN conditions based on column names
   - ✅ CORRECT: Using exact foreign key relationships from schema
   - If a foreign key is JSONB (contains ->>'value'), cast it AND use RULE 1: LEFT JOIN prod ON NULLIF(detail.product_id->>'value', '') IS NOT NULL AND (detail.product_id->>'value')::uuid = prod.id
14. **CRITICAL**: If you're not sure a column exists, DON'T use it - check schema first
15. **RESOLVE ID COLUMNS TO NAMES** - NEVER expose raw ID values:
   - If you see category_id (JSONB): JOIN icap_tenant_category_master and show category.name instead
   - If you see product_id (JSONB): JOIN icap_product_master and show product.name instead
   - ID columns stored as JSONB contain {{"value": "uuid-string"}}, extract with ->>'value'
   - Example JOIN: LEFT JOIN icap_tenant_category_master cat ON NULLIF(d.category_id->>'value', '') IS NOT NULL AND (d.category_id->>'value')::uuid = cat.id
   - Then SELECT: cat.name as category_name (NOT d.category_id)
16. **GROUP BY VALIDATION** - Check if all non-aggregated columns in SELECT are in GROUP BY:
   - If SELECT has cat.name, GROUP BY must include cat.name (or cat.id)
   - If using CASE expressions with table columns, add those columns to GROUP BY
   - Better: Use aggregate function MAX(cat.name) if grouping doesn't need cat.name
17. **PROACTIVE ERROR CHECKING** - Before returning the query, verify:
   ✅ All columns in SELECT exist in the schema
   ✅ All non-aggregated SELECT columns are in GROUP BY
   ✅ All table aliases are defined in FROM/JOIN clauses
   ✅ No ->> operator on non-JSONB columns
   ✅ WHERE clause comes before GROUP BY
   ✅ **NO ID COLUMNS in SELECT** (check for: .id, _id, document_id, vendor_id, product_id, category_id, etc.)
   ✅ **JOIN conditions match schema's foreign keys** - verify each JOIN uses the exact foreign key relationship from schema
   ✅ **All date operations use TO_DATE** - no ::date casts
   ✅ **All numeric JSONB fields use NULLIF** - no direct ::numeric casts
   ✅ **All UUID joins use defensive pattern** - NULLIF check before casting
18. Return ONLY the corrected SQL query, no explanations

CORRECTED QUERY:"""
            
            response = self.llm.invoke([HumanMessage(content=fix_prompt)])
            corrected_query = response.content.strip()
            
            # Remove any markdown code blocks
            if '```' in corrected_query:
                import re
                code_match = re.search(r'```(?:sql)?\n(.*?)\n```', corrected_query, re.DOTALL)
                if code_match:
                    corrected_query = code_match.group(1).strip()
            
            # Basic validation - must be a SELECT query
            if not corrected_query.upper().strip().startswith('SELECT'):
                print("  ⚠️ AI response is not a valid SELECT query")
                return ""
            
            # 🚫 POST-PROCESSING: Remove any ID columns that AI might have included
            corrected_query = self._remove_id_columns_from_query(corrected_query)
            
            print(f"  ✅ AI provided corrected query (length: {len(corrected_query)} chars)")
            return corrected_query
            
        except Exception as e:
            print(f"  ❌ Error in SQL fix attempt: {e}")
            return ""
    
    def _remove_id_columns_from_query(self, query: str) -> str:
        """
        Post-process query to remove any ID columns from SELECT clause
        
        Args:
            query: SQL query string
            
        Returns:
            Query with ID columns removed from SELECT
        """
        try:
            import re
            
            # Split query to isolate SELECT clause
            select_match = re.search(r'SELECT\s+(.*?)\s+FROM', query, re.IGNORECASE | re.DOTALL)
            if not select_match:
                return query  # Can't parse, return as-is
            
            select_clause = select_match.group(1)
            select_start = select_match.start(1)
            select_end = select_match.end(1)
            
            # Split into individual column expressions
            columns = []
            current = ""
            paren_depth = 0
            
            for char in select_clause:
                if char == '(':
                    paren_depth += 1
                elif char == ')':
                    paren_depth -= 1
                elif char == ',' and paren_depth == 0:
                    columns.append(current.strip())
                    current = ""
                    continue
                current += char
            
            if current.strip():
                columns.append(current.strip())
            
            # Filter out ID columns
            id_patterns = [
                r'\b\w+\.id\s+as\s+\w*id\w*',  # Match: d.id as document_id, v.id as vendor_id
                r'\b\w+\.id$',  # Match: d.id, v.id (without alias)
                r'\b\w+\s+as\s+\w*_id$',  # Match: column as something_id
                r'\b\w+\s+as\s+id$',  # Match: column as id
            ]
            
            filtered_columns = []
            removed_columns = []
            
            for col in columns:
                is_id_column = False
                col_lower = col.lower()
                
                # Check against ID patterns
                for pattern in id_patterns:
                    if re.search(pattern, col_lower):
                        is_id_column = True
                        removed_columns.append(col)
                        break
                
                if not is_id_column:
                    filtered_columns.append(col)
            
            if removed_columns:
                print(f"  🚫 Removed {len(removed_columns)} ID column(s) from query:")
                for removed in removed_columns:
                    print(f"     - {removed[:80]}")
            
            # Reconstruct query
            if filtered_columns:
                new_select_clause = ',\n    '.join(filtered_columns)
                new_query = query[:select_start] + new_select_clause + query[select_end:]
                return new_query
            else:
                print("  ⚠️ All columns were ID columns - returning original query")
                return query
                
        except Exception as e:
            print(f"  ⚠️ Error removing ID columns: {e}")
            return query  # Return original on error
    
    def _validate_column_types(self, query: str, schema_context: Dict) -> List[str]:
        """
        Validate that columns in query match their types from schema
        
        Args:
            query: SQL query to validate
            schema_context: Schema information with column types
            
        Returns:
            List of validation issues found (empty if all valid)
        """
        try:
            import re
            from tools.postgres_connector import PostgresConnector
            
            issues = []
            
            # Extract table names from query
            table_pattern = r'(?:FROM|JOIN)\s+([\w_]+)'
            tables = re.findall(table_pattern, query, re.IGNORECASE)
            
            # Get schema for each table
            pg_connector = PostgresConnector()
            table_schemas = {}
            
            for table_name in set(tables):
                schema_info = pg_connector.get_table_schema(table_name)
                if schema_info.get('success'):
                    columns = {col['name']: col for col in schema_info.get('columns', [])}
                    table_schemas[table_name] = columns
            
            # Extract column references from SELECT clause
            select_match = re.search(r'SELECT\s+(.*?)\s+FROM', query, re.IGNORECASE | re.DOTALL)
            if select_match:
                select_clause = select_match.group(1)
                
                # Find column references (table.column or just column)
                column_patterns = [
                    r'(\w+)\.(\w+)',  # table.column
                    r'\b(\w+)\s+as\s+\w+',  # column as alias
                ]
                
                for pattern in column_patterns:
                    matches = re.findall(pattern, select_clause, re.IGNORECASE)
                    for match in matches:
                        if isinstance(match, tuple):
                            table_alias, col_name = match
                        else:
                            table_alias, col_name = None, match
                        
                        # Find which table this alias refers to
                        if table_alias:
                            # Check if this table exists in our schemas
                            for table_name, columns in table_schemas.items():
                                if table_name == table_alias or table_name.endswith('_' + table_alias):
                                    if col_name in columns:
                                        col_info = columns[col_name]
                                        col_type = col_info.get('type', 'unknown')
                                        
                                        # Check if JSONB column is used correctly
                                        if col_type == 'jsonb':
                                            # Check if it uses ->>'value'
                                            if f"{col_name}->>'value'" not in select_clause and f"{table_alias}.{col_name}->>'value'" not in select_clause:
                                                # Check if it's used incorrectly
                                                if re.search(rf'\b{col_name}\b(?!->>)', select_clause, re.IGNORECASE):
                                                    issues.append(f"⚠️ JSONB column '{table_alias}.{col_name}' should use ->>'value' extraction")
                                        
                                        # Check if non-JSONB column incorrectly uses ->>
                                        elif col_type != 'jsonb':
                                            if f"{col_name}->>" in select_clause or f"{table_alias}.{col_name}->>" in select_clause:
                                                issues.append(f"⚠️ Non-JSONB column '{table_alias}.{col_name}' (type: {col_type}) incorrectly uses ->> operator")
            
            return issues
            
        except Exception as e:
            print(f"  ⚠️ Error in column type validation: {e}")
            return []
    
    def _validate_and_fix_query(self, query: str, schema_context: Dict) -> tuple[str, bool]:
        """
        Proactively validate query for common errors and attempt to fix them before execution
        
        Args:
            query: SQL query to validate
            schema_context: Schema information for validation
            
        Returns:
            Tuple of (fixed_query, was_modified)
        """
        try:
            import re
            from langchain_core.messages import HumanMessage
            from tools.postgres_connector import PostgresConnector
            
            print("\n🔍 PRE-EXECUTION VALIDATION: Checking query for common errors...")
            
            issues_found = []
            
            # Add column type validation
            type_issues = self._validate_column_types(query, schema_context)
            issues_found.extend(type_issues)
            
            # 1. Check for ID columns in SELECT
            id_patterns = [
                r'\b\w+\.id\s+as\s+\w*id\w*',
                r'\b\w+\.id(?!\s*=)',  # Match .id not followed by =
                r'\b\w+\s+as\s+\w*_id$',
            ]
            
            select_match = re.search(r'SELECT\s+(.*?)\s+FROM', query, re.IGNORECASE | re.DOTALL)
            if select_match:
                select_clause = select_match.group(1).lower()
                for pattern in id_patterns:
                    if re.search(pattern, select_clause):
                        issues_found.append("⚠️ ID columns detected in SELECT clause")
                        break
            
            # 2. Check for GROUP BY completeness
            if 'group by' in query.lower():
                # Extract non-aggregated columns from SELECT
                if select_match:
                    select_text = select_match.group(1)
                    # Check for columns that should be in GROUP BY
                    case_expr = re.findall(r'case\s+when.*?then\s+(\w+\.\w+)', select_text, re.IGNORECASE)
                    if case_expr:
                        group_by_match = re.search(r'GROUP BY\s+(.*?)(?:ORDER BY|HAVING|$)', query, re.IGNORECASE | re.DOTALL)
                        if group_by_match:
                            group_by_clause = group_by_match.group(1).lower()
                            for col in case_expr:
                                if col.lower() not in group_by_clause:
                                    issues_found.append(f"⚠️ Column {col} used in CASE but not in GROUP BY")
            
            # 3. Check for WHERE after GROUP BY
            where_pos = query.lower().find('where')
            group_pos = query.lower().find('group by')
            if where_pos > 0 and group_pos > 0 and where_pos > group_pos:
                issues_found.append("⚠️ WHERE clause appears after GROUP BY (should be before)")
            
            if not issues_found:
                print("  ✅ Pre-validation passed: No common errors detected")
                return query, False
            
            # Issues found - attempt to fix
            print(f"  🔧 Found {len(issues_found)} potential issue(s):")
            for issue in issues_found:
                print(f"     {issue}")
            
            print("  🤖 Asking AI to fix issues proactively...")
            
            # Get schema details
            # First, identify CTEs (Common Table Expressions) to exclude them
            # CTEs are defined in WITH clauses: WITH cte_name AS (...) or WITH cte1 AS (...), cte2 AS (...)
            cte_pattern = r'WITH\s+(\w+)\s+AS\s*\('
            cte_names = set(re.findall(cte_pattern, query, re.IGNORECASE))
            
            # Also handle multiple CTEs separated by commas
            additional_ctes = re.findall(r',\s*(\w+)\s+AS\s*\(', query, re.IGNORECASE)
            cte_names.update(additional_ctes)
            
            table_pattern = r'(?:FROM|JOIN)\s+([\w_]+)'
            tables_in_query = re.findall(table_pattern, query, re.IGNORECASE)
            
            # Filter out CTEs - they're not real tables
            cte_names_lower = [c.lower() for c in cte_names]
            real_tables = [t for t in tables_in_query if t.lower() not in cte_names_lower]
            
            pg_connector = PostgresConnector()
            schema_details = []
            
            for table_name in real_tables[:5]:  # Limit to 5 tables
                table_schema = pg_connector.get_table_schema(table_name)
                if table_schema.get('success'):
                    columns = table_schema.get('columns', [])
                    jsonb_cols = table_schema.get('jsonb_columns', [])
                    foreign_keys = table_schema.get('foreign_keys', [])
                    
                    schema_info = f"""\nTable: {table_name}
  Columns: {', '.join([c['name'] for c in columns[:20]])}
  JSONB columns: {', '.join(jsonb_cols) if jsonb_cols else 'None'}
  Foreign keys: {', '.join([f"{fk['column']} → {fk['references_table']}.{fk['references_column']}" for fk in foreign_keys[:5]]) if foreign_keys else 'None'}"""
                    schema_details.append(schema_info)
            
            schema_context_str = "\n".join(schema_details) if schema_details else "Schema not available"
            
            fix_prompt = f"""You are a PostgreSQL expert. Fix the issues in this SQL query BEFORE execution.

CURRENT QUERY:
{query}

ISSUES DETECTED:
{chr(10).join(issues_found)}

SCHEMA CONTEXT:
{schema_context_str}

FIX THESE ISSUES:
1. Remove ANY ID columns from SELECT (d.id, v.id, document_id, vendor_id, etc.)
2. Ensure all non-aggregated SELECT columns are in GROUP BY
3. Move WHERE clause before GROUP BY if needed
4. Use schema foreign keys for JOIN conditions
5. Use MAX() or another aggregate for columns that don't need grouping

Return ONLY the corrected SQL query, no explanations.

CORRECTED QUERY:"""
            
            response = self.llm.invoke([HumanMessage(content=fix_prompt)])
            fixed_query = response.content.strip()
            
            # Remove markdown code blocks
            if '```' in fixed_query:
                code_match = re.search(r'```(?:sql)?\n(.*?)\n```', fixed_query, re.DOTALL)
                if code_match:
                    fixed_query = code_match.group(1).strip()
            
            if fixed_query and fixed_query.upper().strip().startswith('SELECT'):
                print(f"  ✅ AI proactively fixed query ({len(fixed_query)} chars)")
                return fixed_query, True
            else:
                print("  ⚠️ AI fix failed, using original query")
                return query, False
                
        except Exception as e:
            print(f"  ⚠️ Error in pre-validation: {e}")
            return query, False
    
    def _save_corrected_query_template(self, agent_data: Dict, corrected_query: str, original_query: str, attempt_number: int) -> None:
        """
        Save AI-corrected query template back to agent JSON for future use
        This updates the execution_guidance with the corrected query template
        
        Args:
            agent_data: Agent configuration dictionary
            corrected_query: The AI-corrected SQL query that worked
            original_query: The original query that failed
            attempt_number: Which attempt succeeded (2 or 3)
        """
        try:
            agent_id = agent_data.get('id')
            if not agent_id:
                print("  ⚠️ No agent_id found - cannot save correction")
                return
            
            # Get current execution guidance
            execution_guidance = agent_data.get('execution_guidance')
            if not execution_guidance:
                print("  ⚠️ No execution_guidance found - cannot save correction")
                return
            
            # Extract the base query (without parameters) from the corrected query
            # We need to reverse-engineer the template by removing the specific parameter values
            query_template = execution_guidance.get('query_template', {})
            parameters = query_template.get('parameters', [])
            
            # Create updated template by replacing parameter placeholders back
            # This is a simplified approach - we store the corrected full template
            corrected_template = corrected_query
            
            # For parameterized queries, we need to extract the base pattern
            # Example: Replace "WHERE date LIKE '02/%/2025'" back to "WHERE date LIKE '{month}/%/{year}'"
            workflow_config = agent_data.get('workflow_config', {})
            trigger_type = workflow_config.get('trigger_type', 'text_query')
            
            # Reconstruct the template with placeholders
            if trigger_type == "month_year" and 'month' in parameters and 'year' in parameters:
                # Extract the month/year pattern and replace with placeholders
                import re
                # Pattern: 'MM/%/YYYY' -> '{month}/%/{year}'
                corrected_template = re.sub(r"'(\d{2})/%/(\d{4})'", "'{month}/%/{year}'", corrected_query)
            elif trigger_type == "date_range" and 'start_date' in parameters and 'end_date' in parameters:
                import re
                # Pattern: '>= 'MM/DD/YYYY' AND <= 'MM/DD/YYYY'' -> '>= '{start_date}' AND <= '{end_date}''
                corrected_template = re.sub(r"'\d{2}/\d{2}/\d{4}'", "'{start_date}'", corrected_query, count=1)
                corrected_template = re.sub(r"'\d{2}/\d{2}/\d{4}'", "'{end_date}'", corrected_template, count=1)
            elif trigger_type == "year" and 'year' in parameters:
                import re
                # Pattern: '%/%/YYYY' -> '%/%/{year}'
                corrected_template = re.sub(r"'%/%/(\d{4})'", "'%/%/{year}'", corrected_query)
            
            # Update the execution guidance with corrected template
            query_template['full_template'] = corrected_template
            query_template['base_query'] = corrected_template.split('WHERE')[0].strip() if 'WHERE' in corrected_template.upper() else corrected_template
            query_template['correction_history'] = query_template.get('correction_history', [])
            query_template['correction_history'].append({
                "original_query": original_query,
                "corrected_query": corrected_query,
                "corrected_template": corrected_template,
                "attempt_number": attempt_number,
                "corrected_at": datetime.now().isoformat(),
                "trigger_type": trigger_type
            })
            
            execution_guidance['query_template'] = query_template
            execution_guidance['last_correction'] = datetime.now().isoformat()
            
            # Save updated agent data to storage
            updated_data = {
                'execution_guidance': execution_guidance
            }
            
            self.storage.update_agent(agent_id, updated_data)
            
            print(f"  ✅ Corrected query template saved to agent JSON")
            print(f"     - Original template had syntax error")
            print(f"     - Corrected template: {corrected_template[:80]}...")
            print(f"     - Correction history: {len(query_template['correction_history'])} correction(s)")
            print(f"  ℹ️  Future executions will use the corrected template")
            
        except Exception as e:
            print(f"  ⚠️ Error saving corrected query template: {e}")
            import traceback
            traceback.print_exc()
    
    def _extract_successful_query_from_steps(self, intermediate_steps: List) -> str:
        """
        Extract the successful SQL query from intermediate steps
        
        Args:
            intermediate_steps: List of execution steps from LangChain
            
        Returns:
            SQL query string if found, otherwise None
        """
        try:
            for step in intermediate_steps:
                # Handle tuple format (action, result)
                if isinstance(step, tuple) and len(step) >= 2:
                    action, result = step[0], step[1]
                    tool_name = getattr(action, 'tool', None)
                    
                    if tool_name == 'postgres_query':
                        # Extract query from tool input
                        tool_input = getattr(action, 'tool_input', {})
                        if isinstance(tool_input, dict):
                            query = tool_input.get('query')
                            if query:
                                # Verify the query was successful by checking result
                                if isinstance(result, str):
                                    try:
                                        result_dict = eval(result)
                                        if result_dict.get('success'):
                                            return query
                                    except:
                                        pass
                                elif isinstance(result, dict) and result.get('success'):
                                    return query
            
            return None
            
        except Exception as e:
            print(f"  ⚠️ Error extracting query from steps: {e}")
            return None
    
    def _save_successful_query_to_agent(self, agent_id: str, agent_data: Dict, successful_query: str, 
                                        user_query: str, input_data: Dict = None) -> None:
        """
        Save a successful query to the agent's execution_guidance for future reuse
        This is called when a query executes successfully, whether it's a new query or a corrected one
        
        Args:
            agent_id: Agent ID
            agent_data: Agent configuration dictionary
            successful_query: The SQL query that executed successfully
            user_query: The original user query/request
            input_data: Optional structured input data (month, year, etc.)
        """
        try:
            workflow_config = agent_data.get('workflow_config', {})
            trigger_type = workflow_config.get('trigger_type', 'text_query')
            
            print(f"  💾 AUTO-SAVE: Saving successful query...")
            print(f"     - Trigger type: {trigger_type}")
            print(f"     - Query length: {len(successful_query)} chars")
            
            # For text_query, save the query but mark it as non-parameterized
            if trigger_type == 'text_query':
                print(f"  📝 Text query mode - saving exact query (no parameterization)")
                query_template_str = successful_query
                parameters = []
            else:
                # Extract parameters from the successful query based on trigger type
                query_template_str, parameters = self._convert_query_to_template(successful_query, trigger_type, input_data)
                
                if not query_template_str:
                    print(f"  ⚠️ Could not convert query to template - saving as-is")
                    query_template_str = successful_query
                    parameters = []
            
            # Get or create execution_guidance
            execution_guidance = agent_data.get('execution_guidance', {})
            
            # Create query template structure
            query_template = {
                "full_template": query_template_str,
                "base_query": successful_query.split('WHERE')[0].strip() if 'WHERE' in successful_query.upper() else successful_query,
                "parameters": parameters,
                "param_instructions": self._get_param_instructions(trigger_type, parameters),
                "auto_saved": True,
                "saved_from": "successful_execution",
                "saved_at": datetime.now().isoformat(),
                "original_query": successful_query,
                "user_query": user_query
            }
            
            # Update or create execution_guidance
            if not execution_guidance or execution_guidance.get('error'):
                # Create new guidance
                execution_guidance = {
                    "query_template": query_template,
                    "execution_plan": self._build_execution_plan(
                        trigger_type=trigger_type,
                        output_format=workflow_config.get('output_format', 'text'),
                        query_template=query_template
                    ),
                    "schema_context": "Auto-generated from successful execution",
                    "generated_at": datetime.now().isoformat(),
                    "configuration": {
                        "trigger_type": trigger_type,
                        "output_format": workflow_config.get('output_format', 'text'),
                        "prompt": agent_data.get('prompt', '')
                    }
                }
            else:
                # Update existing guidance with new query template
                execution_guidance['query_template'] = query_template
                execution_guidance['last_updated'] = datetime.now().isoformat()
                execution_guidance['updated_from'] = 'successful_execution'
            
            # Save to agent storage
            self.storage.update_agent(agent_id, {'execution_guidance': execution_guidance})
            
            print(f"  ✅ Query auto-saved to agent JSON for future reuse")
            print(f"     - Template: {query_template_str[:80]}...")
            print(f"     - Parameters: {parameters}")
            print(f"     - Trigger type: {trigger_type}")
            print(f"  ℹ️  Future executions will use this successful query")
            
        except Exception as e:
            print(f"  ⚠️ Error auto-saving query: {e}")
            import traceback
            traceback.print_exc()
    
    def _convert_query_to_template(self, query: str, trigger_type: str, input_data: Dict = None) -> tuple:
        """
        Convert a successful query to a parameterized template
        
        Args:
            query: The successful SQL query
            trigger_type: Workflow trigger type
            input_data: Optional input data used in execution
            
        Returns:
            Tuple of (template_string, parameters_list)
        """
        try:
            import re
            
            parameters = []
            template = query
            
            if trigger_type == "month_year" and input_data:
                month = input_data.get('month')
                year = input_data.get('year')
                
                if month and year:
                    # Replace specific month/year with template placeholders
                    # Pattern: 'MM/%/YYYY' -> '{month}/%/{year}'
                    pattern = f"'{month}/%/{year}'"
                    if pattern in query:
                        template = query.replace(pattern, "'{month}/%/{year}'")
                        parameters = ['month', 'year']
                    else:
                        # Try without quotes
                        pattern_no_quotes = f"{month}/%/{year}"
                        template = query.replace(pattern_no_quotes, "{month}/%/{year}")
                        parameters = ['month', 'year']
            
            elif trigger_type == "date_range" and input_data:
                start_date = input_data.get('start_date')
                end_date = input_data.get('end_date')
                
                if start_date and end_date:
                    # Replace specific dates with template placeholders
                    template = re.sub(rf"'{re.escape(start_date)}'", "'{start_date}'", query, count=1)
                    template = re.sub(rf"'{re.escape(end_date)}'", "'{end_date}'", template, count=1)
                    parameters = ['start_date', 'end_date']
            
            elif trigger_type == "year" and input_data:
                year = input_data.get('year')
                
                if year:
                    # Replace specific year with template placeholder
                    # Pattern: '%/%/YYYY' -> '%/%/{year}'
                    pattern = f"'%/%/{year}'"
                    if pattern in query:
                        template = query.replace(pattern, "'%/%/{year}'")
                        parameters = ['year']
            
            return (template, parameters)
            
        except Exception as e:
            print(f"  ⚠️ Error converting query to template: {e}")
            return (None, [])
    
    def _get_param_instructions(self, trigger_type: str, parameters: List[str]) -> str:
        """
        Generate parameter extraction instructions based on trigger type
        """
        if trigger_type == "month_year":
            return "Extract 'month' and 'year' from input_data. Month should be 2-digit format (01-12)."
        elif trigger_type == "date_range":
            return "Extract 'start_date' and 'end_date' from input_data. Format: MM/DD/YYYY."
        elif trigger_type == "year":
            return "Extract 'year' from input_data (4-digit format)."
        elif trigger_type == "conditions":
            return f"Extract these fields from input_data: {', '.join(parameters)}"
        else:
            return "Parse user query to determine filter conditions dynamically."
    
    def _inspect_schema_for_prompt(self, prompt: str, agent_tools: List) -> str:
        """
        Inspect database schema based on the user prompt to provide context-specific guidance
        
        Args:
            prompt: User prompt describing what the agent should do
            agent_tools: Available tools (to find postgres connector)
            
        Returns:
            Schema context string to include in system prompt
        """
        try:
            # Find the postgres connector tool
            postgres_tool = None
            for tool in agent_tools:
                if tool.name == 'postgres_inspect_schema':
                    # Get the actual tool function/connector from the tool
                    # LangChain tools wrap the actual function, we need to access it
                    postgres_tool = tool
                    break
            
            if not postgres_tool:
                print("🔴 No postgres_inspect_schema tool found for schema inspection")
                return ""
            
            # Extract entities from the user prompt (invoice, vendor, product, customer, etc.)
            prompt_lower = prompt.lower()
            
            # Common business entities to look for
            entity_keywords = [
                'invoice', 'vendor', 'supplier', 'product', 'item', 'customer', 
                'payment', 'order', 'bill', 'transaction', 'document', 'line item'
            ]
            
            detected_entities = []
            for entity in entity_keywords:
                if entity in prompt_lower:
                    detected_entities.append(entity)
            
            if not detected_entities:
                print("ℹ️ No specific entities detected in prompt, skipping schema inspection")
                return ""
            
            print(f"🔍 Detected entities in prompt: {detected_entities}")
            
            # Import postgres connector directly to call get_table_schema
            from tools.postgres_connector import PostgresConnector
            
            pg_connector = PostgresConnector()
            schema_context_parts = []
            
            # Get list of all tables first
            all_tables_result = pg_connector.get_table_schema(table_name="")
            if not all_tables_result.get('success'):
                print(f"⚠️ Failed to get table list: {all_tables_result.get('error')}")
                return ""
            
            available_tables = all_tables_result.get('tables', [])
            print(f"📊 Found {len(available_tables)} tables in database")
            
            # For each detected entity, find matching tables and inspect them
            inspected_tables = set()
            
            for entity in detected_entities:
                # Find tables related to this entity
                matching_tables = [t for t in available_tables if entity.replace(' ', '_') in t.lower()]
                
                for table_name in matching_tables[:2]:  # Limit to 2 tables per entity to avoid overload
                    if table_name in inspected_tables:
                        continue
                    
                    print(f"🔍 Inspecting schema for table: {table_name}")
                    schema_info = pg_connector.get_table_schema(table_name=table_name)
                    
                    if schema_info.get('success'):
                        inspected_tables.add(table_name)
                        
                        # Extract key information
                        columns = schema_info.get('columns', [])
                        jsonb_cols = schema_info.get('jsonb_columns', [])
                        foreign_keys = schema_info.get('foreign_keys', [])
                        related_tables = schema_info.get('related_tables', '')
                        sample_data = schema_info.get('sample_data', [])
                        
                        # Build context for this table with explicit column types
                        table_context = f"\n**Table: {table_name}**\n"
                        table_context += f"- Total columns: {len(columns)}\n"
                        
                        # Group columns by type for better clarity
                        column_by_type = {}
                        for col in columns:
                            col_type = col.get('type', 'unknown')
                            if col_type not in column_by_type:
                                column_by_type[col_type] = []
                            column_by_type[col_type].append(col['name'])
                        
                        # Show columns grouped by type
                        for col_type, col_names in column_by_type.items():
                            if col_type == 'jsonb':
                                table_context += f"\n- **JSONB columns** ({len(col_names)}): {', '.join(col_names[:8])}"
                                if len(col_names) > 8:
                                    table_context += f" ... and {len(col_names) - 8} more"
                                table_context += f"\n  ⚠️ These MUST use ->>'value' extraction: ({col_names[0]}->>'value')::text"
                            elif col_type == 'uuid':
                                table_context += f"\n- **UUID columns** ({len(col_names)}): {', '.join(col_names[:5])}"
                                if len(col_names) > 5:
                                    table_context += f" ... and {len(col_names) - 5} more"
                            elif col_type in ['varchar', 'text', 'character varying']:
                                table_context += f"\n- **Text columns** ({len(col_names)}): {', '.join(col_names[:5])}"
                                if len(col_names) > 5:
                                    table_context += f" ... and {len(col_names) - 5} more"
                            elif col_type in ['numeric', 'integer', 'bigint', 'decimal']:
                                table_context += f"\n- **Numeric columns** ({len(col_names)}): {', '.join(col_names[:5])}"
                                if len(col_names) > 5:
                                    table_context += f" ... and {len(col_names) - 5} more"
                            else:
                                table_context += f"\n- **{col_type} columns** ({len(col_names)}): {', '.join(col_names[:5])}"
                                if len(col_names) > 5:
                                    table_context += f" ... and {len(col_names) - 5} more"
                        
                        # Show key columns with their types explicitly
                        table_context += f"\n\n- **Key columns with types**:"
                        for col in columns[:10]:  # Show first 10 with types
                            col_name = col['name']
                            col_type = col.get('type', 'unknown')
                            nullable = col.get('nullable', True)
                            null_str = "NULL" if nullable else "NOT NULL"
                            
                            if col_type == 'jsonb':
                                table_context += f"\n  • {col_name}: JSONB ({null_str}) → Use ({col_name}->>'value')::text"
                            else:
                                table_context += f"\n  • {col_name}: {col_type.upper()} ({null_str})"
                        
                        if len(columns) > 10:
                            table_context += f"\n  ... and {len(columns) - 10} more columns"
                        
                        if foreign_keys:
                            table_context += f"\n\n- **Foreign Key Relationships**:"
                            for fk in foreign_keys[:5]:
                                fk_col = fk.get('column', 'unknown')
                                ref_table = fk.get('references_table', 'unknown')
                                ref_col = fk.get('references_column', 'id')
                                # Check if FK column is JSONB
                                fk_col_info = next((c for c in columns if c['name'] == fk_col), None)
                                if fk_col_info and fk_col_info.get('type') == 'jsonb':
                                    table_context += f"\n  • {fk_col} (JSONB) → {ref_table}.{ref_col} (use defensive join pattern)"
                                else:
                                    table_context += f"\n  • {fk_col} → {ref_table}.{ref_col}"
                        
                        if related_tables:
                            table_context += f"\n- Related tables: {related_tables}"
                        
                        # Show sample data structure (first record only)
                        if sample_data and len(sample_data) > 0:
                            sample = sample_data[0]
                            sample_keys = list(sample.keys())[:5]  # Show first 5 fields
                            table_context += f"\n- Sample fields: {', '.join(sample_keys)}"
                        
                        schema_context_parts.append(table_context)
            
            if schema_context_parts:
                context = "The database has been pre-inspected for your task. Key tables and columns:\n"
                context += "\n".join(schema_context_parts)
                context += "\n\n⚠️ IMPORTANT: This is just a preview. You must still call postgres_inspect_schema() for each table before writing queries to get complete column lists and relationships."
                return context
            else:
                return ""
            
        except Exception as e:
            print(f"❌ Error during schema inspection: {e}")
            import traceback
            traceback.print_exc()
            return ""
    
    def _build_query_template(self, prompt: str, trigger_type: str, schema_info: str, workflow_config: Dict = None) -> Dict[str, Any]:
        """
        Build parameterized query template based on trigger type
        Uses LLM to generate the base query, then adds appropriate WHERE clause
        
        Args:
            prompt: User prompt describing the data needed
            trigger_type: Type of trigger (month_year, date_range, year, text_query, conditions)
            schema_info: Schema context from inspection
            workflow_config: Optional workflow configuration with input_fields
            
        Returns:
            Dictionary with query template components
        """
        try:
            # Build prompt for LLM to generate base query
            query_generation_prompt = f"""Based on this user request and database schema, generate a complete SQL SELECT query.

User Request: {prompt}

Database Schema Information:
{schema_info}

🔴 THE 4 GOLDEN RULES OF DEFENSIVE SQL (MUST FOLLOW EVERY TIME):

📌 RULE 1: Defensive Join Pattern (for UUID fields)
   Never cast JSONB to UUID directly in JOIN. Always verify data exists first.
   ❌ BAD: LEFT JOIN icap_product_master prod ON (detail.product_id->>'value')::uuid = prod.id
   ✅ GOOD: LEFT JOIN icap_product_master prod ON NULLIF(detail.product_id->>'value', '') IS NOT NULL AND (detail.product_id->>'value')::uuid = prod.id

📌 RULE 2: Safe Numeric Pattern
   OCR data contains empty strings ''. Casting '' to numeric causes errors.
   ❌ BAD: (invoice.total->>'value')::numeric
   ✅ GOOD: NULLIF(invoice.total->>'value', '')::numeric
   Alternative: COALESCE(NULLIF(invoice.total->>'value', '')::numeric, 0)

📌 RULE 3: Date Handling Pattern (CRITICAL!)
   Dates are stored as MM/DD/YYYY strings. Use TO_DATE for all date operations.
   ❌ BAD: (invoice.due_date->>'value')::date
   ❌ BAD: invoice.due_date::date
   ❌ BAD: CURRENT_DATE - invoice.due_date
   ✅ GOOD: TO_DATE(invoice.due_date->>'value', 'MM/DD/YYYY')
   
   Date aging calculation:
   ✅ CURRENT_DATE - TO_DATE(invoice.due_date->>'value', 'MM/DD/YYYY') AS days_overdue
   
   Date filtering:
   ✅ WHERE TO_DATE(invoice.invoice_date->>'value', 'MM/DD/YYYY') BETWEEN TO_DATE('01/01/2024', 'MM/DD/YYYY') AND TO_DATE('12/31/2024', 'MM/DD/YYYY')
   
   Age buckets:
   ✅ CASE 
        WHEN CURRENT_DATE - TO_DATE(invoice.due_date->>'value', 'MM/DD/YYYY') <= 30 THEN '0-30 days'
        WHEN CURRENT_DATE - TO_DATE(invoice.due_date->>'value', 'MM/DD/YYYY') <= 60 THEN '31-60 days'
        ELSE '90+ days'
      END AS age_bucket

📌 RULE 4: Always Include Document Join
   batch_name lives in icap_document, not icap_invoice. Always join it.
   ✅ INNER JOIN icap_document d ON invoice.document_id = d.id
   This provides: batch_name, status, sub_status, accuracy

🔴 CRITICAL COLUMN TYPE VALIDATION (CHECK BEFORE USING ANY COLUMN):

Before using ANY column in your query, you MUST:
1. **Find the column in the schema above** - verify it exists
2. **Check its type** - is it JSONB, UUID, VARCHAR, NUMERIC, DATE, etc.?
3. **Apply the correct syntax** based on type:
   - JSONB columns: MUST use (column->>'value')::text or (column->>'value')::numeric with NULLIF
   - UUID columns: Use directly (e.g., table.id) or cast JSONB: (column->>'value')::uuid with NULLIF check
   - VARCHAR/TEXT columns: Use directly (e.g., table.name)
   - NUMERIC columns: Use directly (e.g., table.amount) or NULLIF for JSONB numerics
   - DATE columns: Use TO_DATE(column->>'value', 'MM/DD/YYYY') for JSONB dates

4. **Verify foreign key types** - if joining on a JSONB FK column, use defensive join pattern (RULE 1)
5. **Match operations to types** - don't use ::date on JSONB, don't use ::numeric without NULLIF

IMPORTANT Requirements:
1. **COLUMN TYPE CHECKING**: For EVERY column you use, verify its type from the schema above
   - If schema shows "invoice_date: JSONB" → use TO_DATE(invoice_date->>'value', 'MM/DD/YYYY')
   - If schema shows "vendor_id: UUID" → use vendor_id directly (not ->'value')
   - If schema shows "name: VARCHAR" → use name directly
2. Use LEFT JOIN (not INNER JOIN) for optional relationships (vendor, product, category)
3. Use INNER JOIN for required relationships (document)
4. Never include ID columns in SELECT (no invoice_id, vendor_id, document_id, etc.)
5. Use JSONB operators (->>'value') for JSONB columns - this is CRITICAL for JSONB fields
6. Apply RULE 2 (NULLIF) for ALL numeric JSONB fields
7. Apply RULE 3 (TO_DATE) for ALL date JSONB fields
8. Apply RULE 1 (defensive join) for ALL UUID JSONB fields in JOIN conditions
9. Order results appropriately (e.g., ORDER BY invoice_number, line_item_id)
10. Include ALL relevant business fields from primary table first, then related tables, then detail tables
11. DO NOT add any WHERE clause for date filtering - I will add that separately
12. Use proper PostgreSQL syntax - check for typos, correct column names, valid operators
13. Ensure all table aliases are consistent throughout the query
14. Use lowercase for SQL keywords (select, from, left join, where, order by)
15. **VERIFY ALL COLUMNS EXIST**: Cross-reference every column name with the schema above before using it
16. When using GROUP BY with aggregate functions (COUNT, SUM, AVG, MAX, MIN, etc.) in HAVING clause, ALWAYS include those aggregates in the SELECT clause with meaningful aliases
    Example: If using HAVING count(*) > 1, then SELECT must include "count(*) as duplicate_count" or similar
    This allows users to see the aggregate values, not just filter by them
17. **CRITICAL - RESOLVE ID COLUMNS TO NAMES**: 
    ⚠️ If you see icap_invoice_detail table with category_id or product_id JSONB columns:
    - category_id: JOIN icap_tenant_category_master to resolve to category name
      * JOIN condition: LEFT JOIN icap_tenant_category_master cat ON NULLIF(detail.category_id->>'value', '') IS NOT NULL AND (detail.category_id->>'value')::uuid = cat.id
      * SELECT: CASE WHEN detail.category_id->>'value' != '' THEN cat.name ELSE NULL END AS category_name
    - product_id: JOIN icap_product_master to resolve to product name
      * JOIN condition: LEFT JOIN icap_product_master prod ON NULLIF(detail.product_id->>'value', '') IS NOT NULL AND (detail.product_id->>'value')::uuid = prod.id
      * SELECT: CASE WHEN detail.product_id->>'value' != '' THEN prod.name ELSE NULL END AS product_name
    ⚠️ NEVER expose raw category_id or product_id values - ALWAYS resolve to names from master tables
    ⚠️ Use NULLIF checks in JOIN conditions to prevent empty string to UUID casting errors
18. **TYPE CONSISTENCY CHECK**: Before returning the query, verify:
    - All JSONB columns use ->>'value' extraction
    - All date operations use TO_DATE (never ::date on JSONB)
    - All numeric JSONB fields use NULLIF before casting
    - All UUID JSONB joins use defensive pattern
    - All regular columns (VARCHAR, UUID, NUMERIC) are used directly without ->> operator

Generate ONLY the SQL query without date filters. Return just the SQL, no explanations.

SQL QUERY:"""
            
            # Use LLM to generate base query
            from langchain_core.messages import HumanMessage
            response = self.llm.invoke([HumanMessage(content=query_generation_prompt)])
            base_query = response.content.strip()
            
            # Remove any markdown code blocks
            if '```' in base_query:
                import re
                code_match = re.search(r'```(?:sql)?\n(.*?)\n```', base_query, re.DOTALL)
                if code_match:
                    base_query = code_match.group(1).strip()
            
            # Basic validation
            if not base_query.upper().strip().startswith('SELECT'):
                print("⚠️ Generated query does not start with SELECT")
                raise ValueError("Invalid query generated - must be a SELECT statement")
            
            # Build WHERE clause based on trigger_type
            where_clause = ""
            parameters = []
            param_instructions = ""
            
            if trigger_type == "month_year":
                where_clause = "WHERE (invoice_date->>'value' LIKE '{month}/%/{year}')"
                parameters = ["month", "year"]
                param_instructions = "Extract 'month' and 'year' from input_data. Month should be 2-digit format (01-12)."
                
            elif trigger_type == "date_range":
                where_clause = "WHERE (invoice_date->>'value' >= '{start_date}' AND invoice_date->>'value' <= '{end_date}')"
                parameters = ["start_date", "end_date"]
                param_instructions = "Extract 'start_date' and 'end_date' from input_data. Format: MM/DD/YYYY."
                
            elif trigger_type == "year":
                where_clause = "WHERE (invoice_date->>'value' LIKE '%/%/{year}')"
                parameters = ["year"]
                param_instructions = "Extract 'year' from input_data (4-digit format)."
                
            elif trigger_type == "conditions" and workflow_config and workflow_config.get('input_fields'):
                # Build custom WHERE clause from input_fields
                conditions = []
                for field in workflow_config['input_fields']:
                    field_name = field['name']
                    parameters.append(field_name)
                    # Simple equality condition for now - can be enhanced
                    conditions.append(f"{field_name} = '{{{field_name}}}")
                where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
                param_instructions = f"Extract these fields from input_data: {', '.join(parameters)}"
                
            elif trigger_type == "text_query":
                # No fixed filter - query can vary
                where_clause = "-- Custom filter will be applied based on user query"
                parameters = []
                param_instructions = "Parse user query to determine filter conditions dynamically."
            
            # Combine base query with WHERE clause
            full_template = base_query
            if where_clause and not where_clause.startswith('--'):
                # Insert WHERE clause before ORDER BY if it exists
                if 'ORDER BY' in base_query.upper():
                    parts = base_query.upper().split('ORDER BY')
                    insert_pos = base_query.upper().index('ORDER BY')
                    full_template = base_query[:insert_pos] + " " + where_clause + " " + base_query[insert_pos:]
                else:
                    full_template = base_query + " " + where_clause
            
            print(f"\n✅ Generated query template:")
            print(f"  Base query: {base_query[:100]}...")
            print(f"  WHERE clause: {where_clause}")
            print(f"  Parameters: {parameters}")
            
            return {
                "base_query": base_query,
                "where_clause": where_clause,
                "parameters": parameters,
                "param_instructions": param_instructions,
                "full_template": full_template
            }
            
        except Exception as e:
            print(f"❌ Error building query template: {e}")
            import traceback
            traceback.print_exc()
            # Return fallback template
            return {
                "base_query": "-- Error generating query template",
                "where_clause": "",
                "parameters": [],
                "param_instructions": "",
                "full_template": "-- Query generation failed, will use traditional agent execution",
                "error": str(e)
            }
    
    def _build_execution_plan(self, trigger_type: str, output_format: str, query_template: Dict) -> Dict[str, str]:
        """
        Create step-by-step execution plan based on output format
        
        Args:
            trigger_type: Type of trigger
            output_format: Desired output format (csv, table, json, text)
            query_template: Query template with parameters
            
        Returns:
            Dictionary with numbered execution steps
        """
        plan = {
            "step_1": "Load pre-built query template from execution_guidance",
            "step_2": query_template.get('param_instructions', 'Extract parameters from input')
        }
        
        # Step 3: Fill parameters
        if query_template.get('parameters'):
            params = ', '.join([f'{{{p}}}' for p in query_template['parameters']])
            plan["step_3"] = f"Replace template parameters: {params}"
        else:
            plan["step_3"] = "No parameters needed - use query as-is"
        
        # Step 4: Execute query
        plan["step_4"] = "Execute filled query using postgres_query tool"
        
        # Steps 5-6 vary by output format
        if output_format == "csv":
            plan["step_5"] = "Convert query results to CSV format with headers"
            plan["step_6"] = "Encode as base64 and return downloadable CSV file with filename"
            plan["step_7"] = "Include summary statistics in response"
            
        elif output_format == "table":
            plan["step_5"] = "Structure results as table_data with columns and rows arrays"
            plan["step_6"] = "Include row_count and column metadata"
            plan["step_7"] = "Return formatted table for interactive display"
            
        elif output_format == "json":
            plan["step_5"] = "Keep results as JSON array of objects"
            plan["step_6"] = "Add metadata: total_records, columns, query_executed"
            plan["step_7"] = "Return as formatted JSON structure"
            
        elif output_format == "text":
            plan["step_5"] = "Generate human-readable markdown summary from results"
            plan["step_6"] = "Include: executive summary, key findings, detailed analysis"
            plan["step_7"] = "Format with proper sections and insights for decision-making"
        
        return plan
    
    def _generate_execution_guidance(self, prompt: str, trigger_type: str, output_format: str, 
                                     agent_tools: List, workflow_config: Dict = None) -> Dict[str, Any]:
        """
        Generate complete execution guidance: schema analysis + query template + execution plan
        This is called during agent creation/editing to pre-build everything needed for fast execution
        
        Args:
            prompt: User prompt describing what the agent should do
            trigger_type: Workflow trigger type (month_year, date_range, year, etc.)
            output_format: Desired output format (csv, table, json, text)
            agent_tools: Available tools
            workflow_config: Optional workflow configuration
            
        Returns:
            Complete execution guidance dictionary
        """
        try:
            print("\n🚀 Generating execution guidance...")
            print(f"  Prompt: {prompt[:80]}...")
            print(f"  Trigger: {trigger_type}")
            print(f"  Output: {output_format}")
            
            # Step 1: Inspect schema based on prompt
            print("\n📊 Step 1: Inspecting database schema...")
            schema_info = self._inspect_schema_for_prompt(prompt, agent_tools)
            
            if not schema_info:
                print("⚠️ No schema info available - guidance will be limited")
                schema_info = "No schema information available. Agent will inspect schema during execution."
            
            # Step 2: Build query template
            print("\n🔨 Step 2: Building parameterized query template...")
            query_template = self._build_query_template(
                prompt=prompt,
                trigger_type=trigger_type,
                schema_info=schema_info,
                workflow_config=workflow_config
            )
            
            # Step 3: Create execution plan
            print("\n📋 Step 3: Creating execution plan...")
            execution_plan = self._build_execution_plan(
                trigger_type=trigger_type,
                output_format=output_format,
                query_template=query_template
            )
            
            guidance = {
                "query_template": query_template,
                "execution_plan": execution_plan,
                "schema_context": schema_info,
                "generated_at": datetime.now().isoformat(),
                "configuration": {
                    "trigger_type": trigger_type,
                    "output_format": output_format,
                    "prompt": prompt
                }
            }
            
            print("\n✅ Execution guidance generated successfully!")
            print(f"  Query has {len(query_template.get('parameters', []))} parameters")
            print(f"  Execution plan has {len(execution_plan)} steps")
            
            return guidance
            
        except Exception as e:
            print(f"\n❌ Error generating execution guidance: {e}")
            import traceback
            traceback.print_exc()
            
            # Return minimal guidance on error
            return {
                "error": str(e),
                "fallback_mode": True,
                "message": "Execution guidance generation failed. Agent will use traditional execution."
            }
    
    def _generate_system_prompt(self, prompt: str, agent_tools: List, selected_tool_names: List[str], reference_template: str = None) -> str:
        """
        Generate comprehensive system prompt with entity-specific guidance and schema inspection
        
        Args:
            prompt: User prompt
            agent_tools: Available tools
            selected_tool_names: Names of selected tools
            reference_template: Optional SQL template query that failed (for context in fallback scenarios)
            
        Returns:
            System prompt string
        """
        tool_descriptions = "\n".join([f"- {tool.name}: {tool.description}" for tool in agent_tools])
        
        has_postgres = any(tool_name in ['postgres_query', 'postgres_inspect_schema'] for tool_name in selected_tool_names)
        
        # 🔍 AUTO-INSPECT SCHEMA if Postgres tools are selected
        schema_context = ""
        if has_postgres:
            schema_context = self._inspect_schema_for_prompt(prompt, agent_tools)
        
        # 🎯 Detect agent intent and purpose from the prompt
        prompt_lower = prompt.lower()
        
        # Detect specific agent types
        is_duplicate_finder = any(keyword in prompt_lower for keyword in ['duplicate', 'duplicates', 'repeated', 'same invoice', 'same vendor'])
        is_anomaly_detector = any(keyword in prompt_lower for keyword in ['anomaly', 'unusual', 'outlier', 'fraud', 'suspicious', 'abnormal'])
        is_comparison = any(keyword in prompt_lower for keyword in ['compare', 'comparison', 'difference', 'vs', 'versus', 'gap', 'variance'])
        is_trend_analysis = any(keyword in prompt_lower for keyword in ['trend', 'pattern', 'growth', 'decline', 'over time', 'historical'])
        is_report_agent = any(keyword in prompt_lower for keyword in [
            'invoice', 'report', 'vendor', 'product', 'customer', 'order',
            'sales', 'payment', 'transaction', 'financial', 'billing',
            'generate report', 'monthly report', 'yearly report', 'summary report'
        ])
        
        # 🎯🎯🎯 PURPOSE-FIRST SYSTEM PROMPT - User's goal is THE PRIMARY FOCUS
        system_prompt = f"""🎯 YOUR PRIMARY MISSION:
{prompt}

📌 CRITICAL SUCCESS CRITERIA:
Your response MUST directly address the above mission. Every action, every query, every output must serve this exact purpose.
"""
        
        # 📖 Add reference template context if provided (from failed execution guidance)
        if reference_template:
            # Replace template placeholders with a format that won't be parsed by ChatPromptTemplate
            # Replace {param} with [PARAM_param] to avoid ChatPromptTemplate variable parsing
            # This way the AI can still understand the template structure without triggering template variable errors
            import re
            # Replace {variable_name} with [PARAM_variable_name]
            # This prevents ChatPromptTemplate from treating them as template variables
            escaped_template = re.sub(r'\{(\w+)\}', r'[PARAM_\1]', reference_template)
            
            # Verify replacement worked - check that no {variable} patterns remain
            remaining_vars = re.findall(r'\{(\w+)\}', escaped_template)
            if remaining_vars:
                logger.warning(f"Warning: Some template variables were not replaced in reference template: {remaining_vars}")
            else:
                logger.debug(f"Successfully escaped all template variables in reference template")
            
            system_prompt += f"""\n📚 REFERENCE QUERY TEMPLATE (Use as Structure Guide):
A pre-built query template was attempted but failed. Use this as a REFERENCE for:
- Understanding the expected data structure
- Identifying which tables and columns are relevant
- Seeing the intended output format
- Learning the query pattern that aligns with the agent's goal

REFERENCE TEMPLATE:
```sql
{escaped_template}
```

⚠️ IMPORTANT:
- This template may have syntax errors - that's why it failed
- DO NOT copy it blindly - understand its INTENT
- Use it to guide your query structure, table joins, and column selection
- Ensure your new query maintains the same PURPOSE and OUTPUT GOALS
- Fix any syntax issues while preserving the data structure intent
- Note: Template placeholders like [PARAM_start_date] and [PARAM_end_date] represent parameters that should be replaced with actual values from input_data
- When building your query, replace [PARAM_*] placeholders with actual values (e.g., [PARAM_start_date] becomes '02/01/2025')
"""
        
        # 🎯 Add specialized instructions based on detected agent type
        if is_duplicate_finder:
            system_prompt += """\n🔍 DUPLICATE DETECTION REQUIREMENTS:
Your goal is to find and identify duplicate records. Your output MUST:
1. **Explicitly name which records are duplicates** (e.g., "Invoice INV-001 and INV-002 are duplicates")
2. **State WHY they are duplicates** (same vendor + amount? same date + customer? same product?)
3. **Group duplicates together** (e.g., "Group 1: INV-001, INV-002, INV-003 share vendor 'ABC Corp' and amount $500")
4. **Count duplicate groups** (e.g., "Found 5 duplicate groups affecting 12 invoices")
5. **Provide actionable insights** (Which duplicates should be reviewed? Which might be data entry errors?)
6. **ALWAYS include COUNT(*) in GROUP BY queries** to show duplicate count per group
7. **ALWAYS use HAVING COUNT(*) > 1** to filter only actual duplicates

⚠️ CRITICAL SQL Pattern for Duplicates:
```sql
SELECT 
  column1, column2, column3,
  COUNT(*) AS duplicate_count  -- REQUIRED: Shows how many duplicates
FROM table
GROUP BY column1, column2, column3
HAVING COUNT(*) > 1  -- REQUIRED: Only show groups with duplicates
ORDER BY duplicate_count DESC;  -- Show worst duplicates first
```

❌ DO NOT just list all records - ANALYZE and IDENTIFY the duplicates specifically!
❌ DO NOT say "here are the results" - SAY "here are the DUPLICATES I found"
✅ Be specific with invoice numbers, amounts, vendors, dates that make them duplicates
"""
        
        elif is_anomaly_detector:
            system_prompt += """\n⚠️ ANOMALY DETECTION REQUIREMENTS:
Your goal is to find unusual or suspicious records. Your output MUST:
1. **Explicitly identify which records are anomalies** (e.g., "Invoice INV-789 is an outlier")
2. **Explain WHY each is anomalous** (amount too high/low? unexpected vendor? date mismatch? unusual pattern?)
3. **Provide context** ("This invoice is $50,000 while typical invoices from this vendor are $500-$2,000")
4. **Rank by severity** (Which anomalies are most concerning?)
5. **Suggest actions** ("These 3 invoices should be reviewed for potential fraud")

❌ DO NOT just list records - HIGHLIGHT what makes them unusual!
✅ Compare against normal patterns and explain deviations
"""
        
        elif is_comparison:
            system_prompt += """\n📊 COMPARISON ANALYSIS REQUIREMENTS:
Your goal is to compare and contrast data points. Your output MUST:
1. **State the differences explicitly** ("Product A costs $50 while Product B costs $75 - a $25 difference")
2. **Highlight key variances** (Which differences are significant? Which are minor?)
3. **Provide percentage changes** when relevant ("Vendor X increased prices by 15%")
4. **Show trends** (Is the gap widening or narrowing?)
5. **Make comparisons actionable** (What does this difference mean for the business?)

❌ DO NOT just show two lists side by side
✅ ANALYZE the differences and explain their significance
"""
        
        elif is_trend_analysis:
            system_prompt += """\n📈 TREND ANALYSIS REQUIREMENTS:
Your goal is to identify patterns over time. Your output MUST:
1. **Describe the trend direction** ("Invoices have been increasing by 10% month-over-month")
2. **Identify key inflection points** (When did the trend change? What triggered it?)
3. **Quantify the pattern** (Use specific numbers, percentages, rates)
4. **Predict implications** (If this trend continues, what happens?)
5. **Highlight anomalies in the trend** (Which months/periods were unusual?)

❌ DO NOT just show historical data
✅ INTERPRET the pattern and explain what it means
"""
        
        elif is_report_agent:
            system_prompt += """\n📋 REPORTING REQUIREMENTS:
Your goal is to generate a comprehensive, well-organized report. Your output MUST:
1. **Start with an executive summary** (What are the key takeaways?)
2. **Present data in logical sections** (Group related information together)
3. **Include totals and aggregations** when relevant (Total amount, count, averages)
4. **Highlight important findings** (What stands out? What needs attention?)
5. **Be complete and thorough** (Include all relevant data points)

✅ Structure your report to be immediately useful for decision-making
"""
        
        else:
            # Generic analytical agent
            system_prompt += """\n💡 ANALYSIS REQUIREMENTS:
Your output MUST:
1. **Be specific and actionable** (Not just "here are the results")
2. **Include insights and interpretation** (What does this data mean?)
3. **Reference actual data points** (Mention specific values, names, dates)
4. **Address the user's question directly** (Don't go off-topic)
5. **Provide context where helpful** (Comparisons, benchmarks, patterns)
"""
        
        # Add tool descriptions
        system_prompt += f"""\n\n🛠️ AVAILABLE TOOLS:
{tool_descriptions}
"""
        
        # Add schema context if available (before technical guide)
        if has_postgres and schema_context:
            system_prompt += f"""\n\n📊 DATABASE SCHEMA PREVIEW:
{schema_context}
"""
        
        # Add PostgreSQL-specific technical rules ONLY if postgres tools are available
        if has_postgres:
            # Condensed PostgreSQL technical appendix
            system_prompt += """\n\n📚 POSTGRESQL TECHNICAL GUIDE (Supporting Reference):

1. **ALWAYS INSPECT ALL TABLES** - Call postgres_inspect_schema() for EVERY table in your query
2. **VALIDATE BEFORE JOINING** - Inspect schema for ALL tables you plan to JOIN
3. **USE ONLY ACTUAL COLUMN NAMES** - Never assume or guess column names from ANY table
4. **CHECK SAMPLE DATA** - Schema response shows actual column names and their values
5. **JSONB COLUMNS** - Use ->>'value' operator (check jsonb_columns list in each table's schema)
6. **FOREIGN KEYS** - Use foreign_keys list to determine correct JOIN columns
7. **IMPLICIT RELATIONSHIPS** - DB may not have explicit foreign keys; infer from column names and referenced_by
8. **NO HALLUCINATION** - If column doesn't exist in schema, DON'T use it
9. **❌ NEVER EXPOSE ID COLUMNS** - Do NOT include ANY ID columns in SELECT clause:
   - No invoice_id, vendor_id, document_id, product_id, customer_id, etc.
   - IDs are internal system identifiers - only show business-meaningful fields
   - Show: invoice_number, vendor_name, product_description (NOT IDs)
10. **✅ USE PRIMARY TABLE AS BASE** - Always use the main business entity table as FROM:
   - For invoice reports: FROM icap_invoice (NOT FROM icap_invoice_detail)
   - For product reports: FROM icap_product (NOT FROM icap_product_detail)
   - For vendor reports: FROM icap_vendor (NOT FROM icap_vendor_contact)
   - LEFT JOIN detail tables to the primary table (never make detail tables the base)
11. **ORDER BY FOR GROUPING** - Always add ORDER BY to group related records:
   - Example: ORDER BY invoice_number, line_item_id (groups line items by invoice)
12. **📊 COLUMN ORDERING FOR DETAIL REPORTS** - When including detail/line item tables:
   - ✅ FIRST: Select ALL columns from PRIMARY table (invoice_number, invoice_date, total, vendor_name)
   - ✅ SECOND: Select columns from DETAIL table (product_description, quantity, unit_price, line_total)
   - This creates clear visual separation: [Invoice Info] | [Line Item Info]
   - Example: SELECT i.invoice_number, i.invoice_date, i.total, v.name, d.description, d.quantity, d.unit_price
   - Primary table columns ALWAYS come before detail table columns
13. **🎯 MAXIMIZE PRIMARY TABLE DATA** - ALWAYS extract MAXIMUM details from the primary/major table:
   - ⚠️ CRITICAL: Select ALL relevant business fields from the primary table first
   - Don't skip primary table columns - include invoice_number, invoice_date, total, status, etc.
   - Example: For invoice reports, get ALL invoice fields (number, date, total, subtotal, tax, status, notes)
   - THEN add related table data (vendor_name, customer_name)
   - THEN add detail table data (line items)
   - The primary table is the foundation - capture ALL its meaningful data!

📋 MANDATORY WORKFLOW - EFFICIENT SCHEMA INSPECTION:
⚠️ CRITICAL: Inspect ALL related tables BEFORE building query to avoid errors and retries!
⚠️ CRITICAL: For COMPLETE reports, you MUST inspect ALL tables shown in 'referenced_by' and 'related_tables'!

🎯 STEP 0 (FIRST THING): Get complete table list from database
   - Call postgres_inspect_schema() with NO table_name (empty string: '')
   - This returns ONLY a list of table names starting with 'icap_' prefix (no column details, very fast!)
   - Response format: (tables: list of table names, total_tables: count)
   - Extract keywords from the USER'S QUERY to identify relevant tables
   - Example: User asks "vendor report" → filter tables containing 'vendor'
   - Example: User asks "product analysis" → filter tables containing 'product'
   - Example: User asks "customer orders" → filter tables containing 'customer' OR 'order'
   - ⚠️ CRITICAL: Use keywords from USER'S actual query, NOT hardcoded entity names!

Step 1: Identify ALL PRIMARY tables from user's query context
   - User may need multiple main tables (e.g., "invoice and payment" → 2 main tables)
   - Extract entity keywords from the user's actual query/request
   - Example: "vendor report" → keyword is 'vendor'
   - Example: "product inventory" → keyword is 'product'
   - Example: "customer invoices" → keywords are 'customer' AND 'invoice'
   - Filter Step 0 table list for tables containing these keywords
   - Use the table list from STEP 0 to find exact table names dynamically

Step 2: Call postgres_inspect_schema() for EACH primary table

Step 3: From EACH primary table schema, identify related tables using MULTIPLE methods:
   A. **Direct Foreign Key Associations** (explicit constraints if they exist):
      - Read 'foreign_keys' list
      - Read 'referenced_by' list (tables that reference this one)
      - ⚠️ CRITICAL: 'referenced_by' shows child/detail tables - INSPECT THESE!
      - Example: invoice shows referenced_by: icap_invoice_full, icap_bill_staging
      - → These are detail tables you MUST inspect and include in the query!
   
   B. **Column Name Pattern Analysis** - ANY column ending in '_id':
      Extract the base name by removing '_id' suffix, then look for matching table in Step 0 list
      Examples:
      * If you see column 'vendor_id' → Search table list for 'vendor'
      * If you see column 'document_id' → Search table list for 'document'
      * If you see column 'customer_id' → Search table list for 'customer'
      * If you see column 'product_id' → Search table list for 'product'
      * If you see column 'category_id' → Search table list for 'category'
      * For ANY *_id column → Extract base name and find matching table from Step 0 list
   
   C. **Semantic Table Name Discovery** - Search table list from Step 0 for related naming patterns:
      Extract the PRIMARY ENTITY from user's query, then look in Step 0 table list for related tables:
      
      If primary entity is 'invoice', look in Step 0 table list for:
      * Tables containing 'invoice_detail', 'invoice_items', 'invoice_line' 
      * Tables containing 'invoice_payment' (payment records)
      * Tables containing 'invoice_full', 'invoice_header' (consolidated/header views)
      * ANY table name starting with 'invoice_' or containing 'invoice'
      
      If primary entity is 'vendor', look in Step 0 table list for:
      * Tables containing 'vendor_contact', 'vendor_address', 'vendor_payment'
      * ANY table name starting with 'vendor_' or containing 'vendor'
      
      If primary entity is 'product', look in Step 0 table list for:
      * Tables containing 'product_detail', 'product_category', 'product_inventory'
      * ANY table name starting with 'product_' or containing 'product'
      
      If primary entity is 'customer', look in Step 0 table list for:
      * Tables containing 'customer_address', 'customer_contact', 'customer_payment'
      * ANY table name starting with 'customer_' or containing 'customer'
      
      If primary entity is 'order', look in Step 0 table list for:
      * Tables containing 'order_detail', 'order_items', 'order_line', 'order_shipment'
      * ANY table name starting with 'order_' or containing 'order'
      
      ⚠️ CRITICAL: Extract entity from USER'S QUERY dynamically - these are just examples!
      ⚠️ CRITICAL: Use the ACTUAL table list from Step 0 - do NOT guess or hardcode table names!
   
   D. **Relationships Field Analysis**:
      - Read 'relationships' field for additional hints
   
   ⚠️ CRITICAL: Database may NOT have explicit foreign key constraints!
       Use ALL discovery methods (A, B, C, D) to find every related table

Step 4: Combine all related tables from Step 3 (remove duplicates)

Step 5: Call postgres_inspect_schema() for EACH related table found in Step 4
   Example: If invoice has foreign_keys to 'vendor' and 'document',
            and payment has foreign_keys to 'vendor' and 'customer':
   → MUST inspect: vendor, document, customer (all unique related tables)
   
   ⚠️ CRITICAL: If you see 'referenced_by' or 'related_tables' in the schema response:
   → These are ADDITIONAL tables you MUST inspect!
   → Example: If vendor schema shows 'related_tables: icap_invoice_full, icap_product_master'
   → You MUST call postgres_inspect_schema('icap_invoice_full')
   → You MUST call postgres_inspect_schema('icap_product_master')
   → Then include them in your query for COMPLETE data!
Step 6: From ALL inspected schemas, collect:
   - Actual column names (columns list)
   - JSONB columns (jsonb_columns list)
   - JOIN columns (foreign_keys)
Step 7: Build query using ONLY columns from ALL inspected schemas
Step 8: Use LEFT JOIN (not INNER JOIN) to include all records
Step 9: Execute query

🎯 EXAMPLE WORKFLOW:

**Example 1: Single Primary Table (No Explicit Foreign Keys)**
User asks: "Get vendor report"
0. Get table list: postgres_inspect_schema('')
   - Returns: (tables: list of icap_bill_staging, icap_document, icap_invoice, icap_invoice_full, icap_product_master, icap_vendor, etc., total_tables: 7)
   - Extract entity keyword 'vendor' from user query
   - Filter for 'vendor' keyword: Found "icap_vendor"
1. Identify primary table from filtered list: "icap_vendor"
2. Inspect primary table schema: postgres_inspect_schema('icap_vendor')
3. Schema analysis:
   - foreign_keys: [] (empty - no explicit constraints)
   - referenced_by: Lists child tables that reference this table
   - columns: List of all columns with types
   - Scan for *_id patterns in columns list:
     * If you see 'contact_id' → Search Step 0 list for table containing 'contact'
     * If you see 'category_id' → Search Step 0 list for table containing 'category'
4. IMMEDIATELY inspect discovered related table schemas from Step 0 list
5. Collect actual columns from inspected schemas:
   - Read 'columns' list to see actual column names
   - Example: If contact has columns (name: id), (name: email), (name: phone)
   - Use ONLY these actual names in query (NOT guessed names!)
6. Build query: JOIN using discovered *_id columns matched to related table.id
7. Execute once - no errors!

**Example 1b: Complete Report with Dynamic Table Discovery (Product Example)**
User asks: "Generate complete product analysis"
0. FIRST: Get all available tables from database
   - Call: postgres_inspect_schema('')  (empty string)
   - Returns: (tables: list of icap_product, icap_product_category, icap_product_inventory, icap_vendor, icap_invoice, etc., total_tables: 10)
   - Extract entity keyword 'product' from user query
   - Filter tables containing 'product': icap_product, icap_product_category, icap_product_inventory
1. Identify primary table: "icap_product" (first match)
2. Inspect primary table schema: postgres_inspect_schema('icap_product')
3. Multi-method discovery from the schema response:
   Method A (Foreign Keys): Read 'foreign_keys' list from schema response
   Method B (Column *_id patterns): Scan 'columns' list for any column ending in '_id'
     - Found: 'vendor_id' → Search Step 0 table list for table containing 'vendor'
     - Found: 'category_id' → Search Step 0 table list for table containing 'category'
   Method C (Semantic naming): Search Step 0 table list for tables containing 'product'
     - Found tables with 'product_category', 'product_inventory', etc. in Step 0 list
   Method D (Relationships - READ referenced_by!):
     - Schema shows: referenced_by: [(table: <some_detail_table>), (table: <some_full_table>)]
     - ⚠️ MUST inspect these tables from the referenced_by list!
4. Complete discovery results (ALL from Step 0 table list):
   - Direct associations: Tables containing 'vendor', 'category'
   - Semantic matches: All tables from Step 0 containing 'product'
   - Referenced by (child tables): Tables from 'referenced_by' field
   - Total tables to inspect: 6+ related tables (ALL discovered dynamically!)
5. Inspect ALL discovered table schemas:
   - postgres_inspect_schema('<vendor_table>') ← from Step 0 list
   - postgres_inspect_schema('<category_table>') ← from Step 0 list
   - postgres_inspect_schema('<product_category_table>') ← from Step 0 list
   - postgres_inspect_schema('<product_inventory_table>') ← from Step 0 list
   - ... (inspect ALL discovered tables)
6. Analyze each schema for actual columns and JOIN keys:
   - Read 'columns' list from each schema response
   - Identify JOIN columns (typically 'id' and corresponding '*_id' columns)
7. Build comprehensive query with ALL related data:
   - Use ONLY column names from the inspected schemas
   - Use LEFT JOIN for all related tables (never INNER JOIN)
   - Include data from ALL discovered tables
8. Execute - Complete product analysis with ALL details from ALL dynamically discovered tables!

**Example 2: Multiple Primary Tables (Implicit Relationships)**
User asks: "Compare invoices with payments"
0. Get table list: postgres_inspect_schema('')
   - Returns: (tables: list of icap_invoice, icap_invoice_full, icap_payment, icap_vendor, etc., total_tables: 8)
   - Extract entity keywords 'invoice' and 'payment' from user query
   - Filter for both keywords: icap_invoice, icap_invoice_full, icap_payment
1. Identify primary tables: "icap_invoice" and "icap_payment"
2. Inspect both primary table schemas
3. Analyze relationships from schema responses:
   - Read 'columns' list from both schemas
   - Look for common *_id columns to find linking fields
   - Search Step 0 table list for tables matching *_id patterns
4. Combine related tables: All unique tables discovered from both primary tables
5. IMMEDIATELY inspect all related table schemas from Step 0 list
6. Collect actual columns from all inspected schemas
7. Build query with inferred JOINs:
   - Use ONLY actual column names from inspected schemas
   - Match *_id columns to corresponding table.id columns
   - Use LEFT JOIN for all relationships
8. Execute once - no errors, no retries, complete data from ALL related tables!

⚠️ CRITICAL: INSPECT EVERY TABLE BEFORE USING IT
- If you need to join Table A with Table B:
  → MUST call postgres_inspect_schema('table_a')
  → Read foreign_keys to find related tables
  → MUST call postgres_inspect_schema('table_b')
  → Check both schemas for actual column names
  → Use foreign_keys to find correct JOIN columns
- Only then can you safely reference columns from these tables.

⚠️ COMMON MISTAKES TO AVOID:
- ❌ Assuming column names without checking schema
- ❌ Using columns that don't exist in the schema (causes DB errors and retries)
- ❌ Inspecting tables one-by-one after errors (EXPENSIVE - do it upfront!)
- ❌ Guessing table relationships without inspecting foreign_keys
- ❌ Hardcoding ANY table names - ALWAYS use table list from Step 0!
- ❌ Assuming column naming patterns - inspect schema to find actual names!
- ❌ ONLY looking for *_id columns - MUST also search for semantically related tables!
- ❌ Missing related tables - search Step 0 list for semantic naming patterns!
- ❌ Incomplete reports - find ALL related tables from Step 0 list!
- ❌ Using INNER JOIN (use LEFT JOIN to avoid missing data)
- ❌ Forgetting ->>'value' for JSONB columns
- ❌ NOT reading 'relationships' and 'referenced_by' from schema
- ❌ Ignoring columns ending in '_id' - they indicate related tables to inspect!
- ❌ **EXPOSING UUID/ID COLUMNS** - NEVER SELECT id, invoice_id, vendor_id, document_id, product_id, etc. Users must see names, not UUIDs!
- ❌ **WRONG BASE TABLE** - Never use FROM icap_invoice_detail (use FROM icap_invoice instead!)
- ❌ **NO ORDER BY** - Always ORDER BY primary table's key field to group related records
- ❌ **WRONG COLUMN ORDER** - Never put detail columns before primary table columns in SELECT
- ❌ **INCOMPLETE PRIMARY DATA** - Don't skip important fields from primary table (get ALL: number, date, total, subtotal, tax, status, etc.)

✅ CORRECT APPROACH:
0. FIRST: Get complete table list - postgres_inspect_schema('')
   → Returns ONLY table names (lightweight, no column details): (tables: list of names, total_tables: count)
1. Identify primary tables from Step 0 list based on user query keywords
2. Inspect PRIMARY table schemas using exact names from Step 0 (NOW you get full schema details)
3. Read 'foreign_keys', 'referenced_by', 'relationships' from each schema
4. Identify related tables using MULTIPLE discovery methods:
   a) Extract tables from *_id column patterns (search Step 0 list for matches)
   b) Search Step 0 list for semantically related tables (same keyword in name)
   c) Check 'referenced_by' list for child tables
5. Inspect ALL discovered tables from Step 0 list BEFORE writing query
6. Read 'columns' list from each schema to see actual column names
7. Read 'jsonb_columns' list to know which need ->>'value'
8. Build query using ONLY columns from inspected schemas
9. Use LEFT JOIN to include all records and build complete JOIN chain
10. Verify JOIN column exists in BOTH tables' schemas
11. Execute query - should work first time without errors and include ALL relevant data!

📝 CORRECT QUERY STRUCTURE EXAMPLE:
```sql
-- ✅ CORRECT: Primary table as base, MAXIMUM details from primary, primary columns FIRST, then detail columns, no IDs
SELECT 
    -- PRIMARY TABLE COLUMNS FIRST - GET ALL RELEVANT FIELDS (icap_invoice)
    i.invoice_number->>'value' AS invoice_number,
    i.invoice_date->>'value' AS invoice_date,
    i.due_date->>'value' AS due_date,
    i.total->>'value' AS invoice_total,
    i.sub_total->>'value' AS subtotal,
    i.tax->>'value' AS tax,
    i.status->>'value' AS status,
    -- RELATED TABLE COLUMNS (icap_vendor)
    v.name AS vendor_name,
    v.email AS vendor_email,
    -- DETAIL TABLE COLUMNS SECOND (icap_invoice_detail)
    ivd.description->>'value' AS product_description,
    ivd.quantity->>'value' AS quantity,
    ivd.unit_price->>'value' AS unit_price,
    ivd.total_price->>'value' AS line_total
FROM icap_invoice i                    -- ✅ PRIMARY table first
LEFT JOIN icap_vendor v ON i.vendor_id = v.id
LEFT JOIN icap_invoice_detail ivd ON ivd.document_id = i.document_id
WHERE (i.invoice_date->>'value' >= '02/01/2025' AND i.invoice_date->>'value' <= '02/28/2025')
ORDER BY i.invoice_number->>'value', ivd.id;
```

❌ WRONG EXAMPLES:
```sql
-- ❌ WRONG: Exposing UUID/ID columns - Users should NEVER see UUIDs!
SELECT i.id, i.vendor_id, i.invoice_number...  -- DON'T expose any UUIDs!

-- ✅ CORRECT: Join to get meaningful names instead
SELECT 
    (i.invoice_number->>'value') AS invoice_number,
    v.name AS vendor_name  -- Show vendor name, not UUID!
FROM icap_invoice i
LEFT JOIN icap_vendor v ON i.vendor_id = v.id;  -- Use UUID only for JOIN

-- ❌ WRONG: Detail table as base
FROM icap_invoice_detail ivd              -- Wrong base table!
LEFT JOIN icap_invoice i ON ...           -- Invoice should be the base!

-- ❌ WRONG: No ordering
SELECT ... FROM icap_invoice ... ;        -- Missing ORDER BY!

-- ❌ WRONG: Detail columns before primary columns
SELECT ivd.description, ivd.quantity, i.invoice_number  -- Wrong order!

-- ❌ WRONG: Incomplete primary table data (skipping important fields)
SELECT i.invoice_number, i.total, ivd.description  -- Missing: date, subtotal, tax, status!
```

🎯 DATE FILTERING (Based on Trigger Type):
- Dates are stored as strings in JSONB format (typically MM/DD/YYYY)
- Extract date/month/year from user input based on workflow trigger_type
- Use JSONB operator: column->>'value' LIKE 'pattern'

Trigger Type Patterns:
  • month_year: Extract month and year from input
    → Pattern: WHERE date_column->>'value' LIKE 'MM/%/YYYY'
  
  • date_range: Extract start and end dates from input
    → ⚠️ CRITICAL: Do NOT use BETWEEN - it fails for string dates!
    → CORRECT Pattern: WHERE (date_column->>'value' >= 'start_date' AND date_column->>'value' <= 'end_date')
    → Example: WHERE (invoice_date->>'value' >= '02/01/2025' AND invoice_date->>'value' <= '02/28/2025')
    → This works for MM/DD/YYYY string comparison
  
  • year: Extract year from input
    → Pattern: WHERE date_column->>'value' LIKE '%/%/YYYY'
  
  • text_query: Parse date from natural language in user query
    → Extract date components and build appropriate pattern

⚠️ DO NOT:
  ❌ Use EXTRACT() function (dates are strings, not date types)
  ❌ Use date casting (will fail on JSONB strings)
  ❌ Hardcode specific dates - always extract from user input
  ❌ Assume date format - check sample_data in schema to see actual format

🔴🔴🔴 CRITICAL OUTPUT FORMAT RULES 🔴🔴🔴
⚠️ When output_format is "csv", you MUST follow these rules:

1. ❌ DO NOT format the query results yourself
2. ❌ DO NOT create markdown tables with | separators
3. ❌ DO NOT add headers like "### Invoice Report"
4. ❌ DO NOT add any text before or after the data
5. ❌ DO NOT add "If you need further details" messages
6. ✅ ONLY say: "Query executed successfully. Results contain X rows."
7. ✅ The system automatically formats data as CSV for download
8. ✅ The system automatically creates the summary

⚠️ CORRECT final response for CSV output:
"Query executed successfully. Results contain 17 invoice records for year 2025."

❌ WRONG final response (DO NOT DO THIS):
"### Invoice Report\n| Invoice Number | Date |\n|---|---|\n| 123 | 01/01/2025 |"

Remember: For CSV output, just confirm the query executed - don't format anything!

🎨 **MARKDOWN FORMATTING REQUIREMENT (CRITICAL):**
Your final response MUST be in **STRICT MARKDOWN FORMAT**:

✅ **REQUIRED MARKDOWN SYNTAX:**
- Use `##` for main headings
- Use `###` for subheadings  
- Use `**bold**` for important terms (amounts, names, invoice numbers)
- Use `-` or `*` for bullet lists
- Use `1.` `2.` for numbered lists
- Use `>` for blockquotes/warnings
- Use blank lines between sections

❌ **NEVER output plain paragraphs without markdown!**

**Example CORRECT response:**
```markdown
## Invoice Analysis Report

### Summary
- Total invoices: **157**
- Date range: **January 2025**
- Vendor **ABC Corp** has highest amount: **$45,230.00**

### Top 5 Vendors
1. **ABC Corp** - $45,230.00
2. **XYZ Inc** - $32,100.00

> ⚠️ 3 invoices pending approval
```

❌ **WRONG (plain text):**
"The report shows 157 invoices for January 2025. ABC Corp has the highest amount..."

✅ **ALL responses must use markdown formatting!**
"""
        
        elif has_postgres and not is_report_agent:
            # 🎯 FLEXIBLE MODE: Simpler PostgreSQL instructions for non-report agents
            system_prompt += """\n\n🔍 POSTGRESQL USAGE GUIDELINES:

**Schema Inspection (ALWAYS REQUIRED):**
1. **Before writing ANY query**, call `postgres_inspect_schema('')` to see all available tables
2. **For each table you plan to use**, call `postgres_inspect_schema('table_name')` to see:
   - Actual column names and types
   - Which columns are JSONB (require `->>'value'` operator)
   - Sample data
   - Foreign key relationships
3. **Never assume or guess column names** - always inspect first

**JSONB Columns:**
- Many columns are JSONB format
- Extract values using: `column_name->>'value'`
- Example: `invoice_date->>'value'`, `total->>'value'`

**Query Construction:**
- Use **only actual column names** from inspected schemas
- Use `LEFT JOIN` for related tables (not INNER JOIN)
- Check `foreign_keys` in schema to find correct JOIN columns
- For JSONB dates, use `TO_DATE(column->>'value', 'MM/DD/YYYY')` for proper filtering
- **For text/name matching, ALWAYS use case-insensitive comparisons:**
  - Use `ILIKE` instead of `LIKE` for pattern matching (e.g., `WHERE v.name ILIKE '%meat hub%'`)
  - Or use `LOWER()` function (e.g., `WHERE LOWER(v.name) = LOWER('Meat Hub')`)
  - Never use `=` or `LIKE` for vendor names, product names, or any user-provided text
  - Database text fields may have inconsistent capitalization

**Database Write Operations:**
⚠️ For INSERT, UPDATE, or DELETE operations, use `postgres_write` tool (NOT `postgres_query`):
- `postgres_query` is read-only (SELECT only)
- `postgres_write` handles write operations with safety checks:
  - Always use dry_run=True first to preview changes
  - Requires WHERE clause for UPDATE/DELETE
  - Maximum 100 rows per operation
  - Protected system tables cannot be modified
- Example workflow:
  1. postgres_write(query="UPDATE table SET col='val' WHERE id=5", dry_run=True)
  2. Review affected_rows from response
  3. postgres_write(query="UPDATE table SET col='val' WHERE id=5", dry_run=False)

**Output Format Rules:**
- When `output_format` is **"csv"**: Just confirm success ("Query executed successfully. Results contain X rows.") - the system auto-generates CSV
- When `output_format` is **"table"**: Return simple confirmation - the system auto-formats the table
- When `output_format` is **"json"**: Return data in JSON format
- When `output_format` is **"text"**: You can format the response as you see fit (markdown, natural language, etc.)

**Critical Rules:**
- ❌❌❌ **NEVER EXPOSE UUID COLUMNS** - Absolutely forbidden in SELECT clause:
  - NO id, invoice_id, vendor_id, document_id, product_id, customer_id, user_id, etc.
  - UUIDs are internal system identifiers with no business meaning
  - Users should NEVER see raw UUIDs in results
  
- ✅✅✅ **ALWAYS JOIN TO GET MEANINGFUL NAMES** instead of UUIDs:
  - ❌ WRONG: `SELECT invoice_id, vendor_id FROM icap_invoice`
  - ✅ CORRECT: `SELECT i.invoice_number, v.name AS vendor_name FROM icap_invoice i LEFT JOIN icap_vendor v ON i.vendor_id = v.id`
  - ❌ WRONG: `SELECT document_id FROM icap_invoice_detail`
  - ✅ CORRECT: `SELECT (i.invoice_number->>'value') AS invoice_number FROM icap_invoice_detail d LEFT JOIN icap_invoice i ON d.document_id = i.document_id`
  
- 📝 **UUID Replacement Rules:**
  - vendor_id → JOIN icap_vendor, SELECT v.name AS vendor_name
  - product_id → JOIN icap_product_master, SELECT pm.name AS product_name
  - document_id → JOIN icap_invoice, SELECT (i.invoice_number->>'value') AS invoice_number
  - category_id (gl_category_id) → JOIN icap_tenant_category_master, SELECT tcm.name AS category_name
  - gl_id → JOIN icap_gl, SELECT g.name AS gl_name, g.code AS gl_code
  
- 🔗 **Category/Product/GL Mapping Chain:**
  - Product → Category: icap_product_category_mapping (product_id, gl_category_id)
  - Category → GL: icap_tenant_gl_category_mapping (category_id, gl_id)
  - Category Master: icap_tenant_category_master (id)
  - GL Master: icap_gl (id, name, code)
  - **Note:** gl_category_id = category_id (same field, different name)
  
- ⚠️ **Exception:** Only use UUID columns in WHERE/JOIN clauses (never in SELECT)
  - OK: `WHERE i.vendor_id = v.id` (for joining)
  - OK: `WHERE i.id = 'some-uuid'` (for filtering, internal use only)
  - FORBIDDEN: `SELECT i.id, i.vendor_id` (exposing to user)

- ✅ Always inspect schema before querying
- ✅ Use `->>'value'` for JSONB columns
- ✅ Respect the `output_format` setting

🎨 **MARKDOWN FORMATTING REQUIREMENT (CRITICAL):**
Your final response MUST be in **STRICT MARKDOWN FORMAT**:

✅ **REQUIRED MARKDOWN SYNTAX:**
- Use `##` for main headings
- Use `###` for subheadings  
- Use `**bold**` for important terms (amounts, names, invoice numbers)
- Use `-` or `*` for bullet lists
- Use `1.` `2.` for numbered lists
- Use `>` for blockquotes/warnings
- Use blank lines between sections

❌ **NEVER output plain paragraphs without markdown!**

**Example CORRECT format:**
```markdown
## Duplicate Invoice Analysis

### Key Findings
- Found **10 duplicate groups** affecting **30 invoices**
- Vendor **meat Hub** has invoice **#328** duplicated **4 times**

### Business Impact
> ⚠️ High-priority duplicates detected

### Recommendations
1. Review invoices with 4+ duplicates
2. Implement validation checks
```

❌ **WRONG (plain text):**
"Found 6 duplicate invoice groups in the data provided. The first group includes..."

✅ **Markdown formatting is MANDATORY for ALL responses!**
"""
        
        system_prompt += """\n\nUse these tools to help users accomplish their tasks. Always be helpful and provide clear explanations of your actions.

🚨🚨🚨 CRITICAL OUTPUT FORMATTING RULE 🚨🚨🚨

Your FINAL response to the user MUST use **STRICT MARKDOWN FORMAT**:

✅ REQUIRED:
- Start with `## Main Heading`
- Use `### Subheading` for sections
- Use `**bold**` for important terms (invoice numbers, amounts, vendor names, dates)
- Use `-` for bullet lists
- Use `1.` `2.` for numbered lists  
- Use `>` for warnings/highlights
- Add blank lines between sections

❌ FORBIDDEN:
- Plain text paragraphs without any markdown
- Missing headings
- No bullet points or formatting

**CORRECT Example:**
```markdown
## Duplicate Invoice Analysis

### Overview
- Total duplicates: **10 groups**
- Vendor **meat Hub** has invoice **#328** appearing **4 times**

### Critical Issues  
> ⚠️ Requires immediate attention

### Next Steps
1. Review high-priority duplicates
2. Contact vendors for clarification
```

❌ WRONG (plain text):
"Found 10 duplicate groups in the data. The first group is invoice 328 from meat Hub..."

🔴 YOU MUST FORMAT YOUR RESPONSE IN MARKDOWN - NO EXCEPTIONS! 🔴
"""
          
        return system_prompt
      
    def create_agent(self, prompt: str, name: str = None, selected_tools: List[str] = None, workflow_config: Dict[str, Any] = None, description: str = None, category: str = None, icon: str = None, use_cases: List[str] = None) -> Dict[str, Any]:
        """
        Create an agent from a prompt
        
        Args:
            prompt: User prompt describing the agent's purpose
            name: Optional name for the agent
            selected_tools: List of tool names to assign to this agent (if None, uses all tools)
            workflow_config: Optional workflow configuration (trigger_type, input_fields, output_format)
            description: Short description of the agent's purpose
            category: Category/classification (e.g., 'Finance & Accounting')
            icon: Emoji icon for visual representation
            use_cases: List of common use cases for this agent
            
        Returns:
            Dictionary with agent information
        """
        agent_id = str(uuid.uuid4())
        agent_name = name or f"Agent-{agent_id[:8]}"
        
        # Set default workflow config if not provided
        if workflow_config is None:
            workflow_config = {
                "trigger_type": "text_query",
                "input_fields": [],
                "output_format": "text"
            }
        
        # Auto-add postgres_inspect_schema if postgres_query is selected
        if selected_tools is not None and 'postgres_query' in selected_tools:
            if 'postgres_inspect_schema' not in selected_tools:
                selected_tools.append('postgres_inspect_schema')
                print("✅ Auto-added postgres_inspect_schema (required for postgres_query)")
        
        # Filter tools based on selected_tools list
        if selected_tools is not None and len(selected_tools) > 0:
            agent_tools = [t for t in self.tools if t.name in selected_tools]
            print(f"\n🎯 Assigning {len(agent_tools)} specific tools to agent: {selected_tools}")
        elif selected_tools is not None and len(selected_tools) == 0:
            # Empty list provided - no specific tools selected, use AI fallback
            agent_tools = []
            print(f"\nℹ️ No tools specified - agent will use AI reasoning as fallback")
        else:
            # None provided - fallback to all tools (legacy behavior)
            agent_tools = self.tools
            print(f"\n⚠️ Warning: No tool selection provided, using all {len(self.tools)} tools")
        
        # Create system prompt using the new helper method
        selected_tool_names = selected_tools if selected_tools is not None else [t.name for t in self.tools]
        system_prompt = self._generate_system_prompt(prompt, agent_tools, selected_tool_names)

        # Create agent prompt template
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        # Create agent with only selected tools
        agent = create_openai_functions_agent(
            llm=self.llm,
            tools=agent_tools,
            prompt=prompt_template
        )
        
        # Create agent executor with only selected tools
        agent_executor = AgentExecutor(
            agent=agent,
            tools=agent_tools,
            verbose=True,
            handle_parsing_errors=True
        )
        
        # 🎯 GENERATE EXECUTION GUIDANCE (only for structured input types, not text_query)
        execution_guidance = None
        has_postgres = selected_tools is not None and any(tool in selected_tools for tool in ['postgres_query', 'postgres_inspect_schema'])
        trigger_type = workflow_config.get('trigger_type', 'text_query')
        
        # Only generate execution guidance for structured inputs (date_range, month_year, year)
        # Skip for text_query since queries vary too much
        should_generate_guidance = has_postgres and trigger_type in ['date_range', 'month_year', 'year']
        
        if should_generate_guidance:
            print(f"\n🚀 Generating execution guidance for {trigger_type} trigger (enables query caching)...")
            try:
                execution_guidance = self._generate_execution_guidance(
                    prompt=prompt,
                    trigger_type=trigger_type,
                    output_format=workflow_config.get('output_format', 'text'),
                    agent_tools=agent_tools,
                    workflow_config=workflow_config
                )
                
                if execution_guidance and not execution_guidance.get('error'):
                    print("✅ Execution guidance generated! Agent will use fast execution path with query caching.")
                else:
                    print("⚠️ Execution guidance had errors - agent will use traditional path")
                    execution_guidance = None
            except Exception as e:
                print(f"⚠️ Could not generate execution guidance: {e}")
                execution_guidance = None
        elif has_postgres and trigger_type == 'text_query':
            print(f"\nℹ️ Skipping execution guidance for text_query (no caching - queries too variable)")
        
        # Save agent metadata including selected tools and workflow config
        agent_data = {
            "id": agent_id,
            "name": agent_name,
            "description": description or prompt[:100],  # Default to first 100 chars of prompt
            "category": category or "General",
            "icon": icon or "Bot",
            "prompt": prompt,
            "system_prompt": system_prompt,
            "selected_tools": selected_tools or [t.name for t in self.tools],
            "workflow_config": workflow_config,  # Store workflow configuration
            "created_at": datetime.now().isoformat(),
            "use_cases": use_cases or []
        }
        
        # Add execution guidance if generated
        if execution_guidance:
            agent_data["execution_guidance"] = execution_guidance
            print("✅ Execution guidance added to agent data")
        
        self.storage.save_agent(agent_data)
        
        return agent_data
    
    def create_agent_with_streaming(self, prompt: str, name: str = None, selected_tools: List[str] = None, workflow_config: Dict[str, Any] = None, description: str = None, category: str = None, icon: str = None, use_cases: List[str] = None):
        """
        Create an agent with streaming AI reasoning (generator for SSE)
        
        Yields progress events showing AI thinking process
        """
        try:
            agent_id = str(uuid.uuid4())
            agent_name = name or f"Agent-{agent_id[:8]}"
            
            # Step 1: Initial setup
            yield {
                "type": "progress",
                "step": 1,
                "status": "in_progress",
                "message": "Analyzing your requirements...",
                "detail": "Understanding agent purpose and configuration"
            }
            
            # Set default workflow config
            if workflow_config is None:
                workflow_config = {
                    "trigger_type": "text_query",
                    "input_fields": [],
                    "output_format": "text"
                }

            # 🧠 SMART TEMPLATE MATCHING
            # Check if this request matches an existing template
            found_exact_match = False
            matched_template = None
            
            if self.semantic_service:
                try:
                    templates = self._get_agent_templates()
                    matches = self.semantic_service.find_similar_templates(prompt, templates, threshold=0.75, top_k=1)
                    
                    if matches:
                        matched_template, score = matches[0]
                        
                        # Case 1: High Similarity (>0.9) - Adopt Template
                        if score >= 0.9:
                            yield {
                                "type": "progress",
                                "step": 1,
                                "status": "in_progress",
                                "message": f"Found matching template: {matched_template.get('name')}",
                                "detail": "Adopting template configuration..."
                            }
                            
                            found_exact_match = True
                            t_data = matched_template.get("template", {})
                            
                            # Adopt prompt if not too specific? No, user prompt is user prompt.
                            # Adopt tools if not specified
                            if selected_tools is None:
                                selected_tools = t_data.get("tools", [])
                            
                            # Adopt workflow config if not specified (or default)
                            if workflow_config.get("trigger_type") == "text_query" and not workflow_config.get("input_fields"):
                                workflow_config["trigger_type"] = t_data.get("trigger_type", "text_query")
                                workflow_config["input_fields"] = t_data.get("input_fields", [])
                                workflow_config["output_format"] = t_data.get("output_format", "text")
                            
                            # Adopt metadata if missing
                            if not description: description = matched_template.get("description")
                            if not category: category = matched_template.get("category")
                            if not icon: icon = matched_template.get("icon")
                            if not use_cases: use_cases = matched_template.get("use_cases")
                            if not name: name = f"Copy of {matched_template.get('name')}" 
                            
                        # Case 2: Moderate Similarity (>0.75) - Use as Reference
                        else:
                            yield {
                                "type": "progress",
                                "step": 1,
                                "status": "in_progress",
                                "message": "Found similar reference template",
                                "detail": f"Using '{matched_template.get('name')}' as a guide"
                            }
                except Exception as e:
                    logger.warning(f"Template matching failed: {e}")
            
            # Auto-add postgres_inspect_schema
            if selected_tools is not None and 'postgres_query' in selected_tools:
                if 'postgres_inspect_schema' not in selected_tools:
                    selected_tools.append('postgres_inspect_schema')
            
            # Filter tools
            if selected_tools is not None and len(selected_tools) > 0:
                agent_tools = [t for t in self.tools if t.name in selected_tools]
                tool_count = len(agent_tools)
            else:
                agent_tools = self.tools
                tool_count = len(self.tools)
            
            yield {
                "type": "progress",
                "step": 1,
                "status": "completed",
                "message": "Requirements analyzed",
                "detail": f"Selected {tool_count} tools for this agent"
            }
            
            # Step 2: AI thinking - Generate system prompt with streaming
            yield {
                "type": "progress",
                "step": 2,
                "status": "in_progress",
                "message": "Designing agent",
                "substeps": [
                    {
                        "id": "ai-system-prompt",
                        "label": "AI is generating system prompt...",
                        "status": "in_progress"
                    }
                ]
            }
            
            # Build AI reasoning prompt
            tool_descriptions = "\n".join([f"- {tool.name}: {tool.description}" for tool in agent_tools])
            
            # Get templates summary
            templates_summary = self._get_agent_templates_summary()
            
            # 🧠 Template Context Injection
            template_instruction = ""
            if matched_template:
                t_name = matched_template.get('name')
                t_desc = matched_template.get('description')
                t_prompt = matched_template.get('template', {}).get('prompt')
                
                if found_exact_match:
                    template_instruction = f"""
✅ **EXACT TEMPLATE MATCH FOUND: "{t_name}"**
The user's request is nearly identical to this template. 
**CRITICAL INSTRUCTION:** You MUST create an agent that mimics this template exactly.
- Use the same tools.
- Use the same logic.
- Adapt the system prompt: "{t_prompt}"
- Only change details if the user explicitly asked for something different (e.g., different trigger).
"""
                else:
                    template_instruction = f"""
💡 **SIMILAR TEMPLATE FOUND: "{t_name}"**
The user's request is similar to this template: "{t_desc}".
Use this template as your PRIMARY FOUNDATION. Adapt its prompt ("{t_prompt}") to fit the user's specific request.
"""

            reasoning_prompt = f"""You are an AI assistant helping to create an intelligent agent.

**Reference Agent Templates (Good Examples):**
Here are some examples of high-quality agents. Use these as a reference.
{templates_summary}
{template_instruction}

**Agent Purpose:**
{prompt}

**Available Tools:**
{tool_descriptions}

**Your Task:**
Think step-by-step and explain your reasoning as you design this agent.

1. First, explain what this agent needs to do
2. Identify which tools are required and why
3. Describe the key challenges this agent will face
4. Outline the main instructions the agent needs
5. Compare with the reference templates to ensure high quality
6. Finally, write a REFINED PROMPT that will be used as the agent's instructions.

Start by explaining your understanding and reasoning.
Ensure you end your response with:
FINAL PROMPT: [The detailed, refined prompt text here]"""
            
            messages = [
                {"role": "user", "content": reasoning_prompt}
            ]
            
            # Generate AI reasoning (collect tokens but don't stream them)
            ai_reasoning = []
            for token in self._stream_ai_response(messages):
                ai_reasoning.append(token)
            
            # Parse refined prompt from AI output
            full_reasoning = "".join(ai_reasoning)
            refined_prompt = prompt # Default to original
            if "FINAL PROMPT:" in full_reasoning:
                try:
                    parts = full_reasoning.split("FINAL PROMPT:")
                    if len(parts) > 1:
                        refined_prompt = parts[1].strip()
                        print(f"✨ AI Refined Prompt: {refined_prompt[:100]}...")
                except Exception as e:
                    print(f"⚠️ Failed to parse refined prompt: {e}")
            
            # Now generate actual system prompt (non-streaming for simplicity)
            selected_tool_names = selected_tools if selected_tools is not None else [t.name for t in self.tools]
            system_prompt = self._generate_system_prompt(refined_prompt, agent_tools, selected_tool_names)
            
            # Mark AI substep complete
            yield {
                "type": "progress",
                "step": 2,
                "status": "in_progress",
                "message": "Designing agent",
                "substeps": [
                    {
                        "id": "ai-system-prompt",
                        "label": "System prompt generated",
                        "status": "completed",
                        "detail": f"Created {len(system_prompt)} character prompt"
                    }
                ]
            }
            
            yield {
                "type": "progress",
                "step": 2,
                "status": "completed",
                "message": "Agent designed"
            }
            
            # Step 3: Configure workflow
            yield {
                "type": "progress",
                "step": 3,
                "status": "in_progress",
                "message": "Configuring workflow...",
                "detail": f"Setting up {workflow_config.get('trigger_type', 'text_query')} trigger"
            }
            
            # Create agent prompt template
            prompt_template = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ])
            
            # Create agent
            agent = create_openai_functions_agent(
                llm=self.llm,
                tools=agent_tools,
                prompt=prompt_template
            )
            
            agent_executor = AgentExecutor(
                agent=agent,
                tools=agent_tools,
                verbose=True,
                handle_parsing_errors=True
            )
            
            yield {
                "type": "progress",
                "step": 3,
                "status": "completed",
                "message": "Workflow configured"
            }
            
            # Step 4: Generate execution guidance if needed
            execution_guidance = None
            has_postgres = selected_tools is not None and any(tool in selected_tools for tool in ['postgres_query', 'postgres_inspect_schema'])
            trigger_type = workflow_config.get('trigger_type', 'text_query')
            should_generate_guidance = has_postgres
            
            if should_generate_guidance:
                yield {
                    "type": "progress",
                    "step": 4,
                    "status": "in_progress",
                    "message": "Optimizing execution",
                    "substeps": [
                        {
                            "id": "ai-query-template",
                            "label": "AI is generating query template...",
                            "status": "in_progress"
                        }
                    ]
                }
                
                try:
                    execution_guidance = self._generate_execution_guidance(
                        prompt=prompt,
                        trigger_type=trigger_type,
                        output_format=workflow_config.get('output_format', 'text'),
                        agent_tools=agent_tools,
                        workflow_config=workflow_config
                    )
                    
                    yield {
                        "type": "progress",
                        "step": 4,
                        "status": "in_progress",
                        "message": "Optimizing execution",
                        "substeps": [
                            {
                                "id": "ai-query-template",
                                "label": "Query template generated",
                                "status": "completed",
                                "detail": "Agent will use optimized fast-path"
                            }
                        ]
                    }
                    
                    yield {
                        "type": "progress",
                        "step": 4,
                        "status": "completed",
                        "message": "Execution optimized"
                    }
                except Exception as e:
                    yield {
                        "type": "progress",
                        "step": 4,
                        "status": "in_progress",
                        "message": "Optimizing execution",
                        "substeps": [
                            {
                                "id": "ai-query-template",
                                "label": "Optimization failed",
                                "status": "error",
                                "detail": "Will use standard execution"
                            }
                        ]
                    }
                    
                    yield {
                        "type": "progress",
                        "step": 4,
                        "status": "completed",
                        "message": "Using standard execution"
                    }
            else:
                yield {
                    "type": "progress",
                    "step": 4,
                    "status": "completed",
                    "message": "Configuration complete"
                }
            
            # Step 5: Save agent
            yield {
                "type": "progress",
                "step": 5,
                "status": "in_progress",
                "message": "Saving agent...",
                "detail": "Writing configuration to storage"
            }
            
            agent_data = {
                "id": agent_id,
                "name": agent_name,
                "description": description or prompt[:100],
                "category": category or "General",
                "icon": icon or "🤖",
                "prompt": prompt,
                "system_prompt": system_prompt,
                "selected_tools": selected_tools or [t.name for t in self.tools],
                "workflow_config": workflow_config,
                "created_at": datetime.now().isoformat(),
                "use_cases": use_cases or []
            }
            
            if execution_guidance:
                agent_data["execution_guidance"] = execution_guidance
            
            self.storage.save_agent(agent_data)
            
            yield {
                "type": "progress",
                "step": 5,
                "status": "completed",
                "message": "Agent saved successfully"
            }
            
            # Final result
            yield {
                "type": "result",
                "data": agent_data
            }
            
        except Exception as e:
            yield {
                "type": "error",
                "message": str(e)
            }
    
    def execute_agent_with_progress(self, agent_id: str, user_query: str, tool_configs: Dict[str, Dict[str, str]] = None, input_data: Dict[str, Any] = None):
        """
        Execute an agent with real-time progress updates (generator function for SSE)
        
        Yields progress events as dictionaries with:
        - step: int (1-5)
        - status: str ('in_progress', 'completed', 'error')
        - message: str (description)
        - detail: str (optional additional info)
        - result: dict (final result, sent in last event)
        """
        # List to collect progress events from the callback
        progress_events = []
        
        def capturing_callback(step, status, message, detail=None, substeps=None):
            """Callback that captures progress events"""
            event = {
                "step": step,
                "status": status,
                "message": message,
                "type": "progress"
            }
            if detail:
                event["detail"] = detail
            if substeps:
                event["substeps"] = substeps
            progress_events.append(event)
        
        try:
            # Validate agent exists
            agent_data = self.storage.get_agent(agent_id)
            if not agent_data:
                yield {
                    "type": "error",
                    "message": f"Agent {agent_id} not found"
                }
                return
            
            # Execute agent with callback - this will populate progress_events
            # We need to yield events AS they're added to progress_events
            # To do this, we'll track the last yielded index
            import threading
            import time
            
            result_container = {'result': None, 'error': None}
            execution_complete = threading.Event()
            
            def execute_in_thread():
                try:
                    result_container['result'] = self.execute_agent(
                        agent_id, user_query, tool_configs, input_data, capturing_callback
                    )
                except Exception as e:
                    result_container['error'] = e
                finally:
                    execution_complete.set()
            
            # Start execution in background thread
            exec_thread = threading.Thread(target=execute_in_thread)
            exec_thread.start()
            
            # Stream progress events as they come in
            last_yielded_index = 0
            while not execution_complete.is_set() or last_yielded_index < len(progress_events):
                # Yield any new events
                while last_yielded_index < len(progress_events):
                    yield progress_events[last_yielded_index]
                    last_yielded_index += 1
                
                # Small delay to avoid busy-waiting
                if not execution_complete.is_set():
                    time.sleep(0.05)  # 50ms
            
            # Wait for thread to complete
            exec_thread.join()
            
            # Check for errors
            if result_container['error']:
                yield {
                    "type": "error",
                    "message": str(result_container['error']),
                    "error_type": type(result_container['error']).__name__
                }
                return
            
            # Send final result
            yield {
                "type": "result",
                "data": result_container['result']
            }
            
        except Exception as e:
            yield {
                "type": "error",
                "message": str(e),
                "error_type": type(e).__name__
            }
    
    def execute_agent_with_ai_streaming(self, agent_id: str, user_query: str, tool_configs: Dict[str, Dict[str, str]] = None, input_data: Dict[str, Any] = None, visualization_preferences: str = None):
        """
        Execute an agent with AI thinking streams (enhanced version of execute_agent_with_progress)
        
        This method adds real-time AI reasoning display during summary generation.
        Yields both progress events AND ai_thinking events.
        """
        import threading
        import time
        
        # Storage for progress and AI thinking
        progress_events = []
        ai_thinking_buffer = []
        execution_complete = threading.Event()
        result_container = {'result': None, 'error': None}
        
        def capturing_callback(step, status, message, detail=None, substeps=None):
            """Callback that captures progress events"""
            # Skip step 4 and 5 completions - AI streaming will handle these
            if step in [4, 5] and status == 'completed':
                return  # Don't capture these events
            
            event = {
                "step": step,
                "status": status,
                "message": message,
                "type": "progress"
            }
            if detail:
                event["detail"] = detail
            if substeps:
                event["substeps"] = substeps
            progress_events.append(event)
        
        try:
            # Validate agent exists
            agent_data = self.storage.get_agent(agent_id)
            if not agent_data:
                yield {
                    "type": "error",
                    "message": f"Agent {agent_id} not found"
                }
                return
            
            # Start execution in background thread
            def execute_in_thread():
                try:
                    result_container['result'] = self.execute_agent(
                        agent_id, user_query, tool_configs, input_data, capturing_callback, visualization_preferences
                    )
                except Exception as e:
                    result_container['error'] = e
                finally:
                    execution_complete.set()
            
            exec_thread = threading.Thread(target=execute_in_thread)
            exec_thread.start()
            
            # Stream progress events as they come in
            last_yielded_index = 0
            summary_streaming_started = False
            
            while not execution_complete.is_set() or last_yielded_index < len(progress_events):
                # Yield any new progress events
                while last_yielded_index < len(progress_events):
                    event = progress_events[last_yielded_index]
                    yield event
                    
                    # Check if we're at the "Generating output" step (step 4)
                    # This is where AI summary generation happens
                    if event['step'] == 4 and event['status'] == 'in_progress' and not summary_streaming_started:
                        summary_streaming_started = True
                        # We'll inject AI thinking stream here after the thread completes
                    
                    last_yielded_index += 1
                
                # Small delay to avoid busy-waiting
                if not execution_complete.is_set():
                    time.sleep(0.05)  # 50ms
            
            # Wait for thread to complete
            exec_thread.join()
            
            # Check for errors
            if result_container['error']:
                yield {
                    "type": "error",
                    "message": str(result_container['error']),
                    "error_type": type(result_container['error']).__name__
                }
                return
            
            result = result_container['result']
            
            logger.debug(f"Checking for AI streaming opportunity")
            logger.debug(f"Result success: {result and result.get('success')}")
            logger.debug(f"Has intermediate_steps: {result and 'intermediate_steps' in result}")
            if result:
                logger.debug(f"Intermediate steps count: {len(result.get('intermediate_steps', []))}")
            
            # 🎯 NEW: If result has summary data, generate streaming AI analysis
            # Check if we have intermediate_steps with query results to analyze
            if result and result.get('success'):
                # Try to extract rows/columns from intermediate_steps
                intermediate_steps = result.get('intermediate_steps', [])
                rows = None
                columns = None
                
                print(f"\n🎯 Extracting query results for AI streaming...")
                print(f"  Found {len(intermediate_steps)} intermediate steps")
                
                # Extract query results from intermediate steps
                for idx, step in enumerate(intermediate_steps):
                    print(f"  Step {idx}: {type(step)}")
                    
                    # Handle both dict and tuple formats
                    if isinstance(step, dict):
                        # Dict format (from fast path or serialized)
                        tool_name = step.get('action', {}).get('tool')
                        result_str = step.get('result', '')
                        print(f"    Tool: {tool_name}, Result type: {type(result_str)}")
                    elif isinstance(step, tuple) and len(step) >= 2:
                        # Tuple format (from standard execution)
                        action = step[0]
                        result_str = str(step[1])
                        tool_name = getattr(action, 'tool', None) if hasattr(action, 'tool') else None
                        print(f"    Tool: {tool_name}, Result type: {type(result_str)}")
                    else:
                        logger.debug(f"Skipping unknown format")
                        continue
                    
                    # Check if this is a postgres_query result
                    if tool_name == 'postgres_query':
                        logger.debug(f"Found postgres_query step!")
                        # Try to parse the result
                        try:
                            # Result might be a dict, string, or other format
                            if isinstance(result_str, dict):
                                # Already a dict (from fast path or preserved serialization)
                                if 'rows' in result_str:
                                    rows = result_str['rows']
                                    columns = result_str.get('columns', list(rows[0].keys()) if rows else [])
                                    print(f"      Direct dict access: {len(rows)} rows")
                                    break
                            elif isinstance(result_str, str):
                                if result_str.strip().startswith('['):
                                    # JSON array of rows
                                    import json
                                    parsed = json.loads(result_str)
                                    if isinstance(parsed, list) and len(parsed) > 0:
                                        rows = parsed
                                        columns = list(rows[0].keys()) if rows else []
                                        print(f"      Parsed JSON array: {len(rows)} rows")
                                        break
                                elif result_str.strip().startswith('{'):
                                    # JSON dict with rows/columns
                                    import json
                                    parsed = json.loads(result_str)
                                    if isinstance(parsed, dict) and 'rows' in parsed:
                                        rows = parsed['rows']
                                        columns = parsed.get('columns', list(rows[0].keys()) if rows else [])
                                        print(f"      Parsed JSON dict: {len(rows)} rows")
                                        break
                        except Exception as e:
                            print(f"      ✗ Parse error: {e}")
                            pass
                
                # If we found query results, show AI processing substep (without actual AI call)
                if rows and columns and len(rows) > 0:
                    print(f"\n🎯 Found {len(rows)} rows with {len(columns)} columns")
                    
                    # Signal that processing is happening with a nested substep
                    yield {
                        "type": "progress",
                        "step": 4,
                        "status": "in_progress",
                        "message": "Generating output",
                        "substeps": [
                            {
                                "id": "processing",
                                "label": "Processing query results...",
                                "status": "in_progress"
                            }
                        ]
                    }
                    
                    # Mark processing substep as completed
                    yield {
                        "type": "progress",
                        "step": 4,
                        "status": "in_progress",
                        "message": "Generating output",
                        "substeps": [
                            {
                                "id": "processing",
                                "label": "Processing complete",
                                "status": "completed",
                                "detail": f"Processed {len(rows)} records"
                            }
                        ]
                    }
                    
                    # 🎨 Generate visualization config with streaming
                    if result and result.get('table_data'):
                        agent_data = self.storage.get_agent(agent_id)
                        if agent_data:
                            agent_purpose = agent_data.get('prompt', '') or agent_data.get('description', '')
                            
                            # Create streaming callback for visualization generation
                            def viz_streaming_callback(event):
                                yield event
                            
                            # Generate visualization with streaming
                            query_result = {
                                'table_data': result.get('table_data')
                            }
                            
                            yield {
                                "type": "progress",
                                "step": 4,
                                "status": "in_progress",
                                "message": "Generating output",
                                "substeps": [
                                    {
                                        "id": "processing",
                                        "label": "Processing complete",
                                        "status": "completed",
                                        "detail": f"Processed {len(rows)} records"
                                    },
                                    {
                                        "id": "visualization",
                                        "label": "Generating visualizations...",
                                        "status": "in_progress"
                                    }
                                ]
                            }
                            
                            # Stream visualization generation steps
                            viz_events = []
                            def capture_viz_event(event):
                                viz_events.append(event)
                            
                            visualization_config = self._generate_visualization_config(
                                query_result=query_result,
                                agent_purpose=agent_purpose,
                                user_preferences=visualization_preferences,
                                streaming_callback=capture_viz_event
                            )
                            
                            # Yield all visualization events
                            for event in viz_events:
                                yield event
                            
                            # Update result with visualization config
                            if visualization_config:
                                result['visualization_config'] = visualization_config
                                
                                yield {
                                    "type": "progress",
                                    "step": 4,
                                    "status": "in_progress",
                                    "message": "Generating output",
                                    "substeps": [
                                        {
                                            "id": "processing",
                                            "label": "Processing complete",
                                            "status": "completed",
                                            "detail": f"Processed {len(rows)} records"
                                        },
                                        {
                                            "id": "visualization",
                                            "label": "Visualization configuration complete",
                                            "status": "completed",
                                            "detail": f"Generated {len(visualization_config.get('charts', []))} chart(s)"
                                        }
                                    ]
                                }
                    
                    # Now complete step 4
                    yield {
                        "type": "progress",
                        "step": 4,
                        "status": "completed",
                        "message": "Output generated"
                    }
                    
                    # Mark step 5 as complete
                    yield {
                        "type": "progress",
                        "step": 5,
                        "status": "completed",
                        "message": "Complete"
                    }
                else:
                    # No AI streaming - just complete steps 4 and 5
                    print("\n⚠️ No query results found for AI streaming, completing steps normally")
                    yield {
                        "type": "progress",
                        "step": 4,
                        "status": "completed",
                        "message": "Output generated"
                    }
                    yield {
                        "type": "progress",
                        "step": 5,
                        "status": "completed",
                        "message": "Complete"
                    }
            
            # Send final result
            # Convert Decimal objects to float for JSON serialization
            import json
            from decimal import Decimal
            
            def convert_decimals(obj):
                """Recursively convert Decimal objects to float"""
                if isinstance(obj, Decimal):
                    return float(obj)
                elif isinstance(obj, dict):
                    return {k: convert_decimals(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_decimals(item) for item in obj]
                return obj
            
            serializable_result = convert_decimals(result)
            
            yield {
                "type": "result",
                "data": serializable_result
            }
            
        except Exception as e:
            yield {
                "type": "error",
                "message": str(e),
                "error_type": type(e).__name__
            }
    
    def execute_agent(self, agent_id: str, user_query: str, tool_configs: Dict[str, Dict[str, str]] = None, input_data: Dict[str, Any] = None, progress_callback = None, visualization_preferences: str = None) -> Dict[str, Any]:
        """
        Execute an agent with a user query
        
        Args:
            agent_id: Unique agent identifier
            user_query: User's query/request
            tool_configs: Runtime tool configurations (API keys, etc.)
            input_data: Dynamic input data (dates, parameters, etc.)
            progress_callback: Optional callback function for progress updates
                             Called with (step, status, message, detail, substeps=None)
        
        Returns:
            Execution results dictionary
        """
        # 1. Load agent data
        agent_data = self.storage.get_agent(agent_id)
        if not agent_data:
            return {
                "success": False,
                "error": f"Agent {agent_id} not found"
            }
        
        # Get output format from workflow config
        workflow_config = agent_data.get("workflow_config", {})
        output_format = workflow_config.get("output_format", "text")
        
        # ============================================================
        # PRIORITY 0: TRY EXECUTION GUIDANCE FIRST (NEW FAST PATH) ⚡
        # ============================================================
        # This is the NEW pre-built execution guidance system
        if agent_data.get("execution_guidance"):
            print("\n⚡⚡⚡ ULTRA-FAST PATH: Using pre-built execution guidance")
            guidance_result = self._execute_with_guidance(agent_data, user_query, input_data, progress_callback, visualization_preferences)
            if guidance_result and guidance_result.get("success"):
                print("✅ Execution guidance succeeded - returning result")
                return guidance_result
            else:
                print("⚠️ Execution guidance failed - falling back to legacy paths")
                # Extract reference template for context
                execution_guidance = agent_data.get("execution_guidance", {})
                reference_template = execution_guidance.get("query_template", {}).get("full_template", "")
                if reference_template:
                    print(f"📖 Using failed template as reference for AI query generation")
                    print(f"   Template preview: {reference_template[:150]}...")
                
                # Show fallback substep
                if progress_callback:
                    progress_callback(2, 'in_progress', 'Running tools', None, substeps=[
                        {
                            "id": "ai-generate-query",
                            "label": "AI is generating query from scratch...",
                            "status": "in_progress"
                        }
                    ])
        
        # ============================================================
        # PRIORITY 1: TRY CACHED QUERY FIRST (Old Fast Path)
        # ============================================================
        # If a cached query template exists, use it immediately.
        # Only fall back to schema inspection if cache fails.
        cached_query = agent_data.get("cached_query")
        use_cached = False
        
        print(f"\n🔍 Cache Check: cached_query exists = {bool(cached_query)}")
        if cached_query:
            print(f"🔍 Cache data: {cached_query}")
        
        if cached_query and isinstance(cached_query, dict):
            query_template = cached_query.get("template")
            print(f"🔍 Query template exists: {bool(query_template)}")
            if query_template:
                # Try to extract parameters from user_query
                print(f"🔍 Attempting to extract parameters from user_query: '{user_query}'")
                print(f"🔍 Workflow config: {workflow_config}")
                params = self._extract_query_parameters(user_query, workflow_config)
                print(f"🔍 Extracted params: {params}")
                if params:
                    try:
                        # Inject parameters into template
                        final_query = query_template.format(**params)
                        use_cached = True
                        print(f"🚀 Using cached query template with params: {params}")
                        print(f"📝 Final query: {final_query}")
                        
                        # Execute cached query directly via postgres_query tool
                        result = self._execute_cached_query(agent_id, final_query, tool_configs, visualization_preferences)
                        if result.get("success"):
                            result["used_cache"] = True
                            result["output_format"] = output_format
                            print("✅ Cached query executed successfully - skipping schema inspection")
                            return result
                        else:
                            print("⚠️ Cached query execution failed, falling back to full agent execution")
                            use_cached = False
                    except KeyError as e:
                        print(f"⚠️ Missing parameter in cached query: {e}, falling back to full agent execution")
                        use_cached = False
                    except Exception as e:
                        print(f"⚠️ Cached query error: {e}, falling back to full agent execution")
                        use_cached = False
                else:
                    print("⚠️ No parameters extracted from user_query - cannot use cache")
        
        # ============================================================
        # PRIORITY 2: FULL AGENT EXECUTION (Schema Inspection Path)
        # ============================================================
        # Cache not available or failed - perform full schema inspection
        if not use_cached:
            print("🔍 No cached query available or cache failed - performing full schema-driven analysis")
        
        # 2. Apply runtime tool configurations (Environment Variables)
        original_env = {}
        if tool_configs:
            for tool_name, config in tool_configs.items():
                for key, value in config.items():
                    # Construct env var name (e.g., QBO_API_KEY)
                    if key == 'api_key':
                        env_var = f"{tool_name.upper()}_API_API_KEY"
                    elif key == 'secret_key':
                        env_var = f"{tool_name.upper()}_API_SECRET_KEY"
                    elif key == 'access_token':
                        env_var = f"{tool_name.upper()}_ACCESS_TOKEN"
                    elif key == 'region':
                        env_var = f"{tool_name.upper()}_REGION_NAME"
                    else:
                        env_var = f"{tool_name.upper()}_{key.upper()}"
                    
                    # Store original value for cleanup
                    original_env[env_var] = os.getenv(env_var)
                    # Set new temporary value
                    os.environ[env_var] = value
        
        try:
            # 3. Reload tools to pick up new environment variables
            if tool_configs:
                self.tools = self._load_all_tools()
            
            # 4. Filter tools for this specific agent
            selected_tool_names = agent_data.get("selected_tools", [])
            
            # If selected_tools is None/empty, agent_tools becomes []
            agent_tools = [t for t in self.tools if t.name in selected_tool_names] if selected_tool_names else []
            
            # 🎯 CRITICAL: REGENERATE system prompt based on agent's purpose (don't use stale stored version)
            # This ensures the latest purpose-driven prompt logic is always applied
            agent_purpose = agent_data.get("prompt", "")
            
            # Get reference template if execution guidance failed
            reference_template = None
            if agent_data.get("execution_guidance"):
                reference_template = agent_data.get("execution_guidance", {}).get("query_template", {}).get("full_template", "")
            
            system_prompt = self._generate_system_prompt(agent_purpose, agent_tools, selected_tool_names, reference_template)
            print(f"\n🎯 Regenerated purpose-driven system prompt for agent execution")
            print(f"📋 Agent purpose: {agent_purpose[:100]}...")
            if reference_template:
                print(f"📖 Included reference template in system prompt for structural guidance")
            
            # -----------------------------------------------------------
            # ✅ BRANCH 1: Agent HAS tools (Standard Agent Execution)
            # -----------------------------------------------------------
            if agent_tools and len(agent_tools) > 0:
                if progress_callback:
                    progress_callback(1, 'completed', 'Preparing execution', 'Tools loaded')
                    progress_callback(2, 'in_progress', 'Running tools', 'Executing agent with tools')
                
                # Validate system_prompt doesn't contain unexpected template variables
                # ChatPromptTemplate will parse the entire string, so we need to ensure no {variable} patterns exist
                # except for the ones we explicitly define ({input} and agent_scratchpad)
                import re as re_validate
                unexpected_vars = re_validate.findall(r'\{(\w+)\}', system_prompt)
                # Filter out expected variables
                expected_vars = {'input'}  # agent_scratchpad is handled by MessagesPlaceholder
                unexpected_vars = [v for v in unexpected_vars if v not in expected_vars]
                
                if unexpected_vars:
                    logger.warning(f"Found unexpected template variables in system_prompt: {unexpected_vars}")
                    logger.warning("Escaping them to prevent ChatPromptTemplate errors...")
                    # Escape any remaining {variable} patterns by doubling the braces
                    # This makes ChatPromptTemplate treat them as literal text
                    for var in set(unexpected_vars):  # Use set to avoid duplicates
                        # Replace {var} with {{var}} so it becomes literal {var} in the final string
                        system_prompt = system_prompt.replace(f'{{{var}}}', f'{{{{var}}}}')
                    logger.info(f"Escaped {len(set(unexpected_vars))} unexpected template variables")
                
                prompt_template = ChatPromptTemplate.from_messages([
                    ("system", system_prompt),
                    ("human", "{input}"),
                    MessagesPlaceholder(variable_name="agent_scratchpad"),
                ])
                
                # This function REQUIRES at least one tool to work
                agent = create_openai_functions_agent(
                    llm=self.llm,
                    tools=agent_tools,
                    prompt=prompt_template
                )
                
                agent_executor = AgentExecutor(
                    agent=agent,
                    tools=agent_tools,
                    verbose=True,
                    handle_parsing_errors=True,
                    max_iterations=15,  # Limit iterations to prevent context overflow
                    max_execution_time=300,  # 5 minute timeout
                    return_intermediate_steps=True  # ✅ CRITICAL: Return intermediate steps for query extraction
                )
                
                # Execute
                result = agent_executor.invoke({"input": user_query})
                
                if progress_callback:
                    # Show completion of AI query generation
                    progress_callback(2, 'in_progress', 'Running tools', None, substeps=[
                        {
                            "id": "ai-generate-query",
                            "label": "Query generated and executed successfully",
                            "status": "completed",
                            "detail": "AI created query from scratch"
                        }
                    ])
                    progress_callback(2, 'completed', 'Running tools', 'Tools executed successfully')
                    progress_callback(3, 'in_progress', 'Processing data', 'Processing results')
                
                # 💾 AUTO-SAVE: Extract and save successful query to agent JSON
                successful_query = self._extract_successful_query_from_steps(result.get("intermediate_steps", []))
                if successful_query:
                    print(f"\n💾 AUTO-SAVE: Successful query detected, saving to agent JSON...")
                    self._save_successful_query_to_agent(
                        agent_id=agent_id,
                        agent_data=agent_data,
                        successful_query=successful_query,
                        user_query=user_query,
                        input_data=input_data
                    )
                
                # Format output based on output_format
                raw_output = result.get("output", "")
                
                if progress_callback:
                    progress_callback(3, 'completed', 'Processing data', 'Data processed successfully')
                    progress_callback(4, 'in_progress', 'Generating output', 'Formatting output')
                
                # 🎨 FORCE MARKDOWN: If output doesn't have markdown, convert it
                markdown_output = self._ensure_markdown_format(raw_output)
                
                formatted_result = self._format_output(
                    markdown_output,
                    output_format,
                    result.get("intermediate_steps", []),
                    agent_data=agent_data,  # Pass full agent data for context-aware summaries
                    visualization_preferences=visualization_preferences
                )
                
                # Add flag if query was auto-saved
                if successful_query:
                    formatted_result['query_auto_saved'] = True
                    formatted_result['saved_query'] = successful_query
                
                if progress_callback:
                    progress_callback(4, 'completed', 'Generating output', 'Output formatted successfully')
                    progress_callback(5, 'completed', 'Complete', 'Execution completed successfully')
                
                return formatted_result

            # -----------------------------------------------------------
            # ✅ BRANCH 2: Agent has NO tools (Fallback to Simple Chat)
            # -----------------------------------------------------------
            else:
                print(f"ℹ️ Agent {agent_id} has no tools selected. Running as standard LLM chat.")
                
                if progress_callback:
                    progress_callback(1, 'completed', 'Preparing execution', 'No tools required')
                    progress_callback(2, 'in_progress', 'Running tools', 'Querying LLM')
                
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_query)
                ]
                
                # Direct LLM call since we can't use an AgentExecutor without tools
                response = self.llm.invoke(messages)
                
                if progress_callback:
                    progress_callback(2, 'completed', 'Running tools', 'LLM response received')
                    progress_callback(3, 'completed', 'Processing data', 'Processing complete')
                    progress_callback(4, 'in_progress', 'Generating output', 'Formatting output')
                
                # Format output
                formatted_result = self._format_output(
                    response.content,
                    output_format,
                    [],
                    agent_data=agent_data,  # Pass full agent data for context-aware summaries
                    visualization_preferences=visualization_preferences
                )
                
                if progress_callback:
                    progress_callback(4, 'completed', 'Generating output', 'Output formatted successfully')
                    progress_callback(5, 'completed', 'Complete', 'Execution completed successfully')
                
                return formatted_result

        # -----------------------------------------------------------
        # ❌ CATCH BLOCK (Exception Handling)
        # -----------------------------------------------------------
        except Exception as e:
            print(f"❌ Error executing agent {agent_id}: {str(e)}")
            if progress_callback:
                progress_callback(5, 'error', 'Error', str(e))
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }

        # -----------------------------------------------------------
        # 🧹 FINALLY BLOCK (Cleanup)
        # -----------------------------------------------------------
        finally:
            # Restore original environment variables
            for env_var, original_value in original_env.items():
                if original_value is None:
                    os.environ.pop(env_var, None)
                else:
                    os.environ[env_var] = original_value
            
            # Reload tools again to restore original state (remove temporary configs)
            if tool_configs:
                self.tools = self._load_all_tools()
    
    def list_agents(self) -> List[Dict[str, Any]]:
        """List all saved agents"""
        return self.storage.list_agents()
    
    def get_agent(self, agent_id: str) -> Dict[str, Any]:
        """Get agent details"""
        return self.storage.get_agent(agent_id)
    
    def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent"""
        return self.storage.delete_agent(agent_id)
    
    def update_agent(self, agent_id: str, prompt: str, name: str = None, workflow_config: Dict[str, Any] = None, selected_tools: List[str] = None, tool_configs: Dict[str, Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Update an agent's prompt and regenerate system prompt with automatic tool selection
        
        Args:
            agent_id: Unique agent identifier
            prompt: New user prompt
            name: Optional new name
            workflow_config: Optional workflow configuration
            selected_tools: Optional list of selected tool names (if None, uses auto-analysis)
            tool_configs: Optional tool configurations (API keys, etc.)
            
        Returns:
            Updated agent data
        """
        # Get existing agent
        existing_agent = self.storage.get_agent(agent_id)
        if not existing_agent:
            raise ValueError(f"Agent {agent_id} not found")
        
        # Use existing name if not provided
        agent_name = name or existing_agent.get("name")
        
        # Use existing workflow_config if not provided
        if workflow_config is None:
            workflow_config = existing_agent.get("workflow_config", {
                "trigger_type": "text_query",
                "input_fields": [],
                "output_format": "text"
            })
        
        # 🚀 OPTIMIZATION: Check if this is a metadata-only update (name change only)
        original_prompt = existing_agent.get("prompt", "")
        # Note: existing_agent might not have workflow_config set if old data
        original_config = existing_agent.get("workflow_config", {})
        original_tools = existing_agent.get("selected_tools", [])
        
        prompt_has_changed = prompt != original_prompt
        # Note: workflow_config is defaulted above, so we compare that
        # We need to handle case where original_config defaults might differ from standard defaults if data is old,
        # but here we rely on value equality.
        config_has_changed = workflow_config != existing_agent.get("workflow_config")
        
        tools_have_changed = False
        if selected_tools is not None:
             tools_have_changed = set(selected_tools) != set(original_tools)
             
        is_metadata_update_only = (not prompt_has_changed) and (not config_has_changed) and (not tools_have_changed)
        
        if is_metadata_update_only:
             print("ℹ️ Metadata-only update detected. Skipping AI regeneration.")
             updated_data = {
                 "name": agent_name,
                 "prompt": original_prompt,
                 "system_prompt": existing_agent.get("system_prompt"),
                 "selected_tools": original_tools,
                 "workflow_config": workflow_config, # Use the one we resolved (defaults included)
                 "execution_guidance": existing_agent.get("execution_guidance"),
                 "cached_query": existing_agent.get("cached_query"), # Preserve cache!
                 "tool_configs": tool_configs if tool_configs is not None else existing_agent.get("tool_configs", {})
             }
             
             self.storage.update_agent(agent_id, updated_data)
             return self.storage.get_agent(agent_id)

        # Determine which tools to use
        if selected_tools is not None:
            # Use explicitly provided tools (from UI)
            selected_tool_names = selected_tools
            
            # Auto-add postgres_inspect_schema if postgres_query is selected
            if 'postgres_query' in selected_tool_names and 'postgres_inspect_schema' not in selected_tool_names:
                selected_tool_names.append('postgres_inspect_schema')
                print("✅ Auto-added postgres_inspect_schema (required for postgres_query)")
            
            print(f"✅ Using explicitly provided tools: {selected_tool_names}")
        elif TOOL_ANALYZER_AVAILABLE and ToolAnalyzer:
            # Automatically analyze prompt to determine appropriate tools
            try:
                tool_analyzer = ToolAnalyzer()
                existing_tool_names = self.get_available_tools()
                tool_analysis = tool_analyzer.analyze_prompt(prompt, existing_tool_names)
                
                # Use matched tools if analysis was successful, otherwise fall back to existing tools
                if tool_analysis.get("success", False):
                    selected_tool_names = tool_analysis.get("matched_tools", existing_agent.get("selected_tools", []))
                    print(f"🤖 Auto-selected tools based on prompt: {selected_tool_names}")
                else:
                    # Fall back to existing selected tools
                    selected_tool_names = existing_agent.get("selected_tools", [])
                    print(f"⚠️ Tool analysis failed, keeping existing tools: {selected_tool_names}")
            except Exception as e:
                print(f"⚠️ Tool analysis failed with error: {e}, keeping existing tools")
                selected_tool_names = existing_agent.get("selected_tools", [])
        else:
            print("⚠️ Tool analyzer not available, keeping existing tools")
            selected_tool_names = existing_agent.get("selected_tools", [])
        
        # Filter tools based on selected_tool_names
        agent_tools = [t for t in self.tools if t.name in selected_tool_names] if selected_tool_names else []
        
        # Regenerate system prompt using the helper method
        system_prompt = self._generate_system_prompt(prompt, agent_tools, selected_tool_names)
        
        # Prepare updated data
        updated_data = {
            "name": agent_name,
            "prompt": prompt,
            "system_prompt": system_prompt,
            "selected_tools": selected_tool_names,
            "workflow_config": workflow_config
        }
        
        # 🔄 REGENERATE EXECUTION GUIDANCE if critical config changed
        existing_config = existing_agent.get('workflow_config', {})
        existing_prompt = existing_agent.get('prompt', '')
        
        prompt_changed = prompt != existing_prompt
        trigger_changed = workflow_config.get('trigger_type') != existing_config.get('trigger_type')
        format_changed = workflow_config.get('output_format') != existing_config.get('output_format')
        
        has_postgres = selected_tool_names and any(tool in selected_tool_names for tool in ['postgres_query', 'postgres_inspect_schema'])
        trigger_type = workflow_config.get('trigger_type', 'text_query')
        
        # Only regenerate for structured inputs (date_range, month_year, year)
        should_regenerate_guidance = has_postgres
        
        if (prompt_changed or trigger_changed or format_changed) and should_regenerate_guidance:
            print(f"\n🔄 Configuration changed - regenerating execution guidance for {trigger_type}...")
            print(f"  Prompt changed: {prompt_changed}")
            print(f"  Trigger changed: {trigger_changed} ({existing_config.get('trigger_type')} → {workflow_config.get('trigger_type')})")
            print(f"  Format changed: {format_changed} ({existing_config.get('output_format')} → {workflow_config.get('output_format')})")
            
            try:
                execution_guidance = self._generate_execution_guidance(
                    prompt=prompt,
                    trigger_type=trigger_type,
                    output_format=workflow_config.get('output_format', 'text'),
                    agent_tools=agent_tools,
                    workflow_config=workflow_config
                )
                
                if execution_guidance and not execution_guidance.get('error'):
                    updated_data['execution_guidance'] = execution_guidance
                    print("✅ Execution guidance regenerated successfully!")
                else:
                    print("⚠️ Execution guidance had errors - removing from agent")
                    updated_data['execution_guidance'] = None
            except Exception as e:
                print(f"⚠️ Could not regenerate execution guidance: {e}")
                updated_data['execution_guidance'] = None
        elif should_regenerate_guidance and 'execution_guidance' in existing_agent:
            # Config didn't change - preserve existing guidance
            print("ℹ️ No critical configuration changes - keeping existing execution guidance")
            # Don't include execution_guidance in updated_data - it will be preserved automatically
        elif should_regenerate_guidance:
            # Postgres tools but no existing guidance - try to generate
            print(f"\n🆕 No existing execution guidance - generating for {trigger_type}...")
            try:
                execution_guidance = self._generate_execution_guidance(
                    prompt=prompt,
                    trigger_type=trigger_type,
                    output_format=workflow_config.get('output_format', 'text'),
                    agent_tools=agent_tools,
                    workflow_config=workflow_config
                )
                
                if execution_guidance and not execution_guidance.get('error'):
                    updated_data['execution_guidance'] = execution_guidance
                    print("✅ Execution guidance generated for the first time!")
            except Exception as e:
                print(f"⚠️ Could not generate execution guidance: {e}")
        elif has_postgres and trigger_type == 'text_query':
            print(f"\nℹ️ Skipping execution guidance for text_query (no caching - queries too variable)")
            # Remove any existing guidance for text_query
            updated_data['execution_guidance'] = None
        
        # 🗑️ CLEAR cached query when agent is edited (force re-analysis)
        # Explicitly set to None to ensure deletion
        if "cached_query" in existing_agent:
            print("🗑️ Clearing cached query due to agent edit")
        updated_data["cached_query"] = None  # Force clear cache on every edit
        
        # Add tool configs if provided
        if tool_configs is not None:
            updated_data["tool_configs"] = tool_configs
        elif "tool_configs" in existing_agent:
            # Preserve existing tool_configs if not provided
            updated_data["tool_configs"] = existing_agent.get("tool_configs", {})
        
        # Update in storage
        self.storage.update_agent(agent_id, updated_data)
        
        # Return updated agent
        return self.storage.get_agent(agent_id)
    
    def update_agent_with_streaming(self, agent_id: str, prompt: str, name: str = None, workflow_config: Dict[str, Any] = None, selected_tools: List[str] = None, tool_configs: Dict[str, Dict[str, str]] = None):
        """
        Update an agent with streaming AI reasoning (generator for SSE)
        
        Yields progress events showing AI thinking process during update
        """
        try:
            # Step 1: Loading existing agent
            yield {
                "type": "progress",
                "step": 1,
                "status": "in_progress",
                "message": "Loading agent configuration...",
                "detail": "Reading existing agent data"
            }
            
            # Get existing agent
            existing_agent = self.storage.get_agent(agent_id)
            if not existing_agent:
                yield {
                    "type": "error",
                    "message": f"Agent {agent_id} not found"
                }
                return
            
            agent_name = name or existing_agent.get("name")
            
            # Determine workflow config
            if workflow_config is None:
                workflow_config = existing_agent.get("workflow_config", {
                    "trigger_type": "text_query",
                    "input_fields": [],
                    "output_format": "text"
                })
            
            yield {
                "type": "progress",
                "step": 1,
                "status": "completed",
                "message": "Agent configuration loaded",
                "detail": f"Editing agent: {agent_name}"
            }
            
            # 🚀 OPTIMIZATION: Check for metadata-only updates
            original_prompt = existing_agent.get("prompt", "")
            original_config = existing_agent.get("workflow_config", {})
            original_tools = existing_agent.get("selected_tools", [])
            
            prompt_changed = prompt != original_prompt
            config_changed = workflow_config != existing_agent.get("workflow_config")
            
            tools_changed = False
            if selected_tools is not None:
                tools_changed = set(selected_tools) != set(original_tools)
                
            is_metadata_only = not (prompt_changed or config_changed or tools_changed)
            
            if is_metadata_only:
                print("ℹ️ Metadata-only update detected. Skipping AI regeneration.")
                
                # Skip Steps 2, 3, 4
                yield {"type": "progress", "step": 2, "status": "completed", "message": "Tool analysis skipped (no changes)"}
                yield {"type": "progress", "step": 3, "status": "completed", "message": "Agent update skipped (no changes)"}
                yield {"type": "progress", "step": 4, "status": "completed", "message": "Optimization skipped (no changes)"}
                
                # Step 5: Save
                yield {"type": "progress", "step": 5, "status": "in_progress", "message": "Saving changes..."}
                
                updated_data = {
                    "name": agent_name,
                    "prompt": original_prompt,
                    "system_prompt": existing_agent.get("system_prompt"),
                    "selected_tools": original_tools,
                    "workflow_config": workflow_config,
                    "execution_guidance": existing_agent.get("execution_guidance"),
                    "cached_query": existing_agent.get("cached_query"), # Preserve cache
                    "tool_configs": tool_configs if tool_configs else existing_agent.get("tool_configs", {})
                }
                
                self.storage.update_agent(agent_id, updated_data)
                
                yield {"type": "progress", "step": 5, "status": "completed", "message": "Changes saved"}
                
                yield {
                    "type": "result",
                    "data": self.storage.get_agent(agent_id)
                }
                return
            
            # Step 2: Tool analysis
            yield {
                "type": "progress",
                "step": 2,
                "status": "in_progress",
                "message": "Analyzing tool requirements...",
                "detail": "Determining which tools are needed"
            }
            
            # Determine which tools to use
            if selected_tools is not None:
                selected_tool_names = selected_tools
                if 'postgres_query' in selected_tool_names and 'postgres_inspect_schema' not in selected_tool_names:
                    selected_tool_names.append('postgres_inspect_schema')
            elif TOOL_ANALYZER_AVAILABLE and ToolAnalyzer:
                try:
                    tool_analyzer = ToolAnalyzer()
                    existing_tool_names = self.get_available_tools()
                    tool_analysis = tool_analyzer.analyze_prompt(prompt, existing_tool_names)
                    
                    if tool_analysis.get("success", False):
                        selected_tool_names = tool_analysis.get("matched_tools", existing_agent.get("selected_tools", []))
                    else:
                        selected_tool_names = existing_agent.get("selected_tools", [])
                except Exception:
                    selected_tool_names = existing_agent.get("selected_tools", [])
            else:
                selected_tool_names = existing_agent.get("selected_tools", [])
            
            agent_tools = [t for t in self.tools if t.name in selected_tool_names] if selected_tool_names else []
            
            yield {
                "type": "progress",
                "step": 2,
                "status": "completed",
                "message": "Tool analysis complete",
                "detail": f"Selected {len(agent_tools)} tools"
            }
            
            # Step 3: AI thinking - Regenerate system prompt with streaming
            yield {
                "type": "progress",
                "step": 3,
                "status": "in_progress",
                "message": "Updating agent design",
                "substeps": [
                    {
                        "id": "ai-update-prompt",
                        "label": "AI is analyzing changes...",
                        "status": "in_progress"
                    }
                ]
            }
            
            # Build AI reasoning prompt for updates
            tool_descriptions = "\n".join([f"- {tool.name}: {tool.description}" for tool in agent_tools])
            
            # Detect what changed
            changes = []
            if prompt != existing_agent.get('prompt', ''):
                changes.append("purpose/prompt")
            if workflow_config.get('trigger_type') != existing_agent.get('workflow_config', {}).get('trigger_type'):
                changes.append("trigger type")
            if set(selected_tool_names) != set(existing_agent.get('selected_tools', [])):
                changes.append("tool selection")
            
            changes_text = ", ".join(changes) if changes else "configuration"
            
            # Get templates summary
            templates_summary = self._get_agent_templates_summary()
            
            reasoning_prompt = f"""You are updating an existing agent. Here's what changed:

**Reference Agent Templates (Good Examples):**
Here are some examples of high-quality agents. Use these as a reference to maintain quality during the update.
{templates_summary}

**Original Agent:**
- Name: {existing_agent.get('name')}
- Original Purpose: {existing_agent.get('prompt', '')[:200]}...

**Updated Requirements:**
- New Purpose: {prompt}
- Changed: {changes_text}

**Available Tools:**
{tool_descriptions}

**Your Task:**
Explain what changed and how you're adapting the agent's instructions.

1. Summarize what's different from the original agent
2. Explain if any new tools are needed or if existing ones should be removed
3. Describe key adjustments to the agent's behavior
4. Note any special considerations for the updated mission
5. Ensure the updated agent meets the quality standards of the reference templates
6. Finally, write a REFINED PROMPT that will be used as the agent's instructions.

Start by explaining your analysis.
Ensure you end your response with:
FINAL PROMPT: [The detailed, refined prompt text here]"""
            
            messages = [
                {"role": "user", "content": reasoning_prompt}
            ]
            
            # Generate AI's reasoning (collect tokens but don't stream them)
            ai_reasoning = []
            for token in self._stream_ai_response(messages):
                ai_reasoning.append(token)
            
            # Parse refined prompt from AI output
            full_reasoning = "".join(ai_reasoning)
            refined_prompt = prompt # Default to original
            if "FINAL PROMPT:" in full_reasoning:
                try:
                    parts = full_reasoning.split("FINAL PROMPT:")
                    if len(parts) > 1:
                        refined_prompt = parts[1].strip()
                        print(f"✨ AI Refined Prompt: {refined_prompt[:100]}...")
                except Exception as e:
                    print(f"⚠️ Failed to parse refined prompt: {e}")
            
            # Generate actual system prompt (non-streaming)
            system_prompt = self._generate_system_prompt(refined_prompt, agent_tools, selected_tool_names)
            
            # Mark AI substep complete
            yield {
                "type": "progress",
                "step": 3,
                "status": "in_progress",
                "message": "Updating agent design",
                "substeps": [
                    {
                        "id": "ai-update-prompt",
                        "label": "System prompt updated",
                        "status": "completed",
                        "detail": f"Regenerated {len(system_prompt)} character prompt"
                    }
                ]
            }
            
            yield {
                "type": "progress",
                "step": 3,
                "status": "completed",
                "message": "Agent design updated"
            }
            
            # Step 4: Regenerate execution guidance if needed
            execution_guidance = None
            existing_config = existing_agent.get('workflow_config', {})
            prompt_changed = prompt != existing_agent.get('prompt', '')
            trigger_changed = workflow_config.get('trigger_type') != existing_config.get('trigger_type')
            format_changed = workflow_config.get('output_format') != existing_config.get('output_format')
            
            has_postgres = selected_tool_names and any(tool in selected_tool_names for tool in ['postgres_query', 'postgres_inspect_schema'])
            trigger_type = workflow_config.get('trigger_type', 'text_query')
            should_regenerate_guidance = has_postgres
            
            if (prompt_changed or trigger_changed or format_changed) and should_regenerate_guidance:
                yield {
                    "type": "progress",
                    "step": 4,
                    "status": "in_progress",
                    "message": "Optimizing execution",
                    "substeps": [
                        {
                            "id": "ai-regenerate-template",
                            "label": "AI is regenerating query template...",
                            "status": "in_progress"
                        }
                    ]
                }
                
                try:
                    execution_guidance = self._generate_execution_guidance(
                        prompt=prompt,
                        trigger_type=trigger_type,
                        output_format=workflow_config.get('output_format', 'text'),
                        agent_tools=agent_tools,
                        workflow_config=workflow_config
                    )
                    
                    if execution_guidance and not execution_guidance.get('error'):
                        yield {
                            "type": "progress",
                            "step": 4,
                            "status": "in_progress",
                            "message": "Optimizing execution",
                            "substeps": [
                                {
                                    "id": "ai-regenerate-template",
                                    "label": "Query template regenerated",
                                    "status": "completed",
                                    "detail": "Agent will use optimized fast-path"
                                }
                            ]
                        }
                        
                        yield {
                            "type": "progress",
                            "step": 4,
                            "status": "completed",
                            "message": "Execution optimized"
                        }
                    else:
                        execution_guidance = None
                        yield {
                            "type": "progress",
                            "step": 4,
                            "status": "in_progress",
                            "message": "Optimizing execution",
                            "substeps": [
                                {
                                    "id": "ai-regenerate-template",
                                    "label": "Optimization failed",
                                    "status": "error",
                                    "detail": "Will use standard execution"
                                }
                            ]
                        }
                        
                        yield {
                            "type": "progress",
                            "step": 4,
                            "status": "completed",
                            "message": "Using standard execution"
                        }
                except Exception:
                    execution_guidance = None
                    yield {
                        "type": "progress",
                        "step": 4,
                        "status": "in_progress",
                        "message": "Optimizing execution",
                        "substeps": [
                            {
                                "id": "ai-regenerate-template",
                                "label": "Optimization error",
                                "status": "error"
                            }
                        ]
                    }
                    yield {
                        "type": "progress",
                        "step": 4,
                        "status": "completed",
                        "message": "Using standard execution"
                    }
            else:
                yield {
                    "type": "progress",
                    "step": 4,
                    "status": "completed",
                    "message": "Execution configuration preserved"
                }
            
            # Step 5: Save updated agent
            yield {
                "type": "progress",
                "step": 5,
                "status": "in_progress",
                "message": "Saving changes...",
                "detail": "Updating agent configuration"
            }
            
            # Prepare updated data
            updated_data = {
                "name": agent_name,
                "prompt": prompt,
                "system_prompt": system_prompt,
                "selected_tools": selected_tool_names,
                "workflow_config": workflow_config
            }
            
            if execution_guidance:
                updated_data['execution_guidance'] = execution_guidance
            
            # Clear cached query
            updated_data["cached_query"] = None
            
            # Add tool configs
            if tool_configs is not None:
                updated_data["tool_configs"] = tool_configs
            elif "tool_configs" in existing_agent:
                updated_data["tool_configs"] = existing_agent.get("tool_configs", {})
            
            # Update in storage
            self.storage.update_agent(agent_id, updated_data)
            
            yield {
                "type": "progress",
                "step": 5,
                "status": "completed",
                "message": "Agent updated successfully"
            }
            
            # Final result
            updated_agent = self.storage.get_agent(agent_id)
            yield {
                "type": "result",
                "data": updated_agent
            }
            
        except Exception as e:
            yield {
                "type": "error",
                "message": str(e)
            }
    
    def get_available_tools(self) -> List[str]:
        """
        Get list of available tool names by scanning loaded tools
        
        Returns:
            List of actual tool names (e.g., 'postgres_query', not 'postgres_connector')
        """
        # Return actual tool names from loaded tools
        return [tool.name for tool in self.tools]
    
    def get_tool_schema(self, tool_name: str) -> Dict[str, Any]:
        """
        Get configuration schema for a specific tool from its class definition
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Dictionary with tool configuration requirements
        """
        print(f"[Tool Schema] Getting schema for: {tool_name}")
        
        # Find the tool
        tool = next((t for t in self.tools if t.name == tool_name), None)
        if not tool:
            print(f"[Tool Schema] Tool {tool_name} not found in loaded tools")
            print(f"[Tool Schema] Available tools: {[t.name for t in self.tools]}")
            return None
        
        print(f"[Tool Schema] Found tool: {tool.name}")
        
        # Import the tool class dynamically
        tools_dir = Path(__file__).parent.parent / "tools"
        tool_file = tools_dir / f"{tool_name}.py"
        
        print(f"[Tool Schema] Looking for file: {tool_file}")
        
        if not tool_file.exists():
            # Try other patterns
            for py_file in tools_dir.glob("*.py"):
                if py_file.stem in tool_name or tool_name in py_file.stem:
                    tool_file = py_file
                    print(f"[Tool Schema] Found alternative file: {tool_file}")
                    break
        
        if not tool_file.exists():
            print(f"[Tool Schema] File not found: {tool_file}")
            return {
                "tool_name": tool_name,
                "config_fields": []
            }
        
        # Import the module and get the class
        try:
            import importlib.util
            import sys
            
            # Add parent directory to sys.path temporarily to resolve relative imports
            tools_parent = str(tools_dir.parent)
            if tools_parent not in sys.path:
                sys.path.insert(0, tools_parent)
            
            spec = importlib.util.spec_from_file_location(f"tools.{tool_file.stem}", tool_file)
            module = importlib.util.module_from_spec(spec)
            
            # Add to sys.modules to allow relative imports
            sys.modules[f"tools.{tool_file.stem}"] = module
            
            spec.loader.exec_module(module)
            
            print(f"[Tool Schema] Module loaded successfully")
            
            # Find the tool class (it should inherit from BaseTool)
            from tools.base_tool import BaseTool
            tool_class = None
            for item_name in dir(module):
                item = getattr(module, item_name)
                if (isinstance(item, type) and 
                    issubclass(item, BaseTool) and 
                    item is not BaseTool):
                    tool_class = item
                    print(f"[Tool Schema] Found tool class: {item_name}")
                    break
            
            if tool_class and hasattr(tool_class, 'get_config_schema'):
                config_fields = tool_class.get_config_schema()
                print(f"[Tool Schema] Config fields: {config_fields}")
                return {
                    "tool_name": tool_name,
                    "config_fields": config_fields
                }
            else:
                print(f"[Tool Schema] Tool class not found or doesn't have get_config_schema method")
        except Exception as e:
            print(f"[Tool Schema] Error loading schema for {tool_name}: {e}")
            import traceback
            traceback.print_exc()
        
        # Fallback: return empty schema
        print(f"[Tool Schema] Returning empty schema for {tool_name}")
        return {
            "tool_name": tool_name,
            "config_fields": []
        }

    def _extract_query_parameters(self, user_query: str, workflow_config: Dict[str, Any]) -> Dict[str, str]:
        """
        Extract parameters from user query based on trigger type
        
        Args:
            user_query: User's query string (can be JSON or natural language)
            workflow_config: Workflow configuration
            
        Returns:
            Dictionary of parameters for template substitution
        """
        import re
        import json
        
        trigger_type = workflow_config.get("trigger_type", "text_query")
        params = {}
        
        # 🔧 FIX: Check if user_query is JSON format (from frontend form)
        try:
            query_json = json.loads(user_query)
            if isinstance(query_json, dict):
                # Direct extraction from JSON
                print(f"🔧 Extracting params from JSON: {query_json}")
                if trigger_type == "month_year":
                    if 'month' in query_json and 'year' in query_json:
                        params['month'] = str(query_json['month']).zfill(2)  # Ensure 2 digits
                        params['year'] = str(query_json['year'])
                elif trigger_type == "date_range":
                    if 'start_date' in query_json and 'end_date' in query_json:
                        params['start_date'] = query_json['start_date']
                        params['end_date'] = query_json['end_date']
                elif trigger_type == "year":
                    if 'year' in query_json:
                        params['year'] = str(query_json['year'])
                
                if params:
                    print(f"✅ Extracted params from JSON: {params}")
                    return params
        except (json.JSONDecodeError, ValueError):
            # Not JSON, continue with regex extraction
            pass
        
        # Extract month/year for month_year trigger (Natural Language)
        if trigger_type == "month_year":
            # Look for patterns like "February 2025" or month numbers
            month_match = re.search(r'(\d{2})/%/(\d{4})', user_query)
            if month_match:
                params['month'] = month_match.group(1)
                params['year'] = month_match.group(2)
            else:
                # Try to find month name and year
                month_names = {
                    "january": "01", "february": "02", "march": "03",
                    "april": "04", "may": "05", "june": "06",
                    "july": "07", "august": "08", "september": "09",
                    "october": "10", "november": "11", "december": "12"
                }
                for month_name, month_num in month_names.items():
                    if month_name.lower() in user_query.lower():
                        params['month'] = month_num
                        break
                
                year_match = re.search(r'\b(20\d{2})\b', user_query)
                if year_match:
                    params['year'] = year_match.group(1)
        
        # Extract date range for date_range trigger
        elif trigger_type == "date_range":
            # Look for date patterns MM/DD/YYYY
            date_matches = re.findall(r'(\d{2}/\d{2}/\d{4})', user_query)
            if len(date_matches) >= 2:
                params['start_date'] = date_matches[0]
                params['end_date'] = date_matches[1]
        
        # Extract year for year trigger
        elif trigger_type == "year":
            year_match = re.search(r'\b(20\d{2})\b', user_query)
            if year_match:
                params['year'] = year_match.group(1)
        
        return params if params else None
    
    def _generate_cached_query_output(self, agent_data: Dict[str, Any], output_format: str, row_count: int, rows: List[Dict], columns: List[str]) -> str:
        """
        Generate purpose-driven output message for cached query execution using AI
        
        Args:
            agent_data: Full agent metadata (name, description, use_cases, prompt, category)
            output_format: Output format (csv, table, json, text)
            row_count: Number of rows returned
            rows: Query result rows
            columns: Column names
            
        Returns:
            Purpose-driven output message
        """
        try:
            # ✅ ALWAYS generate purpose-aware summary regardless of output format
            if row_count == 0:
                return "No matching records found for your query."
            
            # Build context-aware prompt for AI with ALL data analysis
            sample_rows = rows[:10] if len(rows) > 10 else rows  # Increased from 5 to 10 for better analysis
            sample_data = "\n".join([
                " | ".join([f"{col}: {row.get(col, 'N/A')}" for col in columns])
                for row in sample_rows
            ])
            
            # 🎯 Build context from agent metadata (NO hardcoded instructions!)
            agent_name = agent_data.get('name', '')
            agent_desc = agent_data.get('description', '')
            use_cases = agent_data.get('use_cases', [])
            agent_category = agent_data.get('category', '')
            agent_prompt = agent_data.get('prompt', '')
            
            agent_context = f"""\n\n🎯 AGENT CONTEXT:
- Name: {agent_name}
- Description: {agent_desc}
- Category: {agent_category}
- Use Cases: {', '.join(use_cases)}

⚠️ CRITICAL: Analyze the data according to THIS SPECIFIC agent's purpose and use cases.
"""
            
            ai_prompt = f"""You are an AI assistant helping with this task:
"{agent_prompt}"

A database query was executed and returned {row_count} record(s) with the following columns:
{', '.join(columns)}

Sample data (first {len(sample_rows)} rows):
{sample_data}
{agent_context}

Provide a comprehensive, analytical summary (3-5 sentences) that directly addresses the agent's purpose.
Be SPECIFIC with data points - mention actual values, IDs, names, amounts, dates from the results.

Do NOT just say "results contain X records" - ANALYZE what those records mean in context of the task.
Do NOT format as markdown, just plain text."""
            
            from langchain_core.messages import HumanMessage
            response = self.llm.invoke([HumanMessage(content=ai_prompt)])
            output = response.content.strip()
            
            print(f"\n🤖 Generated purpose-driven output for cached query: {output[:100]}...")
            return output
            
        except Exception as e:
            print(f"⚠️ Error generating cached query output: {e}")
            # Fallback to simple message
            return f"Query executed successfully. Results contain {row_count} records."
    
    def _execute_cached_query(self, agent_id: str, query: str, tool_configs: Dict[str, Dict[str, str]] = None, visualization_preferences: str = None) -> Dict[str, Any]:
        """
        Execute a cached PostgreSQL query directly
        
        Args:
            agent_id: Agent identifier
            query: SQL query to execute
            tool_configs: Optional tool configurations
            
        Returns:
            Execution result
        """
        try:
            # ✅ Set environment variable to skip AUTO-INSPECT for cached queries
            import os
            original_skip_flag = os.getenv('SKIP_AUTO_INSPECT')
            os.environ['SKIP_AUTO_INSPECT'] = 'true'
            
            try:
                # Find postgres_query tool
                postgres_tool = None
                for tool in self.tools:
                    if tool.name == 'postgres_query':
                        postgres_tool = tool
                        break
                
                if not postgres_tool:
                    return {
                        "success": False,
                        "error": "postgres_query tool not found"
                    }
                
                # Execute query (AUTO-INSPECT will be skipped due to env var)
                result_str = postgres_tool.func(query=query)
                
                # Parse result
                import ast
                try:
                    result = ast.literal_eval(result_str)
                except:
                    result = {"success": False, "error": result_str}
                
                if result.get("success"):
                    # Get agent data to determine output format and agent purpose
                    agent_data = self.storage.get_agent(agent_id)
                    workflow_config = agent_data.get("workflow_config", {})
                    output_format = workflow_config.get("output_format", "text")
                    agent_prompt = agent_data.get("prompt", "")
                    
                    row_count = result.get("row_count", 0)
                    rows = result.get("rows", [])
                    columns = result.get("columns", [])
                    
                    # 🎯 Generate purpose-driven output message using AI
                    output = self._generate_cached_query_output(
                        agent_data=agent_data,
                        output_format=output_format,
                        row_count=row_count,
                        rows=rows,
                        columns=columns
                    )
                    
                    # ✅ FIX: Create intermediate steps in DICTIONARY format (not tuple)
                    # Must match the format from _format_output() to pass Pydantic validation
                    intermediate_steps = [
                        {
                            "action": {
                                "tool": "postgres_query",
                                "tool_input": {"query": query},
                                "log": f"Executing cached query"
                            },
                            "result": result_str
                        }
                    ]
                    
                    # ✅ Use _format_output to handle CSV generation and summary
                    formatted_result = self._format_output(output, output_format, intermediate_steps, agent_data=agent_data, visualization_preferences=visualization_preferences)
                    formatted_result["cached_execution"] = True
                    formatted_result["used_cache"] = True
                    
                    return formatted_result
                else:
                    return result
            
            finally:
                # 🧹 Restore original environment variable
                if original_skip_flag is None:
                    os.environ.pop('SKIP_AUTO_INSPECT', None)
                else:
                    os.environ['SKIP_AUTO_INSPECT'] = original_skip_flag
                    
        except Exception as e:
            return {
                "success": False,
                "error": f"Cached query execution failed: {str(e)}"
            }
    
    def _format_query_result(self, result: Dict[str, Any]) -> str:
        """
        Format query result into readable output
        
        Args:
            result: Query result dictionary
            
        Returns:
            Formatted string output
        """
        if not result.get("success"):
            return f"Error: {result.get('error', 'Unknown error')}"
        
        rows = result.get("rows", [])
        columns = result.get("columns", [])
        row_count = result.get("row_count", 0)
        
        if row_count == 0:
            return "No results found."
        
        # Create markdown table
        output = f"Found {row_count} record(s):\n\n"
        
        if columns:
            # Header
            output += "| " + " | ".join(columns) + " |\n"
            output += "| " + " | ".join(["---"] * len(columns)) + " |\n"
            
            # Rows
            for row in rows:
                output += "| " + " | ".join([str(row.get(col, "")) for col in columns]) + " |\n"
        
        return output
    
    # ============================================================================
    # AI REASONING STREAMING METHODS
    # ============================================================================
    
    def _stream_ai_response(self, messages: List[Dict[str, str]]):
        """
        Stream AI response token-by-token using OpenAI streaming API
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            
        Yields:
            String tokens as they arrive from the AI
        """
        if not self.use_openai:
            # Fallback for non-OpenAI: return full response at once
            from langchain.schema import HumanMessage
            content = "\n".join([msg['content'] for msg in messages if msg['role'] == 'user'])
            response = self.llm.invoke([HumanMessage(content=content)])
            yield response.content
            return
        
        # Use OpenAI streaming
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.openai_api_key)
            
            stream = client.chat.completions.create(
                model=self.openai_model,
                messages=messages,
                stream=True,
                temperature=0.7
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            print(f"⚠️ Streaming error: {e}")
            # Fallback to non-streaming
            from langchain.schema import HumanMessage
            content = "\n".join([msg['content'] for msg in messages if msg['role'] == 'user'])
            response = self.llm.invoke([HumanMessage(content=content)])
            yield response.content

    # ============================================================================
    # SAVED RESULTS MANAGEMENT
    # ============================================================================
    
    def save_execution_result(self, agent_id: str, result_name: str, result_data: Dict) -> str:
        """
        Save an execution result for an agent
        
        Args:
            agent_id: Agent ID
            result_name: Name/description for the result
            result_data: The complete execution result to save
            
        Returns:
            result_id: Unique identifier for the saved result
        """
        import uuid
        from datetime import datetime
        
        result_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        saved_result = {
            "id": result_id,
            "name": result_name,
            "timestamp": timestamp,
            "data": result_data
        }
        
        # Save to agent-specific results directory
        results_dir = os.path.join(self.storage.storage_dir, 'results', agent_id)
        os.makedirs(results_dir, exist_ok=True)
        
        result_file = os.path.join(results_dir, f"{result_id}.json")
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(saved_result, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Saved execution result: {result_name} ({result_id})")
        return result_id
    
    def list_saved_results(self, agent_id: str) -> List[Dict]:
        """
        List all saved execution results for an agent
        
        Args:
            agent_id: Agent ID
            
        Returns:
            List of saved result metadata (id, name, timestamp)
        """
        results_dir = os.path.join(self.storage.storage_dir, 'results', agent_id)
        
        if not os.path.exists(results_dir):
            return []
        
        results = []
        for filename in os.listdir(results_dir):
            if filename.endswith('.json'):
                result_path = os.path.join(results_dir, filename)
                try:
                    with open(result_path, 'r', encoding='utf-8') as f:
                        result_data = json.load(f)
                        # Return metadata only (not full data)
                        results.append({
                            "id": result_data.get('id'),
                            "name": result_data.get('name'),
                            "timestamp": result_data.get('timestamp')
                        })
                except Exception as e:
                    print(f"⚠️ Error loading result {filename}: {e}")
        
        # Sort by timestamp (newest first)
        results.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return results
    
    def get_saved_result(self, agent_id: str, result_id: str) -> Dict:
        """
        Get a specific saved execution result
        
        Args:
            agent_id: Agent ID
            result_id: Result ID
            
        Returns:
            Complete saved result data
        """
        result_path = os.path.join(self.storage.storage_dir, 'results', agent_id, f"{result_id}.json")
        
        if not os.path.exists(result_path):
            return None
        
        try:
            with open(result_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Error loading result {result_id}: {e}")
            return None
    
    def delete_saved_result(self, agent_id: str, result_id: str) -> bool:
        """
        Delete a saved execution result
        
        Args:
            agent_id: Agent ID
            result_id: Result ID
            
        Returns:
            True if deleted successfully
        """
        result_path = os.path.join(self.storage.storage_dir, 'results', agent_id, f"{result_id}.json")
        
        if not os.path.exists(result_path):
            return False
        
        try:
            os.remove(result_path)
            print(f"🗑️ Deleted result: {result_id}")
            return True
        except Exception as e:
            print(f"❌ Error deleting result {result_id}: {e}")
            return False

