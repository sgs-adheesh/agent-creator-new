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
from pathlib import Path
from config import settings
from langchain.agents import create_openai_functions_agent, AgentExecutor
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_models import ChatOllama
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from storage import AgentStorage

# Import ToolAnalyzer (with error handling to avoid circular imports)
try:
    from services.tool_analyzer import ToolAnalyzer
    TOOL_ANALYZER_AVAILABLE = True
except ImportError:
    ToolAnalyzer = None
    TOOL_ANALYZER_AVAILABLE = False


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
        else:
            self.llm = ChatOllama(
                base_url=settings.ollama_base_url,
                model=settings.ollama_model,
                temperature=0.7
            )
        
        # Load all available tools dynamically
        self.tools = self._load_all_tools()
    
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
                
                # Find the tool class (should end with 'Connector')
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    # Check if it's a class and has the required methods
                    if (isinstance(attr, type) and 
                        attr_name.endswith('Connector') and
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
    
    def reload_tools(self):
        """Reload all tools from directory (useful after generating new tools)"""
        self.tools = self._load_all_tools()
    
    def _format_output(self, output: str, output_format: str, intermediate_steps: List) -> Dict[str, Any]:
        """
        Format agent output based on the specified output_format
        
        Args:
            output: Raw output from agent
            output_format: Desired format (text, json, csv, table)
            intermediate_steps: Execution steps from LangChain (list of tuples)
            
        Returns:
            Formatted response dictionary
        """
        # Convert LangChain intermediate_steps tuples to serializable dictionaries
        serialized_steps = []
        if intermediate_steps:
            for step in intermediate_steps:
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
        
        base_response = {
            "success": True,
            "output": output,
            "intermediate_steps": serialized_steps,
            "output_format": output_format
        }
        
        # Generate summary from query results
        summary = self._generate_summary_from_results(intermediate_steps)
        if summary:
            base_response["summary"] = summary
            print(f"\n📊 Summary Generated:")
            print(f"  - Total records: {summary.get('total_records', 'N/A')}")
            print(f"  - Has numeric analysis: {'numeric_analysis' in summary}")
            print(f"  - Has date analysis: {'date_analysis' in summary}")
            print(f"  - Has categorical analysis: {'categorical_analysis' in summary}")
            if 'full_summary' in summary:
                print(f"\n  Full Summary Preview:")
                print(f"  {summary['full_summary'][:500]}...")
        else:
            print(f"\n⚠️ No summary generated (no query results found)")
        
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
        
        # TABLE format - convert to structured table data
        elif output_format == "table":
            table_data = self._extract_table_from_output(output, intermediate_steps)
            if table_data:
                base_response["table_data"] = table_data
            return base_response
        
        # Unknown format - return as text
        else:
            return base_response
    
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
            print(f"\n📊 CSV Generation Debug:")
            print(f"  - Total intermediate steps: {len(intermediate_steps)}")
            
            # Try to find postgres_query results in intermediate steps
            for i, step in enumerate(intermediate_steps):
                # Handle both tuple format (action, result) and dict format {"action": ..., "result": ...}
                if isinstance(step, dict):
                    # Dictionary format (from cached execution)
                    action = step.get('action', {})
                    result = step.get('result', '')
                    tool_name = action.get('tool') if isinstance(action, dict) else None
                    print(f"  - Step {i}: tool = {tool_name} (dict format)")
                elif len(step) >= 2:
                    # Tuple format (from regular execution)
                    action, result = step[0], step[1]
                    tool_name = getattr(action, 'tool', None)
                    print(f"  - Step {i}: tool = {tool_name} (tuple format)")
                else:
                    continue
                
                if tool_name == 'postgres_query':
                    print(f"  - Found postgres_query result!")
                    # Try to parse result as dict
                    if isinstance(result, str):
                        try:
                            result_dict = eval(result)  # or json.loads if result is JSON
                            print(f"  - Parsed result as dict")
                        except Exception as e:
                            print(f"  - Failed to parse result: {e}")
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
        try:
            # Try to find postgres_query results in intermediate steps
            for step in intermediate_steps:
                # Handle both tuple format (action, result) and dict format {"action": ..., "result": ...}
                if isinstance(step, dict):
                    # Dictionary format (from cached execution)
                    action = step.get('action', {})
                    result = step.get('result', '')
                    tool_name = action.get('tool') if isinstance(action, dict) else None
                elif len(step) >= 2:
                    # Tuple format (from regular execution)
                    action, result = step[0], step[1]
                    tool_name = getattr(action, 'tool', None)
                else:
                    continue
                
                if tool_name == 'postgres_query':
                    # Try to parse result as dict
                    if isinstance(result, str):
                        try:
                            result_dict = eval(result)
                        except:
                            result_dict = result
                    else:
                        result_dict = result
                    
                    if isinstance(result_dict, dict) and 'rows' in result_dict:
                        return {
                            "columns": result_dict.get('columns', []),
                            "rows": result_dict.get('rows', []),
                            "row_count": result_dict.get('row_count', len(result_dict.get('rows', [])))
                        }
            
            # No table data found
            return None
            
        except Exception as e:
            print(f"Error extracting table: {e}")
            return None
    
    def _generate_summary_from_results(self, intermediate_steps: List) -> Dict[str, Any]:
        """
        Generate an elaborated summary of query results from intermediate steps
        
        Args:
            intermediate_steps: Execution steps containing tool results
            
        Returns:
            Dictionary with detailed summary statistics and human-readable insights
        """
        try:
            # Find postgres_query results
            for step in intermediate_steps:
                # Handle both tuple format (action, result) and dict format {"action": ..., "result": ...}
                if isinstance(step, dict):
                    # Dictionary format (from cached execution)
                    action = step.get('action', {})
                    result = step.get('result', '')
                    tool_name = action.get('tool') if isinstance(action, dict) else None
                elif len(step) >= 2:
                    # Tuple format (from regular execution)
                    action, result = step[0], step[1]
                    tool_name = getattr(action, 'tool', None)
                else:
                    continue
                
                if tool_name == 'postgres_query':
                    # Parse result
                    if isinstance(result, str):
                        try:
                            result_dict = eval(result)
                        except:
                            continue
                    else:
                        result_dict = result
                    
                    if isinstance(result_dict, dict) and 'rows' in result_dict:
                        rows = result_dict.get('rows', [])
                        columns = result_dict.get('columns', [])
                        
                        if not rows:
                            return {
                                "total_records": 0,
                                "message": "No records found",
                                "description": "The query returned no matching records."
                            }
                        
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
                                        if inv_num not in invoices:
                                            invoices[inv_num] = []
                                        invoices[inv_num].append(row)
                                
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
                                            invoice_data["date"] = first_row.get(col)
                                        elif 'invoice' in col.lower() and 'total' in col.lower():
                                            try:
                                                invoice_data["total"] = float(str(first_row.get(col, 0)).replace('$', '').replace(',', ''))
                                            except:
                                                pass
                                        elif 'vendor' in col.lower() and 'name' in col.lower():
                                            invoice_data["vendor"] = first_row.get(col)
                                    
                                    # Calculate line-level totals
                                    line_totals = []
                                    quantities = []
                                    for row in inv_rows:
                                        for col in columns:
                                            if 'line' in col.lower() and 'total' in col.lower():
                                                try:
                                                    val = float(str(row.get(col, 0)).replace('$', '').replace(',', ''))
                                                    if val > 0:
                                                        line_totals.append(val)
                                                except:
                                                    pass
                                            elif 'quantity' in col.lower():
                                                try:
                                                    val = float(str(row.get(col, 0)).replace('$', '').replace(',', ''))
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
                            f"**Total Records:** {len(rows)}  ",
                            f"**Columns ({len(columns)}):** {', '.join(f'`{c}`' for c in columns)}\n",
                        ]
                        
                        # Add invoice breakdown section if available
                        if invoice_breakdown:
                            full_summary_parts.append("## 📎 Invoice Breakdown\n")
                            full_summary_parts.append(f"*Analysis of {len(invoice_breakdown)} unique invoice(s)*\n")
                            
                            for inv_num, data in sorted(invoice_breakdown.items(), key=lambda x: x[1].get('date', ''), reverse=True):
                                full_summary_parts.append(f"### Invoice: {inv_num}")
                                if data.get('vendor'):
                                    full_summary_parts.append(f"- **Vendor:** {data['vendor']}")
                                if data.get('date'):
                                    full_summary_parts.append(f"- **Date:** {data['date']}")
                                if data.get('total'):
                                    full_summary_parts.append(f"- **Invoice Total:** ${data['total']:,.2f}")
                                full_summary_parts.append(f"- **Line Items:** {data['line_items']} items")
                                if data.get('total_quantity'):
                                    full_summary_parts.append(f"- **Total Quantity:** {data['total_quantity']:,.0f} units")
                                if data.get('line_items_total'):
                                    full_summary_parts.append(f"- **Calculated Line Total:** ${data['line_items_total']:,.2f}")
                                full_summary_parts.append("")  # Empty line between invoices
                        
                        if numeric_summary:
                            full_summary_parts.append("## 💰 Financial/Numeric Analysis\n")
                            for col, data in numeric_summary.items():
                                full_summary_parts.append(f"### {col}")
                                if data.get('is_header_field'):
                                    # Header field (duplicated across line items)
                                    full_summary_parts.append(f"*Note: This is a header-level field, repeated across {data['total_entries']} line items*\n")
                                    full_summary_parts.append(f"- **Unique Invoice Totals:** {data['unique_count']}")
                                    full_summary_parts.append(f"- **Values:** {', '.join([f'${v:,.2f}' for v in data['unique_values']])}")
                                    full_summary_parts.append(f"- **Range:** ${data['min']:,.2f} - ${data['max']:,.2f}\n")
                                elif data.get('is_quantity'):
                                    # Quantity field (no dollar signs)
                                    full_summary_parts.append(f"- **Total:** {data['sum']:,.0f} units")
                                    full_summary_parts.append(f"- **Average:** {data['average']:,.1f} units")
                                    full_summary_parts.append(f"- **Min:** {data['min']:,.0f}")
                                    full_summary_parts.append(f"- **Max:** {data['max']:,.0f}")
                                    full_summary_parts.append(f"- **Count:** {data['count']} values\n")
                                elif data.get('is_currency'):
                                    # Currency field
                                    full_summary_parts.append(f"- **Total:** ${data['sum']:,.2f}")
                                    full_summary_parts.append(f"- **Average:** ${data['average']:,.2f}")
                                    full_summary_parts.append(f"- **Min:** ${data['min']:,.2f}")
                                    full_summary_parts.append(f"- **Max:** ${data['max']:,.2f}")
                                    full_summary_parts.append(f"- **Count:** {data['count']} values\n")
                                else:
                                    # Generic numeric field
                                    full_summary_parts.append(f"- **Total:** {data['sum']:,.2f}")
                                    full_summary_parts.append(f"- **Average:** {data['average']:,.2f}")
                                    full_summary_parts.append(f"- **Min:** {data['min']:,.2f}")
                                    full_summary_parts.append(f"- **Max:** {data['max']:,.2f}")
                                    full_summary_parts.append(f"- **Count:** {data['count']} values\n")
                        
                        if date_summary:
                            full_summary_parts.append("## 📅 Date/Time Analysis\n")
                            for col, data in date_summary.items():
                                full_summary_parts.append(f"### {col}")
                                full_summary_parts.append(f"- **From:** {data['from']}")
                                full_summary_parts.append(f"- **To:** {data['to']}")
                                full_summary_parts.append(f"- **Total Entries:** {data['count']}")
                                full_summary_parts.append(f"- **Unique Dates:** {data['unique_count']}\n")
                        
                        if categorical_summary:
                            full_summary_parts.append("## 🏷️ Categorical Analysis\n")
                            for col, data in categorical_summary.items():
                                full_summary_parts.append(f"### {col}")
                                full_summary_parts.append(f"- **Unique Values:** {data['unique_count']}")
                                full_summary_parts.append(f"- **Total Entries:** {data['total_entries']}")
                                if 'top_values' in data and data['top_values']:
                                    full_summary_parts.append(f"- **Top Values:**")
                                    for item in data['top_values']:
                                        full_summary_parts.append(f"  - {item['value']}: **{item['count']}** occurrences")
                                full_summary_parts.append("")
                        
                        if text_summary:
                            full_summary_parts.append("## 📝 Text/Description Fields\n")
                            for col, data in text_summary.items():
                                full_summary_parts.append(f"### {col}")
                                full_summary_parts.append(f"- **Unique Entries:** {data['unique_count']}")
                                full_summary_parts.append(f"- **Total Entries:** {data['total_entries']}")
                                full_summary_parts.append(f"- **Average Length:** {data['avg_length']} characters")
                                if 'samples' in data and data['samples']:
                                    full_summary_parts.append(f"- **Sample Values:**")
                                    for sample in data['samples']:
                                        preview = str(sample)[:60] + '...' if len(str(sample)) > 60 else str(sample)
                                        full_summary_parts.append(f"  - {preview}")
                                full_summary_parts.append("")
                        
                        summary["full_summary"] = "\n".join(full_summary_parts)
                        
                        # Generate AI-powered summary if LLM is available
                        print(f"\n🤖 Attempting to generate AI summary...")
                        try:
                            ai_summary = self._generate_ai_summary(rows, columns, summary)
                            if ai_summary:
                                summary["ai_summary"] = ai_summary
                                # Prepend AI summary to full summary
                                summary["full_summary"] = f"# 🤖 AI-Generated Insights\n\n{ai_summary}\n\n---\n\n{summary['full_summary']}"
                                print(f"✅ AI summary successfully added to response")
                            else:
                                print(f"⚠️ AI summary returned None")
                        except Exception as e:
                            print(f"❌ Could not generate AI summary: {e}")
                            import traceback
                            traceback.print_exc()
                        
                        return summary
            
            return None
            
        except Exception as e:
            print(f"Error generating summary: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _generate_ai_summary(self, rows: List[Dict], columns: List[str], summary: Dict[str, Any]) -> str:
        """
        Generate AI-powered natural language summary from query results
        
        Args:
            rows: Query result rows
            columns: Column names
            summary: Statistical summary data
            
        Returns:
            AI-generated markdown summary text
        """
        try:
            # Prepare data snapshot for AI analysis (limit to first 10 rows for context)
            sample_rows = rows[:10] if len(rows) > 10 else rows
            
            # Build prompt for AI summary generation
            analysis_prompt = f"""Analyze the following database query results and provide a concise, business-focused summary.

**Dataset Overview:**
- Total Records: {len(rows)}
- Columns: {', '.join(columns)}

**Statistical Summary:**
{self._format_summary_for_ai(summary)}

**Sample Data (first {len(sample_rows)} records):**
{self._format_sample_data(sample_rows, columns)}

**Instructions:**
Provide a detailed, insightful summary (4-6 sentences) that:
1. Identifies the key findings and patterns in the data
2. Highlights any notable trends, concentrations, or anomalies
3. Provides business-relevant observations and actionable insights
4. Mentions specific numbers, vendors, or amounts when relevant
5. Uses natural, professional language suitable for business stakeholders

Do NOT:
- Simply repeat the raw statistics without interpretation
- Use overly technical jargon
- Make assumptions or recommendations beyond the data
- Use markdown formatting (plain text only)

Provide a comprehensive analysis:"""
            
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
    
    def _generate_system_prompt(self, prompt: str, agent_tools: List, selected_tool_names: List[str]) -> str:
        """
        Generate comprehensive system prompt with entity-specific guidance
        
        Args:
            prompt: User prompt
            agent_tools: Available tools
            selected_tool_names: Names of selected tools
            
        Returns:
            System prompt string
        """
        tool_descriptions = "\n".join([f"- {tool.name}: {tool.description}" for tool in agent_tools])
        
        has_postgres = any(tool_name in ['postgres_query', 'postgres_inspect_schema'] for tool_name in selected_tool_names)
        
        system_prompt = f"""You are an AI agent with the following purpose:
{prompt}

You have access to the following tools:
{tool_descriptions}"""
        
        if has_postgres:
            # Base PostgreSQL instructions with strict schema adherence - 100% DYNAMIC
            system_prompt += """\n\n🔴 CRITICAL POSTGRES RULES:

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
- ❌ **EXPOSING ID COLUMNS** - Never SELECT invoice_id, vendor_id, document_id, product_id, etc.
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
-- ❌ WRONG: Exposing ID columns
SELECT i.id AS invoice_id, i.invoice_number...  -- DON'T expose IDs!

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

Remember: For CSV output, just confirm the query executed - don't format anything!"""
        
        system_prompt += """\n\nUse these tools to help users accomplish their tasks. Always be helpful and provide clear explanations of your actions."""
          
        return system_prompt
      
    def create_agent(self, prompt: str, name: str = None, selected_tools: List[str] = None, workflow_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Create an agent from a prompt
        
        Args:
            prompt: User prompt describing the agent's purpose
            name: Optional name for the agent
            selected_tools: List of tool names to assign to this agent (if None, uses all tools)
            workflow_config: Optional workflow configuration (trigger_type, input_fields, output_format)
            
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
        
        # Save agent metadata including selected tools and workflow config
        agent_data = {
            "id": agent_id,
            "name": agent_name,
            "prompt": prompt,
            "system_prompt": system_prompt,
            "selected_tools": selected_tools or [t.name for t in self.tools],
            "workflow_config": workflow_config,  # Store workflow configuration
            "created_at": datetime.now().isoformat(),
        }
        
        self.storage.save_agent(agent_data)
        
        return agent_data
    
    def execute_agent(self, agent_id: str, user_query: str, tool_configs: Dict[str, Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Execute an agent with a user query
        
        Args:
            agent_id: Unique agent identifier
            user_query: User's query/request
            tool_configs: Optional runtime tool configurations (e.g., API keys)
            
        Returns:
            Dictionary with execution results and formatted output
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
        # PRIORITY 1: TRY CACHED QUERY FIRST (Fast Path)
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
                        result = self._execute_cached_query(agent_id, final_query, tool_configs)
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
            
            system_prompt = agent_data.get("system_prompt", agent_data.get("prompt", ""))
            
            # -----------------------------------------------------------
            # ✅ BRANCH 1: Agent HAS tools (Standard Agent Execution)
            # -----------------------------------------------------------
            if agent_tools and len(agent_tools) > 0:
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
                
                # Format output based on output_format
                formatted_result = self._format_output(
                    result.get("output", ""),
                    output_format,
                    result.get("intermediate_steps", [])
                )
                
                return formatted_result

            # -----------------------------------------------------------
            # ✅ BRANCH 2: Agent has NO tools (Fallback to Simple Chat)
            # -----------------------------------------------------------
            else:
                print(f"ℹ️ Agent {agent_id} has no tools selected. Running as standard LLM chat.")
                
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_query)
                ]
                
                # Direct LLM call since we can't use an AgentExecutor without tools
                response = self.llm.invoke(messages)
                
                # Format output
                formatted_result = self._format_output(
                    response.content,
                    output_format,
                    []
                )
                
                return formatted_result

        # -----------------------------------------------------------
        # ❌ CATCH BLOCK (Exception Handling)
        # -----------------------------------------------------------
        except Exception as e:
            print(f"❌ Error executing agent {agent_id}: {str(e)}")
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
    
    def _execute_cached_query(self, agent_id: str, query: str, tool_configs: Dict[str, Dict[str, str]] = None) -> Dict[str, Any]:
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
                    # Get agent data to determine output format
                    agent_data = self.storage.get_agent(agent_id)
                    workflow_config = agent_data.get("workflow_config", {})
                    output_format = workflow_config.get("output_format", "text")
                    
                    # Format simple output message
                    row_count = result.get("row_count", 0)
                    output = f"Query executed successfully. Results contain {row_count} records."
                    
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
                    formatted_result = self._format_output(output, output_format, intermediate_steps)
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

