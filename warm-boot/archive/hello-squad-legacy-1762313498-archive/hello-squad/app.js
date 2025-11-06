console.log('Application loaded');
document.addEventListener('DOMContentLoaded', function() {
  fetch('/health')
    .then(response => response.json())
    .then(data => {
      document.getElementById('app').innerHTML = `Health Check: ${data.status}`;
    })
    .catch(error => {
      console.error('Error fetching health check:', error);
      document.getElementById('app').innerHTML = 'Failed to fetch health check.';
    });
});