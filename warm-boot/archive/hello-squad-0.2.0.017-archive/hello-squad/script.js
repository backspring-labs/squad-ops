```javascript
// helloSquad.js

/**
 * HelloSquad Application
 */

(function() {
    const app = {};

    // Constants
    const TEAM_ID = "12345";
    const API_URL = `https://api.hello-squad.com/v1/team/${TEAM_ID}`;

    // DOM Elements
    const dashboardContainer = document.getElementById('team-status-dashboard');
    const activityFeedContainer = document.getElementById('activity-feed');
    const projectProgressContainer = document.getElementById('project-progress-tracking');

    // Data Models
    class TeamStatus {
        constructor(teamId) {
            this.teamId = teamId;
            this.status = '';
        }

        async fetchStatus() {
            try {
                const response = await fetch(`${API_URL}/status`);
                if (response.ok) {
                    const data = await response.json();
                    this.status = data.status;
                } else {
                    throw new Error('Failed to fetch team status');
                }
            } catch (error) {
                console.error(error);
                alert('Error fetching team status. Please try again later.');
            }
        }

        updateUI() {
            dashboardContainer.innerHTML = `<p>Status: ${this.status}</p>`;
        }
    }

    class ActivityFeed {
        constructor(teamId) {
            this.teamId = teamId;
            this.activities = [];
        }

        async fetchActivities() {
            try {
                const response = await fetch(`${API_URL}/activities`);
                if (response.ok) {
                    const data = await response.json();
                    this.activities = data.activities;
                } else {
                    throw new Error('Failed to fetch activity feed');
                }
            } catch (error) {
                console.error(error);
                alert('Error fetching activity feed. Please try again later.');
            }
        }

        updateUI() {
            const feedItems = this.activities.map(activity => `<li>${activity}</li>`).join('');
            activityFeedContainer.innerHTML = `<ul>${feedItems}</ul>`;
        }
    }

    class ProjectProgress {
        constructor(teamId) {
            this.teamId = teamId;
            this.progress = 0;
        }

        async fetchProgress() {
            try {
                const response = await fetch(`${API_URL}/progress`);
                if (response.ok) {
                    const data = await response.json();
                    this.progress = data.progress;
                } else {
                    throw new Error('Failed to fetch project progress');
                }
            } catch (error) {
                console.error(error);
                alert('Error fetching project progress. Please try again later.');
            }
        }

        updateUI() {
            const progressBar = document.getElementById('progress-bar');
            progressBar.style.width = this.progress + '%';
            progressBar.setAttribute('aria-valuenow', this.progress);
            projectProgressContainer.innerHTML = `<p>Project Progress: ${this.progress}%</p>`;
        }
    }

    // Event Listeners
    app.init = function() {
        const teamStatus = new TeamStatus(TEAM_ID);
        const activityFeed = new ActivityFeed(TEAM_ID);
        const projectProgress = new ProjectProgress(TEAM_ID);

        teamStatus.fetchStatus();
        activityFeed.fetchActivities();
        projectProgress.fetchProgress();

        setInterval(() => {
            teamStatus.fetchStatus().then(teamStatus.updateUI.bind(teamStatus));
            activityFeed.fetchActivities().then(activityFeed.updateUI.bind(activityFeed));
            projectProgress.fetchProgress().then(projectProgress.updateUI.bind(projectProgress));
        }, 5000); // Update every 5 seconds
    };

    app.init();
})();
```

```html
<!-- index.html -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HelloSquad</title>
</head>
<body>
    <div id="team-status-dashboard"></div>
    <div id="activity-feed"></div>
    <div id="project-progress-tracking">
        <progress id="progress-bar" value="50" max="100"></progress>
    </div>

    <script src="helloSquad.js"></script>
</body>
</html>
```