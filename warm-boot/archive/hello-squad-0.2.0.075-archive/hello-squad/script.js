document.addEventListener("DOMContentLoaded", () => {
    const agentStatusSection = document.getElementById("agent-status");
    const healthCheckSection = document.getElementById("health-check");

    fetch("/api/agents/status")
        .then(response => response.json())
        .then(data => {
            if (data && data.status) {
                agentStatusSection.innerHTML = `<p>Agent Status: ${data.status}</p>`;
            } else {
                throw new Error("No status found");
            }
        })
        .catch(error => {
            console.error("Error fetching agent status:", error);
            agentStatusSection.innerHTML = "<p>Error fetching agent status</p>";
        });

    fetch("/api/health")
        .then(response => response.json())
        .then(data => {
            if (data && data.version) {
                const version = data.version;
                healthCheckSection.innerHTML = `<p>Framework Version: ${version}</p>`;
            } else {
                throw new Error("No health check found");
            }
        })
        .catch(error => {
            console.error("Error fetching health check:", error);
            healthCheckSection.innerHTML = "<p>Error fetching health check</p>";
        });
});