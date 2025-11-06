console.log('Application loaded');

function fetchHealthCheck() {
  fetch('http://localhost:8080/health')
    .then(response => response.json())
    .then(data => {
      console.log('Health Check:', data);
      document.getElementById('app').innerText = `Health Status: ${data.status}`;
    })
    .catch(error => {
      console.error('Error fetching health check:', error);
      document.getElementById('app').innerText = 'Failed to fetch health check.';
    });
}

function fetchAgentStatus() {
  fetch('http://localhost:8080/agents/status')
    .then(response => response.json())
    .then(data => {
      console.log('Agent Status:', data);
      document.getElementById('app').innerText = `Agent Status: ${data.status}`;
    })
    .catch(error => {
      console.error('Error fetching agent status:', error);
      document.getElementById('app').innerText = 'Failed to fetch agent status.';
    });
}

fetchHealthCheck();
fetchAgentStatus();