console.log('Application v0.5.1.001 loaded');

function fetchAgentStatus() {
  fetch('http://localhost:8080/agents/status')
    .then(response => response.json())
    .then(data => {
      document.getElementById('app').innerHTML = `Current Agent Status: ${data.status}`;
    })
    .catch(error => console.error('Error fetching agent status:', error));
}

function fetchHealthCheck() {
  fetch('http://localhost:8080/health')
    .then(response => response.text())
    .then(data => {
      document.getElementById('app').innerHTML += `<br>Health Check: ${data}`;
    })
    .catch(error => console.error('Error fetching health check:', error));
}

document.addEventListener('DOMContentLoaded', function() {
  fetchAgentStatus();
  setInterval(fetchAgentStatus, 5000);
  fetchHealthCheck();
  setInterval(fetchHealthCheck, 10000);
});