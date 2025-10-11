# 🎯 SquadOps Test Level Guide
## When to Use Which Test Level

**Purpose**: Choose the right test level for your development phase  
**Goal**: Balance speed vs safety based on your current needs  

---

## 🚀 **Test Levels Overview**

| Level | Command | Time | Purpose | When to Use |
|-------|---------|------|---------|-------------|
| **Smoke** | `./tests/run_tests.sh smoke` | 30s | Basic health check | Quick confidence check |
| **Unit** | `./tests/run_tests.sh unit` | 1-2m | Core logic validation | After code changes |
| **Regression** | `./tests/run_tests.sh regression` | 2-3m | Critical workflow safety | Before commits |
| **Integration** | `./tests/run_tests.sh integration` | 3-5m | Component interactions | After major changes |
| **All** | `./tests/run_tests.sh all` | 5-10m | Complete validation | Before releases |

---

## 🎯 **Development Phase Guide**

### **Phase 1: Active Development** 🔥
*You're actively coding with AI assistance*

#### **Use: Smoke Test** ⏱️ 30 seconds
```bash
./tests/run_tests.sh smoke
```
**When:**
- After each AI-assisted change
- Before switching to different tasks
- When you want quick confidence
- During rapid iteration cycles

**What it tests:**
- Basic agent initialization
- Core agent functionality
- No external dependencies

**Perfect for:** "Did I break something obvious?"

---

### **Phase 2: Code Review** 🔍
*You've made changes and want to validate them*

#### **Use: Unit Tests** ⏱️ 1-2 minutes
```bash
./tests/run_tests.sh unit
```
**When:**
- After completing a feature
- Before moving to integration testing
- When you've modified agent logic
- After refactoring code

**What it tests:**
- Individual agent methods
- Core business logic
- Agent behavior consistency
- Configuration validation

**Perfect for:** "Do my changes work as expected?"

---

### **Phase 3: Pre-Commit Safety** 🛡️
*You're ready to commit but want to be sure*

#### **Use: Regression Tests** ⏱️ 2-3 minutes
```bash
./tests/run_tests.sh regression
```
**When:**
- Before every commit
- After major changes
- When you've modified core workflows
- Before sharing code with others

**What it tests:**
- PRD → Task → Agent workflows
- Agent communication patterns
- Task lifecycle management
- Version management
- Governance decisions

**Perfect for:** "Did I break any critical workflows?"

---

### **Phase 4: Integration Validation** 🔗
*You've made changes that affect multiple components*

#### **Use: Integration Tests** ⏱️ 3-5 minutes
```bash
./tests/run_tests.sh integration
```
**When:**
- After modifying agent communication
- When you've changed database schema
- After updating infrastructure services
- Before major releases

**What it tests:**
- Agent-to-agent messaging
- Database operations
- Service interactions
- API endpoints
- Container operations

**Perfect for:** "Do all the pieces work together?"

---

### **Phase 5: Release Preparation** 🚀
*You're preparing for a release or major milestone*

#### **Use: All Tests** ⏱️ 5-10 minutes
```bash
./tests/run_tests.sh all
```
**When:**
- Before major releases
- Before deploying to production
- When you want complete confidence
- After major refactoring

**What it tests:**
- Everything above, plus:
- Performance benchmarks
- Memory usage
- Error handling
- Edge cases

**Perfect for:** "Is everything ready for production?"

---

## 🎯 **AI-Assisted Development Workflow**

### **During Rapid Development** 🔥
```bash
# 1. Start your AI-assisted coding session
./tests/run_tests.sh smoke    # Quick health check

# 2. Make changes with AI assistance
# ... your rapid development ...

# 3. Check if you broke anything obvious
./tests/run_tests.sh smoke    # 30 seconds

# 4. Continue or fix and repeat
```

### **Before Taking a Break** ☕
```bash
# You've made several changes, want to commit
./tests/run_tests.sh unit     # 1-2 minutes
# If passes, you're good to take a break
# If fails, fix quickly before break
```

### **Before Committing** 💾
```bash
# You're ready to commit your changes
./tests/run_tests.sh regression    # 2-3 minutes
# Only commit if this passes!
```

### **Before Major Milestones** 🎯
```bash
# You're preparing for a release or demo
./tests/run_tests.sh all      # 5-10 minutes
# Complete confidence before big moments
```

---

## 🚨 **Emergency Situations**

### **"I Think I Broke Something"** 🚨
```bash
# Quick check - 30 seconds
./tests/run_tests.sh smoke

# If that passes, deeper check - 2-3 minutes  
./tests/run_tests.sh regression

# If that fails, you know exactly what broke
```

### **"AI Suggestion Seems Risky"** 🤖
```bash
# Test the change before committing
./tests/run_tests.sh unit     # 1-2 minutes
# If passes, the AI suggestion is probably safe
# If fails, the AI suggestion broke something
```

### **"I Lost Track of What Changed"** 😵
```bash
# Run regression tests to see what's broken
./tests/run_tests.sh regression    # 2-3 minutes
# The test failures will tell you exactly what changed
```

---

## 📊 **Test Level Decision Tree**

```
Start Here
    ↓
Are you actively coding? 
    ↓ YES                    ↓ NO
    ↓                        ↓
Quick health check?          Ready to commit?
    ↓ YES        ↓ NO         ↓ YES        ↓ NO
    ↓            ↓            ↓            ↓
SMOKE          UNIT        REGRESSION    INTEGRATION
(30s)         (1-2m)       (2-3m)        (3-5m)
    ↓            ↓            ↓            ↓
Continue      Fix issues   Commit if    Fix issues
coding        if needed    passes       if needed
```

---

## 🎯 **Pro Tips**

### **Speed vs Safety Trade-offs**
- **Smoke**: Fastest feedback, catches obvious breaks
- **Unit**: Good balance of speed and coverage
- **Regression**: Best safety net for critical workflows
- **Integration**: Thorough but slower
- **All**: Complete confidence but slowest

### **When in Doubt**
```bash
# Start with smoke test
./tests/run_tests.sh smoke

# If that passes, try unit tests
./tests/run_tests.sh unit

# If that passes, you're probably safe
# If anything fails, fix it before continuing
```

### **Continuous Development**
```bash
# Set up a watch for continuous testing
pip install pytest-watch
ptw tests/unit/ -- -m "not slow"
# Now tests run automatically as you code!
```

---

## 🎉 **Summary**

**Choose your test level based on:**
- **How much time you have** (30s vs 10m)
- **How risky your changes are** (small tweak vs major refactor)
- **What phase you're in** (active coding vs pre-commit)
- **How much confidence you need** (quick check vs complete validation)

**Remember:** It's better to run a quick smoke test than no test at all! 🚀


