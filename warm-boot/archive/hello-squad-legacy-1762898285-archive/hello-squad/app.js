console.log('Application loaded');

const fetchActivityFeed = async () => {
  try {
    const response = await fetch('/api/activity');
    if (response.ok) {
      const data = await response.json();
      displayActivityFeed(data);
    } else {
      console.error('Failed to fetch activity feed');
    }
  } catch (error) {
    console.error('Error fetching activity feed:', error);
  }
}

const displayActivityFeed = (data) => {
  const feedContainer = document.getElementById('activity-feed');
  data.forEach(item => {
    const div = document.createElement('div');
    div.textContent = item;
    feedContainer.appendChild(div);
  });
}
document.addEventListener('DOMContentLoaded', function() {
  fetchActivityFeed();
});