console.log('HelloSquad v0.4.0.141 | WarmBoot Run: ECID-WB-141 loaded');

function fetchAgentStatus() {
  fetch('http://localhost:8080/agents/status', {
    method: 'GET'
  }).then(response => response.json()).then(data => {
    document.getElementById('app').innerHTML = `Agent Status: ${data.status}`;
  });
}

function fetchHealthCheck() {
  fetch('http://localhost:8080/health', {
    method: 'GET'
  }).then(response => response.json()).then(data => {
    document.getElementById('app').innerHTML += `<br>Health Check: ${data.status}`;
  });
}

fetchAgentStatus();
fetchHealthCheck();