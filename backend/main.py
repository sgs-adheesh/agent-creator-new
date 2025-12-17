from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from services import AgentService
from services.workflow_generator import WorkflowGenerator
from services.tool_analyzer import ToolAnalyzer
from services.tool_generator import ToolGenerator
from services.semantic_service import SemanticService 

app = FastAPI(title="Agent Generator API", version="1.0.0")

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
    print(f"⚠️ Warning: ToolAnalyzer initialization failed: {e}")
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


class ExecuteAgentRequest(BaseModel):
    query: Optional[str] = None  # Text query (for text_query type)
    input_data: Optional[Dict[str, Any]] = None  # Dynamic input data (dates, conditions, etc.)
    tool_configs: Optional[Dict[str, Dict[str, str]]] = None  # Runtime tool configurations


class AgentResponse(BaseModel):
    id: str
    name: str
    prompt: str
    created_at: str
    workflow_config: Optional[Dict[str, Any]] = None  # Include workflow config in response


class ExecuteAgentResponse(BaseModel):
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    intermediate_steps: Optional[List[Dict[str, Any]]] = None


class UpdateAgentRequest(BaseModel):
    prompt: str
    name: Optional[str] = None
    workflow_config: Optional[WorkflowConfig] = None


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


@app.get("/")
async def root():
    return {"message": "Agent Generator API"}


@app.post("/api/agents/create", response_model=AgentResponse)
async def create_agent(request: CreateAgentRequest):
    """Create a new agent from a prompt"""
    try:
        # Convert workflow_config to dict if provided
        workflow_config_dict = None
        if request.workflow_config:
            workflow_config_dict = request.workflow_config.dict()
        
        agent_data = agent_service.create_agent(
            prompt=request.prompt,
            name=request.name,
            selected_tools=request.selected_tools,
            workflow_config=workflow_config_dict  # Pass workflow config
        )
        return AgentResponse(**agent_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agents", response_model=List[AgentResponse])
async def list_agents():
    """List all saved agents"""
    try:
        agents = agent_service.list_agents()
        return [AgentResponse(**agent) for agent in agents]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str):
    """Get agent details by ID"""
    try:
        agent = agent_service.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        return AgentResponse(**agent)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/agents/{agent_id}/execute", response_model=ExecuteAgentResponse)
async def execute_agent(agent_id: str, request: ExecuteAgentRequest):
    """Execute an agent with dynamic input"""
    try:
        # Build execution query from dynamic inputs
        query = request.query or ""
        if request.input_data:
            # Convert input_data to query context
            query = f"Input Data: {request.input_data}\n{query}"
        
        result = agent_service.execute_agent(agent_id, query, request.tool_configs)
        return ExecuteAgentResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
            workflow_config=workflow_config_dict
        )
        
        return AgentResponse(**updated_agent)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

