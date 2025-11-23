function fetchStatus() {
  return fetch('http://localhost:8080/agents/status')
    .then(response => response.json())
    .catch(error => console.error('Error fetching status:', error));
}

function fetchHealthCheck() {
  return fetch('http://localhost:8080/health')
    .then(response => response.text())
    .catch(error => console.error('Error fetching health check:', error));
}

fetchStatus()
  .then(data => {
    const statusElement = document.createElement('p');
    statusElement.textContent = `Framework Version: ${process.env.FRAMEWORK_VERSION} | Agent Status: ${data.status}`;
    document.getElementById('app').appendChild(statusElement);
  })
  .catch(error => console.error('Error fetching framework version:', error));

fetchHealthCheck()
  .then(text => {
    const healthElement = document.createElement('p');
    healthElement.textContent = `Health Check: ${text}`;
    document.getElementById('app').appendChild(healthElement);
  })
  .catch(error => console.error('Error fetching health check:', error));