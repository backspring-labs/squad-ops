console.log('Application starting...');

document.addEventListener("DOMContentLoaded", () => {
    const analysisSection = document.querySelector("#dashboard section.analysis");

    try {
        fetch("/analysis_data.json")
            .then(response => response.json())
            .then(data => {
                if (data) {
                    analysisSection.innerHTML = `<p>${data.message}</p>`;
                } else {
                    throw new Error("No data found.");
                }
            })
            .catch(error => {
                console.error('Error fetching analysis data:', error);
                analysisSection.innerHTML = `<p>Error: ${error.message}</p>`;
            });
    } catch (error) {
        console.error('Initialization error:', error);
    }
});