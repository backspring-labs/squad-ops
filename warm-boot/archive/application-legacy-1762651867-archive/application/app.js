console.log('Application loaded');

document.addEventListener('DOMContentLoaded', function() {
  fetch('/hello-squad/agents/status')
    .then(response => response.json())
    .then(data => displayActivityFeed(data))
    .catch(error => console.error('Error fetching data:', error));

  fetch('/hello-squad/health')
    .then(response => response.text())
    .then(status => document.getElementById('status').innerText = status)
    .catch(error => console.error('Error checking health:', error));
});

function displayActivityFeed(data) {
  const feedContainer = document.getElementById('activity-feed');
  feedContainer.innerHTML = '';
  data.forEach(item => {
    const itemElement = document.createElement('div');
    itemElement.innerText = `User: ${item.user}, Action: ${item.action}, Timestamp: ${new Date(item.timestamp).toLocaleString()}`;
    feedContainer.appendChild(itemElement);
  });
}

function displayProgressTracking(data) {
  const trackingContainer = document.getElementById('progress-tracking');
  // Implement progress tracking logic here
}