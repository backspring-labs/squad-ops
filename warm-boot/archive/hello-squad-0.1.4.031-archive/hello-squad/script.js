// HelloSquad JavaScript
document.addEventListener('DOMContentLoaded', function() {
    console.log('HelloSquad application loaded');
    
    // Simulate real-time updates
    updateAgentStatus();
    addActivity('Application loaded successfully');
    
    // Update progress
    updateProgress(75);
    
    // Simulate agent activity
    setInterval(simulateAgentActivity, 5000);
});

function updateAgentStatus() {
    const agents = [
        { id: 'max', name: 'Max', status: 'Active', task: 'Governance & Coordination' },
        { id: 'neo', name: 'Neo', status: 'Building', task: 'Application Development' }
    ];
    
    agents.forEach(agent => {
        const card = document.getElementById(agent.id);
        if (card) {
            const statusEl = card.querySelector('.status');
            const taskEl = card.querySelector('.task');
            
            statusEl.textContent = agent.status;
            statusEl.className = `status ${agent.status.toLowerCase()}`;
            taskEl.textContent = agent.task;
        }
    });
}

function addActivity(message) {
    const activitiesContainer = document.getElementById('activities');
    const activity = document.createElement('div');
    activity.className = 'activity';
    
    const timestamp = new Date().toLocaleTimeString();
    activity.innerHTML = `
        <span class="timestamp">${timestamp}</span>
        <span class="message">${message}</span>
    `;
    
    activitiesContainer.insertBefore(activity, activitiesContainer.firstChild);
    
    // Keep only last 10 activities
    while (activitiesContainer.children.length > 10) {
        activitiesContainer.removeChild(activitiesContainer.lastChild);
    }
}

function updateProgress(percentage) {
    const progressFill = document.querySelector('.progress-fill');
    const progressText = document.querySelector('.progress p');
    
    if (progressFill) {
        progressFill.style.width = `${percentage}%`;
    }
    
    if (progressText) {
        progressText.textContent = `${percentage}% Complete`;
    }
}

function simulateAgentActivity() {
    const activities = [
        'Max analyzed PRD requirements',
        'Neo created new application files',
        'Max delegated build task to Neo',
        'Neo executed implementation plan',
        'Application deployed successfully',
        'Health check passed',
        'Real-time updates active'
    ];
    
    const randomActivity = activities[Math.floor(Math.random() * activities.length)];
    addActivity(randomActivity);
}

// Add CSS for status colors
const style = document.createElement('style');
style.textContent = `
    .status.active { background: #28a745; }
    .status.building { background: #ffc107; color: #000; }
    .status.completed { background: #17a2b8; }
    .status.error { background: #dc3545; }
`;
document.head.appendChild(style);