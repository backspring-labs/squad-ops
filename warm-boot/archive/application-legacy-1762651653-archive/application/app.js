console.log('Application loaded');

document.addEventListener('DOMContentLoaded', function() {
  fetch('/health')
    .then(response => response.json())
    .then(data => {
      document.getElementById('app').innerText = `Health Check: ${data.status}`;
    })
    .catch(error => {
      console.error('Error fetching health check:', error);
      document.getElementById('app').innerText = 'Failed to fetch health check.';
    });
});