document.addEventListener('DOMContentLoaded', function() {
  const frameworkVersion = process.env.FRAMEWORK_VERSION || 'Unknown';
  const agentStatus = fetch('http://localhost:8080/agents/status').then(response => response.json()).then(data => data.status);

  document.querySelector('#app .status p strong:nth-child(2)').textContent = `SquadOps Framework Version: ${frameworkVersion}`;
  document.querySelector('#app .status p strong:nth-child(3)').textContent = `Agent Status: ${agentStatus}`;
});