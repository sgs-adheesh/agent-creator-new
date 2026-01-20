from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import os
import uuid
import logging
from pathlib import Path

from services import AgentService
from services.workflow_generator import WorkflowGenerator
from services.tool_analyzer import ToolAnalyzer
from services.tool_generator import ToolGenerator
from services.semantic_service import SemanticService
from tools.postgres_connector import PostgresConnector
from utils.logger import setup_logging, get_logger
from utils.validation import (
    validate_agent_name,
    validate_uuid,
    sanitize_string,
    validate_workflow_config
)

# Setup logging
setup_logging(log_level=os.getenv("LOG_LEVEL", "INFO"))
logger = get_logger(__name__)

app = FastAPI(title="Agent Generator API", version="1.0.0")

# Initialize PostgreSQL schema cache on startup
# NOTE: Cache is ALWAYS refreshed from database on every application restart
# to ensure the latest schema changes are captured (force_refresh=True by default)
logger.info("🚀 Starting application...")
logger.info("📊 Initializing PostgreSQL schema cache...")
try:
    # force_refresh=True: Always rebuild cache from database on app restart
    # force_refresh=False: Try to load from cache file if available (faster but may be stale)
    PostgresConnector.initialize_cache(force_refresh=True)
    logger.info("✅ PostgreSQL schema cache initialized successfully")
except Exception as e:
    logger.warning(f"⚠️ Warning: Failed to initialize PostgreSQL cache: {e}")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
agent_service = AgentService()
workflow_generator = WorkflowGenerator()

# Initialize ToolAnalyzer with error handling
try:
    tool_analyzer = ToolAnalyzer()
except Exception as e:
    logger.warning(f"⚠️ Warning: ToolAnalyzer initialization failed: {e}")
    tool_analyzer = None

tool_generator = ToolGenerator()
semantic_service = SemanticService()


# Request/Response models
class WorkflowConfig(BaseModel):
    """Workflow configuration for dynamic UI"""
    trigger_type: str  # "text_query", "date_range", "month_year", "year", "conditions", "scheduled"
    input_fields: Optional[List[Dict[str, Any]]] = []  # Dynamic fields configuration
    output_format: str = "text"  # "text", "csv", "json", "table"


class CreateAgentRequest(BaseModel):
    prompt: str
    name: Optional[str] = None
    selected_tools: Optional[List[str]] = None
    workflow_config: Optional[WorkflowConfig] = None  # New: workflow configuration
    description: Optional[str] = None
    category: Optional[str] = None
    icon: Optional[str] = None
    use_cases: Optional[List[str]] = None


class ExecuteAgentRequest(BaseModel):
    query: Optional[str] = None  # Text query (for text_query type)
    input_data: Optional[Dict[str, Any]] = None  # Dynamic input data (dates, conditions, etc.)
    tool_configs: Optional[Dict[str, Dict[str, str]]] = None  # Runtime tool configurations
    visualization_preferences: Optional[str] = None  # User-specified visualization approach (e.g., "pie chart by vendor", "bar chart over time")


class AgentResponse(BaseModel):
    id: str
    name: str
    prompt: str
    created_at: str
    workflow_config: Optional[Dict[str, Any]] = None  # Include workflow config in response
    selected_tools: Optional[List[str]] = None  # Include selected tools in response
    tool_configs: Optional[Dict[str, Dict[str, str]]] = None  # Include tool configurations


class ExecuteAgentResponse(BaseModel):
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    intermediate_steps: Optional[List[Dict[str, Any]]] = None
    output_format: Optional[str] = None
    csv_data: Optional[str] = None
    csv_filename: Optional[str] = None
    download_link: Optional[str] = None
    table_data: Optional[Dict[str, Any]] = None
    json_data: Optional[Any] = None
    summary: Optional[Dict[str, Any]] = None
    cached_execution: Optional[bool] = None
    used_cache: Optional[bool] = None
    visualization_config: Optional[Dict[str, Any]] = None  # LLM-generated visualization configuration


