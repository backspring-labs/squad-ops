document.addEventListener('DOMContentLoaded', function() {
  fetch('/api/status')
    .then(response => response.json())
    .then(data => buildDashboard(data))
    .catch(error => console.error('Error fetching data:', error));
});

function buildDashboard(status) {
  const dashboard = document.getElementById('dashboard');
  dashboard.innerHTML = '<h2>Team Status</h2>' +
                        '<p>Status: ' + status.status + '</p>' +
                        '<p>Message: ' + status.message + '</p>';
}