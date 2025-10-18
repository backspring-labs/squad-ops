// Vanilla JavaScript for dynamic content and interactions
document.addEventListener('DOMContentLoaded', () => {
    const appContainer = document.getElementById('app');

    // Fetch agent status and health check data
    Promise.all([
        fetch('http://localhost:8080/agents/status'),
        fetch('http://localhost:8080/health')
    ]).then(responses => {
        return Promise.all(responses.map(response => response.json()));
    }).then(data => {
        const [agentStatus, healthCheck] = data;

        // Display agent status
        appContainer.innerHTML += `
            <h2>Agent Status</h2>
            <p>Framework Version: ${process.env.FRAMEWORK_VERSION}</p>
            <pre>${JSON.stringify(agentStatus, null, 2)}</pre>
        `;

        // Display health check
        appContainer.innerHTML += `
            <h2>Health Check</h2>
            <pre>${JSON.stringify(healthCheck, null, 2)}</pre>
        `;
    }).catch(error => {
        console.error('Failed to fetch data:', error);
        appContainer.innerHTML = '<p>Error fetching data.</p>';
    });
});