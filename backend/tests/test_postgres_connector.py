"""
Unit tests for PostgreSQL connector
"""
import pytest
from unittest.mock import Mock, patch
from tools.postgres_connector import PostgresConnector


class TestPostgresConnector:
    """Test PostgreSQL connector functionality"""
    
    @pytest.fixture
    def connector(self):
        """Create a connector instance for testing"""
        return PostgresConnector()
    
    def test_initialization(self, connector):
        """Test that connector initializes without errors"""
        assert connector is not None
        assert connector.name == "postgres_query"
    
    def test_execute_empty_query(self, connector):
        """Test that empty queries return error"""
        result = connector.execute(query="")
        assert result["success"] is False
        assert "No query provided" in result["error"]
    
    @patch('tools.postgres_connector.PostgresConnector._get_connection')
    def test_execute_dangerous_query(self, mock_conn, connector):
        """Test that dangerous queries are rejected"""
        result = connector.execute(query="DROP TABLE users")
        # Should fail validation before execution
        assert result["success"] is False
    
    def test_get_table_schema_empty_table(self, connector):
        """Test schema retrieval with empty table name"""
        # This should return schema info or error gracefully
        result = connector.get_table_schema(table_name="")
        assert isinstance(result, dict)