class UpdateAgentRequest(BaseModel):
    prompt: str
    name: Optional[str] = None
    workflow_config: Optional[WorkflowConfig] = None
    selected_tools: Optional[List[str]] = None  # Allow updating selected tools
    tool_configs: Optional[Dict[str, Dict[str, str]]] = None  # Tool configurations


class ToolAnalysisRequest(BaseModel):
    prompt: str


class ToolGenerationRequest(BaseModel):
    tool_spec: Dict[str, Any]


class ToolAnalysisResponse(BaseModel):
    success: bool
    matched_tools: Optional[List[str]] = None
    new_tools_needed: Optional[List[Dict[str, Any]]] = None
    reasoning: Optional[str] = None
    requires_user_confirmation: bool = False
    error: Optional[str] = None


class SemanticSearchRequest(BaseModel):
    query: str
    context: Optional[str] = None  # "create_agent", "edit_agent", "execute"


class SemanticSearchResponse(BaseModel):
    success: bool
    intent: Optional[Dict[str, Any]] = None
    suggested_tools: Optional[List[Dict[str, Any]]] = None
    confidence: float = 0.0
    error: Optional[str] = None


class CacheQueryRequest(BaseModel):
    query_template: str
    parameters: List[str]
    tables: Optional[List[str]] = None
    joins: Optional[List[str]] = None


@app.get("/api/templates")
async def get_templates():
    """Get all predefined agent templates"""
    try:
        templates_file = Path(__file__).parent / "templates" / "agent_templates.json"
        
        if not templates_file.exists():
            return {"success": True, "templates": []}
        
        with open(templates_file, 'r', encoding='utf-8') as f:
            templates = json.load(f)
        
        return {"success": True, "templates": templates}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class CreateAgentFromTemplateRequest(BaseModel):
    name: Optional[str] = None
    visualization_preferences: Optional[str] = None  # User's visualization preferences

