console.log('Application v0.5.1.001 loaded');

const fetchStatus = async () => {
  try {
    const response = await fetch('/hello-squad/agents/status');
    if (response.ok) {
      const data = await response.json();
      document.getElementById('app').innerHTML = JSON.stringify(data, null, 2);
    } else {
      console.error(`Failed to fetch agent status: ${response.status}`);
    }
  } catch (error) {
    console.error('Error fetching agent status:', error);
  }
};

const fetchHealth = async () => {
  try {
    const response = await fetch('/hello-squad/health');
    if (response.ok) {
      document.getElementById('app').innerHTML += `<p>Health check: ${await response.text()}</p>`;
    } else {
      console.error(`Failed to fetch health check: ${response.status}`);
    }
  } catch (error) {
    console.error('Error fetching health check:', error);
  }
};

document.addEventListener('DOMContentLoaded', async () => {
  await fetchStatus();
  await fetchHealth();
});