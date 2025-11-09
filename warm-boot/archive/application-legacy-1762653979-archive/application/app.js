console.log('Application loaded');

async function fetchAgentStatus() {
  try {
    const response = await fetch('http://localhost:8080/agents/status', {
      headers: {
        'Content-Type': 'application/json'
      }
    });
    if (response.ok) {
      const data = await response.json();
      document.getElementById('dashboard').innerHTML = JSON.stringify(data, null, 2);
    } else {
      console.error('Failed to fetch agent status');
    }
  } catch (error) {
    console.error('Error fetching agent status:', error);
  }
}

async function fetchHealthCheck() {
  try {
    const response = await fetch('http://localhost:8080/health', {
      headers: {
        'Content-Type': 'application/json'
      }
    });
    if (response.ok) {
      const data = await response.json();
      console.log(data);
    } else {
      console.error('Failed to fetch health check');
    }
  } catch (error) {
    console.error('Error fetching health check:', error);
  }
}

window.addEventListener('DOMContentLoaded', async function() {
  setInterval(fetchAgentStatus, 5000);
  setInterval(fetchHealthCheck, 10000);
});