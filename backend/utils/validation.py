"""
Input validation utilities
"""
import re
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, ValidationError


class ValidationError(Exception):
    """Custom validation error"""
    pass


def validate_sql_query(query: str) -> tuple[bool, Optional[str]]:
    """
    Validate SQL query for safety
    
    Args:
        query: SQL query string
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not query or not query.strip():
        return False, "Query cannot be empty"
    
    query_upper = query.upper().strip()
    
    # Check for dangerous operations
    dangerous_ops = ['DROP', 'TRUNCATE', 'ALTER', 'CREATE', 'GRANT', 'REVOKE']
    for op in dangerous_ops:
        if op in query_upper:
            return False, f"Dangerous operation '{op}' is not allowed"
    
    # Check for SQL injection patterns
    sql_injection_patterns = [
        r';\s*(DROP|DELETE|UPDATE|INSERT|ALTER|CREATE)',
        r'--',
        r'/\*.*\*/',
        r'UNION.*SELECT',
        r'EXEC\s*\(',
        r'EXECUTE\s*\(',
    ]
    
    for pattern in sql_injection_patterns:
        if re.search(pattern, query_upper, re.IGNORECASE | re.DOTALL):
            return False, f"Potentially unsafe SQL pattern detected"
    
    return True, None


def validate_agent_name(name: str) -> tuple[bool, Optional[str]]:
    """
    Validate agent name
    
    Args:
        name: Agent name string
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not name or not name.strip():
        return False, "Agent name cannot be empty"
    
    if len(name) > 100:
        return False, "Agent name must be 100 characters or less"
    
    # Check for invalid characters
    invalid_chars = ['<', '>', '|', '&', ';', '`', '$', '(', ')']
    for char in invalid_chars:
        if char in name:
            return False, f"Agent name contains invalid character: {char}"
    
    return True, None


def validate_uuid(uuid_string: str) -> tuple[bool, Optional[str]]:
    """
    Validate UUID format
    
    Args:
        uuid_string: UUID string to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    uuid_pattern = re.compile(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
        re.IGNORECASE
    )
    
    if not uuid_pattern.match(uuid_string):
        return False, "Invalid UUID format"
    
    return True, None


def sanitize_string(input_string: str, max_length: int = 1000) -> str:
    """
    Sanitize string input
    
    Args:
        input_string: Input string to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Sanitized string
    """
    if not input_string:
        return ""
    
    # Remove null bytes
    sanitized = input_string.replace('\x00', '')
    
    # Truncate if too long
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length]
    
    return sanitized.strip()


def validate_workflow_config(config: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Validate workflow configuration
    
    Args:
        config: Workflow configuration dictionary
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(config, dict):
        return False, "Workflow config must be a dictionary"
    
    # Validate trigger_type
    valid_trigger_types = [
        "text_query", "date_range", "month_year", 
        "year", "conditions", "scheduled"
    ]
    
    trigger_type = config.get("trigger_type")
    if trigger_type and trigger_type not in valid_trigger_types:
        return False, f"Invalid trigger_type: {trigger_type}. Must be one of {valid_trigger_types}"
    
    # Validate output_format
    valid_output_formats = ["text", "csv", "json", "table"]
    output_format = config.get("output_format", "text")
    if output_format not in valid_output_formats:
        return False, f"Invalid output_format: {output_format}. Must be one of {valid_output_formats}"
    
    # Validate input_fields if present
    input_fields = config.get("input_fields", [])
    if not isinstance(input_fields, list):
        return False, "input_fields must be a list"
    
    return True, None
