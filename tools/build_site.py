#!/usr/bin/env python3
"""Build the public site from tools/site-source.html.

tools/site-source.html is the source of truth: the whole site as one file (render.py splices each case's markup into it).
It is NOT served as a page (noindex, and robots.txt disallows /tools/). This script reads it and writes:
  index.html                 the home page: a light index of cases (real links, no case markup)
  cases/<slug>/index.html    one page per released case
  assets/site.css, case.js, home.js, signup.js
  sitemap.xml, robots.txt

Per-episode settings live in tools/cases.json (slug, h1, seo_title, description, og_image, and, for the newest
episode, a "feature" block for the Latest case file box). Site-wide settings (analytics, signup)
live in tools/site-config.json. The "Coming Sunday" teaser comes from tools/coming.json.
Only RELEASED episodes get a page. An unreleased episode is refused, and must not be in tools/cases.json
(or anywhere else in the public repo) until its release day.

Usage:
  python3 tools/build_site.py --all-released             # rebuild everything
  python3 tools/build_site.py --only 01 02               # rebuild just these case pages (plus home, sitemap, assets)
  python3 tools/build_site.py --all-released --preview-dir DIR
        # private preview copy: relative links, noindex, no analytics, signup shown offline. Not for the live site.
"""
import argparse, datetime, html, json, pathlib, re, sys
from urllib.parse import urlencode

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = "https://precisionandinstinct.com"
REQUIRED = ("slug", "h1", "seo_title", "description", "og_image")


def die(msg):
    sys.exit("build_site: " + msg)


def between(text, start, end, include_start=True):
    i = text.find(start)
    if i < 0:
        die("anchor not found: %r" % start[:60])
    j = text.find(end, i + len(start))
    if j < 0:
        die("anchor not found: %r" % end[:60])
    return text[i if include_start else i + len(start):j]


def load():
    src = (ROOT / "tools" / "site-source.html").read_text(encoding="utf-8")
    # episodes array and case-file map, parsed so site-source.html stays the single source of truth
    eps_block = between(src, "var eps = [", "];", include_start=False)
    eps = []
    for m in re.finditer(r"\[\s*'((?:[^'\\]|\\.)*)',\s*'([^']*)',\s*'([^']*)',\s*'([^']*)'(?:,\s*'([^']*)')?\s*\]", eps_block):
        eps.append({"title": m.group(1).replace("\\'", "'"), "years": m.group(2), "status": m.group(3),
                    "notes": m.group(4), "release": m.group(5)})
    if len(eps) < 12:
        die("could not parse eps array")
    cf_line = between(src, "var CASEFILES = {", "};", include_start=False)
    hashes = dict(re.findall(r"'(\d\d)':\s*'(#[^']+)'", cf_line))
    return src, eps, hashes


def extract_css(src):
    css = between(src, "<style>\n", "\n</style>", include_start=False)
    return css.replace('url("img/', 'url("/img/')


def extract_js(src):
    main = between(src, "<script>\n(function () {\n  function navH()", "</script>\n</body>")
    main = main[len("<script>\n"):]
    # 1. nav height + RSS player embed (everything before the home-grid block)
    part1 = between(main, "(function () {\n  function navH()", "(function () {\n  /* case grid */")
    # 2. motion flag, scrub helper, buildCase, clip audio, sound, scene videos (home grid, teaser, buildHome and the
    #    hash router are left out: a case page is one fixed view)
    motion = between(main, "  var motion = window.gsap", "  var home = document.getElementById('view-home');")
    cases_ctx = ("  var cases = Array.prototype.slice.call(document.querySelectorAll('.case-view'));\n"
                 "  var ctx = null;\n\n")
    scrub = between(main, "  function scrub(", "  var heroStingFired = false;") + "  var heroStingFired = false;\n"
    build_case = between(main, "  function buildCase(root) {", "  function show() {")
    show = ("  function show() {\n"
            "    var active = cases[0];\n"
            "    if (ctx) { ctx.revert(); ctx = null; }\n"
            "    document.querySelectorAll('.code-lines .cl').forEach(function (l) { if (l.dataset.final) l.textContent = l.dataset.final; });\n"
            "    if (typeof bedForView === 'function') bedForView(true);\n"
            "    if (motion) {\n"
            "      ctx = gsap.context(function () { buildCase(active); }, active);\n"
            "      ScrollTrigger.refresh();\n"
            "    }\n"
            "  }\n\n")
    tail = between(main, "  /* audio clips: one at a time", "  window.addEventListener('hashchange', show);")
    after = main[main.index("  show();\n})();"):]
    js = part1 + "(function () {\n" + motion + cases_ctx + scrub + "\n" + build_case + show + tail + after
    # sanity: nothing left that belongs to the home view or the router
    for bad in ("CASEFILES", "buildHome", "case-grid", "released", "hashchange", "view-home"):
        if bad in js:
            die("home/router code left in case.js: " + bad)
    js = fix_audio_paths(js)
    return js


