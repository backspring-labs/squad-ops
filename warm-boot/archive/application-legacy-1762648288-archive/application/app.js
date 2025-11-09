console.log('Application loaded');

const fetchActivityFeed = async () => {
  try {
    const response = await fetch('/hello-squad/agents/status');
    if (response.ok) {
      const data = await response.json();
      document.getElementById('activity-feed').innerHTML = JSON.stringify(data, null, 2);
    } else {
      console.error('Failed to fetch activity feed:', response.statusText);
    }
  } catch (error) {
    console.error('Error fetching activity feed:', error);
  }
}
document.addEventListener('DOMContentLoaded', function() {
  fetchActivityFeed();
});