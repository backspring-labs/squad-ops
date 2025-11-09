console.log('Application loaded');

const fetchStatus = async () => {
  try {
    const response = await fetch('/health');
    if (response.ok) {
      document.getElementById('app').innerText = 'Health check successful';
    } else {
      document.getElementById('app').innerText = 'Health check failed';
    }
  } catch (error) {
    console.error('Error fetching status:', error);
    document.getElementById('app').innerText = 'Failed to fetch status';
  }
}
document.addEventListener('DOMContentLoaded', function() {
  fetchStatus();
});