def fix_audio_paths(js):
    # music files are relative in the source; on /cases/<slug>/ pages they must resolve from the site root
    # (the page sets window.PI_BASE: "/" on the live site, "../" or "" in a private preview)
    js, n = re.subn(r"'(audio/beds/[^']+)'", r"PI_BASE + '\1'", js)
    if n < 1 or re.search(r"(?<!PI_BASE \+ )'audio/", js):
        die("music paths were not all rewritten (found %d)" % n)
    return "var PI_BASE = (typeof window.PI_BASE === 'string') ? window.PI_BASE : '/';\n" + js


def extract_home_js(src):
    """The home page script: nav height, hero scenes, sound. No case, player or router code."""
    main = between(src, "<script>\n(function () {\n  function navH()", "</script>\n</body>")
    main = main[len("<script>\n"):]
    nav = between(main, "(function () {\n  function navH()", "(function () {\n  /* episode player")
    motion = between(main, "  var motion = window.gsap", "  var home = document.getElementById('view-home');")
    scrub_home = between(main, "  function scrub(", "  function buildCase(root) {")   # scrub, hero sting, buildHome
    show = ("  var home = document.getElementById('view-home');\n"
            "  var ctx = null;\n\n" + scrub_home +
            "  function show() {\n"
            "    if (ctx) { ctx.revert(); ctx = null; }\n"
            "    document.querySelectorAll('.code-lines .cl').forEach(function (l) { if (l.dataset.final) l.textContent = l.dataset.final; });\n"
            "    if (typeof bedForView === 'function') bedForView(false);\n"
            "    if (motion) {\n"
            "      ctx = gsap.context(buildHome);\n"
            "      ScrollTrigger.refresh();\n"
            "    }\n"
            "    /* arriving from a case page's 'All case files' link lands on the grid; anything else starts at the top */\n"
            "    var place = function () { var t = document.getElementById('cases'); if (location.hash === '#cases' && t) t.scrollIntoView(); else window.scrollTo(0, 0); };\n"
            "    place(); requestAnimationFrame(place);\n"
            "    setTimeout(function () { place(); if (motion) ScrollTrigger.update(); }, 60);\n"
            "  }\n\n")
    sound = between(main, "  /* ——— music bed", "  window.addEventListener('hashchange', show);")
    after = main[main.index("  window.addEventListener('hashchange', show);"):]
    js = nav + "(function () {\n" + motion + show + sound + after
    for bad in ("CASEFILES", "buildCase", "case-grid", "released", "view-case", "[data-clip]"):
        if bad in js and bad != "[data-clip]":
            die("case/router code left in home.js: " + bad)
    return fix_audio_paths(js)


def case_blocks(src, hashes):
    """Return {num: that case's <div class="case-view"> ... </div> markup}."""
    out = {}
    for num, h in hashes.items():
        m = re.search(r'<div id="view-case[^"]*" class="case-view" data-hash="%s" hidden>' % re.escape(h), src)
        if not m:
            die("case view not found for %s %s" % (num, h))
        start = m.start()
        end = src.index("\n</div>\n", start) + len("\n</div>")
        out[num] = src[start:end]
    return out


def rootify(markup, prefix):
    markup = re.sub(r'(src|poster|href)="(img|audio|vendor)/', r'\1="' + prefix + r'\2/', markup)
    markup = re.sub(r"url\('(img|audio)/", r"url('" + prefix + r"\1/", markup)
    markup = re.sub(r'url\("(img|audio)/', r'url("' + prefix + r'\1/', markup)
    return markup


