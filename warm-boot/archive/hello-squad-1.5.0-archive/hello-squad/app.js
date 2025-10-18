console.log('Application starting...');

document.addEventListener('DOMContentLoaded', function() {
    const feedItems = document.querySelectorAll('#activity-feed .feed-item');
    feedItems.forEach(item => item.addEventListener('click', showDetails));

    // Mock data for project progress chart
    const ctx = document.getElementById('progress-chart').getContext('2d');
    const chartData = {
        labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
        datasets: [{
            label: 'Project X Progress',
            data: [65, 59, 80, 81, 56, 55],
            fill: false,
            borderColor: 'rgb(75, 192, 192)',
            tension: 0.1
        }]
    };

    new Chart(ctx, {
        type: 'line',
        data: chartData,
        options: {}
    });

    function showDetails(e) {
        alert(`Showing details for activity with ID: ${e.target.getAttribute('data-id')}`);
    }
});