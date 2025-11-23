#!/usr/bin/env python3
"""
Chat Handler Capability
Implements comms.chat capability for handling interactive chat messages from console.
Transport-agnostic - just receives request and returns response.
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class ChatHandler:
    """
    Chat Handler - Implements comms.chat capability
    
    Handles interactive chat messages from console.
    Checks agent busy status before processing.
    Generates response using agent's LLM.
    Returns transport-agnostic result.
    """
    
    def __init__(self, agent_instance):
        """
        Initialize ChatHandler with agent instance.
        
        Args:
            agent_instance: Agent instance (must have BaseAgent methods/attributes)
        """
        self.agent = agent_instance
        self.name = agent_instance.name if hasattr(agent_instance, 'name') else 'unknown'
    
    def _should_retrieve_memories(self, message: str) -> bool:
        """
        Determine if memory retrieval is needed for this query.
        
        Args:
            message: User's chat message
            
        Returns:
            True if memories should be retrieved, False otherwise
        """
        message_lower = message.lower().strip()
        
        # Skip for very short messages (likely greetings)
        if len(message_lower) < 10:
            return False
        
        # Skip for simple greetings
        simple_greetings = ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening']
        if message_lower in simple_greetings:
            return False
        
        # Skip for simple commands without context needs
        simple_commands = ['help', 'status', 'version', 'who are you']
        if message_lower in simple_commands:
            return False
        
        # Retrieve for questions (contains question words or ends with ?)
        question_words = ['what', 'when', 'where', 'who', 'why', 'how', 'which', 'can you', 'tell me', 'explain']
        if any(word in message_lower for word in question_words) or message_lower.endswith('?'):
            return True
        
        # Retrieve for longer messages (likely need context)
        if len(message_lower) > 30:
            return True
        
        # Default: retrieve for most messages
        return True
    
    def _format_memory(self, mem: Dict[str, Any], index: int) -> str:
        """
        Format a memory for inclusion in the prompt.
        Extracts key information from structured content.
        
        Args:
            mem: Memory dictionary
            index: Memory index (for attribution)
            
        Returns:
            Formatted memory string
        """
        mem_id = mem.get('id', 'unknown')
        mem_content = mem.get('content', {})
        
        # Parse content if it's a JSON string
        if isinstance(mem_content, str):
            try:
                mem_content = json.loads(mem_content) if mem_content else {}
            except json.JSONDecodeError:
                pass
        
        # Extract memory kind from content['action'] or tags
        mem_kind = 'memory'
        if isinstance(mem_content, dict) and 'action' in mem_content:
            mem_kind = mem_content['action']
        else:
            # Try to extract from tags
            tags = mem.get('tags', [])
            if tags:
                # Find first tag that's not a pid/ecid/agent tag
                for tag in tags:
                    if ':' not in tag:
                        mem_kind = tag
                        break
        
        # Extract key information from structured content
        summary_parts = []
        
        if isinstance(mem_content, dict):
            # Extract common fields (action is the memory kind)
            if 'action' in mem_content:
                summary_parts.append(f"Action: {mem_content['action']}")
            if 'result' in mem_content:
                result = mem_content['result']
                if isinstance(result, dict):
                    # Extract key fields from result dict
                    result_summary = []
                    if 'task_id' in result:
                        result_summary.append(f"task_id={result['task_id']}")
                    if 'status' in result:
                        result_summary.append(f"status={result['status']}")
                    if 'decision' in result:
                        result_summary.append(f"decision={result['decision']}")
                    if 'description' in result:
                        result_summary.append(f"desc={result['description'][:50]}")
                    if result_summary:
                        summary_parts.append(f"Result: {', '.join(result_summary)}")
                    else:
                        summary_parts.append(f"Result: {json.dumps(result)[:100]}")
                else:
                    summary_parts.append(f"Result: {str(result)[:100]}")
            if 'task_id' in mem_content:
                summary_parts.append(f"Task: {mem_content['task_id']}")
            if 'description' in mem_content:
                summary_parts.append(f"Description: {mem_content['description'][:100]}")
            
            # If no structured fields found, use string representation
            if not summary_parts:
                content_str = json.dumps(mem_content)[:150]
                summary_parts.append(content_str)
        else:
            # Non-dict content
            summary_parts.append(str(mem_content)[:150])
        
        summary = " | ".join(summary_parts)
        
        # Format with ID for attribution (use first 8 chars of UUID)
        mem_id_short = mem_id[:8] if len(mem_id) > 8 else mem_id
        return f"[Memory {index} (ID: {mem_id_short}...)] {mem_kind}: {summary}"
    
    def _filter_memories_by_relevance(self, memories: List[Dict[str, Any]], min_relevance: float = 0.6) -> List[Dict[str, Any]]:
        """
        Filter memories by relevance score if available.
        LanceDB search may include _distance field (lower is better).
        Convert distance to similarity score (1 - normalized_distance).
        
        Args:
            memories: List of memory dictionaries
            min_relevance: Minimum relevance score (0.0-1.0)
            
        Returns:
            Filtered list of memories
        """
        if not memories:
            return []
        
        # Check if memories have distance/similarity scores
        # LanceDB search() returns _distance column (lower distance = higher similarity)
        filtered = []
        for mem in memories:
            # Check for distance field (LanceDB convention)
            distance = mem.get('_distance')
            if distance is not None:
                # Convert distance to similarity (assuming max distance ~2.0 for normalized vectors)
                # For cosine distance: similarity = 1 - distance (if distance is normalized)
                # For L2 distance: we need to normalize, but for now use simple conversion
                similarity = 1.0 - min(distance, 1.0)  # Cap distance at 1.0
                
                if similarity >= min_relevance:
                    mem['_similarity'] = similarity
                    filtered.append(mem)
                else:
                    logger.debug(f"{self.name} filtered memory {mem.get('id', 'unknown')} (similarity: {similarity:.2f} < {min_relevance})")
            else:
                # No distance available, include all memories
                filtered.append(mem)
        
        return filtered if filtered else memories  # Return all if no filtering possible
    
    async def handle(self, message: str, session_id: str) -> Dict[str, Any]:
        """
        Handle chat message - checks busy status and generates response.
        
        Implements the comms.chat capability.
        
        Args:
            message: Chat message text from user
            session_id: Console session identifier
            
        Returns:
            Dictionary containing:
            - response_text: Agent's response text
            - agent_name: Name of responding agent
            - timestamp: ISO timestamp of response
            - status: "available" or "busy"
        """
        try:
            # Check agent busy status
            agent_status = getattr(self.agent, 'status', 'online')
            current_task = getattr(self.agent, 'current_task', None)
            
            # Agent is available if status is "Available" or "online" AND no current task
            # Agent is busy if status is "Active-Non-Blocking" or "Active-Blocking" OR has current_task
            is_available = (agent_status == "Available" or agent_status == "online") and current_task is None
            
            if not is_available:
                busy_message = f"[{self.name} is currently busy with task {current_task}. Please try again later.]"
                logger.info(f"{self.name} received chat request but is busy (status={agent_status}, task={current_task})")
                return {
                    "response_text": busy_message,
                    "agent_name": self.name,
                    "timestamp": datetime.utcnow().isoformat(),
                    "status": "busy"
                }
            
            # Agent is available - generate response
            logger.info(f"{self.name} processing chat message: {message[:100]}...")
            
            # Conditionally retrieve memories based on query classification
            relevant_memories = []
            if self._should_retrieve_memories(message):
                try:
                    if hasattr(self.agent, 'retrieve_memories'):
                        # Determine memory count based on query complexity
                        # Use 2-3 for most queries, 5 for complex queries
                        query_length = len(message.strip())
                        memory_count = 5 if query_length > 100 else 3
                        
                        # Search agent's LanceDB memories using the message as query
                        memories = await self.agent.retrieve_memories(
                            query=message,
                            k=memory_count,
                            ns="role"  # Agent-level memories
                        )
                        
                        if memories:
                            # Filter by relevance threshold
                            relevant_memories = self._filter_memories_by_relevance(memories, min_relevance=0.6)
                            logger.info(f"{self.name} found {len(relevant_memories)} relevant memories (from {len(memories)} candidates) for chat query")
                        else:
                            logger.debug(f"{self.name} no memories found for query")
                except Exception as e:
                    logger.warning(f"{self.name} failed to retrieve memories: {e}", exc_info=True)
                    relevant_memories = []
            else:
                logger.debug(f"{self.name} skipping memory retrieval for simple query")
            
            # Retrieve role context from memory
            role_context = None
            if hasattr(self.agent, 'retrieve_memories'):
                try:
                    # Search for role_identity memory
                    role_memories = await self.agent.retrieve_memories(
                        query="role identity who am I",
                        k=5,
                        ns="role"
                    )
                    
                    # Extract role_context from memory payload
                    # Memory structure: mem['content']['action'] == 'role_identity'
                    #                   mem['content']['result']['role_context']
                    if role_memories:
                        for mem in role_memories:
                            content = mem.get('content', {})
                            if isinstance(content, dict):
                                action = content.get('action', '')
                                result = content.get('result', {})
                                if action == 'role_identity' and isinstance(result, dict):
                                    role_context = result.get('role_context')
                                    if role_context:
                                        logger.debug(f"{self.name}: Retrieved role context from memory")
                                        break
                except Exception as e:
                    logger.debug(f"{self.name}: Failed to retrieve role context from memory: {e}")
            
            # Fallback to simple prompt if role context not found
            if not role_context:
                agent_role = getattr(self.agent, 'agent_type', 'agent')
                role_context = f"You are {self.name}, a {agent_role} agent in the SquadOps system.\n\n"
            
            # Format memories for prompt with attribution
            memory_context = ""
            if relevant_memories:
                memory_context = "\n\nRelevant memories from my past experiences:\n"
                for i, mem in enumerate(relevant_memories, 1):
                    formatted_memory = self._format_memory(mem, i)
                    memory_context += formatted_memory + "\n"
                
                memory_context += "\nIMPORTANT: When answering the user's question, you MUST reference specific memories if they are relevant. "
                memory_context += "Use the format 'Based on Memory X (ID: ...)' when citing memories. "
                memory_context += "If the memories are not relevant to the question, you may answer without referencing them, but acknowledge that you checked your memories."
            
            # Create chat prompt with role context and memory context
            chat_prompt = f"""{role_context}User message: {message}
{memory_context}

