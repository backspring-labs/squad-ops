// WarmBoot run-005 Integration Tests
const testResults = {
    backend_api: false,
    frontend_components: false,
    theme_toggle: false,
    agent_status: false,
    activity_feed: false
};

// Test backend API endpoints
async function testBackendAPI() {
    try {
        const response = await fetch('/api/agents/status');
        const data = await response.json();
        testResults.backend_api = data.agents && data.agents.length > 0;
        console.log('Backend API test:', testResults.backend_api ? 'PASS' : 'FAIL');
    } catch (error) {
        console.error('Backend API test failed:', error);
    }
}

// Test frontend components
function testFrontendComponents() {
    const agentDashboard = document.getElementById('agent-dashboard');
    const activityFeed = document.getElementById('activity-feed');
    const themeToggle = document.getElementById('theme-toggle-btn');
    
    testResults.frontend_components = !!(agentDashboard && activityFeed && themeToggle);
    console.log('Frontend components test:', testResults.frontend_components ? 'PASS' : 'FAIL');
}

// Test theme toggle
function testThemeToggle() {
    const initialTheme = document.documentElement.getAttribute('data-theme');
    toggleTheme();
    const newTheme = document.documentElement.getAttribute('data-theme');
    testResults.theme_toggle = initialTheme !== newTheme;
    console.log('Theme toggle test:', testResults.theme_toggle ? 'PASS' : 'FAIL');
}

// Run all tests
function runIntegrationTests() {
    console.log('🧪 Running WarmBoot run-005 Integration Tests...');
    testBackendAPI();
    testFrontendComponents();
    testThemeToggle();
    
    setTimeout(() => {
        const passedTests = Object.values(testResults).filter(result => result).length;
        const totalTests = Object.keys(testResults).length;
        console.log(`✅ Integration Tests Complete: ${passedTests}/${totalTests} passed`);
        
        if (passedTests === totalTests) {
            console.log('🎉 All integration tests passed!');
        } else {
            console.log('⚠️ Some integration tests failed');
        }
    }, 1000);
}

// Auto-run tests when page loads
document.addEventListener('DOMContentLoaded', runIntegrationTests);