def build_page(num, eps, hashes, blocks, cfg, urls, released_nums, preview, conf):
    ep = eps[int(num) - 1]
    c = cfg[num]
    slug = c["slug"]
    prefix = "../" if preview else "/"
    url = "%s/cases/%s/" % (SITE, slug)
    home_href = "../index.html" if preview else "/"
    cases_href = "../index.html" if preview else "/#cases"
    block = blocks[num]
    # unwrap the view div into <main>, visible
    block = re.sub(r'^<div id="view-case[^"]*" class="case-view" data-hash="[^"]*" hidden>', '<main id="case" class="case-view">', block, count=1)
    block = re.sub(r"</div>$", "</main>", block)
    # the headline leads with the term people search for
    block, n = re.subn(r"<h1>.*?</h1>", "<h1>%s</h1>" % html.escape(c["h1"], quote=False), block, count=1, flags=re.S)
    if n != 1:
        die("no <h1> in case %s" % num)
    block = rootify(block, prefix)
    block = block.replace('href="#cases"', 'href="%s"' % cases_href)
    # preview-only wording becomes plain wording (this note is what visitors see if the embed does not load)
    block = re.sub(r"Plays here on the live site\. In this preview it opens on RSS\.com\.", "Opens the full episode on RSS.com.", block)
    # end-of-case navigation, written into the HTML (the home page builds the same thing in script)
    idx = released_nums.index(num)
    nxt = released_nums[(idx + 1) % len(released_nums)]
    nav = ['<nav class="case-end" aria-label="Keep going">',
           '<a class="home-btn" href="%s"><span class="k">Back to the archive</span><span class="t">&larr; All case files</span></a>' % cases_href]
    if nxt != num:
        if nxt in urls:
            nxt_href = (cfg[nxt]["slug"] + ".html") if preview else urls[nxt]
        else:
            nxt_href = cases_href if preview else "/" + hashes[nxt]
        nav.append('<a class="next-file" href="%s"><span class="k">Next case file &middot; Episode %s</span><span class="t">%s <span style="color:var(--accent)">&rarr;</span></span></a>'
                   % (nxt_href, nxt, html.escape(eps[int(nxt) - 1]["title"], quote=False)))
    nav.append("</nav>")
    marker = '<footer style="text-align:left">'
    i = block.rfind(marker)
    if i < 0:
        die("end footer not found in case %s" % num)
    form = signup_html(conf, preview)
    block = block[:i] + "".join(nav) + "\n    " + (form + "\n    " if form else "") + block[i:]
    # footer: the AI-voice disclosure, then copyright and the privacy link. No mailing address on the website.
    block, k = re.subn(r'(<footer style="text-align:left">.*?<p class="small">.*?</p>)', lambda m: m.group(1) + footer_lines(prefix, preview), block, count=1, flags=re.S)
    if k != 1:
        die("footer not found in case %s" % num)
    block = decorate_links(block, slug, "page")
    # every asset path must now be root-relative (or ../ in a preview): a bare "img/..." would break on /cases/<slug>/
    left = re.findall(r"""["'(]((?:img|audio|vendor)/[^"')\s]*)""", block)
    if left:
        die("relative asset paths left in case %s: %s" % (num, left[:3]))
    t, d = html.escape(c["seo_title"]), html.escape(c["description"])
    # a headline with one very long word (HAMMARSKJÖLD) is scaled so that word fits the screen.
    # h1_word_em = width of the longest word in em units (measure once, see README)
    em = c.get("h1_word_em")
    fit = ("<style>.c-open h1{font-size:min(clamp(44px,10vw,112px),calc((100vw - 56px) / %s))}</style>\n" % em) if em else ""
    if preview:
        seo = '<meta name="robots" content="noindex, nofollow">'
    else:
        seo = f"""<link rel="canonical" href="{url}">
<meta name="robots" content="index, follow">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Precision &amp; Instinct">
<meta property="og:title" content="{t}">
<meta property="og:description" content="{d}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{SITE}{c["og_image"]}">
<meta name="twitter:card" content="summary_large_image">"""
    case_nav = decorate_links(f"""<nav class="nav">
  <a class="nav-brand" href="{home_href}">PRECISION <span class="amp">&amp;</span> INSTINCT</a>
  <a href="{cases_href}">Case files</a>
  <a href="https://notes.precisionandinstinct.com/episodes/">Sources</a>
  <a class="btn-primary" href="https://precisionandinstinct.taplink.bio">Where to listen &rarr;</a>
</nav>
""", slug, "nav")
    head = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t}</title>
<meta name="description" content="{d}">
{seo}
{head_common(conf, prefix, preview)}{fit}</head>
<body>

{case_nav}
"""
    extra_scripts = ('<script src="%sassets/signup.js"></script>\n' % prefix if form else "") + ('<script src="%sassets/track.js"></script>\n' % prefix if (conf["plausible"].get("enabled") and not preview) else "")
    tail = f"""

<div class="sound" id="sound">
  <button class="sound-btn" id="sound-btn" type="button" aria-pressed="false"><span class="bars" aria-hidden="true"><i></i><i></i><i></i><i></i></span><span class="lbl">Sound off</span></button>
</div>

