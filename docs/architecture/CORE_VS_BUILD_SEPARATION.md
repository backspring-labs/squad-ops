# 🏗️ Core Framework vs Build Container Separation
## Strategic Architecture Decision for SquadOps

**Date**: January 2025  
**Purpose**: Define what belongs in core framework vs local build containers  
**Goal**: Maintain stable core while enabling rapid WarmBoot iterations  

---

## 🎯 **Core Framework (Stable, Versioned)**

### **What Stays in Core**
These components form the **stable foundation** and should be carefully versioned:

#### **1. Agent Architecture** (`agents/`)
- ✅ **BaseAgent class** - Core agent functionality
- ✅ **Agent roles** - Lead, Dev, QA, etc. (core logic only)
- ✅ **Agent factory** - Agent instantiation system
- ✅ **Communication protocols** - RabbitMQ messaging
- ✅ **Agent configuration** - Role definitions, capabilities

#### **2. Infrastructure Services** (`infra/`)
- ✅ **Task Management API** - Core task lifecycle
- ✅ **Health Check Service** - System monitoring
- ✅ **Database schema** - Core tables and indexes
- ✅ **Docker Compose** - Service orchestration
- ✅ **Configuration management** - Environment settings

#### **3. Core Protocols** (`docs/SIPs/`)
- ✅ **SIP definitions** - Protocol specifications
- ✅ **Architecture decisions** - Design patterns
- ✅ **Governance rules** - Business logic
- ✅ **Compliance frameworks** - Regulatory requirements

#### **4. Framework Utilities** (`config/`, `scripts/`)
- ✅ **Version management** - Framework versioning
- ✅ **Deployment configs** - Core deployment settings
- ✅ **Migration scripts** - Database schema changes
- ✅ **CLI tools** - Framework management
- ✅ **Build script** - Agent package assembly (`scripts/build_agent.py`)

#### **5. Build Artifacts** (`dist/agents/{role}/`)
- ✅ **manifest.json** - Build artifact metadata (what was built)
  - Schema version: `manifest_version: "1.0"`
  - Includes: capabilities, skills, shared_modules, resolver_graph, files_included, build_hash, git_commit, build_time_utc, squadops_version
  - Purpose: Deterministic build tracking, debugging, RCA
- ✅ **agent_info.json** - Runtime identity metadata (who is running)
  - Schema version: `agent_info_version: "1.0"`
  - Includes: role, agent_id, capabilities, skills, build_hash, container_hash, runtime_env, startup_time_utc, agent_entrypoint
  - Purpose: Runtime introspection, observability, debugging container drift
- ✅ **Build Hash** - SHA256 hash of all files in `dist` directory (excluding manifest files)
  - Ensures deterministic builds
  - Propagates through both `manifest.json` and `agent_info.json`
  - Can be used as Docker LABEL for registry-level introspection

---

## 🚀 **Build Container (Dynamic, Iterative)**

### **What Goes to Build Container**
These components are **generated during WarmBoot** and should be isolated:

#### **1. Generated Applications** (`warm-boot/apps/`)
- 🔄 **Application code** - HTML, CSS, JS, Dockerfiles
- 🔄 **Application configs** - App-specific settings
- 🔄 **Application assets** - Images, fonts, data files
- 🔄 **Application documentation** - App-specific docs

#### **2. WarmBoot Artifacts** (`warm-boot/runs/`)
- 🔄 **Run logs** - Execution traces and debug info
- 🔄 **Generated reports** - Analysis and metrics
- 🔄 **Temporary files** - Build artifacts and caches
- 🔄 **Test results** - Application-specific test outputs

#### **3. Development Iterations** (`warm-boot/archive/`)
- 🔄 **Version archives** - Previous application versions
- 🔄 **Build artifacts** - Compiled code and assets
- 🔄 **Deployment packages** - Container images and configs
- 🔄 **Rollback snapshots** - Previous working states

#### **4. Experimental Features** (`warm-boot/experiments/`)
- 🔄 **Prototype code** - Experimental implementations
- 🔄 **A/B test variants** - Different implementation approaches
- 🔄 **Performance tests** - Load testing and benchmarks
- 🔄 **Integration tests** - End-to-end test scenarios

---

## 🎯 **Separation Strategy**

### **Core Framework Principles**
1. **Stability First** - Core changes require careful review
2. **Backward Compatibility** - Maintain API contracts
3. **Version Control** - Semantic versioning for releases
4. **Documentation** - Comprehensive docs for all changes
5. **Testing** - Full test coverage for core components

