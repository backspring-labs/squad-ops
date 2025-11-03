console.log('HelloSquad v0.3.0.125 | WarmBoot Run: ECID-WB-125');
document.addEventListener('DOMContentLoaded', function() {
  fetch('http://localhost:8080/health')
    .then(response => response.json())
    .then(data => {
      document.getElementById('app').innerText = `Health Check: ${data.status}`;
    })
    .catch(error => {
      console.error('Error fetching health check:', error);
    });
});