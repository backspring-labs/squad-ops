---
sip_uid: "17642554775883363"
sip_number: 21
title: "Agent-Memory-Protocol"
status: "implemented"
author: "Unknown"
approver: null
created_at: "2025-11-27T09:57:57.588841Z"
updated_at: "2025-11-27T10:12:48.890518Z"
original_filename: "SIP-021-Agent-Memory-Protocol.md"
---

> **Implementation Note (2026-03-06 audit):** Only the data model skeleton is implemented
> (`MemoryEntry`, `MemoryQuery`, `MemoryResult` frozen dataclasses in `src/squadops/memory/models.py`).
> The full memory system described below (LanceDB persistence, semantic search, agent-specific
> memory managers, cleanup policies) has not been built. This SIP should be treated as a design
> spec for future implementation, not a description of current functionality.

# SIP-021: Agent Memory Protocol

## Summary
Establish a comprehensive agent memory system that enables agents to persist, retrieve, and build upon past interactions, decisions, and knowledge through a "lore" system with context binding and memory versioning.

## Problem Statement
Currently, agents operate with stateless interactions, losing valuable context and knowledge between sessions. This leads to:
- Repeated work on similar problems
- Inability to learn from past decisions
- Lack of context continuity across tasks
- No accumulation of domain knowledge
- Inefficient agent coordination without shared memory

## Proposed Solution
Implement a multi-layered agent memory system with:
1. **Lore System** - Persistent knowledge storage with semantic retrieval
2. **Context Binding** - Dynamic linking of related memories and tasks
3. **Memory Versioning** - Track knowledge evolution over time
4. **Agent-Specific Memory Patterns** - Tailored memory structures per agent type
5. **Memory Cleanup** - Automated pruning of outdated or low-value memories

## Technical Specifications

### 1. Database Schema

