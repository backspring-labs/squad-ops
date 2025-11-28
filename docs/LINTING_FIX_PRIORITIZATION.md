# Linting Error Fix Prioritization Plan

**Created**: 2025-01-28  
**Total Errors**: 1,712  
**Auto-fixable**: 1,382 (with `--fix`)  
**Additional auto-fixable**: 58 (with `--unsafe-fixes`)

## Progress Tracking

- [ ] Phase 1: Auto-fix Safe Issues (1,382 errors)
- [ ] Phase 2: Critical Safety Fixes (62 errors)
- [ ] Phase 3: Code Quality Review (69 errors)
- [ ] Phase 4: Remaining Manual Fixes (~200 errors)

## Error Distribution

| Error Code | Count | Description | Auto-fixable | Priority |
|------------|-------|-------------|--------------|----------|
| UP006 | 548 | Modern type annotations (dict vs Dict) | Yes | High |
| F401 | 257 | Unused imports | Yes | High |
| I001 | 236 | Import sorting | Yes | Medium |
| UP045 | 206 | Optional syntax (X \| None) | Yes | High |
| UP035 | 164 | Deprecated typing imports | Yes | Medium |
| F841 | 69 | Unused variables | Partial | Medium |
| UP015 | 63 | Unnecessary file mode arguments | Yes | Low |
| F541 | 44 | f-strings without placeholders | Yes | Low |
| B904 | 37 | Exception chaining issues | No | **Critical** |
| E722 | 25 | Bare except clauses | No | **Critical** |

## Priority Tiers

### Tier 1: Critical Safety Issues (62 errors)
**Impact**: Can hide bugs, cause runtime errors, or lose error context  
**Risk**: High - May mask real problems

#### E722 - Bare except clauses (25 errors)
- [x] **Status**: Completed
- **Why**: Catches all exceptions including SystemExit/KeyboardInterrupt
- **Action**: Replace with specific exception types
- **Files**: `infra/health-check/main.py` (multiple instances)
- **Manual fix required**: Yes
- **Notes**: Fixed all 25 bare except clauses by replacing with `except Exception:` 

#### B904 - Exception chaining (37 errors)
- [x] **Status**: Completed
- **Why**: Loses original exception context
- **Action**: Add `from err` or `from None` to raise statements
- **Files**: `infra/health-check/main.py` (multiple instances)
- **Manual fix required**: Yes
- **Notes**: Fixed all 37 exception chaining issues by adding `from e` to raise statements 

### Tier 2: Code Quality & Correctness (326 errors)
**Impact**: Dead code, potential bugs, code clarity  
**Risk**: Medium - Indicates potential issues

#### F401 - Unused imports (257 errors)
- [ ] **Status**: Not Started
- **Why**: Dead code, potential typos, import mistakes
- **Action**: Remove unused imports
- **Auto-fixable**: Yes (with `--fix`)
- **Priority**: High - Easy wins, improves clarity
- **Command**: `ruff check --fix .` (will fix this along with others)
- **Notes**: 

#### F841 - Unused variables (69 errors)
- [ ] **Status**: Not Started
- **Why**: Dead code, potential logic errors
- **Action**: Remove or use variables
- **Auto-fixable**: Partial (some require manual review)
- **Priority**: Medium - Review context before removing
- **Notes**: 

### Tier 3: Modernization & Type Safety (918 errors)
**Impact**: Code modernization, better type hints, Python 3.11+ compatibility  
**Risk**: Low - Style improvements

#### UP006 - Modern type annotations (548 errors)
- [ ] **Status**: Not Started
- **Why**: Python 3.9+ supports `dict` instead of `Dict`
- **Action**: Replace `Dict` → `dict`, `List` → `list`, `Tuple` → `tuple`
- **Auto-fixable**: Yes (with `--fix`)
- **Priority**: High - Large volume, easy auto-fix
- **Command**: `ruff check --fix .` (will fix this along with others)
- **Notes**: 

#### UP045 - Optional syntax (206 errors)
- [ ] **Status**: Not Started
- **Why**: Python 3.10+ supports `X | None` instead of `Optional[X]`
- **Action**: Replace `Optional[X]` → `X | None`
- **Auto-fixable**: Yes (with `--fix`)
- **Priority**: High - Modern syntax, auto-fixable
- **Command**: `ruff check --fix .` (will fix this along with others)
- **Notes**: 

#### UP035 - Deprecated typing imports (164 errors)
- [ ] **Status**: Not Started
- **Why**: `typing.Dict` deprecated in favor of built-in `dict`
- **Action**: Remove `from typing import Dict, List` and use built-ins
- **Auto-fixable**: Yes (with `--fix`)
- **Priority**: Medium - Often fixed alongside UP006
- **Command**: `ruff check --fix .` (will fix this along with others)
- **Notes**: 

### Tier 4: Code Style & Consistency (406 errors)
**Impact**: Readability, consistency, minor style improvements  
**Risk**: Very Low - Purely stylistic

