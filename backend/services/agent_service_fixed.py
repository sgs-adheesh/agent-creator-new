# This is just the _generate_system_prompt method that needs to replace lines 958-1395
# Will be used to manually fix the broken file

def _generate_system_prompt(self, prompt: str, agent_tools: List, selected_tool_names: List[str]) -> str:
    """
    Generate system prompt for the agent based on user's purpose
    
    Args:
        prompt: User prompt
        agent_tools: Available tools
        selected_tool_names: Names of selected tools
        
    Returns:
        System prompt string
    """
    tool_descriptions = "\n".join([f"- {tool.name}: {tool.description}" for tool in agent_tools])
    
    has_postgres = any(tool_name in ['postgres_query', 'postgres_inspect_schema'] for tool_name in selected_tool_names)
    
    # 🎯🎯🎯 USER PROMPT IS THE ABSOLUTE PRIORITY - Everything else is secondary support
    prompt_lower = prompt.lower()
    
    # Detect specific agent types for specialized guidance ONLY
    is_duplicate_finder = any(keyword in prompt_lower for keyword in ['duplicate', 'duplicates', 'repeated', 'same invoice', 'same vendor'])
    is_anomaly_detector = any(keyword in prompt_lower for keyword in ['anomaly', 'unusual', 'outlier', 'fraud', 'suspicious', 'abnormal'])
    is_comparison = any(keyword in prompt_lower for keyword in ['compare', 'comparison', 'difference', 'vs', 'versus', 'gap', 'variance'])
    is_trend_analysis = any(keyword in prompt_lower for keyword in ['trend', 'pattern', 'growth', 'decline', 'over time', 'historical'])
    
    # ============================================================
    # SYSTEM PROMPT: USER'S PURPOSE DOMINATES EVERYTHING
    # ============================================================
    system_prompt = f"""YOUR TASK:
{prompt}

You MUST accomplish the above task exactly as described. Every action must directly serve this goal.
"""
    
    # Add BRIEF specialized guidance based on detected type (ONLY if detected)
    if is_duplicate_finder:
        system_prompt += """\nFor duplicate detection: Explicitly identify WHICH records are duplicates and WHY (same vendor? amount? date?). Group them and count the groups.\n"""
    elif is_anomaly_detector:
        system_prompt += """\nFor anomaly detection: Identify WHICH records are unusual and WHY (amount outlier? date mismatch? suspicious pattern?). Provide specific values.\n"""
    elif is_comparison:
        system_prompt += """\nFor comparison: State differences explicitly with actual values. Show what changed, by how much, and what it means.\n"""
    elif is_trend_analysis:
        system_prompt += """\nFor trend analysis: Describe the pattern direction, quantify changes, identify inflection points, and explain implications.\n"""
    
    # Tools list
    system_prompt += f"""\nAVAILABLE TOOLS:\n{tool_descriptions}\n"""
    
    # MINIMAL PostgreSQL technical notes (ONLY if postgres tools exist)
    if has_postgres:
        system_prompt += """\nDATABASE USAGE:\n• ALWAYS call postgres_inspect_schema('') first to list all tables\n• Then call postgres_inspect_schema('table_name') for each table you need\n• Use ONLY actual column names from inspected schemas (never guess)\n• For JSONB columns, use: column_name->>'value'\n• Never expose ID columns (invoice_id, vendor_id) - use business fields only\n• For date filtering: Use >= and <= with MM/DD/YYYY strings or LIKE patterns\n"""
    
    return system_prompt
