console.log('Application loaded');
document.addEventListener('DOMContentLoaded', function() {
  fetch('/health').then(response => response.text()).then(data => {
    document.querySelector('main').innerHTML = `Health Check: ${data}`;
  }).catch(error => {
    console.error('Error fetching health check:', error);
    document.querySelector('main').innerHTML = 'Failed to load health check.';
  });
});