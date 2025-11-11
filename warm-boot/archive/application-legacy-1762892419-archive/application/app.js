console.log('Application loaded');

const fetchStatus = async () => {
  try {
    const response = await fetch('/agents/status');
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

const fetchHealthCheck = async () => {
  try {
    const response = await fetch('/health');
    if (response.ok) {
      console.log(response.status); // Real-time health check status
    } else {
      console.error('Failed to fetch health check');
    }
  } catch (error) {
    console.error('Error fetching health check:', error);
  }
};

fetchStatus();
fetchHealthCheck();