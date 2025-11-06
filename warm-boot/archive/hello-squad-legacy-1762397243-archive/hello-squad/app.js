const statusElement = document.getElementById('status');
const activityFeed = document.getElementById('activity-feed');

// Fetch real framework version from environment variables
fetch('/api/framework/version', {
  method: 'GET'
}).then(response => response.json()).then(data => {
  console.log(`Framework Version: ${data.version}`);
});

// Fetch agent status and health check
const fetchAgentStatus = () => {
  fetch('http://localhost:8080/agents/status', {
    method: 'GET'
  }).then(response => response.json()).then(data => {
    const statusText = data.status === 'online' ? 'Online' : 'Offline';
    statusElement.textContent = `Agent Status: ${statusText}`;
  });
};

const fetchHealthCheck = () => {
  fetch('http://localhost:8080/health', {
    method: 'GET'
  }).then(response => response.json()).then(data => {
    console.log(`Health Check: ${data.status}`);
  });
};

// Fetch WarmBoot run ID and version
const fetchWarmBootInfo = () => {
  const warmBootRunId = '$run_id';
  statusElement.textContent += `
  <br>WarmBoot Run ID: ${warmBootRunId}`;
};

fetchAgentStatus();
fetchHealthCheck();
fetchWarmBootInfo();

// Activity feed logic (placeholder)
const addActivity = message => {
  const activityItem = document.createElement('div');
  activityItem.textContent = message;
  activityFeed.appendChild(activityItem);
};

setInterval(() => {
  addActivity(`Activity: ${new Date().toLocaleTimeString()}`);
}, 5000);