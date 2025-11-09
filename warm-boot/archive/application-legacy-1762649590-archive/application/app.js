console.log('Application loaded');
document.addEventListener('DOMContentLoaded', function() {
  fetch('/hello-squad/agents/status')
    .then(response => response.json())
    .then(data => displayActivityFeed(data))
    .catch(error => console.error('Error fetching data:', error));
});

function displayActivityFeed(data) {
  const activityFeed = document.getElementById('activity-feed');
  activityFeed.innerHTML = '';
  data.forEach(item => {
    const li = document.createElement('li');
    li.textContent = item.activity + ' - ' + item.timestamp;
    activityFeed.appendChild(li);
  });
}

setInterval(() => {
  fetch('/hello-squad/health')
    .then(response => response.json())
    .catch(error => console.error('Error fetching health check:', error));
}, 5000);