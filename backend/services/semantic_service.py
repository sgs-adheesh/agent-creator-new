"""Semantic Search Service for intelligent prompt understanding
Uses embeddings to find similar tools and understand user intent
"""
from typing import Dict, Any, List, Tuple
import numpy as np
import warnings
import logging
import os
from config import settings
from langchain_openai import OpenAIEmbeddings
from langchain_community.embeddings import OllamaEmbeddings

# Suppress tiktoken encoding warnings (expected for new embedding models)
warnings.filterwarnings('ignore', message='.*model not found.*')
warnings.filterwarnings('ignore', category=UserWarning, module='tiktoken_ext.openai_public')

# Also suppress at logger level
logging.getLogger('tiktoken_ext.openai_public').setLevel(logging.ERROR)
os.environ['TIKTOKEN_QUIET'] = '1'


class SemanticService:
    """Provides semantic search capabilities using embeddings"""
    
    def __init__(self):
        # Initialize embedding model
        if settings.use_openai and settings.openai_api_key:
            self.embeddings = OpenAIEmbeddings(
                model="text-embedding-3-small",
                api_key=settings.openai_api_key,
                show_progress_bar=False
            )
        else:
            self.embeddings = OllamaEmbeddings(
                base_url=settings.ollama_base_url,
                model="nomic-embed-text"
            )
        
        # Tool descriptions for semantic matching
        self.tool_descriptions = {
            "postgres_query": "Query PostgreSQL database for structured data like customer records, invoices, orders, transactions, user accounts, business data",
            "qdrant_search": "Search vector database for semantic similarity, embeddings, similar documents, related items, nearest neighbors, AI-powered search",
            "gmail_api": "Send emails, read inbox, manage Gmail messages, email automation, SMTP operations",
            "stripe_api": "Process payments, handle subscriptions, manage billing, payment gateway integration, checkout flows",
            "paypal_api": "Accept PayPal payments, manage transactions, process refunds, PayPal checkout",
            "salesforce_api": "Manage CRM data, customer relationships, sales leads, opportunities, contacts, accounts",
            "aws_s3_api": "Upload files to S3, download objects, manage cloud storage, file buckets, AWS storage",
            "dropbox_api": "Upload files to Dropbox, sync files, cloud file storage, file sharing",
            "google_drive_api": "Upload files to Google Drive, manage documents, share files, Google Workspace integration",
            "microsoft_onedrive_api": "Upload files to OneDrive, Microsoft cloud storage, Office 365 file management",
            "google_analytics_api": "Fetch website analytics, track user behavior, traffic data, conversion metrics",
            "google_sheets_api": "Read/write Google Sheets, spreadsheet automation, data reports, tabular data",
            "qbo_connector": "Query QuickBooks data, accounting information, financial records, invoices, expenses"
        }
        
        # Pre-compute tool embeddings for faster matching
        self._tool_embeddings_cache = None
    
    def _get_tool_embeddings(self) -> Dict[str, List[float]]:
        """Get or compute embeddings for all tools"""
        if self._tool_embeddings_cache is None:
            print("🔄 Computing tool embeddings...")
            self._tool_embeddings_cache = {}
            
            for tool_name, description in self.tool_descriptions.items():
                embedding = self.embeddings.embed_query(description)
                self._tool_embeddings_cache[tool_name] = embedding
            
            print(f"✅ Cached embeddings for {len(self._tool_embeddings_cache)} tools")
        
        return self._tool_embeddings_cache
    
    def compute_similarity(self, text1: str, text2: str) -> float:
        """
        Compute cosine similarity between two texts
        
        Returns:
            Similarity score between 0 and 1
        """
        emb1 = np.array(self.embeddings.embed_query(text1))
        emb2 = np.array(self.embeddings.embed_query(text2))
        
        # Cosine similarity
        similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
        return float(similarity)
    
    def find_similar_tools(
        self, 
        prompt: str, 
        available_tools: List[str],
        threshold: float = 0.5,
        top_k: int = 5
    ) -> List[Tuple[str, float]]:
        """
        Find tools semantically similar to the prompt
        
        Args:
            prompt: User's input text
            available_tools: List of tool names to search within
            threshold: Minimum similarity score (0-1)
            top_k: Maximum number of tools to return
            
        Returns:
            List of (tool_name, similarity_score) tuples, sorted by score
        """
        # Get prompt embedding
        prompt_embedding = np.array(self.embeddings.embed_query(prompt))
        
        # Get tool embeddings
        tool_embeddings = self._get_tool_embeddings()
        
        # Compute similarities
        similarities = []
        for tool_name in available_tools:
            if tool_name in tool_embeddings:
                tool_emb = np.array(tool_embeddings[tool_name])
                
                # Cosine similarity
                similarity = np.dot(prompt_embedding, tool_emb) / (
                    np.linalg.norm(prompt_embedding) * np.linalg.norm(tool_emb)
                )
                
                if similarity >= threshold:
                    similarities.append((tool_name, float(similarity)))
        
        # Sort by similarity (highest first)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_k]
    
    def extract_intent(self, prompt: str) -> Dict[str, Any]:
        """
        Extract user intent from prompt using semantic understanding
        
        Returns:
            Dictionary with intent classification:
            {
                "primary_action": "query|create|update|search|process|analyze",
                "data_type": "customer|invoice|document|payment|email|file",
                "urgency": "high|medium|low",
                "confidence": 0.0-1.0
            }
        """
        prompt_lower = prompt.lower()
        
        # Define intent patterns with their keywords
        action_patterns = {
            "query": ["find", "get", "retrieve", "fetch", "search", "lookup", "show", "list"],
            "create": ["create", "add", "insert", "generate", "make", "build"],
            "update": ["update", "modify", "change", "edit", "revise"],
            "delete": ["delete", "remove", "clear", "erase"],
            "analyze": ["analyze", "report", "summarize", "aggregate", "calculate"],
            "process": ["process", "handle", "execute", "run", "perform"]
        }
        
        data_patterns = {
            "customer": ["customer", "client", "user", "account holder"],
            "invoice": ["invoice", "bill", "receipt", "payment record"],
            "document": ["document", "file", "pdf", "attachment"],
            "payment": ["payment", "transaction", "charge", "refund"],
            "email": ["email", "message", "mail", "notification"],
            "analytics": ["analytics", "metrics", "statistics", "traffic"]
        }
        
        # Find primary action
        primary_action = "query"  # default
        max_action_score = 0
        for action, keywords in action_patterns.items():
            score = sum(1 for kw in keywords if kw in prompt_lower)
            if score > max_action_score:
                max_action_score = score
                primary_action = action
        
        # Find data type
        data_type = "general"
        max_data_score = 0
        for dtype, keywords in data_patterns.items():
            score = sum(1 for kw in keywords if kw in prompt_lower)
            if score > max_data_score:
                max_data_score = score
                data_type = dtype
        
        # Estimate confidence based on keyword matches
        total_words = len(prompt_lower.split())
        confidence = min((max_action_score + max_data_score) / max(total_words * 0.3, 1), 1.0)
        
        return {
            "primary_action": primary_action,
            "data_type": data_type,
            "confidence": round(confidence, 2),
            "requires_database": any(kw in prompt_lower for kw in ["database", "query", "find", "customer", "invoice"]),
            "requires_vector_search": any(kw in prompt_lower for kw in ["similar", "semantic", "vector", "embeddings"])
        }
    
    def enhance_tool_matching(
        self,
        prompt: str,
        keyword_matches: List[str],
        available_tools: List[str]
    ) -> List[str]:
        """
        Enhance keyword-based tool matching with semantic search
        
        Args:
            prompt: User's input
            keyword_matches: Tools matched by keyword rules
            available_tools: All available tools
            
        Returns:
            Enhanced list of matched tools
        """
        # If keyword matching found tools, use those as primary
        if keyword_matches:
            matched_tools = set(keyword_matches)
        else:
            matched_tools = set()
        
        # Add semantically similar tools
        semantic_matches = self.find_similar_tools(
            prompt, 
            available_tools,
            threshold=0.6,  # High threshold for quality
            top_k=3
        )
        
        # Add high-confidence semantic matches
        for tool_name, score in semantic_matches:
            if score >= 0.7:  # Very confident
                matched_tools.add(tool_name)
                print(f"🎯 Semantic match: {tool_name} (score: {score:.2f})")
        
        return list(matched_tools)

    def find_similar_templates(
        self, 
        prompt: str, 
        templates: List[Dict[str, Any]],
        threshold: float = 0.6,
        top_k: int = 3
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Find agent templates semantically similar to the prompt
        
        Args:
            prompt: User's input text
            templates: List of template dictionaries
            threshold: Minimum similarity score (0-1)
            top_k: Maximum number of templates to return
            
        Returns:
            List of (template, similarity_score) tuples, sorted by score
        """
        if not templates:
            return []
            
        # Get prompt embedding
        prompt_embedding = np.array(self.embeddings.embed_query(prompt))
        
        results = []
        for template in templates:
            # Create a rich text representation of the template for embedding
            # Combine name, description, and prompt for best matching
            template_text = f"{template.get('name', '')} {template.get('description', '')} {template.get('template', {}).get('prompt', '')}"
            
            # Compute embedding for this template
            # Note: For production, these should be cached, but for <20 templates calculating on fly is acceptable
            template_embedding = np.array(self.embeddings.embed_query(template_text))
            
            # Cosine similarity
            similarity = np.dot(prompt_embedding, template_embedding) / (
                np.linalg.norm(prompt_embedding) * np.linalg.norm(template_embedding)
            )
            
            if similarity >= threshold:
                results.append((template, float(similarity)))
        
        # Sort by similarity (highest first)
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results[:top_k]
