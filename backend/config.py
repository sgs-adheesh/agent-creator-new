import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    # Ollama settings (legacy)
    ollama_base_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "gpt-oss")
    
    # OpenAI settings
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    use_openai: bool = os.getenv("USE_OPENAI", "false").lower() == "true"
    
    # Qdrant settings
    qdrant_url: str = os.getenv("QDRANT_URL", "https://0e1e9ae9-597a-4bc5-bafd-9773e2123a1f.us-east4-0.gcp.cloud.qdrant.io")
    qdrant_api_key: Optional[str] = os.getenv("QDRANT_API_KEY")
    qdrant_collection: str = os.getenv("QDRANT_COLLECTION", "icap_dev")
    
    # Postgres settings (kept for backward compatibility)
    postgres_host: Optional[str] = os.getenv("PG_HOST", "localhost")
    postgres_port: int = int(os.getenv("PG_PORT", "5432"))
    postgres_database: Optional[str] = os.getenv("PG_DATABASE")
    postgres_user: Optional[str] = os.getenv("PG_USER")
    postgres_password: Optional[str] = os.getenv("PG_PASSWORD")
    
    # Storage settings
    agents_storage_dir: str = os.getenv("AGENTS_STORAGE_DIR", "agents")
    tools_output_dir: str = os.getenv("TOOLS_OUTPUT_DIR", "tools")


settings = Settings()

