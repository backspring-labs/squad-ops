console.log('Application loaded');
document.addEventListener('DOMContentLoaded', function() {
  fetch('/hello-squad/agents/status')
    .then(response => response.json())
    .then(data => displayDashboard(data));
});
function displayDashboard(agents) {
  const dashboardContainer = document.getElementById('dashboard');
  agents.forEach(agent => {
    const activityFeedItem = document.createElement('div');
    activityFeedItem.innerHTML = `<p>${agent.name} - ${agent.status}</p>`;
    dashboardContainer.appendChild(activityFeedItem);
  });
}
fetch('/hello-squad/health')
  .then(response => response.text())
  .then(data => {
    const versionInfo = document.createElement('footer');
    versionInfo.innerHTML = `v0.5.1.a236a70a | WarmBoot Run: test-ecid-a236a70a`;
    document.body.appendChild(versionInfo);
  });