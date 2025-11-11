const activityFeed = document.getElementById('activity-feed');
const projectProgress = document.getElementById('project-progress');

async function fetchActivity() {
  try {
    const response = await fetch('/api/activity');
    if (!response.ok) throw new Error(response.statusText);
    const data = await response.json();
    activityFeed.innerHTML = JSON.stringify(data, null, 2);
  } catch (error) {
    console.error('Failed to fetch activity:', error);
  }
}

async function fetchProjectProgress() {
  try {
    const response = await fetch('/api/progress');
    if (!response.ok) throw new Error(response.statusText);
    const data = await response.json();
    projectProgress.innerHTML = JSON.stringify(data, null, 2);
  } catch (error) {
    console.error('Failed to fetch project progress:', error);
  }
}

fetchActivity();
fetchProjectProgress();