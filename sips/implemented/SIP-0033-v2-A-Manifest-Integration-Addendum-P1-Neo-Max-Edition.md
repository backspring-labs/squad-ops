---
sip_uid: "17642554775942955"
sip_number: 33
title: "-SIP-033A-Manifest-Integration-Addendum-P1-Neo-Max-Edition"
status: "implemented"
author: "Unknown"
approver: "None"
created_at: "2025-10-15T00:00:00Z"
updated_at: "2025-11-27T10:12:48.899626Z"
original_filename: "SIP-033A-Manifest-Integration-Addendum-P1.md"
---

# 🧩 SIP-033A: Manifest Integration Addendum (P1 – Neo + Max Edition)

**Version:** 0.9 (Phase-1)  
**Date:** 2025-10-15  
**Extends:** `SIP-033_Structured_Code_Request_Protocol.md`  
**Applies To:** Neo (Developer Orchestrator), Max (Governance & Logging)  
**Next Revision:** Will expand to include Devin, EVE, and Data in Phase-2  

---

## 🧭 Purpose
Describe how **Neo** parses a local **architecture manifest** and transforms it into a valid `SIP-033` JSON payload for code generation through Ollama, while **Max** provides minimal governance and logging.  
This lets Neo build and deploy small WarmBoot apps locally (like *Hello Squad*) with structured, markdown-free outputs.

---

## ⚙️ Simplified Roles

| Agent | Phase-1 Responsibility |
|:------|:------------------------|
| **Neo** | Read manifest, generate JSON request, call Ollama, write files. |
| **Max** | Validate PID alignment, record manifest snapshot and checksums. |

---

## 🧩 Workflow Overview
```
architecture_manifest.yaml
        ↓
Neo → build JSON payload → send to Ollama
        ↓
Ollama → JSON code output → Neo writes files
        ↓
Max → log PID, manifest, and file checksums
```

---

## 🧱 Manifest Example
```yaml
project: hello_squad
language: python
framework: fastapi
modules:
  - name: api
    files:
      - path: app.py
        description: "FastAPI entrypoint returning Hello Squad!"
  - name: tests
    files:
      - path: test_app.py
        description: "Basic route test"
dependencies: [fastapi, uvicorn]
entrypoint: app.py
```

---

## 🧩 Neo Translation Logic
```python
manifest = yaml.safe_load(open("architecture_manifest.yaml"))
context = {
    "framework": manifest["framework"],
    "language": manifest["language"],
    "output_dir": f"/workspace/{manifest['project']}",
    "requirements": manifest.get("dependencies", [])
}
deliverables = [
    {"path": f["path"], "description": f.get("description", "")}
    for m in manifest["modules"] for f in m["files"]
]
payload = {
    "type": "code_request",
    "pid": "PID-016",
    "objective": f"Generate {manifest['project']} per manifest",
    "context": context,
    "deliverables": deliverables,
    "manifest_ref": "architecture_manifest.yaml",
    "format": "json",
    "instructions": "Return only JSON using defined schema."
}
```

Neo posts this `payload.json` to Ollama:
```bash
curl http://localhost:11434/api/generate -d @payload.json
```

---

## 🧠 Response Handling
```python
for f in response["files"]:
    path = Path(f"/workspace/{f['path']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f["content"])
```

---

## 🧾 Max Governance Actions

| Task | Description |
|:------|:-------------|
| PID Validation | Confirm `pid` matches request. |
| Manifest Snapshot | Copy manifest to `/logs/PID-###_manifest.yaml`. |
| Checksum | SHA-256 each generated file. |
| Registry Entry | Append `{pid,status,checksums}` JSON record to local registry. |

---

## 🧱 Local Directory Layout
```
/workspace/hello_squad/
    app.py
    test_app.py
    requirements.txt
/logs/
    PID-016_manifest.yaml
    PID-016_checksums.json
```

---

## 🧭 Phase-1 Behavior Summary

| Aspect | Neo Action | Max Action |
|:--------|:------------|:------------|
| Manifest Parsing | Load & extract deliverables. | – |
| Payload Assembly | Inject manifest context. | – |
| Model Call | Send to Ollama and receive JSON. | – |
| File Write | Write outputs to workspace. | – |
| Governance | – | Validate PID, record checksums. |

---

## ✅ Outcomes
- No markdown cleanup required.  
- Full reproducibility via manifest + PID log.  
- Minimal resource use; works offline or on MacBook/Spark.  
- Forward-compatible with future agents (Devin and EVE).

---

> _SIP-033A (P1) establishes Neo’s manifest-to-JSON translation process and Max’s lightweight governance path, forming the foundation for autonomous code generation in resource-limited deployments._
