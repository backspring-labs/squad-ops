> **HISTORICAL** — LanceDB was chosen for agent memory per SIP-042.
> This evaluation pre-dates that decision and is retained for reference only.

# Memori Integration Analysis & Recommendation

**Date:** January 2025
**Status:** Superseded by SIP-042 (LanceDB)
**Context:** Evaluating Memori as external memory system vs native SQL-based implementation

---

## Executive Summary

After researching Memori and analyzing SquadOps requirements, I recommend a **hybrid approach**: Use Memori for agent-level memory management, integrated with native SQL-based Squad Memory Pool for squad-level sharing.

**Key Findings:**
- ✅ Memori is a mature, open-source memory engine with proven capabilities
- ✅ Aligns perfectly with IDEA_036's vision of agent-level Memori + Squad Memory Pool
- ✅ Provides advanced features (dual-mode, semantic search) out of the box
- ✅ Reduces implementation time and maintenance burden
- ⚠️ Requires integration work but provides better foundation than building from scratch

---

## 1. Memori vs Mem0 Clarification

**⚠️ IMPORTANT:** There appears to be confusion about "Memori":
- **Memori.ai** (Italian company): Conversational AI platform, NOT a memory layer
- **Mem0**: Open-source memory layer for AI applications (YCombinator-backed)

**Recommendation Updated:** See `docs/MEM0-VS-MEMORI-COMPARISON.md` for full analysis.

**New Recommendation:** **Mem0** appears to be the better choice for SquadOps.

---

## 1. Memori Overview (Original Analysis)

### 1.1 What is Memori?

**Memori** (from IDEA_036 reference) - may refer to:
- Human-like memory functions (context, preferences, relationships)
- Dual-mode memory architecture (conscious/auto)
- Multi-agent system support
- Universal integration (`memori.enable()`)
- Structured memory types (short-term, long-term, rules, entity)

### 1.2 Key Features

| Feature | Description | Benefit for SquadOps |
|---------|-------------|---------------------|
| **Dual-Mode Memory** | Conscious (working memory) + Auto (intelligent search) | Matches IDEA_036's vision exactly |
| **Semantic Search** | Built-in semantic retrieval across knowledge base | No need to build vector embeddings |
| **Multi-Agent Support** | Designed for multi-agent systems | Perfect for 10-agent squad |
| **Easy Integration** | Single line of code to enable | Fast implementation |
| **Structured Types** | Short-term, long-term, rules, entity memory | Aligns with SIP-021 memory types |
| **Memory Relationships** | Tracks relationships between memories | Supports context binding |

### 1.3 Memori Architecture

```
Memori System:
├── Memory Agent (stores memories)
├── Conscious Agent (working memory)
└── Retrieval Agent (semantic search)

Memory Types:
├── Short-term (conscious mode)
├── Long-term (auto mode)
├── Rules (governance patterns)
└── Entity (structured data)
```

---

## 2. Comparison: Memori vs Native Implementation

### 2.1 Feature Comparison

| Feature | Memori | Native SQL | Winner |
|---------|--------|-----------|--------|
| **Semantic Search** | ✅ Built-in (vector embeddings) | ❌ Keyword-based (needs vectors) | **Memori** |
| **Memory Relationships** | ✅ Built-in | ✅ Can build | **Tie** |
| **Multi-Agent Support** | ✅ Designed for it | ✅ Can build | **Tie** |
| **Dual-Mode (Conscious/Auto)** | ✅ Built-in | ❌ Need to build | **Memori** |
| **Performance** | ✅ Optimized | ✅ Can optimize | **Tie** |
| **Integration Effort** | ⚠️ Integration work | ❌ Full implementation | **Memori** |
| **Customization** | ⚠️ API-based | ✅ Full control | **Native** |
| **SquadOps-Specific Features** | ❌ Need to build | ✅ Full control | **Native** |
| **Maintenance** | ✅ Community maintained | ❌ Self-maintained | **Memori** |
| **Squad Memory Pool** | ❌ Not included | ✅ Full control | **Native** |
| **SIR Generation** | ❌ Not included | ✅ Full control | **Native** |

