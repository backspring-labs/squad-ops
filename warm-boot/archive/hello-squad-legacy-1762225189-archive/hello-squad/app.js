document.addEventListener('DOMContentLoaded', function() {
  fetch('/hello-squad/agents/status')
    .then(response => response.json())
    .then(data => displayActivityFeed(data))
    .catch(error => console.error('Error fetching activity feed:', error));

  fetch('/hello-squad/health')
    .then(response => response.text())
    .then(version => displayVersion(version))
    .catch(error => console.error('Error fetching version:', error));
});

function displayActivityFeed(data) {
  const feedContainer = document.getElementById('activity-feed');
  data.forEach(agent => {
    const activityItem = document.createElement('div');
    activityItem.innerHTML = `
      <p><strong>${agent.name}</strong> is ${agent.status}.</p>
      <small>Last updated: ${new Date().toLocaleString()}</small>
    `;
    feedContainer.appendChild(activityItem);
  });
}

function displayVersion(version) {
  const projectProgress = document.getElementById('project-progress');
  projectProgress.innerHTML = `<p>Framework version: <strong>${version}</strong></p>`;
}