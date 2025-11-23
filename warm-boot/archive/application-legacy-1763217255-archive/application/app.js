console.log('Application loaded');
document.addEventListener('DOMContentLoaded', function() {
  fetch('/application/agents/status')
    .then(response => response.json())
    .then(data => displayActivityFeed(data))
    .catch(error => console.error('Error fetching data:', error));
});

function displayActivityFeed(activities) {
  const activityFeed = document.getElementById('activity-feed');
  activities.forEach(activity => {
    const div = document.createElement('div');
    div.textContent = `User: ${activity.user}, Action: ${activity.action}, Time: ${new Date(activity.timestamp).toLocaleString()}`;
    activityFeed.appendChild(div);
  });
}

window.addEventListener('hashchange', function() {
  if (window.location.hash === '#/health') {
    fetch('/application/health')
      .then(response => response.text())
      .then(data => document.body.textContent = data)
      .catch(error => console.error('Error fetching health check:', error));
  }
});