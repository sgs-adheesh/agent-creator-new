from typing import Dict, Any, List
from config import settings
from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatOllama
from services.semantic_service import SemanticService


class ToolAnalyzer:
    """Analyzes prompts to determine required tools"""
    
    def __init__(self):
        # Initialize LLM
        if settings.use_openai and settings.openai_api_key:
            self.llm = ChatOpenAI(
                model=settings.openai_model,
                api_key=settings.openai_api_key,
                temperature=0.3
            )
        else:
            self.llm = ChatOllama(
                base_url=settings.ollama_base_url,
                model=settings.ollama_model,
                temperature=0.3
            )
        
        # Initialize semantic service for intelligent tool matching
        try:
            self.semantic_service = SemanticService()
            print("✅ Semantic search enabled for intelligent tool matching")
        except Exception as e:
            print(f"⚠️ Semantic service initialization failed: {e}")
            print("⚠️ Falling back to keyword-only matching")
            self.semantic_service = None
    
    def analyze_prompt(self, prompt: str, existing_tools: List[str]) -> Dict[str, Any]:
        """
        Analyze user prompt to detect required tools
        
        Args:
            prompt: User's agent description
            existing_tools: List of already available tool names
            
        Returns:
            Dictionary with proposed new tools and matched existing tools
        """
        analysis_prompt = f"""Analyze this agent prompt and identify what tools/APIs it needs.

User Prompt: {prompt}

Already Available Tools:
{', '.join(existing_tools) if existing_tools else 'None'}

Your task:
1. Identify ALL external services, APIs, or databases mentioned
2. For each service, **FIRST check the Tool Matching Rules below** to see if it matches an existing tool
3. Only propose new tools if NO existing tool matches
4. For new tools needed, provide a clear name and description

Tool Matching Rules:
- "database" or "query database" or "query the database" or "SQL database" or "relational database" or "find in database" → use "postgres_query" if available
- "PostgreSQL" or "Postgres" → use "postgres_query" if available
- "vector database" or "vector data" or "vector store" or "semantic search" or "embeddings" or "similarity search" → use "qdrant_search" if available
- "Qdrant" → use "qdrant_search" if available
- "Google Drive" → use "google_drive_api" if available
- "OneDrive" or "Microsoft OneDrive" → use "microsoft_onedrive_api" if available
- "Gmail" → use "gmail_api" if available
- "Google Analytics" → use "google_analytics_api" if available
- "Google Sheets" → use "google_sheets_api" if available
- "Stripe" → use "stripe_api" if available
- "PayPal" → use "paypal_api" if available
- "Salesforce" → use "salesforce_api" if available
- "AWS S3" or "S3" → use "aws_s3_api" if available
- "Dropbox" → use "dropbox_api" if available
- "QuickBooks" or "QBO" → use "qbo_query" if available

Matching Examples:
- "Help users query the database to find customer information" → matched_tools: ["postgres_query"]
- "Search vector data for similar documents" → matched_tools: ["qdrant_search"]
- "Query the database for invoices" → matched_tools: ["postgres_query"]
- "Find semantically similar items" → matched_tools: ["qdrant_search"]

Respond in JSON format:
{{
    "matched_tools": ["existing_tool_name1", "existing_tool_name2"],
    "new_tools_needed": [
        {{
            "name": "tool_name",
            "display_name": "Human Readable Name",
            "description": "What this tool does and what API/service it connects to",
            "api_type": "REST API|GraphQL|Database|SDK",
            "service": "Service/API name (e.g., Salesforce, Stripe)"
        }}
    ],
    "reasoning": "Brief explanation of tool requirements"
}}

Rules:
- Tool names must be lowercase_with_underscores
- Only suggest tools that are actually needed
- Don't suggest generic tools, be specific to services mentioned
- If no new tools needed, return empty array
- **CRITICAL**: ALWAYS check Tool Matching Rules first - if a match exists, use it!
- **CRITICAL**: "database" (without "vector") ALWAYS means postgres_query
- **CRITICAL**: "vector database" or "vector data" ALWAYS means qdrant_search
- Do NOT propose new database tools if postgres_query or qdrant_search match the requirements
"""

        try:
            response = self.llm.invoke(analysis_prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Debug logging
            print(f"\n📊 Tool Analyzer - Analyzing prompt: {prompt}")
            print(f"📊 Tool Analyzer - LLM Response: {response_text}")
            
            # Extract JSON
            import json
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            
            if json_match:
                analysis = json.loads(json_match.group())
                keyword_matched_tools = analysis.get("matched_tools", [])
                
                # Enhance with semantic search if available
                if self.semantic_service:
                    print("🔍 Enhancing with semantic search...")
                    
                    # Extract intent for better understanding
                    intent = self.semantic_service.extract_intent(prompt)
                    print(f"📊 Intent Analysis: {intent}")
                    
                    # Use semantic matching to enhance/validate keyword matches
                    enhanced_tools = self.semantic_service.enhance_tool_matching(
                        prompt=prompt,
                        keyword_matches=keyword_matched_tools,
                        available_tools=existing_tools
                    )
                    
                    matched_tools = enhanced_tools
                else:
                    matched_tools = keyword_matched_tools
                
                result = {
                    "success": True,
                    "matched_tools": matched_tools,
                    "new_tools_needed": analysis.get("new_tools_needed", []),
                    "reasoning": analysis.get("reasoning", ""),
                    "requires_user_confirmation": len(analysis.get("new_tools_needed", [])) > 0
                }
                print(f"📊 Tool Analyzer - Matched Tools: {result['matched_tools']}")
                print(f"📊 Tool Analyzer - New Tools Needed: {len(result['new_tools_needed'])} tools")
                return result
            else:
                return {
                    "success": False,
                    "error": "Failed to parse AI response",
                    "raw_response": response_text
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Tool analysis failed: {str(e)}"
            }