<script>window.PI_BASE = "{prefix}";</script>
<script src="{prefix}vendor/gsap.min.js"></script>
<script src="{prefix}vendor/ScrollTrigger.min.js"></script>
<script src="{prefix}assets/case.js"></script>
{extra_scripts}</body>
</html>
"""
    return head + block + tail


# ───────────────────────── site-wide pieces ─────────────────────────
COPYRIGHT = "\u00a9 2026 Verb Editorial LLC. All rights reserved."
DISCLOSURE = "The hosts are characters created by Verb Editorial. Their voices are AI-generated. All research, writing and production are done by a human team."
TAPLINK_RE = re.compile(r'<a\b([^>]*?)href="(https://(?:precisionandinstinct\.taplink\.bio|rss\.com/podcasts/precision-instinct/[^"]*))"([^>]*)>')


def footer_lines(prefix, preview):
    """Disclosure, copyright and the privacy link (all pages). The website shows no mailing address."""
    href = (prefix + "privacy.html") if preview else "/privacy/"
    return ('\n      <p class="disclosure">%s</p>'
            '\n      <p class="disclosure copyright">%s &middot; <a href="%s">Privacy</a></p>') % (
        html.escape(DISCLOSURE, quote=False), html.escape(COPYRIGHT, quote=False), href)


def e_ascii(text):
    return html.escape(text, quote=False).encode("ascii", "xmlcharrefreplace").decode()


def load_json(name, default=None):
    path = ROOT / "tools" / name
    if not path.exists():
        if default is not None:
            return default
        die("missing tools/" + name)
    return json.loads(path.read_text(encoding="utf-8"))


def decorate_links(markup, campaign, content):
    """UTM tags on every outbound listening link, plus the Plausible goal name as a class.
    Taplink = "Where to listen"; RSS.com episode links = "Hear the whole debate"."""
    def sub(m):
        pre, url, post = m.groups()
        rss = "rss.com" in url
        q = urlencode({"utm_source": "precisionandinstinct.com", "utm_medium": "website", "utm_campaign": campaign,
                       "utm_content": "player-fallback" if rss else content})
        new = pre + 'href="%s%s%s"' % (url, "&amp;" if "?" in url else "?", q.replace("&", "&amp;")) + post
        goal = "Hear+the+whole+debate" if rss else "Where+to+listen"
        if 'class="' in new:
            new = re.sub(r'class="([^"]*)"', lambda c: 'class="%s plausible-event-name=%s"' % (c.group(1), goal), new, count=1)
        else:
            new += ' class="plausible-event-name=%s"' % goal
        return "<a" + new + ">"
    return TAPLINK_RE.sub(sub, markup)


def signup_html(conf, preview):
    """The Sunday-email signup box. Left out of production builds until signup.live is true (MailerLite ids set).
    The website never shows a mailing address: it belongs only in the email footer (see golive_check.py --send)."""
    su = conf["signup"]
    live = bool(su.get("live"))
    if live:
        if not (su.get("mailerlite_account_id") and su.get("mailerlite_form_id")):
            die("signup.live is true but the MailerLite account id / form id are not set in tools/site-config.json")
    if not live and not preview:
        return ""
    attrs = ' data-ml-account="%s" data-ml-form="%s"' % (su.get("mailerlite_account_id", ""), su.get("mailerlite_form_id", ""))
    if not live:
        attrs += ' data-offline="true"'
    form = ('<section class="signup" aria-labelledby="signup-h">\n'
            '      <div><span class="k">The Sunday email</span><h2 id="signup-h">A new case every Sunday</h2>'
            '<p>One short email when each new case file opens. Unsubscribe any time.</p></div>\n'
            '      <form id="signup-form"%s novalidate>\n'
            '        <label for="signup-email">Email address</label>\n'
            '        <div class="row"><input id="signup-email" name="fields[email]" type="email" autocomplete="email" inputmode="email" required placeholder="you@example.com"><button type="submit">Sign up</button></div>\n'
            '        <p class="msg" role="status" aria-live="polite"></p>\n'
            '%s'
            '      </form>\n'
            '    </section>') % (attrs, '' if live else '        <p class="offline-note">PREVIEW ONLY: this form is not connected yet. It stays out of the live site until MailerLite is set up.</p>\n')
    return form


def head_common(conf, prefix, preview):
    """Favicons, fonts, stylesheet, analytics."""
    out = ('<link rel="icon" href="%sfavicon.ico" sizes="any">\n'
           '<link rel="icon" type="image/png" sizes="32x32" href="%sassets/icon-32.png">\n'
           '<link rel="apple-touch-icon" href="%sapple-touch-icon.png">\n'
           '<link rel="stylesheet" href="%svendor/fonts.css">\n'
           '<link rel="stylesheet" href="%sassets/site.css">\n') % ((prefix,) * 5)
    pl = conf["plausible"]
    if pl.get("enabled") and not preview:
        out += ('<script defer data-domain="%s" src="%s"></script>\n'
                '<script>window.plausible=window.plausible||function(){(window.plausible.q=window.plausible.q||[]).push(arguments)}</script>\n'
                % (pl["domain"], pl["script_src"]))
    return out


def coming_block():
    """The "Coming Sunday" teaser: number, title, date, hook and the episode's small icon. Nothing else."""
    path = ROOT / "tools" / "coming.json"
    if not path.exists():
        return ""
    d = json.loads(path.read_text(encoding="utf-8"))
    if not d:
        return ""
    for k in ("number", "title", "date", "hook"):
        if not str(d.get(k, "")).strip():
            die("tools/coming.json is missing %r" % k)
    extra = set(d) - {"number", "title", "date", "hook"}
    if extra:
        die("tools/coming.json may only hold number, title, date and hook (found %s)" % ", ".join(sorted(extra)))
    num = d["number"]
    when = datetime.date.fromisoformat(d["date"])
    if when <= datetime.date.today():
        die("coming.json date %s is not in the future. After release day, point coming.json at the next episode (or empty it to {})." % d["date"])
    if when.weekday() != 6:
        print("warning: coming.json date %s is a %s, not a Sunday" % (d["date"], when.strftime("%A")))
    icon = ROOT / "img" / "icons" / ("ep%s.png" % num)
    if not icon.exists():
        die("missing the episode icon img/icons/ep%s.png (the only image allowed before release)" % num)
    from PIL import Image
    w, h = Image.open(icon).size
    day = "%s %d" % (when.strftime("%B"), when.day)
    return ('<section class="coming" aria-labelledby="coming-h">\n'
            '      <div class="coming-icon"><img src="img/icons/ep%s.png" alt="" width="%d" height="%d"></div>\n'
            '      <div class="coming-body">\n'
            '        <span class="coming-k">Coming Sunday &middot; <time datetime="%s">%s</time></span>\n'
            '        <h2 id="coming-h"><span class="coming-n">Episode %s</span>%s</h2>\n'
            '        <p>%s</p>\n'
            '      </div>\n'
            '    </section>') % (num, w, h, d["date"], day, num, e_ascii(d["title"]), e_ascii(d["hook"]))


