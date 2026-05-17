// static/install.js - PWA install prompt handler
let deferredPrompt;
window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredPrompt = e;
  // Signal to Streamlit that install is available
  document.body.dataset.installAvailable = 'true';
});
window.installPwa = function() {
  if (deferredPrompt) {
    deferredPrompt.prompt();
    deferredPrompt.userChoice.then(() => { deferredPrompt = null; });
  }
};
