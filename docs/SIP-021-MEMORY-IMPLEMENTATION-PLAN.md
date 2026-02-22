> **HISTORICAL** — LanceDB was chosen for agent memory per SIP-042.
> This planning document pre-dates that decision and is retained for reference only.

# SIP-021 Memory Implementation Plan & Integration Analysis

**Date:** January 2025
**Status:** Superseded by SIP-042 (LanceDB)
**Author:** Build Partner Analysis

---

## Executive Summary

This document provides a comprehensive analysis of SIP-021 (Agent Memory Protocol) and IDEA_036 (Squad Memory Pool), proposes an integrated implementation plan, and reviews the current codebase for memory-related implementations.

**Key Findings:**
- ✅ No existing memory implementation (clean slate)
- ✅ Database infrastructure ready (PostgreSQL with asyncpg pools)
- ✅ BaseAgent structure compatible for memory integration
- ✅ Clear integration path with existing SIPs (SIP-024/025 Task Management)

---

## 1. Current State Analysis

### 1.1 Existing Memory-Related Code

**Finding:** No memory implementation exists in the codebase.

**Checked Locations:**
- `agents/base_agent.py` - No memory manager or memory-related methods
- `agents/roles/*/agent.py` - No memory usage
- `infra/init.sql` - No memory tables (only task management tables)
- `infra/task-api/` - No memory endpoints

**Database Schema Status:**
- ✅ PostgreSQL connection pools established (`asyncpg.create_pool`)
- ✅ Task management tables exist (`agent_task_log`, `execution_cycle`)
- ❌ No memory tables yet (`agent_memory`, `memory_relationships`, etc.)

### 1.2 Integration Points

**BaseAgent Structure:**
```python
class BaseAgent:
    def __init__(self, name: str, agent_type: str, reasoning_style: str):
        self.db_pool = None  # asyncpg pool - ready for memory integration
        self.redis_client = None  # Redis available for caching
        # No memory_manager attribute yet
```

**Database Connection Pattern:**
- Uses `asyncpg.create_pool()` for PostgreSQL
- Connection pool pattern: `pool.acquire()` → connection → work → release
- Task API uses same pattern (see `infra/task-api/main.py`)

---

## 2. SIP-021 Detailed Review

### 2.1 Core Components

#### **A. Lore System**
- **Purpose:** Persistent knowledge storage with semantic retrieval
- **Key Features:**
  - Content deduplication via `content_hash`
  - Context binding via `context_hash`
  - Importance scoring for prioritization
  - Tag-based categorization
  - Expiration for cleanup

#### **B. Context Binding**
- **Purpose:** Dynamic linking of related memories and tasks
- **Relationship Types:**
  - `causes`, `enables`, `conflicts`, `similar`, `depends_on`
- **Strength & Confidence:** 0.0 to 1.0 scoring system

#### **C. Memory Versioning**
- **Purpose:** Track knowledge evolution over time
- **Features:**
  - Version history tracking
  - Rollback capability
  - Merge functionality

#### **D. Agent-Specific Patterns**

| Agent | Pattern | Memory Structure | Use Case |
|-------|---------|------------------|----------|
| **Max** | Task State Log | Decision trees, governance patterns | Store governance decisions with context |
| **Neo** | Graph-Based | Code patterns, solutions | Store code patterns with solutions |
| **Joi** | Conversational Decay | Emotional context, decay over time | Store conversations with emotional context |
| **Data** | Time-Series | Data points, trends | Store data points for pattern detection |

#### **E. Memory Cleanup**
- **Policies:** LRU, importance, age, hybrid
- **Automated Pruning:** Based on importance threshold, max age, access patterns

### 2.2 Database Schema Analysis

**Core Tables:**
1. `agent_memory` - Main storage (JSONB content, hashes, importance scores)
2. `memory_relationships` - Context binding relationships
3. `memory_access_log` - Analytics and optimization
4. `memory_index` - Fast keyword retrieval
5. `agent_memory_profiles` - Per-agent configuration

**Performance Considerations:**
- ✅ Comprehensive indexes planned
- ✅ JSONB for flexible content storage
- ✅ Hash-based deduplication
- ⚠️ Need to consider Redis caching layer

### 2.3 API Design Review

**MemoryManager Class Structure:**
```python
class MemoryManager:
    # Core CRUD
    - store_lore()
    - retrieve_lore()
    - update_memory()
    - delete_memory()
    
    # Context Binding
    - bind_context()
    - get_related_memories()
    - get_context_chain()
    
    # Analysis
    - calculate_importance()
    - find_similar_memories()
    - get_memory_statistics()
    
    # Cleanup
    - cleanup_expired_memories()
    - cleanup_low_importance_memories()
    - optimize_memory_storage()
```