def featured_block(released_with_pages, eps, cfg, case_href):
    n = released_with_pages[-1]
    f = cfg[n].get("feature")
    if not f:
        die("episode %s is the newest, so it needs a \"feature\" block (img, alt, place, blurb) in tools/cases.json for the Latest case file box" % n)
    ep = eps[int(n) - 1]
    return ('<section aria-labelledby="latest">\n'
            '      <div class="section-head"><h2 id="latest">Latest case file</h2><span class="count">Episode %s &middot; Updated each Sunday</span></div>\n'
            '      <a class="featured" href="%s">\n'
            '        <div class="print"><img loading="lazy" decoding="async" src="%s" alt="%s" width="2048" height="1152"></div>\n'
            '        <div class="body">\n'
            '          <div style="display:flex;gap:8px;flex-wrap:wrap"><span class="tag tag-outline">%s</span><span class="tag tag-recon">%s</span></div>\n'
            '          <h3>%s</h3>\n'
            '          <p>%s</p>\n'
            '          <span class="btn">Open the case file &rarr;</span>\n'
            '        </div>\n'
            '      </a>\n'
            '    </section>') % (n, case_href(n), f["img"], html.escape(f["alt"]), e_ascii(ep["status"]), e_ascii(f["place"]),
                               e_ascii(ep["title"]), e_ascii(f["blurb"]))


def grid_html(released, eps, case_href):
    cards = []
    for n in released:
        ep = eps[int(n) - 1]
        cards.append('<a class="case-card is-open" href="%s"><div class="thumb"><img src="img/art/ep%s.jpg" alt="" loading="lazy" width="800" height="800"></div>'
                     '<div class="meta"><span class="ep-badge">EP %s</span><span class="t">%s</span><span class="facts">Case %s &middot; %s &middot; %s</span>'
                     '<span class="s">Open the case file &rarr;</span></div></a>'
                     % (case_href(n), n, n, e_ascii(ep["title"]), n, e_ascii(ep["years"]), e_ascii(ep["status"])))
    return '<div class="case-grid" id="case-grid">\n      ' + "\n      ".join(cards) + "\n    </div>"


