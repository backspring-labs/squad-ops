const fetchApiData = async (url) => {
    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    } catch (error) {
        console.error("API request failed:", error);
        return Promise.reject(error);
    }
};

const updateAgentStatus = () => {
    fetchApiData("/api/agents/status")
        .then(data => {
            if (data && data.status) {
                document.getElementById("agent-status").innerHTML = `<p>Agent Status: ${data.status}</p>`;
            } else {
                throw new Error("No status found");
            }
        })
        .catch(error => {
            console.error("Error fetching agent status:", error);
            document.getElementById("agent-status").innerHTML = "<p>Error fetching agent status</p>";
        });
};

const updateHealthCheck = () => {
    fetchApiData("/api/health")
        .then(data => {
            if (data && data.version) {
                const version = data.version;
                document.getElementById("health-check").innerHTML = `<p>Framework Version: ${version}</p>`;
            } else {
                throw new Error("No health check found");
            }
        })
        .catch(error => {
            console.error("Error fetching health check:", error);
            document.getElementById("health-check").innerHTML = "<p>Error fetching health check</p>";
        });
};

window.onload = () => {
    updateAgentStatus();
    updateHealthCheck();
};