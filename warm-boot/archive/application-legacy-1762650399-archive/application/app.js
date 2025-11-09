console.log('Application loaded');
document.addEventListener('DOMContentLoaded', function() {
  // Fetch agent status and health check
  fetch('/agents/status')
    .then(response => response.json())
    .then(data => {
      console.log('Agent Status:', data);
      document.getElementById('app').innerHTML += `<p>Agent Status: ${data.status}</p>`;
    })
    .catch(error => {
      console.error('Error fetching agent status:', error);
    });

  fetch('/health')
    .then(response => response.text())
    .then(data => {
      console.log('Health Check:', data);
      document.getElementById('app').innerHTML += `<p>Health Check: ${data}</p>`;
    })
    .catch(error => {
      console.error('Error fetching health check:', error);
    });
});