def build_home(src, eps, hashes, cfg, released, conf, preview):
    prefix = "" if preview else "/"
    home_block = between(src, '<div id="view-home">', "<!-- ======================= CASE")
    home_block = home_block.rstrip()
    case_href = (lambda n: "cases/%s.html" % cfg[n]["slug"]) if preview else (lambda n: "/cases/%s/" % cfg[n]["slug"])
    # latest case file (newest released episode), driven by data, not hard-coded
    home_block, k = re.subn(r'<section aria-labelledby="latest">.*?</section>', lambda m: featured_block(released, eps, cfg, case_href), home_block, count=1, flags=re.S)
    if k != 1:
        die("home: Latest case file section not found in site-source.html")
    teaser = coming_block()
    home_block, k = re.subn(r"<!--COMING-->.*?<!--/COMING-->", lambda m: teaser, home_block, count=1, flags=re.S)
    if k != 1:
        die("home: <!--COMING--> markers not found in site-source.html")
    home_block = home_block.replace('<section aria-labelledby="all">', '<section id="cases" aria-labelledby="all">', 1)
    home_block = re.sub(r'<span class="count">[^<]*case files open</span>', '<span class="count">%d episodes &middot; %d case files open</span>' % (len(released), len(released)), home_block, count=1)
    home_block, k = re.subn(r'<div class="case-grid" id="case-grid"></div>', lambda m: grid_html(released, eps, case_href), home_block, count=1)
    if k != 1:
        die("home: empty case grid not found in site-source.html")
    form = signup_html(conf, preview)
    footer_extra = footer_lines(prefix, preview)
    # signup sits just above the footer; disclosure, copyright and the privacy link go inside it
    foot = re.search(r"<footer>\s*(<p class=\"show-line\">.*?</p>)", home_block, re.S)
    if not foot:
        die("home: footer not found in site-source.html")
    home_block = home_block.replace("<footer>", (form + "\n\n    " if form else "") + "<footer>", 1)
    home_block = home_block.replace(foot.group(1), foot.group(1) + footer_extra, 1)
    home_block = decorate_links(home_block, "home", "page")
    # a sticky nav link to the grid
    url = SITE + "/"
    desc = "A scroll-through case file for every Precision & Instinct episode: the evidence, the timeline and clips from the two-host debate on unsolved cases."
    title = "Precision & Instinct Case Files"
    ogimg = SITE + "/img/landing/cover-hosts-v2-3000.jpg"
    if preview:
        seo = '<meta name="robots" content="noindex, nofollow">'
    else:
        seo = f"""<link rel="canonical" href="{url}">
<meta name="robots" content="index, follow">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Precision &amp; Instinct">
<meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(desc)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{ogimg}">
<meta name="twitter:card" content="summary_large_image">"""
    # old "#case-slug" links: forward to the new per-case page before the home page paints
    mapping = {hashes[n]: (case_href(n) if not preview else case_href(n)) for n in released if n in hashes}
    redirect = "<script>(function(){var m=%s,u=m[location.hash];if(u)location.replace(u);})();</script>" % json.dumps(mapping, separators=(",", ":"))
    nav = decorate_links(NAV_HOME % {"p": prefix, "home": "index.html" if preview else "/"}, "home", "nav")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
{seo}
{redirect}
{head_common(conf, prefix, preview)}</head>
<body>

{nav}
<!-- ======================= HOME ======================= -->
{home_block}

<div class="sound" id="sound">
  <button class="sound-btn" id="sound-btn" type="button" aria-pressed="false"><span class="bars" aria-hidden="true"><i></i><i></i><i></i><i></i></span><span class="lbl">Sound off</span></button>
</div>

<script>window.PI_BASE = "{prefix}";</script>
<script src="{prefix}vendor/gsap.min.js"></script>
<script src="{prefix}vendor/ScrollTrigger.min.js"></script>
<script src="{prefix}assets/home.js"></script>
{'<script src="%sassets/signup.js"></script>' % prefix if form else ''}
</body>
</html>
"""


NAV_HOME = """<nav class="nav">
  <a class="nav-brand" href="%(home)s">PRECISION <span class="amp">&amp;</span> INSTINCT</a>
  <a href="%(p)s#cases">Case files</a>
  <a href="https://notes.precisionandinstinct.com/episodes/">Sources</a>
  <a class="btn-primary" href="https://precisionandinstinct.taplink.bio">Where to listen &rarr;</a>
</nav>
"""

SIGNUP_JS = r"""/* Sunday-email signup (MailerLite). The form posts the address to MailerLite's own form endpoint. */
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
"""

TRACK_JS = r"""/* The RSS.com player is an iframe, so its clicks cannot be tagged. Count the click as a "Hear the whole debate" goal. */
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
"""


PRIVACY_CSS = """
  /* privacy page (written by tools/build_site.py) */
  .legal { max-width: 720px; margin: 0 auto; padding: 48px 16px 8px; }
  .legal-foot { max-width: 720px; }
  .legal .kicker { color: var(--accent); }
  .legal h1 { margin: 8px 0 12px; font-weight: 900; font-size: clamp(34px, 6vw, 56px); line-height: 1.04; letter-spacing: -0.02em; }
  .legal .lede { font-size: 17px; color: var(--muted-78); margin: 0 0 8px; max-width: 58ch; }
  .legal .updated { font-size: 13px; color: var(--muted-55); margin: 0 0 8px; }
  .legal h2 { margin: 36px 0 8px; padding-top: 20px; border-top: 2px solid var(--divider); font-weight: 800; font-size: 21px; }
  .legal p, .legal li { color: var(--muted-78); max-width: 62ch; }
  .legal p { margin: 0 0 12px; }
  .legal ul { margin: 0 0 12px; padding-left: 20px; }
  .legal li { margin-bottom: 6px; }
  .legal a { color: var(--accent); text-decoration: underline; text-underline-offset: 3px; }
  .legal a:hover { color: var(--accent-hi); }
  footer .disclosure a { text-decoration: underline; text-underline-offset: 2px; }
  footer .disclosure a:hover { color: var(--accent-hi); }