### **Build Container Principles**
1. **Rapid Iteration** - Fast development cycles
2. **Experimentation** - Try new approaches safely
3. **Isolation** - No impact on core stability
4. **Cleanup** - Regular cleanup of old artifacts
5. **Portability** - Easy to move between environments

---

## 🏗️ **Implementation Architecture**

### **Core Framework Structure**
```
squad-ops/
├── agents/                 # ✅ CORE - Agent architecture
├── infra/                  # ✅ CORE - Infrastructure services
├── config/                 # ✅ CORE - Configuration management
├── docs/                   # ✅ CORE - Documentation and protocols
├── scripts/                # ✅ CORE - Framework utilities (includes build_agent.py)
├── tests/                  # ✅ CORE - Test harness
├── docker-compose.yml      # ✅ CORE - Service orchestration
└── dist/                   # 🔄 BUILD - Build artifacts (gitignored, generated by build script)
```

### **Build Container Structure**
```
build-container/
├── warm-boot/
│   ├── apps/               # 🔄 BUILD - Generated applications
│   ├── runs/               # 🔄 BUILD - Execution artifacts
│   ├── archive/            # 🔄 BUILD - Version archives
│   └── experiments/        # 🔄 BUILD - Experimental features
├── local-config/           # 🔄 BUILD - Local overrides
├── temp/                   # 🔄 BUILD - Temporary files
└── logs/                   # 🔄 BUILD - Build logs

# Note: dist/agents/ is also a build artifact (container-ready agent packages)
# Generated by scripts/build_agent.py, used by Dockerfiles for container builds
```

---

## 🔄 **Workflow Separation**

### **Core Development Workflow**
1. **Feature Planning** - SIP creation and review
2. **Implementation** - Core framework changes
3. **Testing** - Comprehensive test suite
4. **Review** - Code review and approval
5. **Release** - Versioned release with changelog

### **Build Container Workflow**
1. **WarmBoot Init** - Start new build container
2. **Rapid Development** - Fast iteration cycles
3. **Testing** - Application-specific tests
4. **Deployment** - Deploy to target environment
5. **Cleanup** - Archive and cleanup artifacts

---

## 🎯 **Benefits of Separation**

### **Core Framework Benefits**
- ✅ **Stability** - Reliable foundation for all builds
- ✅ **Consistency** - Standardized agent behavior
- ✅ **Maintainability** - Clear separation of concerns
- ✅ **Scalability** - Framework scales independently
- ✅ **Security** - Controlled access to core components

### **Build Container Benefits**
- ✅ **Speed** - Rapid development cycles
- ✅ **Experimentation** - Safe to try new approaches
- ✅ **Isolation** - No risk to core stability
- ✅ **Flexibility** - Custom configurations per build
- ✅ **Cleanup** - Easy to reset and start fresh

---

## 🚀 **Migration Strategy**

### **Phase 1: Identify Components** (Week 1)
- [ ] Audit current codebase
- [ ] Categorize components (Core vs Build)
- [ ] Create migration plan
- [ ] Set up build container structure

### **Phase 2: Implement Separation** (Week 2)
- [ ] Move build components to container
- [ ] Update build scripts
- [ ] Test separation
- [ ] Update documentation

### **Phase 3: Optimize Workflows** (Week 3)
- [ ] Optimize core development workflow
- [ ] Optimize build container workflow
- [ ] Implement cleanup procedures
- [ ] Create monitoring and alerts

---

## 📊 **Success Metrics**

### **Core Framework Metrics**
- ✅ **Stability** - Zero regressions in core functionality
- ✅ **Performance** - Consistent performance across versions
- ✅ **Test Coverage** - 90%+ coverage for core components
- ✅ **Documentation** - 100% API documentation coverage

### **Build Container Metrics**
- ✅ **Speed** - 50% faster development cycles
- ✅ **Isolation** - Zero impact on core stability
- ✅ **Cleanup** - Automated cleanup of old artifacts
- ✅ **Portability** - Easy deployment across environments

---

## 🎯 **Key Insights**

1. **Core Stability** - Keep the foundation rock-solid
2. **Build Flexibility** - Enable rapid experimentation
3. **Clear Boundaries** - Well-defined separation of concerns
4. **Automated Cleanup** - Prevent build container bloat
5. **Version Control** - Proper versioning for both layers

---

**This separation enables rapid AI-assisted development while maintaining a stable, reliable core framework!** 🚀


