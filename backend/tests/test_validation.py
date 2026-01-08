"""
Unit tests for validation utilities
"""
import pytest
from utils.validation import (
    validate_sql_query,
    validate_agent_name,
    validate_uuid,
    sanitize_string,
    validate_workflow_config
)


class TestSQLValidation:
    """Test SQL query validation"""
    
    def test_valid_select_query(self):
        """Test that valid SELECT queries pass validation"""
        query = "SELECT * FROM users WHERE id = 1"
        is_valid, error = validate_sql_query(query)
        assert is_valid is True
        assert error is None
    
    def test_empty_query(self):
        """Test that empty queries fail validation"""
        is_valid, error = validate_sql_query("")
        assert is_valid is False
        assert error is not None
    
    def test_dangerous_drop(self):
        """Test that DROP statements are rejected"""
        query = "DROP TABLE users"
        is_valid, error = validate_sql_query(query)
        assert is_valid is False
        assert "DROP" in error
    
    def test_sql_injection_pattern(self):
        """Test that SQL injection patterns are detected"""
        query = "SELECT * FROM users; DROP TABLE users--"
        is_valid, error = validate_sql_query(query)
        assert is_valid is False


class TestAgentNameValidation:
    """Test agent name validation"""
    
    def test_valid_name(self):
        """Test that valid names pass validation"""
        is_valid, error = validate_agent_name("My Agent")
        assert is_valid is True
        assert error is None
    
    def test_empty_name(self):
        """Test that empty names fail validation"""
        is_valid, error = validate_agent_name("")
        assert is_valid is False
        assert error is not None
    
    def test_too_long_name(self):
        """Test that names over 100 characters fail"""
        long_name = "a" * 101
        is_valid, error = validate_agent_name(long_name)
        assert is_valid is False
    
    def test_invalid_characters(self):
        """Test that names with invalid characters fail"""
        is_valid, error = validate_agent_name("Agent<script>")
        assert is_valid is False


class TestUUIDValidation:
    """Test UUID validation"""
    
    def test_valid_uuid(self):
        """Test that valid UUIDs pass validation"""
        uuid = "123e4567-e89b-12d3-a456-426614174000"
        is_valid, error = validate_uuid(uuid)
        assert is_valid is True
        assert error is None
    
    def test_invalid_uuid(self):
        """Test that invalid UUIDs fail validation"""
        is_valid, error = validate_uuid("not-a-uuid")
        assert is_valid is False
        assert error is not None


class TestSanitizeString:
    """Test string sanitization"""
    
    def test_sanitize_null_bytes(self):
        """Test that null bytes are removed"""
        result = sanitize_string("test\x00string")
        assert "\x00" not in result
    
    def test_truncate_long_string(self):
        """Test that long strings are truncated"""
        long_string = "a" * 2000
        result = sanitize_string(long_string, max_length=1000)
        assert len(result) == 1000


class TestWorkflowConfigValidation:
    """Test workflow configuration validation"""
    
    def test_valid_config(self):
        """Test that valid configs pass validation"""
        config = {
            "trigger_type": "text_query",
            "output_format": "table",
            "input_fields": []
        }
        is_valid, error = validate_workflow_config(config)
        assert is_valid is True
        assert error is None
    
    def test_invalid_trigger_type(self):
        """Test that invalid trigger types fail"""
        config = {
            "trigger_type": "invalid_type",
            "output_format": "table"
        }
        is_valid, error = validate_workflow_config(config)
        assert is_valid is False
    
    def test_invalid_output_format(self):
        """Test that invalid output formats fail"""
        config = {
            "trigger_type": "text_query",
            "output_format": "invalid_format"
        }
        is_valid, error = validate_workflow_config(config)
        assert is_valid is False