"""

PRIVACY_BODY = """<main class="legal" id="main">
  <span class="kicker">Privacy</span>
  <h1>What we collect, and why</h1>
  <p class="lede">Short version: we keep very little. Your email address if you join the Sunday email, and anonymous visit counts. Nothing else.</p>
  <p class="updated">Last updated October 2026</p>

  <h2>Your email address</h2>
  <p>If you sign up for the Sunday email, we collect the email address you type in. That is the only personal information this site asks for. The signup is run through MailerLite, our email service, which stores the list and sends the emails for us.</p>
  <p>We use your address to send you the Sunday email about each new case file, and for nothing else. We do not sell it.</p>

  <h2>Anonymous visit counts</h2>
  <p>We count visits with Plausible Analytics, a privacy-focused service. It does not use cookies and does not collect personal data about visitors. We see things like which pages are read, which country visits come from, and which site sent a visitor.</p>
  <p>We also count clicks on the "Where to listen" and "Hear the whole debate" links, so we know whether the site is sending people to the episodes. These are counts, not records of who clicked.</p>

  <h2>Unsubscribing</h2>
  <p>Every email we send has an unsubscribe link at the bottom. Click it and you are off the list. If you would rather have your address deleted, write to us at the address below and we will remove it.</p>

  <h2>Other services you may meet</h2>
  <ul>
    <li>The site is hosted on GitHub Pages. Like any web host, it receives your IP address when your browser loads a page.</li>
    <li>The episode player on each case page comes from RSS.com, and the "Where to listen" page is on Taplink. When you use them you are on their sites, under their own privacy policies.</li>
  </ul>

  <h2>Contact</h2>
  <p>Questions about this page, or want your address removed? Write to <a href="mailto:evidence@precisionandinstinct.com">evidence@precisionandinstinct.com</a>.</p>
</main>
"""


def build_privacy(conf, preview):
    prefix = "" if preview else "/"
    home = "index.html" if preview else "/"
    cases = "index.html#cases" if preview else "/#cases"
    t, d = "Privacy | Precision & Instinct", "What the Precision & Instinct site collects: email addresses for the Sunday email, and anonymous visit counts. Plain language."
    if preview:
        seo = '<meta name="robots" content="noindex, nofollow">'
    else:
        seo = f"""<link rel="canonical" href="{SITE}/privacy/">
<meta name="robots" content="index, follow">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Precision &amp; Instinct">
<meta property="og:title" content="{html.escape(t)}">
<meta property="og:description" content="{html.escape(d)}">
<meta property="og:url" content="{SITE}/privacy/">
<meta property="og:image" content="{SITE}/img/landing/cover-hosts-v2-3000.jpg">
<meta name="twitter:card" content="summary_large_image">"""
    nav = decorate_links(f"""<nav class="nav">
  <a class="nav-brand" href="{home}">PRECISION <span class="amp">&amp;</span> INSTINCT</a>
  <a href="{cases}">Case files</a>
  <a href="https://notes.precisionandinstinct.com/episodes/">Sources</a>
  <a class="btn-primary" href="https://precisionandinstinct.taplink.bio">Where to listen &rarr;</a>
</nav>
""", "privacy", "nav")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(t)}</title>
<meta name="description" content="{html.escape(d)}">
{seo}
{head_common(conf, prefix, preview)}</head>
<body>

{nav}
{PRIVACY_BODY}
<div class="wrap legal-foot">
  <footer>
    <p class="show-line">Precision &amp; Instinct with Simone Valdez and Eli Marchetti</p>{footer_lines(prefix, preview)}
  </footer>
</div>
</body>
</html>
"""


def email_sample(cfg, eps, released):
    """A filled-in copy of the Sunday email template (newest released case), for review only."""
    n = released[-1]
    f = cfg[n].get("feature", {})
    t = (ROOT / "tools" / "email" / "sunday-email.html").read_text(encoding="utf-8")
    rep = {"{{EP}}": n, "{{TITLE}}": e_ascii(eps[int(n) - 1]["title"]), "{{HOOK}}": e_ascii(f.get("blurb", "")),
           "{{CASE_URL}}": "cases/%s.html" % cfg[n]["slug"], "{{ICON_URL}}": "img/icons/ep%s.png" % n, "{{LISTEN_URL}}": "https://precisionandinstinct.taplink.bio",
           "https://precisionandinstinct.com/img/": "img/", "{$unsubscribe}": "#", "{$url}": "#"}
    for k, v in rep.items():
        t = t.replace(k, v)
    return t


def sitemap_xml(urls):
    rows = "".join("  <url><loc>%s</loc></url>\n" % u for u in urls)
    return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + rows + "</urlset>\n"


