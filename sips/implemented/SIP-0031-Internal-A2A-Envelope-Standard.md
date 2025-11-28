---
sip_uid: "17642554775939368"
sip_number: 31
title: "-SIP-031-Internal-A2A-Envelope-Standard"
status: "implemented"
author: "Nexa_Squad Core Team"
approver: "None"
created_at: "2025-10-15T00:00:00Z"
updated_at: "2025-11-27T10:12:48.897984Z"
original_filename: "SIP-031-Internal-A2A-Envelope-Standard.md"
---

# 🧠 SIP-031: Internal A2A Envelope Standard

**Status:** Draft  
**Version:** v0.1  
**Date:** 2025-10-15  
**Author:** Nexa_Squad Core Team  
**Applies To:** `SquadComms`, `SquadNet`, `SOC`, `WarmBoot` telemetry  
**Parent Protocol:** SquadComms Architecture  
**Related Standards:** [Linux Foundation A2A Protocol](https://github.com/a2aproject/A2A)

---

## 📌 Purpose

To align **all internal agent-to-agent communication within SquadOps** to the industry-standard **A2A JSON envelope** format while preserving **RabbitMQ** as the preferred low-latency internal transport.  
This ensures:
- Message consistency across transports (MQ and HTTP/WS)
- Simplified logging and traceability  
- Future interoperability with A2A-compliant external agents

---

## ⚙️ Motivation

Currently, internal SquadComms messages follow a proprietary JSON schema.  
The Linux Foundation’s **A2A protocol** has emerged as the leading industry standard for agent messaging.  
By adopting its envelope structure internally:
- We remove schema translation between MQ and HTTP endpoints  
- Simplify audit and telemetry integration  
- Prepare SquadOps for external federation with minimal future lift

---

## 🧩 Specification

### 1. Envelope Schema (v0.1)
```json
{
  "id": "msg-<UUID>",
  "from": "agent://<sender>",
  "to": "agent://<recipient>",
  "type": "TASK_REQUEST | TASK_UPDATE | TASK_COMPLETE | STATUS_QUERY | BROADCAST | CONSULTATION | ERROR",
  "timestamp": "2025-10-15T17:30:00Z",
  "urgency": "normal | high | governance_override",
  "context": {
    "pid": "PID-###",
    "cycle": "WarmBoot-###",
    "repo": "https://github.com/org/repo",
    "task_id": "TID-###"
  },
  "payload": {
    "description": "Short instruction or artifact summary",
    "data": {}
  }
}
```

### 2. Pydantic Reference Model
```python
from pydantic import BaseModel
from typing import Dict, Any

class A2AEnvelope(BaseModel):
    id: str
    from_: str
    to: str
    type: str
    timestamp: str
    urgency: str = "normal"
    context: Dict[str, Any]
    payload: Dict[str, Any]
```

---

## 🔄 Usage Rules

| Layer | Transport | Schema | Description |
|-------|------------|---------|-------------|
| **Internal (default)** | RabbitMQ / NATS | A2A JSON | Max ↔ Neo, Neo ↔ EVE, etc. |
| **External (optional)** | HTTP(S) / WebSocket | A2A JSON | External agent or partner integration |
| **Logging** | Postgres / Prometheus | A2A JSON | Unified message trace in `agent_task_logs` |

---

## 🔒 Governance & Security

- Internal MQ traffic is trusted within `squadnet`, but still logged for PID traceability.  
- External A2A endpoints require **OIDC tokens (Keycloak)** or **mTLS**.  
- Governance messages marked with `urgency: governance_override` must be validated by **Max** before execution.

---

## 📈 Benefits

| Benefit | Detail |
|----------|--------|
| **Interoperability** | Seamless routing of same envelope via MQ or HTTP |
| **Observability** | Unified telemetry schema for logs, dashboards, WarmBoot analytics |
| **Governance** | Easier audit of message lineage and task provenance |
| **Future-Proofing** | Ready for cross-squad federation and Linux Foundation A2A compliance |
| **Simplicity** | One serializer/deserializer for all communication layers |

---

## 🧠 Implementation Steps

1. **Define shared envelope model** (`/models/a2a_envelope.py`).  
2. **Update SquadComms publisher/consumer** to serialize/deserialize A2AEnvelope JSON.  
3. **Store raw JSON** in:
   - `agent_task_logs`
   - `squadcomms_messages`  
4. **A2A Gateway** (FastAPI) will use identical envelope for `/a2a/message`.  
5. **WarmBoot telemetry** logs the full envelope for replay or audit.

---

## 🧭 Backward Compatibility

- Legacy message formats are accepted during a deprecation window (two WarmBoot cycles).  
- MQ adapters may auto-upgrade old schema → A2AEnvelope v0.1.

---

## 🧩 Future Enhancements

- v0.2: Add digital signatures and hash verification fields  
- v0.3: Register envelope schema ID with public A2A registry  
- v0.4: Introduce compression for large payloads (zstd)  

---

## 🪶 Appendix: Example Internal Message

```json
{
  "id": "msg-2025-0101",
  "from": "agent://max",
  "to": "agent://neo",
  "type": "TASK_REQUEST",
  "timestamp": "2025-10-15T17:33:00Z",
  "urgency": "normal",
  "context": { "pid": "PID-007", "cycle": "WarmBoot-021" },
  "payload": { "description": "Build mock API for HelloSquad" }
}
```

---

**Result:**  
All internal and external agent communication in SquadOps now adheres to a **unified A2A-compliant message envelope**, enabling direct interoperability and streamlined governance.

---
