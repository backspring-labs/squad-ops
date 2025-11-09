console.log('Application loaded');

const fetchStatus = async () => {
  try {
    const response = await fetch('/health');
    if (response.ok) {
      document.getElementById('app').innerText = 'Health check successful';
    } else {
      throw new Error('Health check failed');
    }
  } catch (error) {
    console.error(error);
    document.getElementById('app').innerText = `Error: ${error.message}`;
  }
};
document.addEventListener('DOMContentLoaded', function() {
  fetchStatus();
});