console.log('TestApp v1.0.0 loaded');
document.addEventListener('DOMContentLoaded', function() {
  fetch('/health').then(response => response.text()).then(data => {
    document.body.insertAdjacentHTML('beforeend', `<p>Health Check: ${data}</p>`);
  });
  fetch('/agents/status').then(response => response.json()).then(data => {
    document.body.insertAdjacentHTML('beforeend', `<p>Agent Status: ${JSON.stringify(data)}</p>`);
  });
});