**Strengths:**
- Clean separation of concerns
- Async-ready design
- Comprehensive operations

**Potential Enhancements:**
- Add batch operations for efficiency
- Add semantic search integration (vector embeddings?)
- Add Redis caching layer for hot memories

---

## 3. IDEA_036 Squad Memory Pool Integration

### 3.1 Key Concepts

**Squad Memory Pool (SMP):**
- Shared cognitive layer for validated experiences
- Promoted from agent-level memories
- SQL-native repository (`squad_mem_pool` table)

**SIR Phase (Squad Improvement Recommendations):**
- Analyzes memories to generate actionable recommendations
- Bridges learning → action
- Validated SIRs become formal SIPs

**Memori Integration:**
- IDEA_036 mentions external "Memori" system
- Two modes: `conscious` (transient) and `auto` (persistent)
- **Decision:** ✅ **HYBRID APPROACH** - Use Memori for agent-level + Native SQL for squad-level

### 3.2 Integration Architecture

**✅ RECOMMENDED: Hybrid Architecture**
```
Agent-Level Memory (Memori):
├── Agent → Memori (conscious/auto modes)
├── Semantic search built-in
└── Memory relationships

Squad-Level Memory (Native SQL):
├── Squad Memory Pool (promoted memories)
├── SIR Generation
└── SIR → SIP Pipeline
```

**Benefits:**
- ✅ 5-6 weeks saved on core memory implementation
- ✅ Semantic search out of the box (no vector embedding work)
- ✅ Aligns with IDEA_036 vision (Memori + Squad Memory Pool)
- ✅ Maintains control over SquadOps-specific features

**See:** `docs/MEMORI-INTEGRATION-ANALYSIS.md` for detailed comparison and implementation plan.

### 3.3 Unified Schema Design

**Enhanced Schema for Squad Memory Pool:**

```sql
-- Squad Memory Pool (from IDEA_036, enhanced)
CREATE TABLE squad_mem_pool (
    id SERIAL PRIMARY KEY,
    squad_id TEXT NOT NULL,
    source_agent TEXT NOT NULL,
    source_memory_id INTEGER REFERENCES agent_memory(id), -- Link to agent memory
    topic TEXT NOT NULL,
    context JSONB NOT NULL,
    causal_chain JSONB, -- From IDEA_036
    outcome TEXT,
    promoted_at TIMESTAMP DEFAULT NOW(),
    memory_signature TEXT, -- Hash linking to Memori entries (if used)
    importance_score FLOAT DEFAULT 1.0,
    validation_status TEXT DEFAULT 'pending', -- 'pending', 'validated', 'rejected'
    validated_by TEXT, -- Agent who validated (Max/Data)
    validated_at TIMESTAMP,
    tags TEXT[],
    created_at TIMESTAMP DEFAULT NOW()
);

-- Squad Improvement Recommendations (SIRs)
CREATE TABLE squad_recommendations (
    rec_id TEXT PRIMARY KEY, -- Format: SIR-XXX
    related_memories INTEGER[], -- Array of squad_mem_pool IDs
    category TEXT NOT NULL, -- 'process', 'ops', 'qa', 'performance', etc.
    recommendation TEXT NOT NULL,
    rationale TEXT,
    expected_impact JSONB,
    status TEXT DEFAULT 'draft', -- 'draft', 'approved', 'implemented', 'rejected'
    created_at TIMESTAMP DEFAULT NOW(),
    approved_by TEXT,
    approved_at TIMESTAMP,
    implementation_status TEXT, -- 'not_started', 'in_progress', 'completed', 'failed'
    actual_impact JSONB -- Measured impact after implementation
);

-- Link SIRs to SIPs (when promoted)
CREATE TABLE sir_to_sip_mapping (
    sir_id TEXT REFERENCES squad_recommendations(rec_id),
    sip_number TEXT NOT NULL, -- Format: SIP-XXX
    promoted_at TIMESTAMP DEFAULT NOW(),
    promoted_by TEXT
);
```

**Integration Points:**
- `squad_mem_pool.source_memory_id` → `agent_memory.id` (foreign key)
- Allows promotion of agent memories to squad-level
- Maintains traceability chain

---

## 4. Implementation Plan

### Phase 1: Core Infrastructure (Week 1)

**Deliverables:**
1. Database schema migration
2. Base MemoryManager class
3. Memory CRUD operations
4. Basic indexing and search
5. Memory access logging