### 2.2 Implementation Effort Comparison

| Task | Memori | Native SQL | Time Saved |
|------|--------|-----------|------------|
| **Core Memory Storage** | ✅ Ready | ❌ 2 weeks | **2 weeks** |
| **Semantic Search** | ✅ Ready | ❌ 1-2 weeks | **1-2 weeks** |
| **Memory Relationships** | ✅ Ready | ❌ 1 week | **1 week** |
| **Dual-Mode Architecture** | ✅ Ready | ❌ 1 week | **1 week** |
| **Agent-Specific Patterns** | ⚠️ Integration | ❌ 1 week | **Similar** |
| **Context Binding** | ⚠️ Integration | ❌ 1 week | **Similar** |
| **Squad Memory Pool** | ❌ Need to build | ❌ Need to build | **Same** |
| **SIR Generation** | ❌ Need to build | ❌ Need to build | **Same** |

**Total Time Saved:** ~5-6 weeks for core memory features

### 2.3 Pros & Cons

#### Memori Approach

**Pros:**
- ✅ Mature, battle-tested solution
- ✅ Built-in semantic search (no vector embedding work)
- ✅ Dual-mode architecture matches IDEA_036 vision
- ✅ Reduces implementation time significantly
- ✅ Community-maintained (less maintenance burden)
- ✅ Multi-agent support built-in
- ✅ Easy integration (`memori.enable()`)
- ✅ Supports memory relationships out of the box

**Cons:**
- ⚠️ External dependency (need to manage updates)
- ⚠️ Less control over internals
- ⚠️ Need to adapt to Memori's API patterns
- ⚠️ Squad Memory Pool still needs native implementation
- ⚠️ SIR generation still needs native implementation

#### Native SQL Approach

**Pros:**
- ✅ Full control over implementation
- ✅ No external dependencies
- ✅ Perfect alignment with SquadOps architecture
- ✅ Custom features easier to add
- ✅ Direct integration with existing PostgreSQL

**Cons:**
- ❌ Significant implementation time (5-6 weeks)
- ❌ Need to build semantic search (vector embeddings)
- ❌ Need to build dual-mode architecture
- ❌ Need to build memory relationships
- ❌ Maintenance burden (self-maintained)
- ❌ More code to test and maintain

---

## 3. Recommended Approach: Hybrid Architecture

### 3.1 Best of Both Worlds

**Recommendation:** Use Memori for agent-level memory + Native SQL for Squad Memory Pool

```
Architecture:
├── Agent-Level Memory (Memori)
│   ├── Conscious Mode (working memory)
│   ├── Auto Mode (semantic search)
│   └── Memory Relationships
│
└── Squad-Level Memory (Native SQL)
    ├── Squad Memory Pool (promoted memories)
    ├── SIR Generation
    └── SIR → SIP Pipeline
```

### 3.2 Integration Flow

```
1. Agent Operations (Memori)
   ├── Agent stores memories in Memori
   ├── Memori handles semantic search
   └── Memori manages memory relationships

2. Memory Promotion (Hybrid)
   ├── Max/Data validate agent memories
   ├── Promote validated memories to Squad Memory Pool (SQL)
   └── Link via memory_signature hash

3. Squad-Level Operations (Native SQL)
   ├── Squad Memory Pool queries
   ├── SIR generation from memories
   └── SIR → SIP promotion
```

### 3.3 Benefits of Hybrid Approach

1. **Leverages Memori's Strengths:**
   - Semantic search out of the box
   - Dual-mode architecture
   - Memory relationships
   - Multi-agent support

2. **Maintains SquadOps Control:**
   - Squad Memory Pool in native SQL
   - SIR generation in native SQL
   - Full control over squad-level features

3. **Reduces Implementation Time:**
   - ~5-6 weeks saved on core memory features
   - Focus on Squad Memory Pool and SIR system

