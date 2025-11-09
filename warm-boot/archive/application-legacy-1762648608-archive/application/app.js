console.log('Application loaded');

function fetchTeamStatus() {
  fetch('/agents/status')
    .then(response => response.json())
    .then(data => {
      const dashboard = document.getElementById('dashboard');
      dashboard.innerHTML = '';
      data.forEach(agent => {
        const div = document.createElement('div');
        div.textContent = `Agent: ${agent.name}, Status: ${agent.status}`;
        dashboard.appendChild(div);
      });
    })
    .catch(error => console.error('Error fetching team status:', error));
}

function fetchHealthCheck() {
  fetch('/health')
    .then(response => response.text())
    .then(data => {
      const healthStatus = document.createElement('p');
      healthStatus.textContent = `Health Check: ${data}`;
      document.body.appendChild(healthStatus);
    })
    .catch(error => console.error('Error fetching health check:', error));
}

fetchTeamStatus();
fetchHealthCheck();