**Tasks:**
- [ ] Create migration script: `infra/migrations/add_memory_tables.sql`
- [ ] Implement `agents/memory/memory_manager.py`
- [ ] Add Redis caching layer
- [ ] Create `agents/memory/base.py` with core classes
- [ ] Unit tests for MemoryManager CRUD operations

**Files to Create:**
```
agents/memory/
├── __init__.py
├── base.py           # MemoryManager base class
├── memory_manager.py # Core implementation
├── cache.py          # Redis caching layer
└── utils.py          # Helper functions (hashing, etc.)

infra/migrations/
└── 001_add_memory_tables.sql

tests/unit/memory/
├── test_memory_manager.py
└── test_memory_crud.py
```

### Phase 2: Agent-Specific Patterns (Week 2)

**Deliverables:**
1. MaxMemoryManager (Task State Log)
2. NeoMemoryManager (Graph-Based)
3. JoiMemoryManager (Conversational Decay)
4. DataMemoryManager (Time-Series)
5. Memory profile configuration system

**Tasks:**
- [ ] Implement `agents/memory/max_memory.py`
- [ ] Implement `agents/memory/neo_memory.py`
- [ ] Implement `agents/memory/joi_memory.py`
- [ ] Implement `agents/memory/data_memory.py`
- [ ] Create memory profile loader from config
- [ ] Unit tests for each agent-specific pattern

**Files to Create:**
```
agents/memory/
├── patterns/
│   ├── __init__.py
│   ├── max_memory.py      # Task State Log pattern
│   ├── neo_memory.py       # Graph-Based pattern
│   ├── joi_memory.py       # Conversational Decay pattern
│   └── data_memory.py       # Time-Series pattern
```

### Phase 3: Context Binding (Week 3)

**Deliverables:**
1. ContextBindingEngine
2. Relationship management
3. Context hash generation
4. Binding strength calculation
5. Context propagation system

**Tasks:**
- [ ] Implement `agents/memory/context_binding.py`
- [ ] Add relationship management operations
- [ ] Create context hash algorithm
- [ ] Implement binding strength calculation
- [ ] Add context propagation logic
- [ ] Integration tests for context binding

**Files to Create:**
```
agents/memory/
├── context_binding.py
└── relationships.py
```

### Phase 4: Advanced Features (Week 4)

**Deliverables:**
1. MemoryVersioning system
2. Memory cleanup and optimization
3. Memory analytics and reporting
4. Memory deduplication
5. Memory compression

**Tasks:**
- [ ] Implement `agents/memory/versioning.py`
- [ ] Create cleanup scheduler
- [ ] Add analytics endpoints
- [ ] Implement deduplication logic
- [ ] Add memory compression for large content
- [ ] Performance optimization

**Files to Create:**
```
agents/memory/
├── versioning.py
├── cleanup.py
└── analytics.py
```

### Phase 5: BaseAgent Integration & Squad Memory Pool (Week 5)

**Deliverables:**
1. BaseAgent memory integration
2. Squad Memory Pool implementation
3. SIR Phase implementation
4. Comprehensive testing
5. Documentation

**Tasks:**
- [ ] Add `memory_manager` to BaseAgent `__init__`
- [ ] Integrate memory operations into agent workflows
- [ ] Implement Squad Memory Pool promotion logic
- [ ] Create SIR generation system
- [ ] Add memory endpoints to Task API
- [ ] End-to-end integration tests
- [ ] Update documentation

**Files to Modify:**
```
agents/base_agent.py              # Add memory_manager
agents/roles/lead/agent.py        # Use memory for decisions
agents/roles/dev/agent.py        # Use memory for patterns
infra/task-api/main.py            # Add memory endpoints
```

### Phase 6: Squad Memory Pool & SIR System (Week 6)

**Deliverables:**
1. Squad Memory Pool table and operations
2. SIR generation from memories
3. SIR → SIP promotion pipeline
4. Memory replay engine
5. WarmBoot integration

**Tasks:**
- [ ] Create `squad_mem_pool` table migration
- [ ] Implement `agents/memory/squad_pool.py`
- [ ] Create SIR generation logic
- [ ] Add SIR → SIP promotion workflow
- [ ] Implement memory replay engine
- [ ] Integrate with WarmBoot lifecycle

**Files to Create:**
```
agents/memory/
├── squad_pool.py
├── sir_generator.py
└── replay_engine.py

infra/migrations/
└── 002_add_squad_memory_pool.sql
```

---