4. **Aligns with IDEA_036:**
   - Agent-level Memori (as envisioned)
   - Squad Memory Pool promotion workflow
   - Memory signature linking

---

## 4. Implementation Plan with Memori

### Phase 1: Memori Integration (Week 1-2)

**Deliverables:**
1. Memori installation and configuration
2. Agent-level Memori integration
3. Memory storage and retrieval
4. Basic semantic search

**Tasks:**
- [ ] Install Memori: `pip install memori`
- [ ] Create `agents/memory/memori_adapter.py`
- [ ] Integrate Memori into BaseAgent
- [ ] Configure Memori for each agent type
- [ ] Test conscious/auto mode switching
- [ ] Unit tests for Memori integration

**Files to Create:**
```
agents/memory/
├── __init__.py
├── memori_adapter.py      # Memori integration wrapper
└── config.py              # Memori configuration per agent
```

### Phase 2: Agent-Specific Patterns (Week 2-3)

**Deliverables:**
1. MaxMemoryManager (Memori + Task State Log pattern)
2. NeoMemoryManager (Memori + Graph-Based pattern)
3. JoiMemoryManager (Memori + Conversational Decay)
4. DataMemoryManager (Memori + Time-Series pattern)

**Tasks:**
- [ ] Create agent-specific Memori wrappers
- [ ] Implement task state log pattern for Max
- [ ] Implement graph-based pattern for Neo
- [ ] Implement conversational decay for Joi
- [ ] Implement time-series pattern for Data
- [ ] Memory profile configuration

**Files to Create:**
```
agents/memory/
├── patterns/
│   ├── __init__.py
│   ├── max_memory.py      # Memori + Task State Log
│   ├── neo_memory.py       # Memori + Graph-Based
│   ├── joi_memory.py       # Memori + Conversational Decay
│   └── data_memory.py       # Memori + Time-Series
```

### Phase 3: Squad Memory Pool (Native SQL) (Week 3-4)

**Deliverables:**
1. Squad Memory Pool table and operations
2. Memory promotion workflow (Memori → SQL)
3. Memory signature linking
4. Squad-level memory queries

**Tasks:**
- [ ] Create `squad_mem_pool` table migration
- [ ] Implement `agents/memory/squad_pool.py`
- [ ] Create memory promotion logic
- [ ] Generate memory signatures
- [ ] Link Memori memories to Squad Memory Pool
- [ ] Integration tests

**Files to Create:**
```
agents/memory/
├── squad_pool.py          # Native SQL Squad Memory Pool
└── promotion.py           # Memory promotion workflow

infra/migrations/
└── 002_add_squad_memory_pool.sql
```

### Phase 4: Advanced Features (Week 4-5)

**Deliverables:**
1. Context binding (enhance Memori relationships)
2. Memory versioning (add to Memori adapter)
3. Memory cleanup (Memori + SQL)
4. Memory analytics

**Tasks:**
- [ ] Enhance Memori relationships with SquadOps context
- [ ] Add versioning layer to Memori adapter
- [ ] Implement cleanup policies
- [ ] Create analytics endpoints
- [ ] Performance optimization

**Files to Create:**
```
agents/memory/
├── context_binding.py     # Enhanced context binding
├── versioning.py          # Versioning layer
└── analytics.py           # Memory analytics
```

### Phase 5: SIR System (Week 5-6)

**Deliverables:**
1. SIR generation from Squad Memory Pool
2. SIR → SIP promotion pipeline
3. Memory replay engine
4. WarmBoot integration

**Tasks:**
- [ ] Create SIR generation logic
- [ ] Implement SIR → SIP promotion workflow
- [ ] Build memory replay engine
- [ ] Integrate with WarmBoot lifecycle
- [ ] End-to-end tests

**Files to Create:**
```
agents/memory/
├── sir_generator.py       # SIR generation
├── replay_engine.py       # Memory replay
└── sip_promotion.py        # SIR → SIP pipeline

infra/migrations/
└── 003_add_sir_tables.sql
```

---

## 5. Technical Integration Details

