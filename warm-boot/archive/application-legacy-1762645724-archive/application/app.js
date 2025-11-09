document.addEventListener('DOMContentLoaded', function() {
  // Fetch real framework version from environment variables
  const frameworkVersion = process.env.FRAMEWORK_VERSION || 'Unknown';
  console.log(`Real Framework Version: ${frameworkVersion}`);
  // Fetch agent status and health check
  fetch('http://localhost:8080/agents/status', {
    method: 'GET'
  }).then(response => response.json()).then(data => {
    console.log('Agent Status:', data);
  });
  fetch('http://localhost:8080/health', {
    method: 'GET'
  }).then(response => response.text()).then(text => {
    console.log('Health Check:', text);
  });
});