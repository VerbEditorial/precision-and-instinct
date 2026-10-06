/* Sunday-email signup (MailerLite). The form posts the address to MailerLite's own form endpoint. */
(function () {
  var form = document.getElementById('signup-form');
  if (!form) return;
  var msg = form.querySelector('.msg'), btn = form.querySelector('button'), input = form.querySelector('input');
  function say(text, bad) { msg.textContent = text; msg.className = 'msg' + (bad ? ' err' : ''); }
  form.addEventListener('submit', function (ev) {
    ev.preventDefault();
    var email = input.value.trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { say('Enter a valid email address.', true); input.focus(); return; }
    if (form.dataset.offline) { say('Preview only: nothing was sent.', false); return; }
    var fd = new FormData();
    fd.append('fields[email]', email); fd.append('ml-submit', '1'); fd.append('anticsrf', 'true');
    btn.disabled = true; say('Sending...', false);
    fetch('https://assets.mailerlite.com/jsonp/' + form.dataset.mlAccount + '/forms/' + form.dataset.mlForm + '/subscribe', { method: 'POST', body: fd })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (j && j.success) { say('You are on the list. Check your inbox to confirm, then watch for the next case on Sunday.', false); form.reset(); if (window.plausible) window.plausible('Signup'); }
        else { say('That did not go through. Check the address and try again.', true); }
      })
      .catch(function () { say('Could not reach the signup service. Try again in a moment.', true); })
      .then(function () { btn.disabled = false; });
  });
})();
