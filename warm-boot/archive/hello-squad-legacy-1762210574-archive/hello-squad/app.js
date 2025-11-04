document.addEventListener('DOMContentLoaded', function() {
  const agentStatusSection = document.getElementById('agent-status');
  const healthCheckSection = document.getElementById('health-check');

  fetch('http://localhost:8080/agents/status')
    .then(response => response.json())
    .then(data => {
      const table = document.createElement('table');
      data.forEach(agent => {
        const row = table.insertRow();
        row.insertCell().textContent = agent.name;
        row.insertCell().textContent = agent.status;
      });
      agentStatusSection.appendChild(table);
    })
    .catch(error => {
      console.error('Error fetching agent status:', error);
      agentStatusSection.innerHTML = '<p>Error loading agent status</p>';
    });

  fetch('http://localhost:8080/health')
    .then(response => response.text())
    .then(data => {
      healthCheckSection.textContent = data;
    })
    .catch(error => {
      console.error('Error fetching health check:', error);
      healthCheckSection.innerHTML = '<p>Error loading health check</p>';
    });
});