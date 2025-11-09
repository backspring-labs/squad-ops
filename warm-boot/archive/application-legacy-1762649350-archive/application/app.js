console.log('Application loaded');
document.addEventListener('DOMContentLoaded', function() {
  // Fetch agent status and display
  fetch('/agents/status')
    .then(response => response.json())
    .then(data => {
      const appContainer = document.getElementById('app');
      appContainer.innerHTML = `<p>Agent Status: ${data.status}</p>`;
    })
    .catch(error => console.error('Error fetching agent status:', error));

  // Fetch health check and display
  fetch('/health')
    .then(response => response.text())
    .then(data => {
      const appContainer = document.getElementById('app');
      appContainer.innerHTML += `<p>Health Check: ${data}</p>`;
    })
    .catch(error => console.error('Error fetching health check:', error));
});