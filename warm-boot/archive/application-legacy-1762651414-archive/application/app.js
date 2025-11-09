console.log('Application loaded');
document.addEventListener('DOMContentLoaded', function() {
  fetch('/hello-squad/agents/status')
    .then(response => response.json())
    .then(data => {
      const appDiv = document.getElementById('app');
      appDiv.innerHTML = `<p>Framework Version: ${process.env.FRAMEWORK_VERSION}</p><p>Agent Status: ${data.status}</p>`;
    })
    .catch(error => console.error('Error fetching data:', error));
});