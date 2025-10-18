import React, { useState, useEffect } from 'react';
import fetchActivities from './activity-feed-service';
import fetchProjectProgress from './project-progress-service';

const TeamStatusDashboard = () => {
    const [activities, setActivities] = useState([]);
    const [progress, setProgress] = useState(null);

    useEffect(() => {
        // Fetch activities
        fetchActivities()
            .then(activitiesData => setActivities(activitiesData))
            .catch(error => console.error('Failed to load activities:', error));

        // Fetch project progress
        fetchProjectProgress()
            .then(progressData => setProgress(progressData))
            .catch(error => console.error('Failed to load project progress:', error));
    }, []);

    return (
        <main>
            <header>
                <h1>HelloSquad - Team Status Dashboard</h1>
            </header>
            <aside>
                <h2>Recent Activities</h2>
                <ul>
                    {activities.map(activity => (
                        <li key={activity.id}>
                            <a href="#">{activity.user} completed task #{activity.taskId}</a>
                        </li>
                    ))}
                </ul>
            </aside>
            <section>
                <h2>Project Progress</h2>
                {progress ? 
                    <p style={{ color: 'green', fontSize: '18px' }}>95% Complete</p> : 
                    <p>Loading...</p>}
                <div className="progress-bar" role="progressbar" aria-valuenow={progress?.percentage || 0} aria-valuemin="0" aria-valuemax="100" style={{ width: `${progress?.percentage}%`, backgroundColor: '#3c8dbc', height: '20px' }}></div>
            </section>
        </main>
    );
};

export default TeamStatusDashboard;

v0.2.0.069 | WarmBoot Run: ECID-WB-069