## 5. Integration with Existing SIPs

### 5.1 SIP-024/025 (Task Management)

**Integration Points:**
- Link memories to `execution_cycle.ecid`
- Link memories to `agent_task_log.task_id`
- Store task outcomes in memory

```python
# Example integration
async def store_task_memory(self, task_id: str, ecid: str, outcome: Dict):
    memory_content = {
        "task_id": task_id,
        "ecid": ecid,
        "outcome": outcome,
        "timestamp": datetime.now().isoformat()
    }
    memory_id = await self.memory_manager.store_lore(
        content=memory_content,
        memory_type="task_outcome",
        tags=[f"ecid:{ecid}", f"task:{task_id}"]
    )
```

### 5.2 SIP-005 (Four-Layer Metrics)

**Integration Points:**
- Agent Layer: Memory usage metrics
- Squad Layer: Cross-agent memory sharing
- Application Layer: Memory-driven performance improvements
- Product Layer: Memory requirements in PRDs

**Metrics to Track:**
- `mem_pool_count` - Number of memories per agent
- `mem_retrieval_rate` - Memories retrieved per task
- `mem_reuse_rate` - % of runs using existing memories
- `context_binding_accuracy` - % of accurate bindings

### 5.3 SIP-033A (JSON Workflow)

**Integration Points:**
- Store manifest patterns in memory
- Remember successful build patterns
- Learn from deployment outcomes

```python
# Store successful manifest pattern
async def store_manifest_pattern(self, manifest: Dict, success: bool):
    await self.memory_manager.store_lore(
        content={"manifest": manifest, "success": success},
        memory_type="pattern",
        tags=["manifest", "build"]
    )
```

---

## 6. Technical Design Decisions

### 6.1 Caching Strategy

**Redis Cache Layer:**
- Cache frequently accessed memories (< 1 hour old)
- Cache hot memories (high `access_count`)
- Cache memory relationships
- TTL: 1 hour for hot memories, 5 minutes for regular

**Cache Key Format:**
```
memory:{agent_name}:{memory_id}
memory:{agent_name}:query:{query_hash}
memory:{agent_name}:context:{context_hash}
```

### 6.2 Semantic Search

**Current Approach:** Keyword-based indexing
**Future Enhancement:** Vector embeddings for semantic similarity

**Decision:** Start with keyword-based, add vector search in Phase 4 if needed.

### 6.3 Memory Deduplication

**Strategy:**
1. Generate `content_hash` from content JSONB
2. Check for existing memory with same hash
3. If exists, update `access_count` and `last_accessed`
4. Link via `memory_relationships` if semantically similar but not identical

### 6.4 Performance Targets

**From SIP-021:**
- Memory retrieval: < 100ms (cached), < 500ms (uncached)
- Memory storage: < 500ms
- Context binding: < 200ms
- Memory cleanup: Non-blocking

**Monitoring:**
- Track via `memory_access_log.response_time_ms`
- Alert if > 2x target time

---

## 7. Risk Mitigation

### 7.1 Memory Storage Growth

**Mitigation:**
- Aggressive cleanup policies (default: 90 days max age)
- Importance-based pruning
- Compression for large memories
- Monitoring alerts at 80% capacity

### 7.2 Performance Impact

**Mitigation:**
- Redis caching layer
- Efficient indexes
- Connection pooling (already in place)
- Query optimization

### 7.3 Memory Corruption

**Mitigation:**
- Full version history
- Transaction-based operations
- Data integrity checks
- Regular backups

### 7.4 Privacy and Security

**Mitigation:**
- Access control per agent
- Audit trails via `memory_access_log`
- Encryption for sensitive content (future)
- GDPR compliance considerations

---

## 8. Success Criteria

### Functional Requirements
- [ ] Agents can store and retrieve memories across sessions
- [ ] Context binding works for related memories and tasks
- [ ] Memory versioning maintains complete history
- [ ] Agent-specific memory patterns function correctly
- [ ] Memory cleanup prevents storage bloat
- [ ] Squad Memory Pool promotes validated memories
- [ ] SIR generation produces actionable recommendations

### Performance Requirements
- [ ] Memory retrieval < 100ms (cached), < 500ms (uncached)
- [ ] Memory storage < 500ms
- [ ] Context binding < 200ms
- [ ] Memory cleanup non-blocking

### Quality Requirements
- [ ] Memory deduplication prevents duplicate storage
- [ ] Context binding accuracy > 85%
- [ ] Memory versioning maintains data integrity
- [ ] System handles 1000+ memories per agent without degradation
- [ ] Test coverage > 90% for memory module

