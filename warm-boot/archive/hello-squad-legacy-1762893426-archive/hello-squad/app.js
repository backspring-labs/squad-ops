console.log('Application loaded');

function fetchAgentStatus() {
  fetch('http://localhost:8080/agents/status', {
    method: 'GET'
  }).then(response => response.json()).then(data => {
    document.getElementById('app').innerText = `Team Status: ${data.status}`;
  });
}

function fetchHealthCheck() {
  fetch('http://localhost:8080/health', {
    method: 'GET'
  }).then(response => response.text()).then(data => {
    document.getElementById('app').innerText += `

Health Check: ${data}`;
  });
}

function displayFrameworkVersion() {
  const version = process.env.FRAMEWORK_VERSION || 'Unknown';
  document.getElementById('app').innerText += `

Framework Version: ${version}`;
}

fetchAgentStatus();
fetchHealthCheck();
displayFrameworkVersion();