console.log('Application v0.5.1.e3df2831 | WarmBoot Run: test-ecid-e3df2831 loaded');

const fetchStatus = async () => {
  try {
    const response = await fetch('/agents/status', { method: 'GET' });
    if (response.ok) {
      const data = await response.json();
      document.getElementById('app').innerText = `Agent Status: ${data.status}`;
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
      document.getElementById('app').innerText += `
<br>Application Framework Version: ${process.env.FRAMEWORK_VERSION}`;
    } else {
      console.error('Failed to check application health');
    }
  } catch (error) {
    console.error('Error checking application health:', error);
  }
};
document.addEventListener('DOMContentLoaded', async function() {
  await fetchStatus();
  await checkHealth();
});