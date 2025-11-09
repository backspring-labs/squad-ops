console.log('Application v0.5.1.fbb4bd21 loaded');

const fetchStatus = async () => {
  try {
    const response = await fetch('/health', { method: 'GET' });
    if (response.ok) {
      const data = await response.json();
      console.log('Health Check:', data);
    } else {
      console.error('Health Check failed');
    }
  } catch (error) {
    console.error('Error fetching health check:', error);
  }
};

const fetchAgentStatus = async () => {
  try {
    const response = await fetch('/agents/status', { method: 'GET' });
    if (response.ok) {
      const data = await response.json();
      console.log('Agent Status:', data);
    } else {
      console.error('Agent Status failed');
    }
  } catch (error) {
    console.error('Error fetching agent status:', error);
  }
};

fetchStatus();
fetchAgentStatus();