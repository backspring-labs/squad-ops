document.addEventListener('DOMContentLoaded', function() {
  const welcomeSection = document.getElementById('welcome');
  const agentStatusSection = document.getElementById('agent-status');

  // Fetch build information
  fetch('/hello-squad/build-info')
    .then(response => response.json())
    .then(data => {
      const timestamp = data.timestamp;
      const agents = data.agents;
      welcomeSection.innerHTML = `
        <ul>
          <li>Run ID: ${data.runId}</li>
          <li>Timestamp: ${timestamp}</li>
          <li>Agents: ${agents}</li>
        </ul>
      `;
    })
    .catch(error => {
      console.error('Error fetching build info:', error);
      welcomeSection.innerHTML = '<p>Error loading build information</p>';
    });

  // Fetch agent status
  fetch('/hello-squad/agents/status')
    .then(response => response.json())
    .then(data => {
      const status = data.status;
      agentStatusSection.innerHTML = `<p>Agent Status: ${status}</p>`;
    })
    .catch(error => {
      console.error('Error fetching agent status:', error);
      agentStatusSection.innerHTML = '<p>Error loading agent status</p>';
    });
});