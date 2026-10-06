#!/usr/bin/env python3
"""Checks to run before merging to main. Prints what is wrong; exit code 1 if anything is.

  python3 tools/golive_check.py          # before merging to main
  python3 tools/golive_check.py --send   # before the FIRST Sunday email: also needs a real mailing address
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
problems, notes = [], []

def read(p):
    return (ROOT / p).read_text(encoding="utf-8")

# 1. nothing unreleased in the public repo
src = read("tools/site-source.html")
nums = sorted(re.findall(r"'(\d\d)': '#", src))
last = int(nums[-1])
for d in ("audio", "img"):
    for f in (ROOT / d).iterdir():
        m = re.match(r"(\d\d)-", f.name)
        if m and int(m.group(1)) > last:
            problems.append("%s/%s belongs to an unreleased episode and must not be in the repo" % (d, f.name))
coming = json.loads(read("tools/coming.json") or "{}") if (ROOT / "tools/coming.json").exists() else {}
for f in (ROOT / "img" / "icons").iterdir():
    m = re.match(r"ep(\d\d)\.png", f.name)
    if m and int(m.group(1)) > last and m.group(1) != coming.get("number"):
        problems.append("img/icons/%s is for an episode that is neither released nor the Coming Sunday teaser" % f.name)
cases = json.loads(read("tools/cases.json"))
for n in cases:
    if int(n) > last:
        problems.append("tools/cases.json has an entry for unreleased episode %s" % n)

# 2. built files carry no preview-only pieces
built = [ROOT / "index.html"] + sorted((ROOT / "cases").glob("*/index.html"))
for f in built:
    t = f.read_text(encoding="utf-8")
    for bad, why in (("MAILING ADDRESS GOES HERE", "placeholder mailing address"), ("PREVIEW ONLY", "preview-only note"),
                     ("noindex", "a noindex tag"), ("review=pi2026", "the old review switch")):
        if bad in t:
            problems.append("%s contains %s" % (f.relative_to(ROOT), why))
    if "data-domain" not in t:
        notes.append("%s has no analytics script (plausible.enabled is false?)" % f.relative_to(ROOT))

# 3. signup and address
conf = json.loads(read("tools/site-config.json"))
su = conf["signup"]
addr = conf.get("mailing_address", "").strip()
if su.get("live"):
    if not (su.get("mailerlite_account_id") and su.get("mailerlite_form_id")):
        problems.append("signup is live but the MailerLite ids are empty")
else:
    notes.append("signup is NOT live (the form is left out of the live site until MailerLite is set up)")

# the mailing address is needed for the email and the footer line, not for the signup form
tmpl = read("tools/email/sunday-email.html")
if "MAILING ADDRESS GOES HERE" in tmpl or not addr:
    msg = "the email template still has the placeholder address and mailing_address is empty: do NOT send an email yet"
    if "--send" in sys.argv:
        problems.append(msg)
    else:
        notes.append(msg + " (the signup form itself does not need it)")
if not addr:
    notes.append("the live footer shows no address line until mailing_address is set")

# 4. sitemap
sm = read("sitemap.xml")
want = len(cases) + 1
if sm.count("<loc>") != want:
    problems.append("sitemap.xml has %d URLs, expected %d (rebuild with tools/build_site.py)" % (sm.count("<loc>"), want))

for n in notes:
    print("note:", n)
for p in problems:
    print("PROBLEM:", p)
print("OK" if not problems else "%d problem(s)" % len(problems))
sys.exit(1 if problems else 0)