#### Core Memory Tables
```sql
-- Agent Memory Storage
CREATE TABLE agent_memory (
    id SERIAL PRIMARY KEY,
    agent_name VARCHAR(50) NOT NULL,
    memory_type VARCHAR(50) NOT NULL, -- 'lore', 'context', 'pattern', 'decision', 'experience'
    content JSONB NOT NULL,
    content_hash VARCHAR(64) NOT NULL, -- For deduplication
    context_hash VARCHAR(64), -- For context binding
    version INTEGER DEFAULT 1,
    importance_score FLOAT DEFAULT 1.0,
    access_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP, -- For cleanup
    tags TEXT[] -- For categorization
);

-- Memory Relationships (Context Binding)
CREATE TABLE memory_relationships (
    id SERIAL PRIMARY KEY,
    memory_id_1 INTEGER REFERENCES agent_memory(id),
    memory_id_2 INTEGER REFERENCES agent_memory(id),
    relationship_type VARCHAR(50) NOT NULL, -- 'causes', 'enables', 'conflicts', 'similar', 'depends_on'
    strength FLOAT DEFAULT 1.0, -- 0.0 to 1.0
    confidence FLOAT DEFAULT 1.0, -- 0.0 to 1.0
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Memory Access Log (for optimization and analytics)
CREATE TABLE memory_access_log (
    id SERIAL PRIMARY KEY,
    agent_name VARCHAR(50) NOT NULL,
    memory_id INTEGER REFERENCES agent_memory(id),
    access_type VARCHAR(50) NOT NULL, -- 'read', 'write', 'update', 'delete', 'search'
    context VARCHAR(255),
    query_hash VARCHAR(64), -- For search queries
    response_time_ms INTEGER,
    success BOOLEAN DEFAULT TRUE,
    timestamp TIMESTAMP DEFAULT NOW()
);

-- Memory Index for Fast Retrieval
CREATE TABLE memory_index (
    id SERIAL PRIMARY KEY,
    memory_id INTEGER REFERENCES agent_memory(id),
    keyword VARCHAR(100) NOT NULL,
    weight FLOAT DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Agent Memory Profiles (per-agent configuration)
CREATE TABLE agent_memory_profiles (
    id SERIAL PRIMARY KEY,
    agent_name VARCHAR(50) UNIQUE NOT NULL,
    memory_pattern VARCHAR(50) NOT NULL, -- 'task_state_log', 'graph_based', 'time_series', etc.
    max_memories INTEGER DEFAULT 1000,
    cleanup_policy VARCHAR(50) DEFAULT 'lru', -- 'lru', 'importance', 'age', 'hybrid'
    importance_threshold FLOAT DEFAULT 0.1,
    max_age_days INTEGER DEFAULT 90,
    context_binding_enabled BOOLEAN DEFAULT TRUE,
    versioning_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

#### Indexes for Performance
```sql
-- Performance indexes
CREATE INDEX idx_agent_memory_agent_type ON agent_memory(agent_name, memory_type);
CREATE INDEX idx_agent_memory_content_hash ON agent_memory(content_hash);
CREATE INDEX idx_agent_memory_context_hash ON agent_memory(context_hash);
CREATE INDEX idx_agent_memory_importance ON agent_memory(importance_score DESC);
CREATE INDEX idx_agent_memory_last_accessed ON agent_memory(last_accessed DESC);
CREATE INDEX idx_memory_relationships_memory1 ON memory_relationships(memory_id_1);
CREATE INDEX idx_memory_relationships_memory2 ON memory_relationships(memory_id_2);
CREATE INDEX idx_memory_index_keyword ON memory_index(keyword);
CREATE INDEX idx_memory_access_log_agent_time ON memory_access_log(agent_name, timestamp DESC);
```

### 2. Memory Manager API

#### Core Memory Operations
```python
class MemoryManager:
    """Central memory management system for all agents"""
    
    def __init__(self, agent_name: str, db_pool):
        self.agent_name = agent_name
        self.db_pool = db_pool
        self.memory_cache = {}  # In-memory LRU cache
        self.profile = None  # Agent-specific memory profile
    
    # Core CRUD Operations
    async def store_lore(self, content: Dict[str, Any], memory_type: str = 'lore', 
                        importance: float = 1.0, tags: List[str] = None, 
                        expires_in_days: int = None) -> int:
        """Store a piece of lore (persistent knowledge)"""
        
    async def retrieve_lore(self, query: str, limit: int = 10, 
                           memory_types: List[str] = None) -> List[Dict[str, Any]]:
        """Retrieve relevant lore based on semantic query"""
        
    async def update_memory(self, memory_id: int, new_content: Dict[str, Any], 
                           increment_version: bool = True) -> bool:
        """Update existing memory with versioning"""
        
    async def delete_memory(self, memory_id: int, soft_delete: bool = True) -> bool:
        """Delete memory (soft delete by default)"""
    
    # Context Binding Operations
    async def bind_context(self, memory_ids: List[int], relationship_type: str, 
                          strength: float = 1.0) -> bool:
        """Bind memories together with relationships"""
        
    async def get_related_memories(self, memory_id: int, 
                                  relationship_types: List[str] = None) -> List[Dict[str, Any]]:
        """Get memories related to a given memory"""
        
    async def get_context_chain(self, memory_id: int, max_depth: int = 3) -> Dict[str, Any]:
        """Get full context chain for a memory"""
    
    # Memory Analysis Operations
    async def calculate_importance(self, memory_id: int) -> float:
        """Calculate dynamic importance score based on usage patterns"""
        
    async def find_similar_memories(self, content: Dict[str, Any], 
                                   threshold: float = 0.8) -> List[Dict[str, Any]]:
        """Find similar memories to prevent duplication"""
        
    async def get_memory_statistics(self) -> Dict[str, Any]:
        """Get memory usage statistics for the agent"""
    
    # Cleanup Operations
    async def cleanup_expired_memories(self) -> int:
        """Remove expired memories based on profile settings"""
        
    async def cleanup_low_importance_memories(self) -> int:
        """Remove low-importance memories to stay within limits"""
        
    async def optimize_memory_storage(self) -> Dict[str, Any]:
        """Run optimization routines (compression, deduplication, etc.)"""
