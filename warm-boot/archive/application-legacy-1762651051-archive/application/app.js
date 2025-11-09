console.log('Application loaded');
document.addEventListener('DOMContentLoaded', function() {
  fetch('/hello-squad/agents/status')
    .then(response => response.json())
    .then(data => displayActivityFeed(data))
    .catch(error => console.error('Error fetching agent status:', error));

  fetch('/hello-squad/health')
    .then(response => response.text())
    .then(text => document.getElementById('project-progress').innerText = text)
    .catch(error => console.error('Error fetching health check:', error));
});
function displayActivityFeed(data) {
  const feedElement = document.getElementById('activity-feed');
  feedElement.innerHTML = '';
  data.forEach(item => {
    const activityItem = document.createElement('div');
    activityItem.className = 'activity-item';
    activityItem.innerText = item.activity;
    feedElement.appendChild(activityItem);
  });
}
