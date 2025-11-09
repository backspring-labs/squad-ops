console.log('Application v0.5.1.001 loaded');

function fetchAgentStatus() {
  fetch('http://localhost:8080/agents/status', {
    method: 'GET'
  }).then(response => response.json()).then(data => {
    document.getElementById('app').innerText = `Agent Status: ${data.status}`;
  });
}

function fetchHealthCheck() {
  fetch('http://localhost:8080/health', {
    method: 'GET'
  }).then(response => response.text()).then(data => {
    document.getElementById('app').innerText += `

Health Check: ${data}`;
  });
}

window.onload = function() {
  fetchAgentStatus();
  setInterval(fetchAgentStatus, 5000);
  fetchHealthCheck();
  setInterval(fetchHealthCheck, 10000);
};