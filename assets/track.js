/* The RSS.com player is an iframe, so its clicks cannot be tagged. Count the click as a "Hear the whole debate" goal. */
(function () {
  var fired = false;
  window.addEventListener('blur', function () {
    setTimeout(function () {
      var a = document.activeElement;
      if (!fired && a && a.tagName === 'IFRAME' && /player\.rss\.com/.test(a.src || '') && window.plausible) {
        fired = true; window.plausible('Hear the whole debate', { props: { placement: 'embedded player' } });
      }
    }, 0);
  });
})();
