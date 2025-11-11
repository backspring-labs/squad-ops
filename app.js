console.log('TestApp v1.0.0 loaded');
document.addEventListener('DOMContentLoaded', function() {
  fetch('/health').then(response => response.text()).then(agentStatus => {
    document.querySelector('p').innerText = `Agent Status: ${agentStatus}`;
  }).catch(error => {
    console.error('Error fetching agent status:', error);
  });
});