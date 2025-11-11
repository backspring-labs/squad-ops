const fetch = async (url) => {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  return response.json();
}

const displayAgentStatus = async () => {
  try {
    const agentStatusUrl = 'http://localhost:8080/agents/status';
    const healthCheckUrl = 'http://localhost:8080/health';

    const { version } = await fetch(healthCheckUrl);
    document.title = `HelloSquad v${version} | WarmBoot Run: ECID-WB-155`;

    const agentStatus = await fetch(agentStatusUrl);
    console.log('Agent Status:', agentStatus);
  } catch (error) {
    console.error('Error fetching data:', error);
  }
}
document.addEventListener('DOMContentLoaded', displayAgentStatus);