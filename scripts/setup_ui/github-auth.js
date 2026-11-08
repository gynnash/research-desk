'use strict';

(() => {
  if (window === window.top) return;
  let authorization = null;

  window.openGitHubAuthorization = (attempt) => {
    if (authorization?.attempt === attempt && !authorization.tab.closed) {
      authorization.tab.focus();
      return true;
    }
    // Give GitHub an opener in this frame instead of the top-level wizard.
    const tab = window.open('https://github.com/login/device', '_blank');
    if (!tab) return false;
    authorization = {tab, attempt};
    return true;
  };

  window.finishGitHubAuthorization = (attempt) => {
    if (!authorization || authorization.attempt !== attempt) return;
    const {tab} = authorization;
    authorization = null;
    window.setTimeout(() => tab.close(), 3000);
  };
})();
