console.log('Application loaded');

const dashboardElement = document.getElementById('dashboard');

function fetchDashboardData() {
  fetch('/agents/status')
    .then(response => response.json())
    .then(data => {
      const statusElements = data.map(item => {
        return `<div class="status-item">
          <h2>${item.projectName}</h2>
          <p>Status: ${item.status}</p>
          <p>Progress: ${item.progress}%</p>
        </div>`;
      });
      dashboardElement.innerHTML = statusElements.join('');
    })
    .catch(error => {
      console.error('Error fetching data:', error);
    });
}

fetchDashboardData();
document.addEventListener('DOMContentLoaded', function() {
  setInterval(fetchDashboardData, 5000);
});