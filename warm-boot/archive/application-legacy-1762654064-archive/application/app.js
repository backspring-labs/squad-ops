const fetch = require('node-fetch');

function updateDashboard() {
  const dashboardElement = document.getElementById('dashboard');
  const agentStatusEndpoint = 'http://localhost:8080/agents/status';
  const healthCheckEndpoint = 'http://localhost:8080/health';

  fetch(agentStatusEndpoint)
    .then(response => response.json())
    .then(data => {
      dashboardElement.innerHTML = `<p>Agent Status: ${data.status}</p>`;
    })
    .catch(error => {
      console.error('Error fetching agent status:', error);
      dashboardElement.innerHTML = '<p>Error fetching agent status</p>';
    });

  fetch(healthCheckEndpoint)
    .then(response => response.text())
    .then(data => {
      const frameworkVersion = process.env.FRAMEWORK_VERSION || 'Unknown';
      dashboardElement.innerHTML += `<p>Framework Version: ${frameworkVersion}</p>`;
    })
    .catch(error => {
      console.error('Error fetching health check:', error);
      dashboardElement.innerHTML += '<p>Error fetching health check</p>';
    });
}

window.addEventListener('DOMContentLoaded', updateDashboard);
document.addEventListener('mousemove', updateDashboard);
