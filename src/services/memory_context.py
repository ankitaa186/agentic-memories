"""
Memory context retrieval for enhanced extraction.

This module provides functions to retrieve relevant existing memories
to provide context for the LLM during memory extraction.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import logging

from src.services.retrieval import search_memories
from src.schemas import TranscriptRequest, Message


logger = logging.getLogger("agentic_memories.memory_context")


def get_relevant_existing_memories(
    request: TranscriptRequest,
    max_memories: int = 10,
    similarity_threshold: float = 0.3
) -> List[Dict[str, Any]]:
    """
    Retrieve relevant existing memories for context during extraction.
    
    Args:
        request: The transcript request containing conversation history
        max_memories: Maximum number of existing memories to retrieve
        similarity_threshold: Minimum similarity score for relevance
        
    Returns:
        List of relevant existing memories with metadata
    """
    if not request.history:
        return []
    
    # Extract key topics from the conversation for context retrieval
    context_queries = _extract_context_queries(request.history)
    logger.info("[ctx.relevant] user_id=%s queries=%s", request.user_id, context_queries)
    
    all_memories = []
    seen_ids = set()
    
    # Search for memories related to each context query
    for query in context_queries:
        try:
            memories, _ = search_memories(
                user_id=request.user_id,
                query=query,
                filters={},
                limit=max_memories // len(context_queries) + 1,
                offset=0
            )
            logger.info("[ctx.search] user_id=%s q='%s' got=%s", request.user_id, query, len(memories))
            
            # Add unique memories that meet similarity threshold
            for memory in memories:
                if (memory["id"] not in seen_ids and 
                    memory.get("score", 0) >= similarity_threshold):
                    all_memories.append(memory)
                    seen_ids.add(memory["id"])
                    
        except Exception as e:
            logger.warning(f"[ctx.search.error] q='{query}' error={e}")
            continue
    
    # Sort by relevance score and return top memories
    all_memories.sort(key=lambda x: x.get("score", 0), reverse=True)
    logger.info("[ctx.result] user_id=%s returned=%s", request.user_id, len(all_memories[:max_memories]))
    return all_memories[:max_memories]


def _extract_context_queries(history: List[Message]) -> List[str]:
    """
    Extract context queries from conversation history for memory retrieval.
    
    Args:
        history: List of conversation messages
        
    Returns:
        List of context queries for memory search
    """
    queries = []
    
    # Get user messages from the conversation
    user_messages = [m for m in history if m.role == "user" and m.content.strip()]
    
    if not user_messages:
        return []
    
    # Extract key topics from recent user messages
    for message in user_messages[-3:]:  # Last 3 user messages
        content = message.content.strip()
        
        # Extract potential topics/keywords
        topics = _extract_topics_from_text(content)
        queries.extend(topics)
    
    # Add a general query for recent memories
    queries.append("recent memories")
    
    # Remove duplicates while preserving order
    seen = set()
    unique_queries = []
    for query in queries:
        if query not in seen:
            unique_queries.append(query)
            seen.add(query)
    
    return unique_queries


def _extract_topics_from_text(text: str) -> List[str]:
    """
    Extract potential topics/keywords from text for memory search.
    
    Args:
        text: Input text to extract topics from
        
    Returns:
        List of potential topic queries
    """
    import re
    
    # Convert to lowercase for processing
    text_lower = text.lower()
    
    topics = []
    
    # Extract noun phrases and important words
    # Look for patterns like "I love X", "I'm working on X", "I need to X"
    patterns = [
        r"i love (\w+)",
        r"i like (\w+)",
        r"i prefer (\w+)",
        r"i'm working on (\w+)",
        r"i need to (\w+)",
        r"i want to (\w+)",
        r"i'm planning (\w+)",
        r"i'm learning (\w+)",
        r"i'm studying (\w+)",
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text_lower)
        topics.extend(matches)
    
    # Extract project-related terms
    project_terms = ["project", "work", "job", "career", "business", "startup"]
    for term in project_terms:
        if term in text_lower:
            topics.append(term)
    
    # Extract personal preference terms
    preference_terms = ["book", "movie", "music", "food", "hobby", "sport", "exercise"]
    for term in preference_terms:
        if term in text_lower:
            topics.append(term)
    
    # Extract relationship terms
    relationship_terms = ["friend", "family", "partner", "colleague", "team"]
    for term in relationship_terms:
        if term in text_lower:
            topics.append(term)
    
    # Extract learning terms
    learning_terms = ["learn", "study", "course", "skill", "language", "programming"]
    for term in learning_terms:
        if term in text_lower:
            topics.append(term)
    
    # If no specific topics found, use the full text as a query
    if not topics:
        # Take first few words as a query
        words = text.split()[:5]
        topics.append(" ".join(words))
    
    return topics


def format_memories_for_llm_context(memories: List[Dict[str, Any]]) -> str:
    """
    Format existing memories for inclusion in LLM context.
    
    Args:
        memories: List of existing memories
        
    Returns:
        Formatted string for LLM context
    """
    if not memories:
        return "No existing memories found."
    
    formatted = ["Existing relevant memories:"]
    
    for i, memory in enumerate(memories, 1):
        content = memory.get("content", "")
        layer = memory.get("metadata", {}).get("layer", "unknown")
        memory_type = memory.get("metadata", {}).get("type", "unknown")
        tags = memory.get("metadata", {}).get("tags", [])
        
        # Format tags
        tags_str = ", ".join(tags) if tags else "no tags"
        
        formatted.append(
            f"{i}. [{layer}/{memory_type}] {content} (tags: {tags_str})"
        )
    
    return "\n".join(formatted)


def get_memory_summary_for_user(user_id: str, limit: int = 5) -> str:
    """
    Get a summary of recent memories for a user.
    
    Args:
        user_id: User ID to get memories for
        limit: Maximum number of memories to include
        
    Returns:
        Formatted summary string
    """
    try:
        # Get recent memories across all layers
        memories, _ = search_memories(
            user_id=user_id,
            query="recent memories",
            filters={},
            limit=limit,
            offset=0
        )
        
        if not memories:
            return "No recent memories found."
        
        summary_parts = [f"Recent memories for user {user_id}:"]
        
        for i, memory in enumerate(memories, 1):
            content = memory.get("content", "")
            layer = memory.get("metadata", {}).get("layer", "unknown")
            summary_parts.append(f"{i}. [{layer}] {content}")
        
        return "\n".join(summary_parts)
        
    except Exception as e:
        logger.warning(f"Failed to get memory summary for user {user_id}: {e}")
        return "Unable to retrieve recent memories."
