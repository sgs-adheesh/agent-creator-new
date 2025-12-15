import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path 
from config import settings


class AgentStorage:
    """File-based storage for agents"""
    
    def __init__(self):
        self.storage_dir = Path(settings.agents_storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
    
    def _get_agent_path(self, agent_id: str) -> Path:
        """Get file path for an agent"""
        return self.storage_dir / f"{agent_id}.json"
    
    def save_agent(self, agent_data: Dict) -> str:
        """
        Save agent to file
        
        Args:
            agent_data: Dictionary containing agent information
            
        Returns:
            Agent ID
        """
        agent_id = agent_data.get("id", str(uuid.uuid4()))
        agent_data["id"] = agent_id
        
        agent_path = self._get_agent_path(agent_id)
        
        with open(agent_path, "w") as f:
            json.dump(agent_data, f, indent=2)
        
        return agent_id
    
    def get_agent(self, agent_id: str) -> Optional[Dict]:
        """
        Load agent from file
        
        Args:
            agent_id: Unique agent identifier
            
        Returns:
            Agent data dictionary or None if not found
        """
        agent_path = self._get_agent_path(agent_id)
        
        if not agent_path.exists():
            return None
        
        with open(agent_path, "r") as f:
            return json.load(f)
    
    def list_agents(self) -> List[Dict]:
        """
        List all saved agents
        
        Returns:
            List of agent data dictionaries
        """
        agents = []
        
        for agent_file in self.storage_dir.glob("*.json"):
            try:
                with open(agent_file, "r") as f:
                    agent_data = json.load(f)
                    agents.append(agent_data)
            except Exception as e:
                print(f"Error loading agent from {agent_file}: {e}")
        
        return agents
    
    def update_agent(self, agent_id: str, updated_data: Dict) -> bool:
        """
        Update agent data
        
        Args:
            agent_id: Unique agent identifier
            updated_data: Dictionary with updated fields
            
        Returns:
            True if updated, False if not found
        """
        agent_path = self._get_agent_path(agent_id)
        
        if not agent_path.exists():
            return False
        
        # Load existing data
        with open(agent_path, "r") as f:
            agent_data = json.load(f)
        
        # Update fields
        agent_data.update(updated_data)
        agent_data["id"] = agent_id  # Ensure ID doesn't change
        agent_data["updated_at"] = datetime.now().isoformat()
        
        # Save updated data
        with open(agent_path, "w") as f:
            json.dump(agent_data, f, indent=2)
        
        return True
    
    def delete_agent(self, agent_id: str) -> bool:
        """
        Delete agent file
        
        Args:
            agent_id: Unique agent identifier
            
        Returns:
            True if deleted, False if not found
        """
        agent_path = self._get_agent_path(agent_id)
        
        if agent_path.exists():
            agent_path.unlink()
            return True
        
        return False

