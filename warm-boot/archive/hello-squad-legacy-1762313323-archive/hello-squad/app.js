console.log('Application loaded');

const app = document.getElementById('app');

function fetchAgentStatus() {
  fetch('http://localhost:8080/agents/status', { method: 'GET' })
    .then(response => response.json())
    .then(data => {
      const statusElement = document.createElement('p');
      statusElement.textContent = `Current Agent Status: ${data.status}`;
      app.appendChild(statusElement);
    })
    .catch(error => console.error('Error fetching agent status:', error));
}

function fetchHealthCheck() {
  fetch('http://localhost:8080/health', { method: 'GET' })
    .then(response => response.json())
    .then(data => {
      const healthElement = document.createElement('p');
      healthElement.textContent = `Current Health Check: ${data.status}`;
      app.appendChild(healthElement);
    })
    .catch(error => console.error('Error fetching health check:', error));
}

function updateFrameworkVersion() {
  const versionElement = document.createElement('p');
  versionElement.textContent = `Real Framework Version: ${process.env.FRAMEWORK_VERSION}`;
  app.appendChild(versionElement);
}

document.addEventListener('DOMContentLoaded', function () {
  fetchAgentStatus();
  fetchHealthCheck();
  updateFrameworkVersion();
});