var PI_BASE = (typeof window.PI_BASE === 'string') ? window.PI_BASE : '/';
(function () {
  function navH() { var n = document.querySelector('.nav'); if (n) document.documentElement.style.setProperty('--nav-h', n.offsetHeight + 'px'); }
  navH(); window.addEventListener('resize', navH);
})();
(function () {
  /* episode player: RSS.com embed on the live site; the preview host blocks iframes, so it keeps the link card */
  var host = location.hostname;
  var canEmbed = !/claude|anthropic/.test(host);
  if (canEmbed) {
    document.querySelectorAll('.player[data-rss-ep]').forEach(function (p) {
      var f = document.createElement('iframe');
      f.src = 'https://player.rss.com/' + p.dataset.rssShow + '/' + p.dataset.rssEp + '?theme=dark&v=2';
      f.title = p.dataset.title || 'Episode player';
      f.loading = 'lazy';
      f.setAttribute('scrolling', 'no');
      f.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture';
      f.allowFullscreen = true;
      p.innerHTML = '';
      p.appendChild(f);
    });
  }
})();
(function () {
  var motion = window.gsap && window.ScrollTrigger && window.matchMedia('(prefers-reduced-motion: no-preference)').matches;
  if (motion) { document.documentElement.classList.add('motion'); gsap.registerPlugin(ScrollTrigger); }

  var cases = Array.prototype.slice.call(document.querySelectorAll('.case-view'));
  var ctx = null;

  function scrub(trigger, start, end, extra) {
    return Object.assign({ trigger: trigger, start: start, end: end, scrub: true }, extra || {});
  }

  var heroStingFired = false;

  function buildCase(root) {
    var q = gsap.utils.selector(root);
    function el(sel) { return root.querySelector(sel); }

    /* opening: pin, slow push out of the photo, title rises */
    var open = gsap.timeline({ scrollTrigger: scrub(el('.c-open'), 'top top', '+=90%', { pin: true }) });
    open.fromTo(q('.c-open .bg'), { scale: 1.35 }, { scale: 1, ease: 'none' }, 0)
        .fromTo(q('.c-open .veil'), { opacity: 0.35 }, { opacity: 1, ease: 'none' }, 0)
        .fromTo(q('.c-open .c-title'), { y: 60 }, { y: -30, ease: 'none' }, 0)
        .fromTo(q('.c-icon'), { y: 30, rotation: -10 }, { y: -140, rotation: 5, ease: 'none' }, 0);

    gsap.fromTo(q('.lede > *'), { y: 40, opacity: 0 }, { y: 0, opacity: 1, overwrite: true, stagger: 0.15, duration: 0.8, ease: 'power2.out', scrollTrigger: { trigger: el('.lede'), start: 'top 80%' } });

    /* evidence scene: pinned; the photo holds with one slow push-in while the points build up beside it.
       Wide screens keep earlier points on screen (dimmed); phones show one point at a time. */
    var caps = q('.carry .cap');
    var bars = q('.carry .progress b');
    if (caps.length) {
    var stack = window.matchMedia('(min-width: 721px)').matches;
    var img = el('.carry .frame img');
    /* fit: on wide screens every point stays stacked, so shrink the type until the stack fits the pinned screen (keeps long points from spilling onto the clip below) */
    var capBox = el('.carry .caps');
    function fitCaps() {
      var ps = Array.prototype.slice.call(root.querySelectorAll('.carry .cap p'));
      ps.forEach(function (x) { x.style.fontSize = ''; });
      if (!window.matchMedia('(min-width: 721px)').matches || !capBox) return;
      var size = parseFloat(getComputedStyle(ps[0]).fontSize), limit = window.innerHeight * 0.82;
      while (capBox.getBoundingClientRect().height > limit && size > 15) { size -= 1; ps.forEach(function (x) { x.style.fontSize = size + 'px'; }); }
    }
    fitCaps();
    var fitTimer;
    window.addEventListener('resize', function () { clearTimeout(fitTimer); fitTimer = setTimeout(function () { fitCaps(); ScrollTrigger.refresh(); }, 250); });
    gsap.set(caps, { autoAlpha: 0, y: 24 });
    gsap.set(caps[0], { autoAlpha: 1, y: 0 });
    var carry = gsap.timeline({ scrollTrigger: scrub(el('.carry'), 'top top', '+=320%', { pin: true }) });
    carry.to(bars[0], { scaleX: 1, duration: 1, ease: 'none' });
    for (var i = 1; i < caps.length; i++) {
      carry.to(caps[i - 1], stack ? { opacity: 0.35, duration: 0.4 } : { autoAlpha: 0, y: -24, duration: 0.3 })
           .to(caps[i], { autoAlpha: 1, y: 0, duration: 0.4 }, stack ? '<' : '-=0.1')
           .to(bars[i], { scaleX: 1, duration: 1, ease: 'none' });
    }
    carry.fromTo(img, { scale: 1 }, { scale: 1.12, ease: 'none', duration: carry.duration() }, 0);
    }

    /* suitcase: photo opens like a lid, items check off */
    if (el('.reveal-img')) gsap.fromTo(q('.reveal-img'), { clipPath: 'inset(50% 0% 50% 0%)' }, { clipPath: 'inset(0% 0% 0% 0%)', ease: 'none', scrollTrigger: scrub(el('.split-scene'), 'top 85%', 'top 35%') });
    if (el('.items')) gsap.from(q('.items li'), { x: -30, opacity: 0, stagger: 0.2, ease: 'none', scrollTrigger: scrub(el('.items'), 'top 85%', 'bottom 60%') });

    /* the scrap: letters close in */
    if (el('.scrap')) gsap.fromTo(q('.scrap'), { letterSpacing: '0.5em', opacity: 0 }, { letterSpacing: '0em', opacity: 1, ease: 'none', scrollTrigger: scrub(el('.scrap'), 'top 95%', 'top 45%') });

    /* the code: letters scramble, then settle as you scroll */
    var lines = q('.code-lines .cl');
    if (lines.length) {
    var finals = lines.map(function (l) { if (!l.dataset.final) l.dataset.final = l.textContent; return l.dataset.final; });    var total = finals.join('').length;
    var ABC = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
    function render(p) {
      var settled = Math.floor(p * total), k = 0;
      lines.forEach(function (l, li) {
        var s = '', f = finals[li];
        for (var c = 0; c < f.length; c++, k++) s += k < settled ? f[c] : ABC[(Math.random() * 26) | 0];
        l.textContent = s;
      });
    }
    render(0);
    ScrollTrigger.create({ trigger: el('.code-sheet'), start: 'top 85%', end: 'center 45%', onUpdate: function (self) { render(self.progress); }, onLeave: function () { render(1); } });
    }

    /* two verdicts close in on the seam */
    if (el('.verdicts')) {
      gsap.from(q('.verdicts .v-a'), { xPercent: -105, ease: 'none', scrollTrigger: scrub(el('.verdicts'), 'top 95%', 'top 45%') });
      gsap.from(q('.verdicts .v-b'), { xPercent: 105, ease: 'none', scrollTrigger: scrub(el('.verdicts'), 'top 95%', 'top 45%') });
    }

    /* timeline: vertical scroll drives a horizontal track */
    var track = el('.tl-track');
    function dist() { return Math.max(0, track.scrollWidth - window.innerWidth + 32); }
    gsap.to(track, { x: function () { return -dist(); }, ease: 'none',
      scrollTrigger: { trigger: el('.tl-pin'), start: 'top top', end: function () { return '+=' + dist(); }, pin: true, scrub: true, invalidateOnRefresh: true } });

    /* the two readings slide in from opposite sides */
    gsap.from(q('.brief-precision'), { xPercent: -110, ease: 'none', scrollTrigger: scrub(el('.briefs'), 'top 95%', 'top 45%') });
    gsap.from(q('.brief-instinct'), { xPercent: 110, ease: 'none', scrollTrigger: scrub(el('.briefs'), 'top 95%', 'top 45%') });

    /* no verdict */
    gsap.fromTo(q('.nv'), { scale: 0.7, opacity: 0 }, { scale: 1, opacity: 1, ease: 'none', scrollTrigger: scrub(el('.verdict'), 'top 90%', 'top 40%') });
    gsap.fromTo(q('.questions li'), { y: 30, opacity: 0 }, { y: 0, opacity: 1, overwrite: true, stagger: 0.15, duration: 0.7, ease: 'power2.out', scrollTrigger: { trigger: el('.questions'), start: 'top 85%' } });
  }

  function show() {
    var active = cases[0];
    if (ctx) { ctx.revert(); ctx = null; }
    document.querySelectorAll('.code-lines .cl').forEach(function (l) { if (l.dataset.final) l.textContent = l.dataset.final; });
    if (typeof bedForView === 'function') bedForView(true);
    if (motion) {
      ctx = gsap.context(function () { buildCase(active); }, active);
      ScrollTrigger.refresh();
    }
  }

  /* audio clips: one at a time; a missing file shows as "Clip coming" */
  document.querySelectorAll('[data-clip]').forEach(function (fig) {
    var a = fig.querySelector('audio'), btn = fig.querySelector('.clip-btn'), st = fig.querySelector('.clip-state'), bar = fig.querySelector('.clip-bar i');
    function off(msg) { fig.classList.add('unavailable'); fig.classList.remove('playing'); st.textContent = msg; btn.disabled = true; }
    a.addEventListener('error', function () { off('Clip coming'); });
    a.addEventListener('timeupdate', function () { if (a.duration) bar.style.width = (a.currentTime / a.duration * 100) + '%'; });
    a.addEventListener('ended', function () { fig.classList.remove('playing'); st.textContent = 'Listen again'; });
    btn.addEventListener('click', function () {
      if (a.paused) {
        document.querySelectorAll('[data-clip] audio').forEach(function (o) { if (o !== a) o.pause(); });
        document.querySelectorAll('[data-clip].playing').forEach(function (f) { if (f !== fig) f.classList.remove('playing'); });
        var pr = a.play();
        if (pr && pr.catch) pr.catch(function () { off('Clip coming'); });
        fig.classList.add('playing'); st.textContent = 'Playing';
      } else { a.pause(); fig.classList.remove('playing'); st.textContent = 'Paused'; }
    });
    fetch(a.getAttribute('src'), { method: 'HEAD' }).then(function (r) { if (r.status === 404) off('Clip coming'); }).catch(function () {});  /* only a real 404 marks a clip missing; a host that refuses HEAD requests must not disable working clips */
  });

  /* ——— music bed: on by default; browsers only allow sound after the visitor's first click, tap or key press ——— */
  var BED = PI_BASE + 'audio/beds/bed-detective-theme.mp3';
  var LEVEL = 0.5;
  var sound = document.getElementById('sound'), sbtn = document.getElementById('sound-btn');
  var ac = null, gain = null, srcNode = null, bedBuf = null, onCase = false;
  var wanted = true;
  try { if (localStorage.getItem('pi-sound') === 'off') wanted = false; } catch (e) {}
  function getAudio() {
    if (!ac) { var AC = window.AudioContext || window.webkitAudioContext; if (!AC) return null; ac = new AC(); gain = ac.createGain(); gain.gain.value = 0; gain.connect(ac.destination); }
    return ac;
  }
  function edges(buf) {
    var d = buf.getChannelData(0), n = d.length, lim = Math.min(n, Math.floor(buf.sampleRate * 0.15)), a = 0, z = n - 1;
    while (a < lim && Math.abs(d[a]) < 1e-4) a++;
    while (z > n - lim && Math.abs(d[z]) < 1e-4) z--;
    return [a / buf.sampleRate, (z + 1) / buf.sampleRate];
  }
  function load() {
    if (bedBuf) return Promise.resolve(bedBuf);
    return fetch(BED).then(function (r) { return r.arrayBuffer(); }).then(function (ab) {
      return new Promise(function (res, rej) { ac.decodeAudioData(ab, res, rej); });
    }).then(function (b) { bedBuf = { buf: b, loop: edges(b) }; return bedBuf; });
  }
  function ramp(to, secs) { var t = ac.currentTime; gain.gain.cancelScheduledValues(t); gain.gain.setValueAtTime(gain.gain.value, t); gain.gain.linearRampToValueAtTime(to, t + secs); }
  function stopNode(delay) { var n = srcNode; srcNode = null; sound.classList.remove('playing'); if (n) setTimeout(function () { try { n.stop(); } catch (e) {} }, delay || 0); }
  function play() {
    if (!getAudio()) return;
    ac.resume();
    loadSting();
    load().then(function (b) {
      if (!wanted || onCase || srcNode) return;
      var n = ac.createBufferSource(); n.buffer = b.buf; n.loop = true; n.loopStart = b.loop[0]; n.loopEnd = b.loop[1];
      n.connect(gain); n.start(0, b.loop[0]); srcNode = n; sound.classList.add('playing');
      ramp(LEVEL, 2.5);
    }).catch(function () { sbtn.querySelector('.lbl').textContent = 'Sound unavailable'; });
  }
  function fadeOut() { if (ac && srcNode) { ramp(0, 0.8); stopNode(900); } }
  /* transition sting: plays over the bed as the color blocks clear */
  var STING = PI_BASE + 'audio/beds/sting-transition.mp3', stingBuf = null, lastSting = 0;
  function loadSting() {
    if (stingBuf || !ac) return;
    fetch(STING).then(function (r) { return r.arrayBuffer(); }).then(function (ab) {
      return new Promise(function (res, rej) { ac.decodeAudioData(ab, res, rej); });
    }).then(function (b) { stingBuf = b; }).catch(function () {});
  }
  function playSting() {
    if (!wanted || onCase || !ac || ac.state !== 'running' || !stingBuf) return;
    var now = Date.now(); if (now - lastSting < 2500) return; lastSting = now;
    var n = ac.createBufferSource(), g = ac.createGain(); g.gain.value = 0.9;
    n.buffer = stingBuf; n.connect(g); g.connect(ac.destination); n.start();
  }
  /* intro theme: plays once each time a case file opens; stops for a clip or on leaving */
  /* intro and outro share one slot: starting one fades the other. Levels even out the two files (the outro is mixed ~3 dB quieter) */
  var THEMES = { intro: { url: PI_BASE + 'audio/beds/intro-theme.mp3', level: 0.85 }, outro: { url: PI_BASE + 'audio/beds/outro-theme.mp3', level: 1.15 } };
  var themeBufs = {}, themeNode = null, themeG = null, outroDone = false;
  function loadTheme(k) {
    if (!themeBufs[k]) themeBufs[k] = fetch(THEMES[k].url).then(function (r) { return r.arrayBuffer(); }).then(function (ab) {
      return new Promise(function (res, rej) { ac.decodeAudioData(ab, res, rej); });
    }).catch(function (e) { themeBufs[k] = null; throw e; });
    return themeBufs[k];
  }
  function clipPlaying() { return !!document.querySelector('[data-clip].playing'); }
  function playTheme(k) {
    k = k || 'intro';
    if (!wanted || !onCase || !getAudio()) return;
    if (themeNode && themeNode._k === k) return;
    if (k === 'intro' && themeNode) return;
    ac.resume();
    if (k === 'intro') loadTheme('outro').catch(function () {});   /* have the outro ready by the bottom */
    loadTheme(k).then(function (b) {
      if (!wanted || !onCase || clipPlaying() || (themeNode && themeNode._k === k)) return;
      if (themeNode) stopTheme(0.6);
      var g = ac.createGain(); g.gain.value = THEMES[k].level; g.connect(ac.destination);
      var n = ac.createBufferSource(); n.buffer = b; n._k = k; n.connect(g); n.start();
      themeNode = n; themeG = g;
      sound.hidden = false; sound.classList.add('playing');
      n.onended = function () { if (themeNode === n) { themeNode = null; if (onCase && !cbNode) { sound.classList.remove('playing'); sound.hidden = true; } } };
      if (k === 'intro') { clearTimeout(cbTimer); cbTimer = setTimeout(function () { caseBedStart(); }, Math.max(0, b.duration - 2.5) * 1000); }
    }).catch(function () {});
  }
  function stopTheme(secs) {
    if (!themeNode) return;
    var n = themeNode, g = themeG, t = ac.currentTime; themeNode = null;
    g.gain.cancelScheduledValues(t); g.gain.setValueAtTime(g.gain.value, t); g.gain.linearRampToValueAtTime(0, t + secs);
    setTimeout(function () { try { n.stop(); } catch (e) {} }, secs * 1000 + 100);
    if (onCase && !cbNode) { sound.classList.remove('playing'); sound.hidden = true; }
  }
  /* case bed: loops under the reading, from the tail of the intro until the outro takes over */
  /* the file carries 1 s of the loop's own tail before it and head after it; looping between those fixed points
     keeps the MP3's padding out of the loop entirely, so there is no click */
  var CBED = { url: PI_BASE + 'audio/beds/bed-investigative.mp3', level: 1.0, loopStart: 1.0, loopLen: 28.5 };
  var cbBuf = null, cbNode = null, cbG = null, cbTimer = null;
  function loadCaseBed() {
    if (!cbBuf) cbBuf = fetch(CBED.url).then(function (r) { return r.arrayBuffer(); }).then(function (ab) {
      return new Promise(function (res, rej) { ac.decodeAudioData(ab, res, rej); });
    }).then(function (b) { return { buf: b, loop: [CBED.loopStart, CBED.loopStart + CBED.loopLen] }; }).catch(function (e) { cbBuf = null; throw e; });
    return cbBuf;
  }
  function caseBedStart() {
    if (!wanted || !onCase || outroDone || cbNode || !getAudio()) return;
    ac.resume();
    loadCaseBed().then(function (b) {
      if (!wanted || !onCase || outroDone || cbNode) return;
      var g = ac.createGain(), t = ac.currentTime; g.gain.value = 0; g.connect(ac.destination);
      var n = ac.createBufferSource(); n.buffer = b.buf; n.loop = true; n.loopStart = b.loop[0]; n.loopEnd = b.loop[1];
      n.connect(g); n.start(0, b.loop[0]);
      g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(clipPlaying() ? 0 : CBED.level, t + 3);
      cbNode = n; cbG = g; sound.hidden = false; sound.classList.add('playing');
    }).catch(function () {});
  }
  function caseBedLevel(to, secs) {
    if (!cbG) return; var t = ac.currentTime;
    cbG.gain.cancelScheduledValues(t); cbG.gain.setValueAtTime(cbG.gain.value, t); cbG.gain.linearRampToValueAtTime(to, t + secs);
  }
  function caseBedStop(secs) {
    clearTimeout(cbTimer);
    if (!cbNode) return;
    var n = cbNode; caseBedLevel(0, secs); cbNode = null; cbG = null;
    setTimeout(function () { try { n.stop(); } catch (e) {} }, secs * 1000 + 100);
    if (onCase && !themeNode) { sound.classList.remove('playing'); sound.hidden = true; }
  }
  /* a clip takes the floor: the bed dips out, then comes back once no clip is playing */
  document.querySelectorAll('[data-clip] audio').forEach(function (au) {
    au.addEventListener('play', function () { clearTimeout(cbTimer); caseBedLevel(0, 0.5); });
    function back() { setTimeout(function () {
      if (clipPlaying() || !onCase || outroDone || themeNode) return;
      if (cbNode) caseBedLevel(CBED.level, 2); else caseBedStart();
    }, 400); }
    au.addEventListener('pause', back); au.addEventListener('ended', back);
  });
  document.querySelectorAll('[data-clip] .clip-btn').forEach(function (b) { b.addEventListener('click', function () { stopTheme(0.5); }); });
  /* outro: once per visit, when the reader reaches the bottom of the case file */
  var caseEnds = document.querySelectorAll('.case-view .verdict footer');
  if (caseEnds.length && 'IntersectionObserver' in window) {
    var outroObs = new IntersectionObserver(function (es) {
      es.forEach(function (en) {
        if (!en.isIntersecting || outroDone || !onCase || !wanted || !ac || ac.state !== 'running') return;
        outroDone = true; caseBedStop(1.5); playTheme('outro');
      });
    }, { threshold: 0.6 });
    Array.prototype.forEach.call(caseEnds, function (e) { outroObs.observe(e); });
  }
  /* clicking into the episode player moves focus into its frame: take that as "they're listening" and fade out */
  window.addEventListener('blur', function () {
    setTimeout(function () { var el = document.activeElement; if (el && el.tagName === 'IFRAME' && el.closest('.player')) { stopTheme(0.5); caseBedStop(0.5); } }, 0);
  });
  function setUI() {
    sound.classList.toggle('on', wanted);
    sbtn.setAttribute('aria-pressed', String(wanted));
    sbtn.querySelector('.lbl').textContent = !wanted ? 'Sound off' : (sound.classList.contains('playing') ? 'Sound on' : 'Tap for sound');
  }
  /* the label tells the truth: "Sound on" only once music is actually playing */
  if (window.MutationObserver) new MutationObserver(function () { setUI(); }).observe(sound, { attributes: true, attributeFilter: ['class'] });
  function remember() { try { localStorage.setItem('pi-sound', wanted ? 'on' : 'off'); } catch (e) {} }
  sbtn.addEventListener('click', function () {
    if (onCase) { wanted = !wanted; setUI(); remember(); if (!wanted) { stopTheme(0.6); caseBedStop(0.6); } else if (!outroDone) caseBedStart(); return; }
    if (wanted && !srcNode) { play(); return; }          /* on, but not started yet: start it */
    wanted = !wanted; setUI(); remember();
    if (wanted) play(); else fadeOut();
  });
  function firstGesture(e) {
    document.removeEventListener('pointerdown', firstGesture, true);
    document.removeEventListener('keydown', firstGesture, true);
    if (sbtn.contains(e.target)) return;                 /* the button handles its own click */
    if (!wanted) return;
    if (!onCase) { play(); return; }
    /* opened straight from a link: the theme starts on the first click, unless that click is a clip or they've read well past the opening */
    if (e.target.closest('[data-clip], .player')) return;
    if (window.scrollY < window.innerHeight * 1.5) playTheme(); else caseBedStart();
  }
  document.addEventListener('pointerdown', firstGesture, true);
  document.addEventListener('keydown', firstGesture, true);
  function bedForView(isCase) {
    onCase = isCase;
    caseBedStop(0.8);
    if (isCase) { outroDone = false; fadeOut(); stopTheme(0.6); sound.hidden = true; if (wanted && ac) playTheme('intro'); }
    else { stopTheme(0.8); sound.hidden = false; if (wanted && ac) play(); }
  }
  setUI();
  if ('scrollRestoration' in history) history.scrollRestoration = 'manual';
  /* ScrollTrigger puts scrollRestoration back to 'auto' after each refresh: pin it to manual, and start every page at the top (unless it was opened at an anchor) */
  if (window.ScrollTrigger && ScrollTrigger.clearScrollMemory) ScrollTrigger.clearScrollMemory('manual');
  (function () {
    if (location.hash) return;
    var goTop = function () { window.scrollTo(0, 0); if (window.self !== window.top) { try { document.documentElement.scrollIntoView(); } catch (e) {} } };
    goTop(); requestAnimationFrame(goTop); setTimeout(goTop, 80);
  })();
  show();
})();

  /* animated scene pictures: play only while on screen, and not at all for reduced motion */
  (function () {
    var vids = document.querySelectorAll('video.scene-video');
    if (!vids.length || !('IntersectionObserver' in window) || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    var io = new IntersectionObserver(function (es) { es.forEach(function (en) { if (en.isIntersecting) { en.target.play().catch(function () {}); } else { en.target.pause(); } }); }, { threshold: 0.35 });
    for (var i = 0; i < vids.length; i++) io.observe(vids[i]);
  })();