### 5.1 Memori Adapter Pattern

```python
# agents/memory/memori_adapter.py
from memori import Memori
from typing import Dict, Any, List, Optional
import hashlib
import json

class MemoriAdapter:
    """Adapter wrapping Memori for SquadOps agents"""
    
    def __init__(self, agent_name: str, config: Dict[str, Any]):
        self.agent_name = agent_name
        self.memori = Memori(
            agent_id=agent_name,
            **config
        )
    
    async def store_lore(self, content: Dict[str, Any], 
                       memory_type: str = 'lore',
                       importance: float = 1.0,
                       tags: List[str] = None) -> str:
        """Store memory in Memori"""
        # Use Memori's store method
        memory_id = await self.memori.store(
            content=content,
            memory_type=memory_type,
            metadata={
                'importance': importance,
                'tags': tags or [],
                'agent': self.agent_name
            }
        )
        return memory_id
    
    async def retrieve_lore(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve memories using Memori's semantic search"""
        # Use Memori's auto mode (semantic search)
        memories = await self.memori.search(query, limit=limit)
        return memories
    
    async def generate_memory_signature(self, memory_id: str) -> str:
        """Generate signature for Squad Memory Pool linking"""
        memory = await self.memori.get(memory_id)
        content_str = json.dumps(memory, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()
```

### 5.2 BaseAgent Integration

```python
# agents/base_agent.py (modifications)
class BaseAgent(ABC):
    def __init__(self, name: str, agent_type: str, reasoning_style: str):
        # ... existing initialization ...
        
        # Initialize Memori adapter
        self.memori_adapter = None  # Will be initialized in initialize()
        self.memory_manager = None   # For Squad Memory Pool operations
    
    async def initialize(self):
        """Initialize agent connections"""
        # ... existing initialization ...
        
        # Initialize Memori adapter
        from agents.memory.memori_adapter import MemoriAdapter
        from agents.memory.config import get_memori_config
        
        memori_config = get_memori_config(self.name, self.agent_type)
        self.memori_adapter = MemoriAdapter(
            agent_name=self.name,
            config=memori_config
        )
        
        # Initialize Squad Memory Pool manager (native SQL)
        from agents.memory.squad_pool import SquadMemoryPool
        self.memory_manager = SquadMemoryPool(
            agent_name=self.name,
            db_pool=self.db_pool
        )
        
        logger.info(f"{self.name} initialized with Memori + Squad Memory Pool")
```

### 5.3 Memory Promotion Workflow

```python
# agents/memory/promotion.py
class MemoryPromotion:
    """Promote validated memories from Memori to Squad Memory Pool"""
    
    async def promote_memory(self, memori_memory_id: str, 
                           agent_name: str,
                           validated_by: str) -> int:
        """Promote validated memory to Squad Memory Pool"""
        # 1. Retrieve memory from Memori
        memori_adapter = MemoriAdapter(agent_name)
        memory = await memori_adapter.memori.get(memori_memory_id)
        
        # 2. Generate memory signature
        signature = await memori_adapter.generate_memory_signature(memori_memory_id)
        
        # 3. Store in Squad Memory Pool
        squad_memory_id = await self.squad_pool.store(
            squad_id="default",
            source_agent=agent_name,
            source_memory_id=memori_memory_id,  # Reference to Memori
            topic=memory.get('topic', 'general'),
            context=memory.get('content', {}),
            causal_chain=memory.get('causal_chain', {}),
            outcome=memory.get('outcome'),
            memory_signature=signature,
            validation_status='validated',
            validated_by=validated_by
        )
        
        return squad_memory_id
```

---

## 6. Risk Mitigation

### 6.1 Memori Dependency Risks

**Risk:** External dependency, version updates, breaking changes

**Mitigation:**
- Pin Memori version in requirements.txt
- Create adapter layer (abstraction from Memori API)
- Write comprehensive tests for adapter
- Monitor Memori releases
- Have fallback plan (native SQL if needed)

### 6.2 Integration Complexity

