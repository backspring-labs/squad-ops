# 🏭 Factory Testability Improvements

## 📊 Current State

**Overall Coverage**: 76%
- ✅ QAAgent: 83%
- ✅ AuditAgent: 91%
- ✅ LeadAgent: 74%
- ⚠️ AgentFactory: 74%
- ⚠️ RoleFactory: 62%

## 🎯 Goal: 90% Coverage

To reach 90%, we need to improve AgentFactory and RoleFactory coverage by ~8 percentage points each.

## 🔍 Current Blockers

### RoleFactory (62% coverage)

**Issue**: Hard-coded file system dependencies
```python
def __init__(self, registry_file: str = "agents/roles/registry.yaml"):
    self.registry_file = registry_file
    self.roles = self._load_roles()  # Loads from disk immediately
```

**What's untested** (38% missing):
- `create_role_files()` - Creates actual files on disk
- `_load_roles()` - Reads YAML from specific path
- `generate_agent_class()` - String generation (works but untested)
- `validate_role_registry()` - File system checks

**Testing challenges**:
- Tests run from `/Users/jladd/squad-ops/tests`
- Code expects files at `agents/roles/registry.yaml` (relative to project root)
- Would need complex mocking or temporary file fixtures

### AgentFactory (74% coverage)

**Issue**: Static methods with file system dependencies
```python
@staticmethod
def get_available_roles():
    """Get list of available agent roles"""
    import os
    roles_dir = "agents/roles"
    if os.path.exists(roles_dir):  # Hard-coded path
        return [d for d in os.listdir(roles_dir) 
               if os.path.isdir(os.path.join(roles_dir, d))]
    return []
```

**What's untested** (26% missing):
- `create_agents_from_instances()` - Error handling paths
- `get_available_roles()` - Directory scanning
- Error recovery in `create_agent()` when imports fail

**Testing challenges**:
- Static methods can't be easily dependency-injected
- Hard-coded relative paths
- Import system mocking is complex

## 💡 Proposed Solutions

### Option 1: Dependency Injection (Recommended)

**RoleFactory**:
```python
def __init__(self, registry_file: str = "agents/roles/registry.yaml", 
             file_reader: Optional[Callable] = None):
    self.registry_file = registry_file
    self.file_reader = file_reader or self._default_file_reader
    self.roles = self._load_roles()

def _default_file_reader(self, path: str) -> str:
    """Default file reader - can be mocked in tests"""
    with open(path, 'r') as f:
        return f.read()
```

**AgentFactory**:
```python
@staticmethod
def get_available_roles(roles_dir: str = "agents/roles"):
    """Get list of available agent roles"""
    import os
    if os.path.exists(roles_dir):
        return [d for d in os.listdir(roles_dir) 
               if os.path.isdir(os.path.join(roles_dir, d))]
    return []
```

**Benefits**:
- ✅ Easy to test with mocks
- ✅ Minimal API changes
- ✅ Backward compatible (defaults work as before)

**Effort**: ~30 minutes

### Option 2: Abstract File System Layer

Create a `FileSystemAdapter` class:
```python
class FileSystemAdapter:
    def read_file(self, path: str) -> str:
        with open(path) as f:
            return f.read()
    
    def list_dirs(self, path: str) -> List[str]:
        return [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]
```

**Benefits**:
- ✅ Clean separation of concerns
- ✅ Could support multiple backends (S3, etc.)
- ✅ Very testable

**Drawbacks**:
- ⚠️ Larger refactor
- ⚠️ More abstraction overhead

**Effort**: ~1-2 hours

### Option 3: Test Configuration

Run tests from project root instead of `tests/`:
```python
# pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
# Run from project root
rootdir = .
```

**Benefits**:
- ✅ No code changes needed
- ✅ Paths work correctly

**Drawbacks**:
- ⚠️ Doesn't fix the coupling issue
- ⚠️ Still need file mocking for CI/CD

**Effort**: ~10 minutes

## 🎯 Recommendation

**Option 1 (Dependency Injection)** is the sweet spot:
- Minimal code changes
- Backward compatible
- Easy to test
- Follows SOLID principles (Dependency Inversion)

Would add ~30 minutes of refactoring to reach 90% coverage.

## 📋 Implementation Checklist

If we proceed with Option 1:

### RoleFactory
- [ ] Add optional `file_reader` parameter to `__init__`
- [ ] Extract `_default_file_reader` method
- [ ] Update tests to inject mock file reader
- [ ] Add tests for `create_role_files` with temp directory
- [ ] Add tests for `validate_role_registry` with mocked files

### AgentFactory
- [ ] Add optional `roles_dir` parameter to `get_available_roles`
- [ ] Update `create_agents_from_instances` to accept factory configuration
- [ ] Add tests for error handling in `create_agent`
- [ ] Add tests for `get_available_roles` with mocked directories

### Coverage Target
- [ ] RoleFactory: 62% → 85%+ (+23%)
- [ ] AgentFactory: 74% → 85%+ (+11%)
- [ ] **Overall: 76% → 90%+** 🎯

---

**Next Steps**: Discuss approach and get approval before making framework changes.

