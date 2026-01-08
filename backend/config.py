import os
import logging
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


def validate_environment():
    """
    Validate required environment variables and log warnings for missing optional ones
    """
    warnings = []
    errors = []
    
    # Required for PostgreSQL operations
    if not os.getenv("PG_DATABASE"):
        warnings.append("PG_DATABASE not set - PostgreSQL features will be unavailable")
    if not os.getenv("PG_USER"):
        warnings.append("PG_USER not set - PostgreSQL features will be unavailable")
    if not os.getenv("PG_PASSWORD"):
        warnings.append("PG_PASSWORD not set - PostgreSQL features will be unavailable")
    
    # Required for OpenAI if USE_OPENAI=true
    if os.getenv("USE_OPENAI", "false").lower() == "true":
        if not os.getenv("OPENAI_API_KEY"):
            errors.append("OPENAI_API_KEY is required when USE_OPENAI=true")
    
    # Qdrant settings (optional but recommended)
    if not os.getenv("QDRANT_API_KEY"):
        warnings.append("QDRANT_API_KEY not set - Qdrant features may be unavailable")
    
    # Log warnings
    for warning in warnings:
        logger.warning(f"⚠️ {warning}")
    
    # Log errors
    for error in errors:
        logger.error(f"❌ {error}")
    
    # Return validation status
    return len(errors) == 0, errors, warnings


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

# Validate environment on import
_is_valid, _errors, _warnings = validate_environment()
if not _is_valid:
    logger.error("Environment validation failed. Please fix the errors above.")
