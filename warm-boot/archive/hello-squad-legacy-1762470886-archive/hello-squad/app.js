const statusElement = document.getElementById('status');
const activityFeedElement = document.getElementById('activity-feed');
const projectProgressElement = document.getElementById('project-progress');

async function fetchStatus() {
  try {
    const response = await fetch('/agents/status');
    if (!response.ok) throw new Error('Network response was not ok');
    const data = await response.json();
    statusElement.textContent = `Agent Status: ${data.status}`;
  } catch (error) {
    console.error('Error fetching agent status:', error);
  }
}

async function fetchActivityFeed() {
  try {
    const response = await fetch('/agents/activity');
    if (!response.ok) throw new Error('Network response was not ok');
    const data = await response.json();
    activityFeedElement.innerHTML = data.map(item => `<div>${item}</div>`).join('');
  } catch (error) {
    console.error('Error fetching activity feed:', error);
  }
}

async function fetchProjectProgress() {
  try {
    const response = await fetch('/projects/progress');
    if (!response.ok) throw new Error('Network response was not ok');
    const data = await response.json();
    projectProgressElement.innerHTML = `Project Progress: ${data}%`;
  } catch (error) {
    console.error('Error fetching project progress:', error);
  }
}

async function fetchHealthCheck() {
  try {
    const response = await fetch('/health');
    if (!response.ok) throw new Error('Network response was not ok');
    const data = await response.json();
    console.log(`Framework Version: ${data.frameworkVersion}`);
    console.log(`Agent Status: ${data.agentStatus}`);
  } catch (error) {
    console.error('Error fetching health check:', error);
  }
}

window.addEventListener('DOMContentLoaded', async () => {
  await fetchStatus();
  await fetchActivityFeed();
  await fetchProjectProgress();
  await fetchHealthCheck();
});