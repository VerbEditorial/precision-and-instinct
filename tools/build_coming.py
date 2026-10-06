#!/usr/bin/env python3
"""Write the "Coming Sunday" teaser block on the home page from tools/coming.json.

coming.json holds the NEXT unreleased episode and nothing else: number, title, date, hook.
No case text, clips, audio paths or case links. The only image is the episode's small icon
(img/icons/epNN.png), which is the one image that may be public before release.

Run from the repo root:  python3 tools/build_coming.py
It rewrites the block between <!--COMING--> and <!--/COMING--> in index.html.
"""
import datetime, html, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

def die(msg):
    sys.exit("build_coming: " + msg)

d = json.loads((ROOT / "tools" / "coming.json").read_text(encoding="utf-8"))
for k in ("number", "title", "date", "hook"):
    if not str(d.get(k, "")).strip():
        die("coming.json is missing %r" % k)
extra = set(d) - {"number", "title", "date", "hook"}
if extra:
    die("coming.json may only hold number, title, date and hook (found %s)" % ", ".join(sorted(extra)))
num = d["number"]
if not re.fullmatch(r"\d\d", num):
    die("number must be two digits, like 14")
when = datetime.date.fromisoformat(d["date"])
if when <= datetime.date.today():
    die("the date %s is not in the future. After release day, point coming.json at the next episode." % d["date"])
if when.weekday() != 6:
    print("warning: %s is a %s, not a Sunday" % (d["date"], when.strftime("%A")))
index = (ROOT / "index.html").read_text(encoding="utf-8")
if re.search(r"'%s': '#" % num, index):
    die("episode %s already has a case file on the site. coming.json should hold the next unreleased episode." % num)
icon = ROOT / "img" / "icons" / ("ep%s.png" % num)
if not icon.exists():
    die("missing the episode icon %s" % icon.relative_to(ROOT))
from PIL import Image
w, h = Image.open(icon).size

e = lambda s: html.escape(s, quote=False).encode("ascii", "xmlcharrefreplace").decode()
day = "%s %d" % (when.strftime("%B"), when.day)
block = ('<!--COMING-->\n'
         '    <section class="coming" aria-labelledby="coming-h">\n'
         '      <div class="coming-icon"><img src="img/icons/ep%s.png" alt="" width="%d" height="%d"></div>\n'
         '      <div class="coming-body">\n'
         '        <span class="coming-k">Coming Sunday &middot; <time datetime="%s">%s</time></span>\n'
         '        <h2 id="coming-h"><span class="coming-n">Episode %s</span>%s</h2>\n'
         '        <p>%s</p>\n'
         '      </div>\n'
         '    </section>\n'
         '    <!--/COMING-->') % (num, w, h, d["date"], day, num, e(d["title"]), e(d["hook"]))
pat = re.compile(r"<!--COMING-->.*?<!--/COMING-->", re.S)
if not pat.search(index):
    die("index.html has no <!--COMING--> ... <!--/COMING--> markers")
(ROOT / "index.html").write_text(pat.sub(lambda m: block, index), encoding="utf-8")
print("teaser: Episode %s, %s, %s" % (num, d["title"], day))
