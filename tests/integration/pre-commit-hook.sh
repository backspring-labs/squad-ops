#!/bin/sh
# Git pre-commit hook to validate integration tests
# 
# Install: cp tests/integration/pre-commit-hook.sh .git/hooks/pre-commit
#          chmod +x .git/hooks/pre-commit

# Check if any integration test files are being committed
if git diff --cached --name-only | grep -q "^tests/integration/.*\.py$"; then
    echo "🔍 Validating integration tests..."
    python3 tests/integration/validate_integration_tests.py
    if [ $? -ne 0 ]; then
        echo ""
        echo "❌ Pre-commit hook failed: Integration tests contain mocks!"
        echo "   Fix violations before committing."
        exit 1
    fi
fi

exit 0

