"""
API endpoint for SQL validation during agent editing
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import sys
import os

# Add parent directory to path to import validator
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.defensive_sql_validator import DefensiveSQLValidator, validate_sql

router = APIRouter(prefix="/api/sql", tags=["SQL Validation"])


class SQLValidationRequest(BaseModel):
    query: str
    auto_fix: bool = False


class SQLValidationResponse(BaseModel):
    is_valid: bool
    issues: list
    fixes_applied: list = []
    fixed_query: Optional[str] = None
    original_query: str


@router.post("/validate", response_model=SQLValidationResponse)
async def validate_sql_query(request: SQLValidationRequest):
    """
    Validate a SQL query against defensive SQL rules
    
    Args:
        request: SQLValidationRequest with query and auto_fix flag
        
    Returns:
        SQLValidationResponse with validation results
    """
    try:
        result = validate_sql(request.query, auto_fix=request.auto_fix)
        
        return SQLValidationResponse(
            is_valid=result['is_valid'],
            issues=result['issues'],
            fixes_applied=result.get('fixes_applied', []),
            fixed_query=result.get('fixed_query'),
            original_query=result['original_query']
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation error: {str(e)}")


@router.post("/auto-fix")
async def auto_fix_sql_query(request: SQLValidationRequest):
    """
    Automatically fix a SQL query to follow defensive SQL patterns
    
    Args:
        request: SQLValidationRequest with query
        
    Returns:
        Fixed query and list of fixes applied
    """
    try:
        result = validate_sql(request.query, auto_fix=True)
        
        return {
            "success": True,
            "original_query": result['original_query'],
            "fixed_query": result['fixed_query'],
            "fixes_applied": result['fixes_applied'],
            "remaining_issues": result['issues']
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Auto-fix error: {str(e)}")
