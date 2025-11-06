console.log('Application loaded');

function fetchAgentStatus() {
  fetch('http://localhost:8080/agents/status')
    .then(response => response.json())
    .then(data => {
      document.getElementById('app').innerText = `Agent Status: ${data.status}`;
    })
    .catch(error => {
      console.error('Error fetching agent status:', error);
    });
}

function fetchHealthCheck() {
  fetch('http://localhost:8080/health')
    .then(response => response.text())
    .then(data => {
      document.getElementById('app').innerText = `Health Check: ${data}`;
    })
    .catch(error => {
      console.error('Error fetching health check:', error);
    });
}

fetchAgentStatus();
fetchHealthCheck();