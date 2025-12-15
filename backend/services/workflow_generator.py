import re
from typing import Dict, Any, List
from config import settings
from langchain_community.chat_models import ChatOllama
from langchain_openai import ChatOpenAI


class WorkflowGenerator:
    """Service for generating workflow graphs from agent data"""
    
    def __init__(self, agent_service=None):
        # Store reference to agent service for dynamic tool lookup
        self.agent_service = agent_service
        
        # Initialize LLM based on configuration
        if settings.use_openai and settings.openai_api_key:
            self.llm = ChatOpenAI(
                model=settings.openai_model,
                api_key=settings.openai_api_key,
                temperature=0.3
            )
        else:
            self.llm = ChatOllama(
                base_url=settings.ollama_base_url,
                model=settings.ollama_model,
                temperature=0.3
            )
    
    def generate_workflow(self, agent_data: Dict[str, Any], use_ai: bool = True) -> Dict[str, Any]:
        """
        Generate workflow graph from agent data
        
        Args:
            agent_data: Agent metadata including system_prompt
            use_ai: Whether to use AI for enhancement (hybrid mode)
            
        Returns:
            Workflow graph with nodes and edges
        """
        # Step 1: Programmatic extraction (base workflow)
        base_workflow = self._generate_base_workflow(agent_data)
        
        # Step 2: AI enhancement (if enabled)
        if use_ai:
            try:
                enhanced_workflow = self._enhance_workflow_with_ai(agent_data, base_workflow)
                return enhanced_workflow
            except Exception as e:
                print(f"AI enhancement failed, falling back to base workflow: {e}")
                return base_workflow
        
        return base_workflow
    
    def _generate_base_workflow(self, agent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate base workflow programmatically"""
        system_prompt = agent_data.get("system_prompt", "")
        agent_name = agent_data.get("name", "Agent")
        agent_prompt = agent_data.get("prompt", "")
        workflow_config = agent_data.get("workflow_config", {})
        trigger_type = workflow_config.get("trigger_type", "text_query")
        selected_tools = agent_data.get("selected_tools", [])
        
        # Get tools from selected_tools (assigned during agent creation)
        tools = self._get_tool_info(selected_tools)
        
        # Create input node based on trigger type
        input_node = self._create_input_node(trigger_type)
        
        # Create nodes
        nodes = [
            input_node,
            {
                "id": "agent",
                "type": "agent",
                "position": {"x": 250, "y": 100},
                "data": {
                    "label": agent_name,
                    "description": agent_prompt,
                    "system_prompt": system_prompt
                }
            }
        ]
        
        # Create edges
        edges = [
            {
                "id": "e-input-agent",
                "source": "input",
                "target": "agent",
                "type": "smoothstep",
                "animated": True
            }
        ]
        
        # Add tool nodes
        tool_y_position = 250
        tool_x_start = 100
        tool_spacing = 200
        
        for idx, tool in enumerate(tools):
            tool_id = f"tool-{tool['name']}"
            tool_x = tool_x_start + (idx * tool_spacing)
            
            nodes.append({
                "id": tool_id,
                "type": "tool",
                "position": {"x": tool_x, "y": tool_y_position},
                "data": {
                    "label": tool["display_name"],
                    "description": tool["description"],
                    "tool_name": tool["name"]
                }
            })
            
            # Edge from agent to tool
            edges.append({
                "id": f"e-agent-{tool_id}",
                "source": "agent",
                "target": tool_id,
                "type": "smoothstep",
                "animated": False
            })
            
            # Edge from tool to output (will connect later)
            edges.append({
                "id": f"e-{tool_id}-output",
                "source": tool_id,
                "target": "output",
                "type": "smoothstep",
                "animated": False
            })
        
        # Add output node
        nodes.append({
            "id": "output",
            "type": "output",
            "position": {"x": 250, "y": 400},
            "data": {
                "label": "Result",
                "description": "Agent response to user"
            }
        })
        
        # If no tools, direct connection from agent to output
        if not tools:
            edges.append({
                "id": "e-agent-output",
                "source": "agent",
                "target": "output",
                "type": "smoothstep",
                "animated": False
            })
        
        return {
            "nodes": nodes,
            "edges": edges,
            "metadata": {
                "agent_id": agent_data.get("id"),
                "agent_name": agent_name,
                "tool_count": len(tools),
                "trigger_type": trigger_type,
                "generation_method": "programmatic"
            }
        }
    
    def _create_input_node(self, trigger_type: str) -> Dict[str, Any]:
        """Create input node based on trigger type"""
        
        # Define input node configurations for each trigger type
        input_configs = {
            "text_query": {
                "label": "User Input",
                "description": "User query or question",
                "icon": "💬"
            },
            "date_range": {
                "label": "Date Range",
                "description": "Start and end dates",
                "icon": "📅"
            },
            "month_year": {
                "label": "Month/Year",
                "description": "Monthly report period",
                "icon": "📆"
            },
            "year": {
                "label": "Year",
                "description": "Yearly report period",
                "icon": "📊"
            },
            "conditions": {
                "label": "Conditions",
                "description": "Custom input fields",
                "icon": "⚙️"
            },
            "scheduled": {
                "label": "Scheduled",
                "description": "Automatic execution",
                "icon": "⏰"
            }
        }
        
        config = input_configs.get(trigger_type, input_configs["text_query"])
        
        return {
            "id": "input",
            "type": "input",
            "position": {"x": 250, "y": 0},
            "data": {
                "label": config["label"],
                "description": config["description"],
                "icon": config.get("icon", "📝"),
                "trigger_type": trigger_type
            }
        }
    
    def _get_tool_info(self, selected_tools: List[str]) -> List[Dict[str, str]]:
        """Get tool information from selected tool names"""
        tools = []
        
        for tool_name in selected_tools:
            # Create display name from tool_name (e.g., "postgres_query" -> "Postgres Query")
            display_name = ' '.join(word.capitalize() for word in tool_name.replace('_', ' ').split())
            
            # Get description based on tool name (actual tool names from BaseTool)
            tool_descriptions = {
                'postgres_query': 'Query PostgreSQL database',
                'qbo_query': 'Access QuickBooks Online data',
                'qdrant_search': 'Search vector database with Qdrant',
                'gmail_api': 'Send and manage Gmail emails',
                'stripe_api': 'Process Stripe payments',
                'aws_s3_api': 'Manage AWS S3 storage',
                'dropbox_api': 'Access Dropbox files',
                'google_drive_api': 'Manage Google Drive files',
                'google_sheets_api': 'Read/write Google Sheets',
                'google_analytics_api': 'Query Google Analytics data',
                'salesforce_api': 'Access Salesforce CRM',
                'paypal_api': 'Process PayPal payments',
                'microsoft_onedrive_api': 'Access OneDrive files',
            }
            
            description = tool_descriptions.get(tool_name, f'Execute {display_name}')
            
            tools.append({
                "name": tool_name,
                "display_name": display_name,
                "description": description
            })
        
        return tools
    
    def _extract_tools(self, system_prompt: str) -> List[Dict[str, str]]:
        """Extract tools from system prompt by parsing tool descriptions"""
        tools = []
        
        # Parse tool descriptions from system prompt
        # Format: "- tool_name: description"
        tool_pattern = r'-\s+([\w_]+):\s+([^\n]+)'
        matches = re.findall(tool_pattern, system_prompt)
        
        for match in matches:
            tool_name = match[0]
            tool_description = match[1]
            
            # Create display name from tool_name (e.g., "gmail_api" -> "Gmail API")
            display_name = ' '.join(word.capitalize() for word in tool_name.replace('_', ' ').split())
            
            tools.append({
                "name": tool_name,
                "display_name": display_name,
                "description": tool_description.split(' - ')[0].strip()  # Take first part before separator
            })
        
        return tools
    
    def _enhance_workflow_with_ai(
        self, 
        agent_data: Dict[str, Any], 
        base_workflow: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Use AI to enhance the workflow with intelligent suggestions"""
        
        agent_prompt = agent_data.get("prompt", "")
        system_prompt = agent_data.get("system_prompt", "")
        tools = [node["data"]["tool_name"] for node in base_workflow["nodes"] if node["type"] == "tool"]
        
        enhancement_prompt = f"""You are a workflow analyzer. Analyze this AI agent and suggest workflow enhancements.

Agent Purpose: {agent_prompt}

Available Tools: {', '.join(tools) if tools else 'None'}

Base Workflow Structure:
- Input → Agent → Tools → Output

Your task: Analyze if this agent needs:
1. Decision nodes (for choosing between tools)
2. Conditional branches
3. Sequential tool execution (one tool after another)
4. Parallel tool execution (multiple tools at once)

Respond in JSON format:
{{
    "needs_decision_node": true/false,
    "execution_pattern": "parallel" or "sequential" or "conditional",
    "suggestions": "brief explanation",
    "additional_nodes": []
}}

Be concise and only suggest if truly needed."""

        try:
            # Add timeout to prevent hanging
            import signal
            
            def timeout_handler(signum, frame):
                raise TimeoutError("AI enhancement timed out")
            
            # Set 5 second timeout (only works on Unix, Windows will skip)
            try:
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(5)
            except AttributeError:
                # Windows doesn't support SIGALRM, skip timeout
                pass
            
            response = self.llm.invoke(enhancement_prompt)
            
            # Cancel alarm
            try:
                signal.alarm(0)
            except AttributeError:
                pass
            
            # Try to parse AI response
            import json
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                ai_suggestions = json.loads(json_match.group())
                
                # Apply AI suggestions to base workflow
                enhanced_workflow = self._apply_ai_enhancements(base_workflow, ai_suggestions)
                enhanced_workflow["metadata"]["generation_method"] = "hybrid_ai_enhanced"
                enhanced_workflow["metadata"]["ai_suggestions"] = ai_suggestions.get("suggestions", "")
                
                return enhanced_workflow
            
        except TimeoutError as e:
            print(f"AI enhancement timed out: {e}")
        except Exception as e:
            print(f"AI enhancement failed: {e}")
        
        # Fallback to base workflow
        base_workflow["metadata"]["generation_method"] = "programmatic_only"
        return base_workflow
    
    def _apply_ai_enhancements(
        self, 
        base_workflow: Dict[str, Any], 
        ai_suggestions: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply AI suggestions to enhance the workflow"""
        
        enhanced = base_workflow.copy()
        nodes = enhanced["nodes"].copy()
        edges = enhanced["edges"].copy()
        
        # If AI suggests decision node
        if ai_suggestions.get("needs_decision_node"):
            # Find agent node
            agent_node_idx = next((i for i, n in enumerate(nodes) if n["id"] == "agent"), None)
            if agent_node_idx is not None:
                # Insert decision node between agent and tools
                decision_node = {
                    "id": "decision",
                    "type": "decision",
                    "position": {"x": 250, "y": 175},
                    "data": {
                        "label": "Route Decision",
                        "description": "Determines which tool to use based on query"
                    }
                }
                nodes.insert(agent_node_idx + 1, decision_node)
                
                # Update edges to go through decision node
                new_edges = []
                for edge in edges:
                    if edge["source"] == "agent" and edge["target"].startswith("tool-"):
                        # Redirect to decision node first
                        new_edges.append({
                            "id": "e-agent-decision",
                            "source": "agent",
                            "target": "decision",
                            "type": "smoothstep",
                            "animated": True
                        })
                        new_edges.append({
                            **edge,
                            "id": edge["id"].replace("agent", "decision"),
                            "source": "decision"
                        })
                    else:
                        new_edges.append(edge)
                
                edges = new_edges
        
        enhanced["nodes"] = nodes
        enhanced["edges"] = edges
        
        return enhanced
