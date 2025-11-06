const agentStatusEndpoint = 'http://localhost:8080/agents/status';
const healthCheckEndpoint = 'http://localhost:8080/health';

async function fetchAgentStatus() {
  try {
    const response = await fetch(agentStatusEndpoint);
    if (!response.ok) throw new Error('Failed to fetch agent status');
    return await response.json();
  } catch (error) {
    console.error('Error fetching agent status:', error.message);
  }
}

async function fetchHealthCheck() {
  try {
    const response = await fetch(healthCheckEndpoint);
    if (!response.ok) throw new Error('Failed to fetch health check');
    return await response.json();
  } catch (error) {
    console.error('Error fetching health check:', error.message);
  }
}

async function updateUI() {
  const agentStatus = await fetchAgentStatus();
  const healthCheck = await fetchHealthCheck();
  document.getElementById('app').innerHTML = `
    <p>Agent Status: ${agentStatus.status}</p>
    <p>Health Check: ${healthCheck.status}</p>
  `;
}

updateUI();