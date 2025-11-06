console.log('Application loaded');
document.addEventListener('DOMContentLoaded', function() {
  fetch('/health')
    .then(response => response.json())
    .then(data => {
      const appContainer = document.getElementById('app');
      appContainer.innerHTML = `<p>Health Check: ${data.status}</p>`;
    })
    .catch(error => {
      console.error('Error fetching health check:', error);
    });
});