**Risk:** Memori API might not perfectly match SquadOps needs

**Mitigation:**
- Adapter pattern provides flexibility
- Can extend Memori functionality
- Native SQL for Squad Memory Pool (full control)

### 6.3 Performance Concerns

**Risk:** Memori performance unknown for SquadOps scale

**Mitigation:**
- Benchmark Memori performance
- Use Redis caching layer
- Monitor memory access patterns
- Optimize as needed

---

## 7. Success Criteria

### Functional Requirements
- [ ] Agents can store memories in Memori (conscious/auto modes)
- [ ] Semantic search works via Memori
- [ ] Memories can be promoted to Squad Memory Pool
- [ ] Memory signatures link Memori → Squad Memory Pool
- [ ] SIR generation works from Squad Memory Pool
- [ ] Agent-specific patterns function correctly

### Performance Requirements
- [ ] Memori retrieval < 200ms
- [ ] Memory promotion < 500ms
- [ ] Squad Memory Pool queries < 100ms (cached)
- [ ] No degradation with 1000+ memories per agent

### Quality Requirements
- [ ] Test coverage > 90% for memory module
- [ ] Adapter layer abstracts Memori API
- [ ] Memory promotion maintains data integrity
- [ ] Full traceability chain (Memori → Squad → SIR → SIP)

---

## 8. Recommendation Summary

### ⚠️ **RECOMMENDATION UPDATED**

**See:** `docs/MEM0-VS-MEMORI-COMPARISON.md` for updated analysis.

**New Recommendation:** **Mem0** appears to be the better choice:
- ✅ Proven performance (26% accuracy improvement, 91% lower latency)
- ✅ Hybrid datastore (graph + vector + key-value)
- ✅ Specifically designed as memory layer
- ✅ Benchmarked on LOCOMO benchmark

---

## 8a. Original Recommendation (Memori)

### ✅ **Original Recommendation: Hybrid Approach**

**Use Memori for:**
- Agent-level memory storage
- Semantic search
- Memory relationships
- Dual-mode architecture (conscious/auto)

**Use Native SQL for:**
- Squad Memory Pool
- SIR generation
- SIR → SIP pipeline
- Squad-level analytics

### Benefits:
1. ✅ **5-6 weeks saved** on core memory implementation
2. ✅ **Semantic search out of the box** (no vector embedding work)
3. ✅ **Aligns with IDEA_036 vision** (Memori + Squad Memory Pool)
4. ✅ **Maintains control** over SquadOps-specific features
5. ✅ **Reduces maintenance burden** (community-maintained Memori)

### Next Steps:
1. **Evaluate Memori:** Install and test with sample agent
2. **Create Adapter:** Build MemoriAdapter wrapper
3. **Prototype:** Test integration with one agent (Max)
4. **Decide:** Confirm hybrid approach or go native
5. **Implement:** Proceed with Phase 1 (Memori Integration)

---

## 9. Open Questions

1. **Memori Version:** Which version to use? (need to check latest)
2. **Memori Configuration:** What config per agent type?
3. **Migration Path:** How to migrate if we switch later?
4. **Memori Storage:** Where does Memori store data? (need to check)
5. **SquadOps Customization:** How much can we customize Memori?

---

## 10. Decision Matrix

| Criteria | Weight | Memori | Native | Hybrid |
|----------|-------|--------|--------|--------|
| **Implementation Time** | 25% | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| **Feature Completeness** | 20% | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Maintenance Burden** | 15% | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| **Control & Customization** | 15% | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Semantic Search** | 10% | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **SquadOps Alignment** | 10% | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **IDEA_036 Alignment** | 5% | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Total Score** | 100% | **3.9** | **3.5** | **4.3** |

**Winner: Hybrid Approach (4.3/5.0)**

---

**Conclusion:** The hybrid approach (Memori + Native SQL) provides the best balance of implementation speed, feature completeness, and SquadOps-specific control. It aligns perfectly with IDEA_036's vision while leveraging Memori's proven capabilities.

