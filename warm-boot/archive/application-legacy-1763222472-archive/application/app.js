console.log('Application loaded');
document.addEventListener('DOMContentLoaded', function() {
  fetch('/api/health')
    .then(response => response.json())
    .then(data => {
      document.getElementById('app').innerHTML = `<p>Health Check: ${data.status}</p>`;
    })
    .catch(error => {
      console.error('Error fetching health check:', error);
    });
});