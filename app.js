console.log('TestApp v1.0.0 loaded');
document.addEventListener('DOMContentLoaded', function() {
  fetch('/health')
    .then(response => response.json())
    .then(data => {
      document.getElementById('app').innerHTML = `API Health: ${data.status}`;
    })
    .catch(error => {
      console.error('Error fetching health check:', error);
      document.getElementById('app').innerHTML = 'Failed to fetch API status.';
    });
});