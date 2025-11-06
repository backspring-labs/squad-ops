console.log('HelloSquad v0.3.0.131 | WarmBoot Run: ECID-WB-131 loaded');

document.addEventListener('DOMContentLoaded', function() {
  fetch('/health')
    .then(response => response.json())
    .then(data => {
      document.getElementById('app').innerText = `Health Check Result: ${data.status}`;
    })
    .catch(error => {
      console.error('Error fetching health check:', error);
    });
});