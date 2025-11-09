console.log('Application v0.5.1.001 loaded');

function fetchAgentStatus() {
  fetch('http://localhost:8080/agents/status', {
    headers: {
      'Content-Type': 'application/json'
    }
  })
    .then(response => response.json())
    .then(data => {
      console.log('Agent Status:', data);
    });
}

function fetchHealthCheck() {
  fetch('http://localhost:8080/health', {
    headers: {
      'Content-Type': 'application/json'
    }
  })
    .then(response => response.json())
    .then(data => {
      console.log('Health Check:', data);
    });
}

document.addEventListener('DOMContentLoaded', function() {
  fetchAgentStatus();
  fetchHealthCheck();
});