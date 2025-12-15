import uuid
from datetime import datetime
from typing import Dict, Any, List
from config import settings
from langchain.agents import create_openai_functions_agent, AgentExecutor
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.chat_models import ChatOllama
from langchain_openai import ChatOpenAI
from tools import QdrantConnector, QBOConnector
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
        
        # Initialize tools
        self.qdrant_tool = QdrantConnector()
        self.qbo_tool = QBOConnector()
        
        # Convert tools to LangChain format
        self.tools = [
            self.qdrant_tool.to_langchain_tool(),
            self.qbo_tool.to_langchain_tool()
        ]
    
    def create_agent(self, prompt: str, name: str = None) -> Dict[str, Any]:
        """
        Create an agent from a prompt
        
        Args:
            prompt: User prompt describing the agent's purpose (may include configuration)
            name: Optional name for the agent
            
        Returns:
            Dictionary with agent information
        """
        agent_id = str(uuid.uuid4())
        agent_name = name or f"Agent-{agent_id[:8]}"
        
        # Parse configuration from prompt if exists
        config = self._parse_configuration(prompt)
        base_prompt = config['base_prompt']
        
        # Create system prompt
        system_prompt = f"""You are an AI agent with the following purpose:
{base_prompt}

You have access to the following tools:
- qdrant_search: Search and query data from Qdrant vector database (collection: icap_dev_migration)
- qbo_query: Query QuickBooks Online data (placeholder)

Use these tools to help users accomplish their tasks. Always be helpful and provide clear explanations of your actions."""

        # Create agent prompt template
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        # Create agent
        agent = create_openai_functions_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt_template
        )
        
        # Create agent executor
        agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=True,
            handle_parsing_errors=True
        )
        
        # Save agent metadata with workflow_config format
        workflow_config = {
            "trigger_type": config.get('execution_trigger', 'user_text_input'),
            "input_fields": config.get('custom_fields', []),
            "output_format": config.get('output_format', 'text')
        }
        
        # Handle legacy agents that might have different structure
        if 'workflow_config' in agent_data:
            existing_workflow_config = agent_data.get('workflow_config', {})
            if 'trigger_type' not in workflow_config and 'trigger_type' in existing_workflow_config:
                workflow_config['trigger_type'] = existing_workflow_config['trigger_type']
            if 'output_format' not in workflow_config and 'output_format' in existing_workflow_config:
                workflow_config['output_format'] = existing_workflow_config['output_format']
            if 'input_fields' not in workflow_config and 'input_fields' in existing_workflow_config:
                workflow_config['input_fields'] = existing_workflow_config['input_fields']
        
        agent_data = {
            "id": agent_id,
            "name": agent_name,
            "prompt": prompt,  # Store original prompt with config
            "system_prompt": system_prompt,
            "created_at": datetime.now().isoformat(),
            "workflow_config": workflow_config  # Store in legacy workflow_config format
        }
        
        self.storage.save_agent(agent_data)
        
        return agent_data
    
    def _parse_configuration(self, prompt: str) -> Dict[str, Any]:
        """
        Parse configuration from prompt if it exists
        
        Args:
            prompt: Full prompt potentially with [Configuration] section
            
        Returns:
            Dictionary with base_prompt and configuration details
        """
        lines = prompt.split('\n')
        config_index = -1
        
        for i, line in enumerate(lines):
            if '[Configuration]' in line:
                config_index = i
                break
        
        if config_index == -1:
            # No configuration found
            return {
                'base_prompt': prompt.strip(),
                'execution_trigger': 'query',
                'output_format': 'text',
                'selected_tools': []
            }
        
        # Extract base prompt and configuration
        base_prompt = '\n'.join(lines[:config_index]).strip()
        config_lines = lines[config_index:]
        
        config = {
            'base_prompt': base_prompt,
            'execution_trigger': 'query',
            'output_format': 'text',
            'selected_tools': [],
            'custom_fields': []
        }
        
        for line in config_lines:
            if 'Execution Trigger:' in line:
                trigger = line.split(':', 1)[1].strip().lower()
                config['execution_trigger'] = trigger
            elif 'Output Format:' in line:
                fmt = line.split(':', 1)[1].strip().lower()
                config['output_format'] = fmt
            elif 'Selected Tools:' in line:
                tools = line.split(':', 1)[1].strip()
                if tools and tools != 'auto-detect':
                    config['selected_tools'] = [t.strip() for t in tools.split(',')]
            elif 'Custom Fields:' in line:
                fields_json = line.split(':', 1)[1].strip()
                if fields_json and fields_json != 'none':
                    try:
                        import json
                        config['custom_fields'] = json.loads(fields_json)
                    except:
                        pass
        
        return config
    
    def execute_agent(self, agent_id: str, user_query: str) -> Dict[str, Any]:
        """
        Execute an agent with a user query
        
        Args:
            agent_id: Unique agent identifier
            user_query: User's query/request
            
        Returns:
            Dictionary with execution results
        """
        # Load agent
        agent_data = self.storage.get_agent(agent_id)
        if not agent_data:
            return {
                "success": False,
                "error": f"Agent {agent_id} not found"
            }
        
        # Recreate agent (agents are not serializable, so we recreate from prompt)
        system_prompt = agent_data.get("system_prompt", agent_data.get("prompt", ""))
        
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        agent = create_openai_functions_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=prompt_template
        )
        
        agent_executor = AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=True,
            handle_parsing_errors=True
        )
        
        # Execute agent
        try:
            result = agent_executor.invoke({"input": user_query})
            return {
                "success": True,
                "output": result.get("output", ""),
                "intermediate_steps": result.get("intermediate_steps", [])
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
    
    def list_agents(self) -> List[Dict[str, Any]]:
        """List all saved agents"""
        return self.storage.list_agents()
    
    def get_agent(self, agent_id: str) -> Dict[str, Any]:
        """Get agent details"""
        return self.storage.get_agent(agent_id)
    
    def delete_agent(self, agent_id: str) -> bool:
        """Delete an agent"""
        return self.storage.delete_agent(agent_id)
    
    def update_agent(self, agent_id: str, prompt: str, name: str = None) -> Dict[str, Any]:
        """
        Update an agent's prompt and regenerate system prompt
        
        Args:
            agent_id: Unique agent identifier
            prompt: New user prompt (may include configuration)
            name: Optional new name
            
        Returns:
            Updated agent data
        """
        # Get existing agent
        existing_agent = self.storage.get_agent(agent_id)
        if not existing_agent:
            raise ValueError(f"Agent {agent_id} not found")
        
        # Use existing name if not provided
        agent_name = name or existing_agent.get("name")
        
        # Parse configuration from prompt
        config = self._parse_configuration(prompt)
        base_prompt = config['base_prompt']
        
        # Regenerate system prompt
        system_prompt = f"""You are an AI agent with the following purpose:
{base_prompt}

You have access to the following tools:
- qdrant_search: Search and query data from Qdrant vector database (collection: icap_dev_migration)
- qbo_query: Query QuickBooks Online data (placeholder)

Use these tools to help users accomplish their tasks. Always be helpful and provide clear explanations of your actions."""
        
        # Prepare updated data with workflow_config format
        workflow_config = {
            "trigger_type": config.get('execution_trigger', 'user_text_input'),
            "input_fields": config.get('custom_fields', []),
            "output_format": config.get('output_format', 'text')
        }
        
        updated_data = {
            "name": agent_name,
            "prompt": prompt,  # Store full prompt with config
            "system_prompt": system_prompt,
            "workflow_config": workflow_config  # Store in legacy workflow_config format
        }
        
        # Update in storage
        self.storage.update_agent(agent_id, updated_data)
        
        # Return updated agent
        return self.storage.get_agent(agent_id)

