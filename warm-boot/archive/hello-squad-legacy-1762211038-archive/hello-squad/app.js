console.log('HelloSquad v0.3.0.129 | WarmBoot Run: ECID-WB-129 loaded');
document.addEventListener('DOMContentLoaded', function() {
  // Fetch and display agent status
  fetch('http://localhost:8080/agents/status')
    .then(response => response.json())
    .then(data => {
      const appElement = document.getElementById('app');
      appElement.innerHTML = `<div><h2>Team Status Dashboard</h2></div>
                              <div><p>Agent Count: ${data.agentCount}</p></div>
                              <div><p>Last Update: ${new Date(data.lastUpdate).toLocaleString()}</p></div>`;
    })
    .catch(error => {
      console.error('Error fetching agent status:', error);
      appElement.innerHTML = '<div>Error fetching data</div>';
    });
});