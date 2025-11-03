console.log('Application loaded');
document.addEventListener('DOMContentLoaded', function() {
  // Fetch real framework version from environment variables
  const frameworkVersion = process.env.FRAMEWORK_VERSION || 'Unknown';
  console.log(`Framework Version: ${frameworkVersion}`);
  // Fetch agent status and health check data
  fetch('http://localhost:8080/agents/status', {
    method: 'GET'
  }).then(response => response.json()).then(data => {
    document.getElementById('app').innerHTML = `<p>Agent Status: ${data.status}</p>`;
  });
  fetch('http://localhost:8080/health', {
    method: 'GET'
  }).then(response => response.text()).then(text => {
    document.getElementById('app').innerHTML += `<p>Health Check: ${text}</p>`;
  });
});