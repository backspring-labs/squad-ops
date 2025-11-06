# Recommendation: Mem0 with Local Embeddings (Ollama) for SquadOps

**Date:** 2025-11-05  
**Status:** ⚠️ **DEPRECATED** - Migrated to LanceDB  
**Context:** Mem0 required OpenAI API key, breaking offline builds  
**Migration:** See `MEMORY_LANCEDB_RECOMMENDATION.md` for current implementation

---

## ⚠️ Superseded by LanceDB

This document is kept for historical reference. The current implementation uses **LanceDB** instead of Mem0.

**Previous Solution: Mem0 with Ollama Embeddings**

### Key Finding

**Mem0 DOES support local embeddings** - no OpenAI API key required!

- ✅ **Ollama embeddings** - Local embedding model (`nomic-embed-text`)
- ✅ **Hugging Face embeddings** - Alternative local option
- ✅ **SQLite storage** - Local database for history (as per SIP-042)

### Implementation

```python
from mem0.configs.base import MemoryConfig, EmbedderConfig

# Configure Mem0 with Ollama embeddings (local-first)
embedder_config = EmbedderConfig(
    provider='ollama',
    config={
        'model': 'nomic-embed-text:latest',
        'ollama_base_url': 'http://localhost:11434'
    }
)

config = MemoryConfig(
    history_db_path='/app/data/mem0_{agent}.db',
    embedder=embedder_config
)
memory = Memory(config=config)
```

### Benefits

- ✅ **Local-first** - No external APIs required
- ✅ **SIP-042 compliant** - Mem0 SQLite storage as specified
- ✅ **Edge-ready** - Works on Jetson with Ollama
- ✅ **Production-grade** - No single point of failure
- ✅ **Leverages existing infrastructure** - Uses Ollama already in SquadOps stack

### Updated Architecture

```
Agent Memory Flow:
├── record_memory() → Mem0Adapter
├── Mem0Adapter.put()
│   ├── Ollama embeddings (nomic-embed-text) ← Local, no API key!
│   └── SQLite storage (/app/data/mem0_{agent}.db) ← SIP-042 compliant
└── Semantic search via Mem0.get()
```

---

## 🎯 Alignment with SquadOps Objectives

### ✅ Local-First Architecture
- No external API dependencies
- All processing happens locally

### ✅ Edge Deployment Ready
- Works on Jetson Nano with Ollama
- No internet required for embeddings

### ✅ Production-Grade
- No single point of failure (API dependencies)
- Direct database control (SQLite)

### ✅ Leverages Existing Stack
- Uses Ollama (already deployed)
- Consistent with LLM routing architecture

---

## 📋 Implementation Status

**Status:** ✅ **COMPLETE**

1. ✅ Updated `Mem0Adapter._initialize_mem0()` to use Ollama embeddings
2. ✅ Removed OpenAI API key requirement
3. ✅ Configured `nomic-embed-text` model for embeddings
4. ✅ Maintained SQLite storage path (`/app/data/mem0_{agent}.db`)
5. ✅ Added fallback storage for graceful degradation

---

## 🚀 Next Steps

1. **Test with Ollama running** - Verify embeddings work in production
2. **Pull embedding model** - Ensure `nomic-embed-text` is available in Ollama
3. **Monitor performance** - Track embedding generation latency
4. **Optional enhancement** - Add Hugging Face as alternative embedding provider

---

**Decision:** ✅ **USE MEM0 WITH OLLAMA EMBEDDINGS** - Perfect alignment with SquadOps local-first architecture while maintaining SIP-042 compliance.

