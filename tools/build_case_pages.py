#!/usr/bin/env python3
"""Build one standalone page per case file from index.html.

index.html stays the source of truth (render.py keeps splicing case markup into it).
This script reads it and writes:
  assets/site.css            shared stylesheet (cut from index.html)
  assets/case.js             shared case-page script (cut from index.html, home/router code removed)
  cases/<slug>/index.html    one page per case

Settings per episode live in tools/cases.json: slug, h1, seo_title, description, og_image.
Only RELEASED episodes get a page. An unreleased episode is refused, and must not be in tools/cases.json
(or anywhere else in the public repo) until its release day.

Usage:
  python3 tools/build_case_pages.py --all-released            # every released episode that has a cases.json entry
  python3 tools/build_case_pages.py --only 01 02              # just these
  python3 tools/build_case_pages.py --all-released --preview-dir DIR
        # private preview copy: relative links, noindex, no canonical/share tags. Not for the live site.
"""
import argparse, datetime, html, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = "https://precisionandinstinct.com"
REQUIRED = ("slug", "h1", "seo_title", "description", "og_image")


def die(msg):
    sys.exit("build_case_pages: " + msg)


def between(text, start, end, include_start=True):
    i = text.find(start)
    if i < 0:
        die("anchor not found: %r" % start[:60])
    j = text.find(end, i + len(start))
    if j < 0:
        die("anchor not found: %r" % end[:60])
    return text[i if include_start else i + len(start):j]


def load():
    src = (ROOT / "index.html").read_text(encoding="utf-8")
    # episodes array and case-file map, parsed so index.html stays the single source of truth
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
    # music files are relative in index.html; on /cases/<slug>/ pages they must resolve from the site root
    # (the page sets window.PI_BASE: "/" on the live site, "../" in a private preview)
    js, n = re.subn(r"'(audio/beds/[^']+)'", r"PI_BASE + '\1'", js)
    if n < 1 or re.search(r"(?<!PI_BASE \+ )'audio/", js):
        die("music paths in case.js were not all rewritten (found %d)" % n)
    js = "var PI_BASE = window.PI_BASE || '/';\n" + js
    return js


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


def build_page(num, eps, hashes, blocks, cfg, urls, released_nums, preview):
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
    block = block[:i] + "".join(nav) + "\n    " + block[i:]
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
    head = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t}</title>
<meta name="description" content="{d}">
{seo}
<link rel="icon" href="{prefix}favicon.ico" sizes="any">
<link rel="icon" type="image/png" sizes="32x32" href="{prefix}assets/icon-32.png">
<link rel="apple-touch-icon" href="{prefix}apple-touch-icon.png">
<link rel="stylesheet" href="{prefix}vendor/fonts.css">
<link rel="stylesheet" href="{prefix}assets/site.css">
{fit}</head>
<body>

<nav class="nav">
  <a class="nav-brand" href="{home_href}">PRECISION <span class="amp">&amp;</span> INSTINCT</a>
  <a href="{cases_href}">Case files</a>
  <a href="https://notes.precisionandinstinct.com/episodes/">Sources</a>
  <a class="btn-primary" href="https://precisionandinstinct.taplink.bio">Where to listen &rarr;</a>
</nav>

"""
    tail = f"""

<div class="sound" id="sound">
  <button class="sound-btn" id="sound-btn" type="button" aria-pressed="false"><span class="bars" aria-hidden="true"><i></i><i></i><i></i><i></i></span><span class="lbl">Sound off</span></button>
</div>

<script>window.PI_BASE = "{prefix}";</script>
<script src="{prefix}vendor/gsap.min.js"></script>
<script src="{prefix}vendor/ScrollTrigger.min.js"></script>
<script src="{prefix}assets/case.js"></script>
</body>
</html>
"""
    return head + block + tail


def preview_index(todo, eps, cfg):
    rows = "".join('<li><a href="cases/%s.html"><b>%s</b> &middot; %s</a></li>' % (cfg[n]["slug"], n, html.escape(cfg[n]["h1"], quote=False)) for n in todo)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow"><title>P&amp;I case pages preview</title>
<link rel="icon" href="favicon.ico" sizes="any"><link rel="stylesheet" href="vendor/fonts.css">
<style>body{{margin:0;background:#0E0E10;color:#f2efe9;font-family:Archivo,system-ui,sans-serif;padding:32px 20px;max-width:640px;margin-inline:auto}}
h1{{font-weight:900;letter-spacing:-.02em;margin:0 0 6px}}p{{color:#b9b4aa;line-height:1.5}}ul{{list-style:none;padding:0;margin:24px 0}}
li{{border-top:1px solid rgba(242,239,233,.2)}}li a{{display:block;padding:14px 2px;color:#f2efe9;text-decoration:none}}li a:hover{{color:#c9622f}}
b{{display:inline-block;min-width:28px;color:#B8522C}}</style></head>
<body><h1>Case pages preview</h1>
<p>Private working copy of the one-page-per-case rebuild. Not the live site, not indexed. Each page below is a separate case page.</p>
<ul>{rows}</ul></body></html>
"""


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
    # pages that exist (or are being built now): "next" links point at real pages, anything else falls back to the home page
    urls = {n: "/cases/%s/" % cfg[n]["slug"] for n in cfg if n in todo or (preview or (ROOT / "cases" / cfg[n]["slug"] / "index.html").exists())}
    if preview:
        urls = {n: u for n, u in urls.items() if n in todo}
    blocks = case_blocks(src, hashes)
    nav_order = [n for n in released if n in urls]
    if preview:
        out = pathlib.Path(a.preview_dir)
        (out / "cases").mkdir(parents=True, exist_ok=True)
        for n in todo:
            (out / "cases" / (cfg[n]["slug"] + ".html")).write_text(build_page(n, eps, hashes, blocks, cfg, urls, nav_order, True), encoding="utf-8")
            print("preview /cases/%s.html  (episode %s)" % (cfg[n]["slug"], n))
        (out / "index.html").write_text(preview_index(todo, eps, cfg), encoding="utf-8")
        return
    (ROOT / "assets").mkdir(exist_ok=True)
    (ROOT / "assets" / "site.css").write_text(extract_css(src), encoding="utf-8")
    (ROOT / "assets" / "case.js").write_text(extract_js(src), encoding="utf-8")
    for n in todo:
        out = ROOT / "cases" / cfg[n]["slug"]
        out.mkdir(parents=True, exist_ok=True)
        (out / "index.html").write_text(build_page(n, eps, hashes, blocks, cfg, urls, nav_order, False), encoding="utf-8")
        print("built /cases/%s/  (episode %s)" % (cfg[n]["slug"], n))


if __name__ == "__main__":
    main()
