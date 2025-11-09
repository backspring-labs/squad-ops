console.log('Application loaded');

const fetchStatus = async () => {
  try {
    const response = await fetch('/agents/status', { method: 'GET' });
    if (response.ok) {
      const data = await response.json();
      console.log(data);
    } else {
      console.error('Failed to fetch agent status');
    }
  } catch (error) {
    console.error('Error fetching agent status:', error);
  }
};

const checkHealth = async () => {
  try {
    const response = await fetch('/health', { method: 'GET' });
    if (response.ok) {
      const data = await response.json();
      console.log(data);
    } else {
      console.error('Failed to check health');
    }
  } catch (error) {
    console.error('Error checking health:', error);
  }
};

document.addEventListener('DOMContentLoaded', async function() {
  setInterval(fetchStatus, 10000);
  setInterval(checkHealth, 5000);
});