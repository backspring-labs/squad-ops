console.log('Application loaded');

const fetchStatus = async () => {
  try {
    const response = await fetch('/agents/status');
    if (response.ok) {
      const statusData = await response.json();
      console.log(statusData);
    } else {
      console.error('Failed to fetch agent status');
    }
  } catch (error) {
    console.error('Error fetching agent status:', error);
  }
};

const fetchHealth = async () => {
  try {
    const response = await fetch('/health');
    if (response.ok) {
      const healthData = await response.json();
      console.log(healthData);
    } else {
      console.error('Failed to fetch health check');
    }
  } catch (error) {
    console.error('Error fetching health check:', error);
  }
};

fetchStatus();
fetchHealth();