---

## 9. Testing Strategy

### Unit Tests
- MemoryManager CRUD operations
- Agent-specific pattern implementations
- Context binding logic
- Versioning system
- Cleanup operations

### Integration Tests
- BaseAgent memory integration
- Database operations with real PostgreSQL
- Redis caching layer
- Squad Memory Pool promotion
- SIR generation

### Performance Tests
- Memory retrieval under load
- Storage operations with large content
- Context binding with many relationships
- Cleanup operations performance

### End-to-End Tests
- Complete memory lifecycle (store → retrieve → update → delete)
- Context binding across multiple memories
- Squad Memory Pool promotion workflow
- SIR generation from memories

---

## 10. Next Steps

### Immediate Actions
1. **Review & Approval:** Get stakeholder approval for implementation plan
2. **Resource Allocation:** Assign developer(s) for implementation
3. **Environment Setup:** Ensure development environment ready
4. **Sprint Planning:** Break down Phase 1 into daily tasks

### Phase 1 Kickoff Checklist
- [ ] Create `agents/memory/` directory structure
- [ ] Set up database migration framework
- [ ] Create initial database schema migration
- [ ] Implement base MemoryManager class skeleton
- [ ] Write first unit test (TDD approach)
- [ ] Set up Redis caching layer structure

---

## 11. Open Questions

1. **Memori Integration:** Should we integrate external Memori system or build native?
   - **Recommendation:** ✅ **HYBRID APPROACH** - Use Memori for agent-level memory + Native SQL for Squad Memory Pool
   - **See:** `docs/MEMORI-INTEGRATION-ANALYSIS.md` for detailed analysis
   - **Benefits:** 5-6 weeks saved, semantic search out of box, aligns with IDEA_036 vision

2. **Vector Embeddings:** Should we implement semantic search with embeddings?
   - **Recommendation:** Start with keyword-based, add vectors in Phase 4 if needed

3. **Memory API:** Should memory operations be exposed via FastAPI?
   - **Recommendation:** Yes, add to Task API for external access

4. **Memory Sharing:** How should agents share memories across squad?
   - **Recommendation:** Via Squad Memory Pool promotion workflow

5. **SIR Automation:** How automated should SIR generation be?
   - **Recommendation:** Start with Max/Data manual review, automate later

---

## 12. Appendix: Code Structure Preview

### MemoryManager Base Class Structure

```python
# agents/memory/base.py
from typing import Dict, Any, List, Optional
import asyncpg
import hashlib
import json
from datetime import datetime, timedelta

class MemoryManager:
    """Base memory management system for all agents"""
    
    def __init__(self, agent_name: str, db_pool: asyncpg.Pool, redis_client=None):
        self.agent_name = agent_name
        self.db_pool = db_pool
        self.redis_client = redis_client
        self.memory_cache = {}  # In-memory LRU cache
        self.profile = None
    
    async def initialize(self):
        """Load agent memory profile"""
        # Load from agent_memory_profiles table
        pass
    
    async def store_lore(self, content: Dict[str, Any], 
                        memory_type: str = 'lore',
                        importance: float = 1.0,
                        tags: List[str] = None,
                        expires_in_days: int = None) -> int:
        """Store a piece of lore (persistent knowledge)"""
        # Implementation
        pass
    
    async def retrieve_lore(self, query: str, limit: int = 10,
                          memory_types: List[str] = None) -> List[Dict[str, Any]]:
        """Retrieve relevant lore based on semantic query"""
        # Implementation
        pass
    
    # ... other methods
```

### BaseAgent Integration Preview

```python
# agents/base_agent.py (modifications)
class BaseAgent(ABC):
    def __init__(self, name: str, agent_type: str, reasoning_style: str):
        # ... existing initialization ...
        
        # Initialize memory manager (after db_pool is ready)
        self.memory_manager = None  # Will be initialized in initialize()
    
    async def initialize(self):
        """Initialize agent connections"""
        # ... existing initialization ...
        
        # Initialize memory manager
        from agents.memory.base import MemoryManager
        self.memory_manager = MemoryManager(
            agent_name=self.name,
            db_pool=self.db_pool,
            redis_client=self.redis_client
        )
        await self.memory_manager.initialize()
        
        logger.info(f"{self.name} initialized with memory support")
```

---

**End of Implementation Plan**

This plan provides a comprehensive roadmap for implementing SIP-021 Agent Memory Protocol with IDEA_036 Squad Memory Pool integration. The phased approach ensures incremental delivery with proper testing at each stage.

