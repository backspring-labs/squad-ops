console.log('Application v0.5.1.001 loaded');

const fetchActivityFeed = () => {
  fetch('http://localhost:8080/agents/status')
    .then(response => response.json())
    .then(data => displayActivityFeed(data));
};

const fetchProjectProgress = () => {
  fetch('http://localhost:8080/health')
    .then(response => response.text())
    .then(data => displayProjectProgress(data));
};

const displayActivityFeed = (data) => {
  const activityFeedDiv = document.getElementById('activity-feed');
  activityFeedDiv.innerHTML = '';
  data.forEach(item => {
    const itemElement = document.createElement('div');
    itemElement.textContent = `${item.user} - ${item.activity}`;
    activityFeedDiv.appendChild(itemElement);
  });
};

const displayProjectProgress = (data) => {
  const projectProgressDiv = document.getElementById('project-progress');
  projectProgressDiv.innerHTML = '';
  const progressElement = document.createElement('div');
  progressElement.textContent = `Project Status: ${data}`;
  projectProgressDiv.appendChild(progressElement);
};

fetchActivityFeed();
fetchProjectProgress();
document.addEventListener('DOMContentLoaded', function() {
});