console.log('Application loaded');
document.addEventListener('DOMContentLoaded', function() {
  fetch('/api/status')
    .then(response => response.json())
    .then(data => {
      document.getElementById('app').innerHTML = `
        <p>Status: ${data.status}</p>
        <p>Health Check: ${data.healthCheck}</p>
      `;
    })
    .catch(error => {
      console.error('Error fetching data:', error);
      document.getElementById('app').innerHTML = '<p>Error loading data.</p>';
    });
});