```

### 3. Agent-Specific Memory Patterns

#### Max (Governance) - Task State Log Pattern
```python
class MaxMemoryManager(MemoryManager):
    """Task state log with decision trees and governance patterns"""
    
    async def store_decision(self, decision: Dict[str, Any], context: Dict[str, Any]):
        """Store governance decisions with full context"""
        
    async def get_decision_history(self, decision_type: str) -> List[Dict[str, Any]]:
        """Retrieve historical decisions for consistency"""
        
    async def build_decision_tree(self, current_situation: Dict[str, Any]) -> Dict[str, Any]:
        """Build decision tree based on past similar situations"""
```

#### Neo (Deductive) - Graph-Based Pattern
```python
class NeoMemoryManager(MemoryManager):
    """Graph-based memory for code patterns and solutions"""
    
    async def store_code_pattern(self, pattern: Dict[str, Any], solution: Dict[str, Any]):
        """Store code patterns with their solutions"""
        
    async def find_similar_patterns(self, problem: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find similar code patterns for reuse"""
        
    async def build_solution_graph(self, problem_type: str) -> Dict[str, Any]:
        """Build graph of related solutions"""
```

#### Joi (Empathetic) - Conversational Decay Pattern
```python
class JoiMemoryManager(MemoryManager):
    """Conversational memory with emotional context and decay"""
    
    async def store_conversation(self, conversation: Dict[str, Any], emotional_context: Dict[str, Any]):
        """Store conversations with emotional context"""
        
    async def get_conversation_context(self, user_id: str) -> Dict[str, Any]:
        """Get conversation context with decay applied"""
        
    async def apply_emotional_decay(self, conversation_id: int) -> float:
        """Apply emotional decay to conversation importance"""
```

#### Data (Inductive) - Time-Series Pattern
```python
class DataMemoryManager(MemoryManager):
    """Time-series memory for pattern detection and trend analysis"""
    
    async def store_data_point(self, data_point: Dict[str, Any], timestamp: datetime):
        """Store data points in time-series format"""
        
    async def detect_patterns(self, time_range: Tuple[datetime, datetime]) -> List[Dict[str, Any]]:
        """Detect patterns in time-series data"""
        
    async def predict_trends(self, metric: str, lookback_days: int) -> Dict[str, Any]:
        """Predict trends based on historical data"""
```

### 4. Context Binding System

#### Context Binding Engine
```python
class ContextBindingEngine:
    """Engine for binding related memories and tasks"""
    
    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager = memory_manager
        self.binding_rules = self._load_binding_rules()
    
    async def bind_task_context(self, current_task: Dict[str, Any], 
                               retrieved_memories: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Bind current task context with relevant memories"""
        
    async def generate_context_hash(self, content: Dict[str, Any]) -> str:
        """Generate hash for context binding"""
        
    async def calculate_binding_strength(self, memory1: Dict[str, Any], 
                                        memory2: Dict[str, Any]) -> float:
        """Calculate binding strength between two memories"""
        
    async def propagate_context(self, memory_id: int, new_context: Dict[str, Any]):
        """Propagate context changes to related memories"""
```

### 5. Memory Versioning System

#### Version Control for Memories
```python
class MemoryVersioning:
    """Version control system for agent memories"""
    
    async def create_memory_version(self, memory_id: int, new_content: Dict[str, Any]) -> int:
        """Create new version of existing memory"""
        
    async def get_memory_version(self, memory_id: int, version: int = None) -> Dict[str, Any]:
        """Get specific version of memory (latest if version not specified)"""
        
    async def get_version_history(self, memory_id: int) -> List[Dict[str, Any]]:
        """Get complete version history for memory"""
        
    async def merge_memory_versions(self, memory_id: int, version1: int, version2: int) -> Dict[str, Any]:
        """Merge two versions of memory"""
        
    async def rollback_memory(self, memory_id: int, target_version: int) -> bool:
        """Rollback memory to specific version"""
```

## Implementation Plan

### Phase 1: Core Infrastructure (Week 1)
- [ ] Create database schema and migrations
- [ ] Implement base MemoryManager class
- [ ] Add memory CRUD operations
- [ ] Create basic indexing and search functionality
- [ ] Add memory access logging

### Phase 2: Agent-Specific Patterns (Week 2)
- [ ] Implement MaxMemoryManager (Task State Log)
- [ ] Implement NeoMemoryManager (Graph-Based)
- [ ] Implement JoiMemoryManager (Conversational Decay)
- [ ] Implement DataMemoryManager (Time-Series)
- [ ] Add memory profile configuration system

### Phase 3: Context Binding (Week 3)
- [ ] Implement ContextBindingEngine
- [ ] Add relationship management
- [ ] Create context hash generation
- [ ] Implement binding strength calculation
- [ ] Add context propagation system

### Phase 4: Advanced Features (Week 4)
- [ ] Implement MemoryVersioning system
- [ ] Add memory cleanup and optimization
- [ ] Create memory analytics and reporting
- [ ] Add memory deduplication
- [ ] Implement memory compression

### Phase 5: Integration and Testing (Week 5)
- [ ] Integrate with BaseAgent class
- [ ] Add memory operations to agent workflows
- [ ] Create comprehensive test suite
- [ ] Performance optimization
- [ ] Documentation and examples

## Benefits

### 1. Enhanced Agent Capabilities
- **Persistent Learning**: Agents learn from past interactions and improve over time
- **Context Continuity**: Maintain context across tasks and sessions
- **Knowledge Accumulation**: Build domain expertise through experience
- **Reduced Redundancy**: Avoid repeating similar work

### 2. Improved Coordination
- **Shared Knowledge**: Agents can access relevant knowledge from other agents
- **Better Decision Making**: Decisions based on historical patterns and outcomes
- **Consistent Behavior**: Maintain consistency in similar situations
- **Efficient Problem Solving**: Leverage past solutions for similar problems

### 3. System Intelligence
- **Pattern Recognition**: Identify patterns across agent interactions
- **Trend Analysis**: Track performance and behavior trends
- **Predictive Capabilities**: Predict outcomes based on historical data
- **Self-Optimization**: System improves its own performance over time

## Risks and Mitigation

### Risk: Memory Storage Growth
- **Mitigation**: Implement aggressive cleanup policies and memory limits
- **Monitoring**: Track memory growth and implement alerts
- **Optimization**: Regular compression and deduplication

### Risk: Performance Impact
- **Mitigation**: Efficient indexing and caching strategies
- **Monitoring**: Track query performance and optimize slow queries
- **Scaling**: Implement memory sharding for large deployments

### Risk: Memory Corruption
- **Mitigation**: Comprehensive backup and recovery procedures
- **Validation**: Data integrity checks and validation
- **Versioning**: Full version history for rollback capability

### Risk: Privacy and Security
- **Mitigation**: Implement data encryption and access controls
- **Auditing**: Comprehensive audit trails for memory access
- **Compliance**: Ensure compliance with data protection regulations

## Success Criteria

### Functional Requirements
- [ ] Agents can store and retrieve memories across sessions
- [ ] Context binding works for related memories and tasks
- [ ] Memory versioning maintains complete history
- [ ] Agent-specific memory patterns function correctly
- [ ] Memory cleanup prevents storage bloat

### Performance Requirements
- [ ] Memory retrieval responds within 100ms for cached memories
- [ ] Memory storage completes within 500ms
- [ ] Context binding calculations complete within 200ms
- [ ] Memory cleanup runs without blocking agent operations

### Quality Requirements
- [ ] Memory deduplication prevents duplicate storage
- [ ] Context binding accuracy > 85% for related memories
- [ ] Memory versioning maintains data integrity
- [ ] System handles 1000+ memories per agent without degradation

## Dependencies

### External Dependencies
- **PostgreSQL**: Database for memory storage
- **Redis**: Caching layer for frequently accessed memories
- **FastAPI**: API framework for memory operations
- **SQLAlchemy**: ORM for database operations

### Internal Dependencies
- **BaseAgent**: Integration with agent base class
- **Database Schema**: Existing database infrastructure
- **Agent Profiles**: Agent configuration system
- **Logging System**: Existing logging infrastructure

## SIP Integration Points

### **SIP-005 (Four-Layer Metrics) Integration**
- **Agent Layer Metrics**: Memory usage, retrieval patterns, context binding success rates
- **Squad Layer Metrics**: Cross-agent memory sharing, memory coordination latency
- **Application Layer Metrics**: Memory-driven performance improvements, learning outcomes
- **Product Layer Metrics**: Memory requirements in PRDs, memory-driven feature evolution

### **SIP-004 (Continuous Adaptation) Integration**
- **Memory-Driven Adaptation**: Memory patterns inform role refinements and micro-adjustments
- **Learning Loops**: Memory accumulation drives continuous improvement cycles
- **Adaptation Traceability**: Memory changes linked to adaptation cycles and PID tracking
- **Performance Correlation**: Memory effectiveness measured across adaptation cycles

### **SIP-006 (Warm Boot Analysis) Integration**
- **Memory Analysis**: Include memory effectiveness and learning outcomes in WBA reports
- **Retrospective Memory**: Track what agents learned from past runs and failures
- **Memory Recommendations**: Suggest memory improvements and optimizations in WBA
- **Pattern Recognition**: Use memory to identify recurring issues and success patterns

### **SIP-007 (Armory Protocol) Integration**
- **Tool Usage Memory**: Remember which tools worked well for which tasks and contexts
- **Tool Performance Patterns**: Store tool effectiveness and failure patterns in memory
- **Tool Recommendations**: Use memory to suggest optimal tool combinations and usage
- **Tool Evolution**: Memory-driven tool selection improvements and deprecation decisions

### **SIP-010 (Secrets Lifecycle) Integration**
- **Secret Access Patterns**: Remember which agents accessed which secrets and when
- **Security Violation Memory**: Store security incident patterns and responses in memory
- **Access Optimization**: Use memory to optimize secret access patterns and reduce risk
- **Compliance Tracking**: Memory-driven compliance monitoring and audit trail enhancement

### **SIP-012 (Pattern-First Development) Integration**
- **Pattern Effectiveness Memory**: Remember which patterns worked for which problems and contexts
- **Pattern Evolution Tracking**: Store pattern usage, success rates, and evolution patterns
- **Expert Consultation Memory**: Remember expert model recommendations and their outcomes
- **Architecture Decision Memory**: Store ADR patterns, outcomes, and decision rationale

### **SIP-013 (Extensibility) Integration**
- **Extension Performance Memory**: Remember extension effectiveness and failure patterns
- **Extension Usage Patterns**: Store extension usage, success rates, and optimization opportunities
- **Extension Evolution**: Memory-driven extension optimization and lifecycle management
- **Extension Governance**: Memory-based extension decision tracking and compliance

### **SIP-018 (Squad Context Protocol) Integration**
- **Context Binding**: Memory context hashes align with PID context hashes for traceability
- **Multi-Dimensional Context**: Memory integrates with business, artifact, governance, temporal, observability, reasoning, and human context dimensions
- **Context Propagation**: Memory changes propagate to related context dimensions
- **Context Graph**: Memory relationships contribute to unified context graph structure

## Integration Implementation Strategy

### **Phase 1: Core Memory + SIP-005 Integration**
```python
class MetricsAwareMemoryManager(MemoryManager):
    """Memory manager integrated with Four-Layer Metrics"""
    
    async def store_memory_with_metrics(self, content: Dict[str, Any], 
                                       layer: str, metrics_context: Dict[str, Any]):
        """Store memory with metrics layer context"""
        
    async def get_memory_effectiveness_metrics(self) -> Dict[str, Any]:
        """Get memory effectiveness metrics for SIP-005 reporting"""
        
    async def correlate_memory_with_performance(self, run_id: str) -> Dict[str, Any]:
        """Correlate memory usage with performance metrics"""
```

### **Phase 2: Adaptation + WBA Integration**
```python
class AdaptationAwareMemoryManager(MemoryManager):
    """Memory manager integrated with Continuous Adaptation and WBA"""
    
    async def store_adaptation_memory(self, adaptation: Dict[str, Any], 
                                    outcome: Dict[str, Any]):
        """Store adaptation decisions and outcomes"""
        
    async def get_adaptation_patterns(self) -> List[Dict[str, Any]]:
        """Get patterns from adaptation history"""
        
    async def generate_wba_memory_insights(self, run_id: str) -> Dict[str, Any]:
        """Generate memory insights for Warm Boot Analysis"""
```

### **Phase 3: Tool + Security Integration**
```python
class ToolAwareMemoryManager(MemoryManager):
    """Memory manager integrated with Armory and Secrets protocols"""
    
    async def store_tool_usage_memory(self, tool_id: str, usage_context: Dict[str, Any], 
                                    outcome: Dict[str, Any]):
        """Store tool usage patterns and outcomes"""
        
    async def get_tool_recommendations(self, task_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get tool recommendations based on memory patterns"""
        
    async def store_security_memory(self, security_event: Dict[str, Any], 
                                  response: Dict[str, Any]):
        """Store security patterns and responses"""
```

### **Phase 4: Pattern + Extension Integration**
```python
class PatternAwareMemoryManager(MemoryManager):
    """Memory manager integrated with Pattern-First and Extensibility protocols"""
    
    async def store_pattern_memory(self, pattern: Dict[str, Any], 
                                 context: Dict[str, Any], outcome: Dict[str, Any]):
        """Store pattern usage and effectiveness"""
        
    async def get_pattern_recommendations(self, problem_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get pattern recommendations based on memory"""
        
    async def store_extension_memory(self, extension: Dict[str, Any], 
                                   performance: Dict[str, Any]):
        """Store extension performance and usage patterns"""
```

### **Phase 5: Unified Context Integration**
```python
class UnifiedContextMemoryManager(MemoryManager):
    """Memory manager integrated with Squad Context Protocol"""
    
    async def store_memory_with_pid_context(self, content: Dict[str, Any], 
                                          pid: str, context_dimensions: Dict[str, Any]):
        """Store memory with full PID context from SIP-018"""
        
    async def get_memories_by_context_dimension(self, dimension: str, 
                                              value: str) -> List[Dict[str, Any]]:
        """Get memories by context dimension"""
        
    async def propagate_context_changes(self, context_change: Dict[str, Any]):
        """Propagate context changes to related memories"""
```

## Timeline

### Estimated Duration: 5 weeks

#### Week 1: Core Infrastructure
- Database schema design and implementation
- Base MemoryManager class
- Basic CRUD operations
- Memory access logging

#### Week 2: Agent-Specific Patterns
- MaxMemoryManager implementation
- NeoMemoryManager implementation
- JoiMemoryManager implementation
- DataMemoryManager implementation

#### Week 3: Context Binding
- ContextBindingEngine implementation
- Relationship management
- Context hash generation
- Binding strength calculation

#### Week 4: Advanced Features
- MemoryVersioning system
- Memory cleanup and optimization
- Memory analytics and reporting
- Performance optimization

#### Week 5: Integration and Testing
- BaseAgent integration
- Comprehensive testing
- Performance tuning
- Documentation and deployment

## Conclusion

The Agent Memory Protocol (SIP-021) provides a comprehensive foundation for persistent agent intelligence, enabling agents to learn, remember, and build upon past experiences. This system transforms agents from stateless processors into intelligent entities capable of accumulating knowledge and improving performance over time.

The implementation plan provides a structured approach to building this complex system, with clear phases, success criteria, and risk mitigation strategies. The protocol is designed to be scalable, performant, and maintainable while providing the flexibility needed for different agent types and use cases.
