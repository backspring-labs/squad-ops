console.log('Application loaded');
document.addEventListener('DOMContentLoaded', function() {
  fetch('/health')
    .then(response => response.text())
    .then(body => {
      const statusDiv = document.createElement('div');
      statusDiv.innerHTML = body;
      document.body.appendChild(statusDiv);
    })
    .catch(error => {
      console.error('Failed to fetch health check:', error);
    });
});