ROBOTS = "User-agent: *\nAllow: /\nDisallow: /tools/\n\nSitemap: " + SITE + "/sitemap.xml\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="+", help="episode numbers to build, e.g. 01 02")
    ap.add_argument("--all-released", action="store_true")
    ap.add_argument("--preview-dir", help="write a private preview copy here instead of into the repo")
    a = ap.parse_args()
    src, eps, hashes = load()
    cfg = json.loads((ROOT / "tools" / "cases.json").read_text(encoding="utf-8"))
    today = datetime.date.today().isoformat()
    released = [n for n in sorted(hashes) if not eps[int(n) - 1]["release"] or eps[int(n) - 1]["release"] <= today]
    for n in cfg:
        if n not in released:
            die("tools/cases.json has an entry for episode %s, which is not released yet. Add it on its release day." % n)
        for k in REQUIRED:
            if not cfg[n].get(k):
                die("tools/cases.json episode %s is missing %r" % (n, k))
        if len(cfg[n]["description"]) > 165:
            print("warning: episode %s description is %d characters (search results cut around 155-160)" % (n, len(cfg[n]["description"])))
    slugs = [cfg[n]["slug"] for n in cfg]
    if len(set(slugs)) != len(slugs):
        die("duplicate slug in tools/cases.json")
    if a.all_released:
        todo = [n for n in released if n in cfg]
    elif a.only:
        todo = a.only
    else:
        die("give --only NN [NN ...] or --all-released")
    for n in todo:
        if n not in released:
            die("episode %s is not released yet (%s); no public page for it" % (n, eps[int(n) - 1]["release"]))
        if n not in cfg:
            die("episode %s has no entry in tools/cases.json" % n)
    preview = bool(a.preview_dir)
    missing = [n for n in released if n not in cfg]
    if missing:
        die("released episode(s) %s have no entry in tools/cases.json (the home page links to every released case)" % ", ".join(missing))
    conf = load_json("site-config.json")
    # "next case file" links point at pages that exist
    urls = {n: "/cases/%s/" % cfg[n]["slug"] for n in released}
    blocks = case_blocks(src, hashes)
    nav_order = list(released)
    css, case_js, home_js = extract_css(src), extract_js(src), extract_home_js(src)
    if preview:
        out = pathlib.Path(a.preview_dir)
        (out / "cases").mkdir(parents=True, exist_ok=True)
        (out / "assets").mkdir(parents=True, exist_ok=True)
        (out / "assets" / "site.css").write_text((css + PRIVACY_CSS).replace('url("/img/', 'url("../img/'), encoding="utf-8")
        (out / "assets" / "case.js").write_text(case_js, encoding="utf-8")
        (out / "assets" / "home.js").write_text(home_js, encoding="utf-8")
        (out / "assets" / "signup.js").write_text(SIGNUP_JS, encoding="utf-8")
        for n in todo:
            (out / "cases" / (cfg[n]["slug"] + ".html")).write_text(build_page(n, eps, hashes, blocks, cfg, urls, nav_order, True, conf), encoding="utf-8")
            print("preview /cases/%s.html  (episode %s)" % (cfg[n]["slug"], n))
        (out / "index.html").write_text(build_home(src, eps, hashes, cfg, released, conf, True), encoding="utf-8")
        print("preview index.html")
        (out / "privacy.html").write_text(build_privacy(conf, True), encoding="utf-8")
        print("preview privacy.html")
        (out / "email-sample.html").write_text(email_sample(cfg, eps, released), encoding="utf-8")
        return
    (ROOT / "assets").mkdir(exist_ok=True)
    (ROOT / "assets" / "site.css").write_text(css + PRIVACY_CSS, encoding="utf-8")
    (ROOT / "assets" / "case.js").write_text(case_js, encoding="utf-8")
    (ROOT / "assets" / "home.js").write_text(home_js, encoding="utf-8")
    (ROOT / "assets" / "signup.js").write_text(SIGNUP_JS, encoding="utf-8")
    (ROOT / "assets" / "track.js").write_text(TRACK_JS, encoding="utf-8")
    for n in todo:
        out = ROOT / "cases" / cfg[n]["slug"]
        out.mkdir(parents=True, exist_ok=True)
        (out / "index.html").write_text(build_page(n, eps, hashes, blocks, cfg, urls, nav_order, False, conf), encoding="utf-8")
        print("built /cases/%s/  (episode %s)" % (cfg[n]["slug"], n))
    (ROOT / "index.html").write_text(build_home(src, eps, hashes, cfg, released, conf, False), encoding="utf-8")
    print("built / (home)")
    (ROOT / "privacy").mkdir(exist_ok=True)
    (ROOT / "privacy" / "index.html").write_text(build_privacy(conf, False), encoding="utf-8")
    print("built /privacy/")
    (ROOT / "sitemap.xml").write_text(sitemap_xml([SITE + "/"] + [SITE + urls[n] for n in released] + [SITE + "/privacy/"]), encoding="utf-8")
    (ROOT / "robots.txt").write_text(ROBOTS, encoding="utf-8")
    print("wrote sitemap.xml (%d URLs) and robots.txt" % (len(released) + 2))

if __name__ == "__main__":
    main()
