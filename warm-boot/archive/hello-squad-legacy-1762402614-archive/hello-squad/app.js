console.log('Application loaded');
document.addEventListener('DOMContentLoaded', function() {
  fetch('/health').then(response => response.text()).then(version => {
    document.querySelector('footer').innerText = `v${version} | WarmBoot Run: ECID-WB-149`;
  });
});