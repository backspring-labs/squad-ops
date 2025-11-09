console.log('Application loaded');

function fetchActivityFeed() {
  fetch('/hello-squad/agents/status')
    .then(response => response.json())
    .then(data => displayActivityFeed(data))
    .catch(error => console.error('Error fetching activity feed:', error));
}

function displayActivityFeed(feed) {
  const feedElement = document.getElementById('activity-feed');
  feedElement.innerHTML = '';
  feed.forEach(entry => {
    const entryDiv = document.createElement('div');
    entryDiv.textContent = `User: ${entry.user}, Action: ${entry.action}, Timestamp: ${new Date(entry.timestamp).toLocaleString()}`;
    feedElement.appendChild(entryDiv);
  });
}
document.addEventListener('DOMContentLoaded', function() {
  fetchActivityFeed();
});