const fetch = require('node-fetch');

async function fetchActivityFeed() {
  try {
    const response = await fetch('http://localhost:8080/agents/status');
    if (response.ok) {
      const data = await response.json();
      document.querySelector('#app .activity-feed').innerHTML = JSON.stringify(data, null, 2);
    } else {
      console.error(`Failed to fetch activity feed: ${response.status}`);
    }
  } catch (error) {
    console.error('Error fetching activity feed:', error);
  }
}

async function fetchProjectProgress() {
  try {
    const response = await fetch('http://localhost:8080/health');
    if (response.ok) {
      const data = await response.json();
      document.querySelector('#app .project-progress').innerHTML = JSON.stringify(data, null, 2);
    } else {
      console.error(`Failed to fetch project progress: ${response.status}`);
    }
  } catch (error) {
    console.error('Error fetching project progress:', error);
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  await fetchActivityFeed();
  await fetchProjectProgress();
});