import uuid
from datetime import datetime
from typing import Dict, Any, List
import os
import sys
import importlib
from pathlib import Path
from config import settings
from langchain.agents import create_openai_functions_agent, AgentExecutor
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_models import ChatOllama
from langchain_openai import ChatOpenAI
from storage import AgentStorage


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
        
        # Create system prompt with only selected tools
        tool_descriptions = "\n".join([f"- {tool.name}: {tool.description}" for tool in agent_tools])
        
        system_prompt = f"""You are an AI agent with the following purpose:
{prompt}

You have access to the following tools:
{tool_descriptions}

Use these tools to help users accomplish their tasks. Always be helpful and provide clear explanations of your actions."""

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
            Dictionary with execution results
        """
        # 1. Load agent data
        agent_data = self.storage.get_agent(agent_id)
        if not agent_data:
            return {
                "success": False,
                "error": f"Agent {agent_id} not found"
            }
        
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
                    handle_parsing_errors=True
                )
                
                # Execute
                result = agent_executor.invoke({"input": user_query})
                
                return {
                    "success": True,
                    "output": result.get("output", ""),
                    "intermediate_steps": result.get("intermediate_steps", [])
                }

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
                
                return {
                    "success": True,
                    "output": response.content,
                    "intermediate_steps": [] 
                }

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
    
    def update_agent(self, agent_id: str, prompt: str, name: str = None, workflow_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Update an agent's prompt and regenerate system prompt
        
        Args:
            agent_id: Unique agent identifier
            prompt: New user prompt
            name: Optional new name
            workflow_config: Optional workflow configuration
            
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
        
        # Get selected tools from existing agent
        selected_tool_names = existing_agent.get("selected_tools", [])
        agent_tools = [t for t in self.tools if t.name in selected_tool_names] if selected_tool_names else self.tools
        
        # Regenerate system prompt with selected tools
        tool_descriptions = "\n".join([f"- {tool.name}: {tool.description}" for tool in agent_tools])
        
        system_prompt = f"""You are an AI agent with the following purpose:
{prompt}

You have access to the following tools:
{tool_descriptions}

Use these tools to help users accomplish their tasks. Always be helpful and provide clear explanations of your actions."""
        
        # Prepare updated data
        updated_data = {
            "name": agent_name,
            "prompt": prompt,
            "system_prompt": system_prompt,
            "workflow_config": workflow_config
        }
        
        # Update in storage
        self.storage.update_agent(agent_id, updated_data)
        
        # Return updated agent
        return self.storage.get_agent(agent_id)
    
    def get_available_tools(self) -> List[str]:
        """
        Get list of available tool names by scanning the tools directory
        
        Returns:
            List of tool names (without .py extension)
        """
        tools_dir = Path(__file__).parent.parent / "tools"
        tool_files = []
        
        if tools_dir.exists():
            for file in tools_dir.glob("*.py"):
                # Skip __init__.py and private files
                if file.name.startswith("__") or file.name.startswith("_"):
                    continue
                # Extract tool name (filename without .py)
                tool_name = file.stem
                tool_files.append(tool_name)
        
        return tool_files