Please provide a helpful, concise response. Be conversational but professional.
Keep responses under 200 words unless the user asks for detailed information."""

            # Generate response using agent's LLM client
            try:
                if not hasattr(self.agent, 'llm_client') or not self.agent.llm_client:
                    logger.error(f"{self.name} LLM client not initialized")
                    response_text = f"[Sorry, I'm not properly configured to respond. Please contact the system administrator.]"
                else:
                    # Use real LLM client for chat response
                    llm_result = await self.agent.llm_client.complete(
                        prompt=chat_prompt,
                        temperature=0.7,
                        max_tokens=500
                    )
                    response_text = llm_result.get('response', '') if isinstance(llm_result, dict) else str(llm_result)
                    if not response_text:
                        response_text = f"[{self.name} received your message: '{message}'. I'm processing it now.]"
            except Exception as e:
                logger.error(f"{self.name} failed to generate LLM response: {e}", exc_info=True)
                response_text = f"[Sorry, I encountered an error processing your message: {str(e)}. Please try again.]"
            
            return {
                "response_text": response_text,
                "agent_name": self.name,
                "timestamp": datetime.utcnow().isoformat(),
                "status": "available"
            }
            
        except Exception as e:
            logger.error(f"{self.name} failed to handle chat message: {e}", exc_info=True)
            return {
                "response_text": f"[Sorry, I encountered an error: {str(e)}]",
                "agent_name": self.name,
                "timestamp": datetime.utcnow().isoformat(),
                "status": "error"
            }