@app.post("/api/templates/{template_id}/create", response_model=AgentResponse)
async def create_agent_from_template(template_id: str, request: CreateAgentFromTemplateRequest = CreateAgentFromTemplateRequest()):
    """Create a new agent from a template (instant - no AI processing)"""
    try:
        # Load template
        templates_file = Path(__file__).parent / "templates" / "agent_templates.json"
        
        if not templates_file.exists():
            raise HTTPException(status_code=404, detail="Templates file not found")
        
        with open(templates_file, 'r', encoding='utf-8') as f:
            templates = json.load(f)
        
        # Find template
        template = next((t for t in templates if t["id"] == template_id), None)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        # Generate new agent ID
        agent_id = str(uuid.uuid4())
        agent_name = request.name if request.name else template["name"]
        
        # Get visualization preferences: user input > template default > None
        visualization_prefs = None
        if request.visualization_preferences:
            visualization_prefs = request.visualization_preferences
        elif template.get("template", {}).get("default_visualization_preferences"):
            visualization_prefs = template["template"]["default_visualization_preferences"]
        
        # Extract template data
        template_data = template["template"]
        
        # Create agent data directly from template (NO AI processing)
        agent_data = {
            "id": agent_id,
            "name": agent_name,
            "description": template.get("description"),
            "category": template.get("category"),
            "icon": template.get("icon"),
            "prompt": template_data["prompt"],
            "system_prompt": agent_service._generate_system_prompt(
                prompt=template_data["prompt"],
                agent_tools=[t for t in agent_service.tools if t.name in template_data.get("tools", [])],
                selected_tool_names=template_data.get("tools", [])
            ),
            "selected_tools": template_data.get("tools", []),
            "workflow_config": {
                "trigger_type": template_data["trigger_type"],
                "input_fields": template_data.get("input_fields", []),
                "output_format": "table"
            },
            "created_at": datetime.now().isoformat(),
            "use_cases": template.get("use_cases", []),
            "execution_guidance": template_data.get("execution_guidance"),  # Copy pre-built execution guidance
            "visualization_preferences": visualization_prefs  # Store visualization preferences
        }
        
        # Save agent
        agent_service.storage.save_agent(agent_data)
        
        print(f"✅ Created agent '{agent_name}' from template '{template_id}' (instant - no AI processing)")
        
        return AgentResponse(**agent_data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    return {"message": "Agent Generator API"}


@app.post("/api/agents/create", response_model=AgentResponse)
async def create_agent(request: CreateAgentRequest):
    """Create a new agent from a prompt"""
    try:
        # Validate agent name if provided
        if request.name:
            is_valid, error_msg = validate_agent_name(request.name)
            if not is_valid:
                raise HTTPException(status_code=400, detail=f"Invalid agent name: {error_msg}")
        
        # Validate workflow config if provided
        if request.workflow_config:
            workflow_config_dict = request.workflow_config.dict()
            is_valid, error_msg = validate_workflow_config(workflow_config_dict)
            if not is_valid:
                raise HTTPException(status_code=400, detail=f"Invalid workflow config: {error_msg}")
        else:
            workflow_config_dict = None
        
        # Sanitize prompt
        sanitized_prompt = sanitize_string(request.prompt, max_length=5000)
        
        agent_data = agent_service.create_agent(
            prompt=sanitized_prompt,
            name=request.name,
            selected_tools=request.selected_tools,
            workflow_config=workflow_config_dict  # Pass workflow config
        )
        return AgentResponse(**agent_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating agent: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agents/create/stream")
async def create_agent_stream(request: CreateAgentRequest):
    """
    Create a new agent with streaming AI reasoning via Server-Sent Events (SSE)
    """
    async def event_generator():
        try:
            # Convert workflow_config to dict if provided
            workflow_config_dict = None
            if request.workflow_config:
                workflow_config_dict = request.workflow_config.dict()
            
            # Execute agent creation with streaming
            for progress_event in agent_service.create_agent_with_streaming(
                prompt=request.prompt,
                name=request.name,
                selected_tools=request.selected_tools,
                workflow_config=workflow_config_dict,
                description=request.description,
                category=request.category,
                icon=request.icon,
                use_cases=request.use_cases
            ):
                # Send progress update as SSE
                yield f"data: {json.dumps(progress_event, default=str)}\n\n"
            
        except Exception as e:
            error_event = {
                "type": "error",
                "message": str(e)
            }
            yield f"data: {json.dumps(error_event, default=str)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@app.get("/api/agents", response_model=List[AgentResponse])
async def list_agents():
    """List all saved agents"""
    try:
        agents = agent_service.list_agents()
        return [AgentResponse(**agent) for agent in agents]
    except Exception as e:
        logger.error(f"Error listing agents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str):
    """Get agent details by ID"""
    try:
        # Validate UUID format
        is_valid, error_msg = validate_uuid(agent_id)
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"Invalid agent ID: {error_msg}")
        
        agent = agent_service.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        return AgentResponse(**agent)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent {agent_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agents/{agent_id}/execute", response_model=ExecuteAgentResponse)
async def execute_agent(agent_id: str, request: ExecuteAgentRequest):
    """Execute an agent with dynamic input"""
    try:
        # Validate UUID format
        is_valid, error_msg = validate_uuid(agent_id)
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"Invalid agent ID: {error_msg}")
        
        # Get agent to check trigger type
        agent = agent_service.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        workflow_config = agent.get("workflow_config", {})
        trigger_type = workflow_config.get("trigger_type", "text_query")
        
        # Build execution query from dynamic inputs
        query = request.query or ""
        
        # Handle different trigger types
        if request.input_data:
            if trigger_type == "month_year":
                # Convert month/year to natural language query
                month = request.input_data.get("month", "")
                year = request.input_data.get("year", "")
                if month and year:
                    # Map month number to name
                    month_names = {
                        "01": "January", "02": "February", "03": "March",
                        "04": "April", "05": "May", "06": "June",
                        "07": "July", "08": "August", "09": "September",
                        "10": "October", "11": "November", "12": "December"
                    }
                    month_name = month_names.get(month, month)
                    query = f"""Generate report for {month_name} {year}.

🔴 CRITICAL INSTRUCTIONS:
1. Inspect schema for ALL tables you need to answer this query
2. Identify date/time columns from the schema (check JSONB columns list)
3. Check sample_data to see the actual date format (usually MM/DD/YYYY)
4. For month+year filtering for {month_name} {year}:
   - ⚠️ CRITICAL: Month comes FIRST in MM/DD/YYYY format!
   - CORRECT Pattern: WHERE (date_column->>'value' LIKE '{month}/%/{year}')
   - Example: WHERE (invoice_date->>'value' LIKE '02/%/2025')
   - This matches all dates in February 2025 (02/01/2025, 02/15/2025, etc.)
5. Use LEFT JOIN for related tables (never INNER JOIN)
6. Only use columns that exist in the inspected schemas

Return ALL {month_name} {year} records."""
            elif trigger_type == "date_range":
                # Handle date range with explicit pattern
                start_date = request.input_data.get("start_date", "")
                end_date = request.input_data.get("end_date", "")
                if start_date and end_date:
                    query = f"""Generate report from {start_date} to {end_date}.

🔴 CRITICAL INSTRUCTIONS:
1. Inspect schema for ALL tables you need to answer this query
2. Identify date/time columns from the schema (check JSONB columns list)
3. Check sample_data to see the actual date format (usually MM/DD/YYYY)
4. For date range filtering between {start_date} and {end_date}:
   - Use string comparison with >= and <= operators
   - Pattern: WHERE (date_column->>'value' >= '{start_date}' AND date_column->>'value' <= '{end_date}')
   - This works for MM/DD/YYYY format when both dates are in the same format
5. Use LEFT JOIN for related tables (never INNER JOIN)
6. Only use columns that exist in the inspected schemas

Return ONLY records between {start_date} and {end_date} (inclusive)."""
            elif trigger_type == "year":
                # Handle year - generic pattern
                year = request.input_data.get("year", "")
                if year:
                    query = f"""Generate report for year {year}.

🔴 CRITICAL INSTRUCTIONS:
1. Inspect schema for ALL tables you need to answer this query
2. Identify date/time columns from the schema (check JSONB columns list)
3. Check sample_data to see the actual date format (usually MM/DD/YYYY)
4. For year filtering for year {year}:
   - CORRECT Pattern: WHERE (date_column->>'value' LIKE '%/%/{year}')
   - Example: WHERE (invoice_date->>'value' LIKE '%/%/2025')
   - This matches all dates in 2025 (01/15/2025, 06/30/2025, 12/31/2025, etc.)
5. Use LEFT JOIN for related tables (never INNER JOIN)
6. Only use columns that exist in the inspected schemas

Return ONLY year {year} records."""
            else:
                # Generic conversion
                query = f"Input Data: {request.input_data}\n{query}"
        
        result = agent_service.execute_agent(agent_id, query, request.tool_configs, request.input_data, None, request.visualization_preferences)
        return ExecuteAgentResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing agent {agent_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agents/{agent_id}/execute/stream")
async def execute_agent_stream(agent_id: str, request: ExecuteAgentRequest):
    """
    Execute an agent with real-time progress streaming via Server-Sent Events (SSE)
    """
    async def event_generator():
        try:
            # Get agent to check trigger type
            agent = agent_service.get_agent(agent_id)
            if not agent:
                yield f"data: {{\"error\": \"Agent not found\"}}\n\n"
                return
            
            workflow_config = agent.get("workflow_config", {})
            trigger_type = workflow_config.get("trigger_type", "text_query")
            
            # Build execution query from dynamic inputs
            query = request.query or ""
            
            # Handle different trigger types (same logic as regular execute)
            if request.input_data:
                if trigger_type == "month_year":
                    month = request.input_data.get("month", "")
                    year = request.input_data.get("year", "")
                    if month and year:
                        month_names = {
                            "01": "January", "02": "February", "03": "March",
                            "04": "April", "05": "May", "06": "June",
                            "07": "July", "08": "August", "09": "September",
                            "10": "October", "11": "November", "12": "December"
                        }
                        month_name = month_names.get(month, month)
                        query = f"Generate report for {month_name} {year}.\n\nReturn ALL {month_name} {year} records."
            
            # Execute agent with progress streaming AND AI thinking
            for progress_event in agent_service.execute_agent_with_ai_streaming(
                agent_id, query, request.tool_configs, request.input_data, request.visualization_preferences
            ):
                # Send progress update as SSE
                yield f"data: {json.dumps(progress_event, default=str)}\n\n"
            
        except Exception as e:
            error_event = {
                "type": "error",
                "message": str(e)
            }
            yield f"data: {json.dumps(error_event, default=str)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@app.delete("/api/agents/{agent_id}")
async def delete_agent(agent_id: str):
    """Delete an agent"""
    try:
        deleted = agent_service.delete_agent(agent_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Agent not found")
        return {"success": True, "message": f"Agent {agent_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agents/{agent_id}/results/save")
async def save_execution_result(agent_id: str, request: Request):
    """Save an execution result for an agent"""
    try:
        data = await request.json()
        result_data = data.get('result')
        result_name = data.get('name', f"Result {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        if not result_data:
            raise HTTPException(status_code=400, detail="No result data provided")
        
        # Save result to storage
        result_id = agent_service.save_execution_result(agent_id, result_name, result_data)
        
        return {
            "success": True,
            "result_id": result_id,
            "message": "Result saved successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agents/{agent_id}/results")
async def list_saved_results(agent_id: str):
    """List all saved execution results for an agent"""
    try:
        results = agent_service.list_saved_results(agent_id)
        return {
            "success": True,
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agents/{agent_id}/results/{result_id}")
async def get_saved_result(agent_id: str, result_id: str):
    """Get a specific saved execution result"""
    try:
        result = agent_service.get_saved_result(agent_id, result_id)
        if not result:
            raise HTTPException(status_code=404, detail="Result not found")
        return {
            "success": True,
            "result": result
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/agents/{agent_id}/results/{result_id}")
async def delete_saved_result(agent_id: str, result_id: str):
    """Delete a saved execution result"""
    try:
        deleted = agent_service.delete_saved_result(agent_id, result_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Result not found")
        return {
            "success": True,
            "message": "Result deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agents/{agent_id}/workflow")
async def get_agent_workflow(agent_id: str, use_ai: bool = False):
    """Get workflow graph for an agent"""
    try:
        agent = agent_service.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        workflow = workflow_generator.generate_workflow(agent, use_ai=use_ai)
        return workflow
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/agents/{agent_id}", response_model=AgentResponse)
async def update_agent(agent_id: str, request: UpdateAgentRequest):
    """Update an agent's prompt and workflow configuration"""
    try:
        # Get existing agent
        existing_agent = agent_service.get_agent(agent_id)
        if not existing_agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        # Convert workflow_config to dict if provided
        workflow_config_dict = None
        if request.workflow_config:
            workflow_config_dict = request.workflow_config.dict()
        
        # Update agent using the service (regenerate system_prompt and auto-select tools)
        updated_agent = agent_service.update_agent(
            agent_id=agent_id,
            prompt=request.prompt,
            name=request.name,
            workflow_config=workflow_config_dict,
            selected_tools=request.selected_tools,  # Pass selected tools
            tool_configs=request.tool_configs  # Pass tool configurations
        )
        
        return AgentResponse(**updated_agent)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/agents/{agent_id}/stream")
async def update_agent_stream(agent_id: str, request: UpdateAgentRequest):
    """
    Update an agent with streaming AI reasoning via Server-Sent Events (SSE)
    """
    async def event_generator():
        try:
            # Get existing agent
            existing_agent = agent_service.get_agent(agent_id)
            if not existing_agent:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Agent not found'})}\n\n"
                return
            
            # Convert workflow_config to dict if provided
            workflow_config_dict = None
            if request.workflow_config:
                workflow_config_dict = request.workflow_config.dict()
            
            # Execute agent update with streaming
            for progress_event in agent_service.update_agent_with_streaming(
                agent_id=agent_id,
                prompt=request.prompt,
                name=request.name,
                workflow_config=workflow_config_dict,
                selected_tools=request.selected_tools,
                tool_configs=request.tool_configs
            ):
                # Send progress update as SSE
                yield f"data: {json.dumps(progress_event, default=str)}\n\n"
            
        except Exception as e:
            error_event = {
                "type": "error",
                "message": str(e)
            }
            yield f"data: {json.dumps(error_event, default=str)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


@app.post("/api/tools/analyze", response_model=ToolAnalysisResponse)
async def analyze_tools(request: ToolAnalysisRequest):
    """Analyze prompt to detect required tools"""
    try:
        # Get list of existing tools
        existing_tools = agent_service.get_available_tools()
        
        # Analyze prompt
        if tool_analyzer is not None:
            analysis = tool_analyzer.analyze_prompt(request.prompt, existing_tools)
        else:
            # Fallback response when tool_analyzer is not available
            analysis = {
                "success": False,
                "error": "Tool analyzer not available",
                "matched_tools": [],
                "new_tools_needed": [],
                "reasoning": "Tool analyzer service is not available"
            }
        
        return ToolAnalysisResponse(**analysis)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tools/generate")
async def generate_tool(request: ToolGenerationRequest):
    """Generate tool code from specification"""
    try:
        result = tool_generator.generate_tool(request.tool_spec)
        
        # Reload agent service tools if generation successful
        if result.get("success"):
            print("\n🔄 Reloading agent service tools...")
            agent_service.reload_tools()
            print("✅ Agent service reloaded successfully\n")
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tools/list")
async def list_tools():
    """List all available tools"""
    try:
        tools = agent_service.get_available_tools()
        return {"success": True, "tools": tools}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/tools/{tool_name}/schema")
async def get_tool_schema(tool_name: str):
    """Get configuration schema for a specific tool"""
    try:
        schema = agent_service.get_tool_schema(tool_name)
        if not schema:
            raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
        return schema
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/semantic/search", response_model=SemanticSearchResponse)
async def semantic_search(request: SemanticSearchRequest):
    """Perform semantic search to understand query intent and suggest tools"""
    try:
        # Extract intent
        intent = semantic_service.extract_intent(request.query)
        
        # Find similar tools
        available_tools = agent_service.get_available_tools()
        similar_tools = semantic_service.find_similar_tools(
            prompt=request.query,
            available_tools=available_tools,
            threshold=0.5,
            top_k=5
        )
        
        # Format results
        suggested_tools = [
            {"name": tool_name, "confidence": score}
            for tool_name, score in similar_tools
        ]
        
        return SemanticSearchResponse(
            success=True,
            intent=intent,
            suggested_tools=suggested_tools,
            confidence=intent.get("confidence", 0.0)
        )
    except Exception as e:
        return SemanticSearchResponse(
            success=False,
            error=str(e)
        )


@app.post("/api/agents/{agent_id}/cache-query")
async def cache_query(agent_id: str, request: CacheQueryRequest):
    """Cache a query template for future reuse"""
    try:
        # Get agent
        agent = agent_service.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        
        # Prepare cached query data
        cached_query = {
            "template": request.query_template,
            "parameters": request.parameters,
            "tables": request.tables or [],
            "joins": request.joins or [],
            "cached_at": datetime.now().isoformat()
        }
        
        # Update agent with cached query
        agent["cached_query"] = cached_query
        agent_service.storage.update_agent(agent_id, {"cached_query": cached_query})
        
        return {
            "success": True,
            "message": "Query cached successfully",
            "cached_query": cached_query
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

