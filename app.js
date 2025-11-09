console.log('TestApp v1.0.0 loaded');
document.addEventListener('DOMContentLoaded', function() {
  fetch('/health')
    .then(response => response.ok ? console.log('Health check passed') : console.error('Health check failed'))
    .catch(error => console.error('Error during health check:', error));
});