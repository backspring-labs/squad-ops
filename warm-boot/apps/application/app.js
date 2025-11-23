const fetch = require('node-fetch');

async function fetchData() {
  try {
    const frameworkVersion = process.env.FRAMEWORK_VERSION;
    const agentStatus = await getAgentStatus();
    displayData(frameworkVersion, agentStatus);
  } catch (error) {
    console.error('Error fetching data:', error);
  }
}

function getAgentStatus() {
  return fetch('http://localhost:8080/agents/status')
    .then(response => response.json())
    .catch(error => { throw new Error(`Failed to fetch agent status: ${error}`); });
}

function displayData(frameworkVersion, agentStatus) {
  const appContainer = document.getElementById('app');
  appContainer.innerHTML = `Framework Version: ${frameworkVersion}<br>Agent Status: ${agentStatus.status}`;
}

window.addEventListener('DOMContentLoaded', fetchData);