#### I001 - Import sorting (236 errors)
- [ ] **Status**: Not Started
- **Why**: Consistent import ordering improves readability
- **Action**: Sort imports alphabetically and group (stdlib, third-party, local)
- **Auto-fixable**: Yes (with `--fix`)
- **Priority**: Medium - Easy auto-fix, improves readability
- **Command**: `ruff check --fix .` (will fix this along with others)
- **Notes**: 

#### UP015 - Unnecessary file modes (63 errors)
- [ ] **Status**: Not Started
- **Why**: Default file modes are redundant
- **Action**: Remove explicit `mode='r'` from `open()` calls
- **Auto-fixable**: Yes (with `--fix`)
- **Priority**: Low - Minor style improvement
- **Command**: `ruff check --fix .` (will fix this along with others)
- **Notes**: 

#### F541 - f-strings without placeholders (44 errors)
- [ ] **Status**: Not Started
- **Why**: Unnecessary f-string formatting
- **Action**: Convert to regular strings
- **Auto-fixable**: Yes (with `--fix`)
- **Priority**: Low - Minor style improvement
- **Command**: `ruff check --fix .` (will fix this along with others)
- **Notes**: 

### Tier 5: Edge Cases & Minor Issues
**Impact**: Very minor issues  
**Risk**: Very Low

- [ ] **F811**: Redefined while unused (23 errors)
- [ ] **E402**: Module import not at top (7 errors)
- [ ] **B007**: Unused loop control variable (3 errors)
- [ ] **Other**: Various minor issues

## Implementation Strategy

### Phase 1: Auto-fix Safe Issues (Immediate)
- [ ] **Status**: Not Started
- **Target**: ~1,382 auto-fixable errors
- **Time**: Low effort, high impact
- **Steps**:
  1. Run `ruff check --fix .` to fix all auto-fixable issues
  2. Review changes in git diff
  3. Run tests to ensure nothing broke
  4. Commit changes
- **Completion Date**: 
- **Notes**: 

### Phase 2: Critical Safety Fixes (Manual Review Required)
- [x] **Status**: Completed
- **Target**: 62 critical errors (E722, B904)
- **Time**: Medium effort, high importance
- **Steps**:
  1. Fix bare except clauses (E722) - Replace with specific exceptions
  2. Fix exception chaining (B904) - Add proper `from` clauses
  3. Focus on `infra/health-check/main.py` first (most instances)
  4. Test thoroughly after each file
- **Completion Date**: 2025-01-28
- **Notes**: All 62 critical errors fixed. All unit tests still pass (483 passed). 

### Phase 3: Code Quality Review (Selective)
- [ ] **Status**: Not Started
- **Target**: F841 unused variables (69 errors)
- **Time**: Medium effort, requires context
- **Steps**:
  1. Review each unused variable
  2. Determine if it should be removed or used
  3. Fix obvious dead code
  4. Leave ambiguous cases for later
- **Completion Date**: 
- **Notes**: 

### Phase 4: Remaining Manual Fixes
- [ ] **Status**: Not Started
- **Target**: Remaining non-auto-fixable issues
- **Time**: Low-medium effort
- **Steps**:
  1. Fix F811 (redefined imports)
  2. Fix E402 (import placement)
  3. Fix other minor issues as encountered
- **Completion Date**: 
- **Notes**: 

## Recommended Execution Order

1. **Start with auto-fix**: `ruff check --fix .` (fixes 1,382 errors)
2. **Review critical files**: Focus on `infra/health-check/main.py` for E722/B904
3. **Test thoroughly**: Ensure no regressions
4. **Iterate**: Fix remaining issues incrementally

## Files Requiring Special Attention

- [ ] `infra/health-check/main.py`: 25 E722, 37 B904 errors (critical)
- [ ] `agents/base_agent.py`: Many type annotation updates
- [ ] `config/`: Multiple unused imports
- [ ] `scripts/`: Type modernization needed

## Success Criteria

- [ ] All critical safety issues (E722, B904) resolved
- [ ] All auto-fixable issues applied
- [ ] Tests pass after fixes
- [ ] Code follows modern Python 3.11+ conventions
- [ ] No regressions introduced

## Quick Reference Commands

```bash
# Check all errors
python3 -m ruff check .

# Auto-fix all fixable issues
python3 -m ruff check --fix .

# Check specific directory
python3 -m ruff check agents/

# Check with statistics
python3 -m ruff check . --statistics

# Check specific error code
python3 -m ruff check . --select E722
```

## Update Log

| Date | Phase/Error | Status | Notes |
|------|------------|--------|-------|
| 2025-01-28 | Plan Created | Initial | Document created with full prioritization |
| 2025-01-28 | Tier 1 - E722 | Completed | Fixed all 25 bare except clauses across multiple files |
| 2025-01-28 | Tier 1 - B904 | Completed | Fixed all 37 exception chaining issues across multiple files |
| 2025-01-28 | Phase 2 | Completed | All 62 critical safety errors resolved, tests passing |

