#!/usr/bin/env python3
"""Build one standalone page per case file from index.html.

index.html stays the source of truth (render.py keeps splicing case markup into it).
This script reads it and writes:
  assets/site.css            shared stylesheet (cut from index.html)
  assets/case.js             shared case-page script (cut from index.html, home/router code removed)
  cases/<slug>/index.html    one page per case

Usage:  python3 tools/build_case_pages.py --only 01 [02 03 ...]
        python3 tools/build_case_pages.py --all-released

Page text is the existing case markup, unchanged except: asset paths made root-relative,
the preview-only player note reworded, and the end-of-case navigation written into the HTML.
"""
import argparse, datetime, html, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE = "https://precisionandinstinct.com"
NOTES = "https://notes.precisionandinstinct.com/episodes/"


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
    return js


def case_blocks(src, hashes):
    """Return {num: inner html of that case's <div class="case-view"> ... </div>}."""
    out = {}
    for num, h in hashes.items():
        m = re.search(r'<div id="view-case[^"]*" class="case-view" data-hash="%s" hidden>' % re.escape(h), src)
        if not m:
            die("case view not found for %s %s" % (num, h))
        start = m.start()
        # the case view ends at the first line that is exactly "</div>" after its closing </section>
        end = src.index("\n</div>\n", start) + len("\n</div>")
        out[num] = src[start:end]
    return out


def rootify(markup):
    markup = re.sub(r'(src|poster|href)="(img|audio|vendor)/', r'\1="/\2/', markup)
    markup = re.sub(r"url\('(img|audio)/", r"url('/\1/", markup)
    markup = re.sub(r'url\("(img|audio)/', r'url("/\1/', markup)
    return markup


def build_page(num, eps, hashes, blocks, cfg, urls, released_nums):
    ep = eps[int(num) - 1]
    c = cfg[num]
    slug = c["slug"]
    url = "%s/cases/%s/" % (SITE, slug)
    block = blocks[num]
    # unwrap the view div into <main>, visible
    block = re.sub(r'^<div id="view-case[^"]*" class="case-view" data-hash="[^"]*" hidden>', '<main id="case" class="case-view">', block, count=1)
    block = re.sub(r"</div>$", "</main>", block)
    block = rootify(block)
    block = block.replace('href="#cases"', 'href="/#cases"')
    # preview-only wording becomes plain wording (this note is what visitors see if the embed does not load)
    block = re.sub(r"Plays here on the live site\. In this preview it opens on RSS\.com\.", "Opens the full episode on RSS.com.", block)
    # end-of-case navigation, written into the HTML (the home page builds the same thing in script)
    idx = released_nums.index(num)
    nxt = released_nums[(idx + 1) % len(released_nums)]
    nav = ['<nav class="case-end" aria-label="Keep going">',
           '<a class="home-btn" href="/#cases"><span class="k">Back to the archive</span><span class="t">&larr; All case files</span></a>']
    if nxt != num:
        nxt_href = urls.get(nxt) or "/" + hashes[nxt]
        nav.append('<a class="next-file" href="%s"><span class="k">Next case file &middot; Episode %s</span><span class="t">%s <span style="color:var(--accent)">&rarr;</span></span></a>'
                   % (nxt_href, nxt, html.escape(eps[int(nxt) - 1]["title"], quote=False)))
    nav.append("</nav>")
    marker = '<footer style="text-align:left">'
    i = block.rfind(marker)
    if i < 0:
        die("end footer not found in case %s" % num)
    block = block[:i] + "".join(nav) + "\n    " + block[i:]
    img = c["og_image"]
    head = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(c["seo_title"])}</title>
<meta name="description" content="{html.escape(c["description"])}">
<link rel="canonical" href="{url}">
<meta name="robots" content="index, follow">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Precision &amp; Instinct">
<meta property="og:title" content="{html.escape(c["seo_title"])}">
<meta property="og:description" content="{html.escape(c["description"])}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{SITE}{img}">
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="/vendor/fonts.css">
<link rel="stylesheet" href="/assets/site.css">
</head>
<body>

<nav class="nav">
  <a class="nav-brand" href="/">PRECISION <span class="amp">&amp;</span> INSTINCT</a>
  <a href="/#cases">Case files</a>
  <a href="https://notes.precisionandinstinct.com/episodes/">Sources</a>
  <a class="btn-primary" href="https://precisionandinstinct.taplink.bio">Where to listen &rarr;</a>
</nav>

"""
    tail = """

<div class="sound" id="sound">
  <button class="sound-btn" id="sound-btn" type="button" aria-pressed="false"><span class="bars" aria-hidden="true"><i></i><i></i><i></i><i></i></span><span class="lbl">Sound off</span></button>
</div>

<script src="/vendor/gsap.min.js"></script>
<script src="/vendor/ScrollTrigger.min.js"></script>
<script src="/assets/case.js"></script>
</body>
</html>
"""
    return head + block + tail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="+", help="episode numbers to build, e.g. 01 02")
    ap.add_argument("--all-released", action="store_true")
    a = ap.parse_args()
    src, eps, hashes = load()
    cfg = json.loads((ROOT / "tools" / "cases.json").read_text(encoding="utf-8"))
    today = datetime.date.today().isoformat()
    released = [n for n in sorted(hashes) if not eps[int(n) - 1]["release"] or eps[int(n) - 1]["release"] <= today]
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
    # urls of pages that exist (or are being built now) so "next" links point at real pages
    urls = {n: "/cases/%s/" % cfg[n]["slug"] for n in cfg if n in todo or (ROOT / "cases" / cfg[n]["slug"] / "index.html").exists()}
    (ROOT / "assets").mkdir(exist_ok=True)
    (ROOT / "assets" / "site.css").write_text(extract_css(src), encoding="utf-8")
    (ROOT / "assets" / "case.js").write_text(extract_js(src), encoding="utf-8")
    blocks = case_blocks(src, hashes)
    for n in todo:
        out = ROOT / "cases" / cfg[n]["slug"]
        out.mkdir(parents=True, exist_ok=True)
        (out / "index.html").write_text(build_page(n, eps, hashes, blocks, cfg, urls, released), encoding="utf-8")
        print("built /cases/%s/  (episode %s)" % (cfg[n]["slug"], n))


if __name__ == "__main__":
    main()
