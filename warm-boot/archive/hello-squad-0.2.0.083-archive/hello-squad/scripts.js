const activityFeedContainer = document.getElementById('activity-feed');
const projectProgressContainer = document.getElementById('project-progress');

async function fetchData(url) {
    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error("Failed to fetch data:", error);
        alert('Error fetching data. Please try again later.');
    }
}

async function displayActivityFeed() {
    const activityData = await fetchData('http://localhost:8080/agents/status');
    activityFeedContainer.innerHTML = `<ul>${activityData.map(item => `<li>${item}</li>`).join('')}</ul>`;
}

async function displayProjectProgress() {
    const progressData = await fetchData('http://localhost:8080/health');
    projectProgressContainer.innerHTML = `<p>Current Framework Version: ${progressData.version}</p><p>Agent Status: ${progressData.status}</p>`;
}

document.addEventListener("DOMContentLoaded", () => {
    displayActivityFeed();
    displayProjectProgress();
});