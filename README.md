# Precision & Instinct case files

Public companion site for the Precision & Instinct podcast: one scroll-through "case file" page per episode.
Hosted on GitHub Pages at precisionandinstinct.com (publishes from the `main` branch, repo root).

## What lives where

| Path | What it is |
|---|---|
| `tools/site-source.html` | **The source of truth.** The whole site as one file: styles, home markup, and the full markup of every released case file (spliced in by `render.py` between `<!--CASE:NN-->` markers). Not a public page (noindex, and `robots.txt` blocks `/tools/`). |
| `index.html` | The home page: a light index of cases with real links. **Generated. Do not edit by hand.** |
| `cases/<slug>/index.html` | One page per released case, e.g. `/cases/tamam-shud-somerton-man/`. **Generated.** |
| `assets/site.css`, `home.js`, `case.js`, `signup.js`, `track.js` | Shared style and scripts. **Generated** (`signup.js` and `track.js` are fixed text in the build script). |
| `sitemap.xml`, `robots.txt` | **Generated.** |
| `tools/build_site.py` | The build script. |
| `tools/cases.json` | Per-episode page settings (see below). |
| `tools/coming.json` | The "Coming Sunday" teaser (see below). |
| `tools/site-config.json` | Analytics, signup and mailing-address settings. |
| `tools/email/sunday-email.html` | The branded Sunday email template for MailerLite. |
| `tools/golive_check.py` | Safety checks to run before merging to `main`. |
| `audio/`, `img/` | Clips, music beds and images, one folder per episode (`NN-slug`). |
| `notes/` | Redirect page for the on-air address `precisionandinstinct.com/notes`. |

Edit `tools/site-source.html` (or let `render.py` splice into it), then run the build. Never edit the generated files.

## Rule: unreleased episodes are never in this repo

This repo is public, and GitHub Pages serves every file in it. An episode's text, clips, images, `cases.json` entry
and page are added **on its release day, not before**. Until then the episode lives only in the Dropbox episode folder.
The one exception is the small teaser (number, title, date, hook, and the episode's icon). Hiding something with a date
check in the page is not hiding it: anyone can read the files. The build script refuses to build an unreleased
episode, and `tools/golive_check.py` flags unreleased audio or images.

## Release day: adding a new episode

Do these on the episode's Sunday, after it is live on RSS.com. Work on a branch; merge to `main` when it checks out.

1. **Add the files.** Copy the episode's `audio/NN-slug/` and `img/NN-slug/` folders from the Dropbox pipeline output into the repo. Copy its `img/art/epNN.jpg` and `img/icons/epNN.png`.
2. **Splice the case** into the source: `python3 render.py tools/site-source.html cases/NN-case.json` (from the pipeline folder). This also adds the `CASEFILES` line.
3. **Register it in `tools/site-source.html`:** its row in the `eps` list (title, years, status, notes slug; no date, so it shows at once).
4. **Add its entry to `tools/cases.json`:**
   - `slug`: the URL ending, led by what people search for (e.g. `mad-gasser-of-mattoon`).
   - `h1`: the page headline, also led by the search term (e.g. `Tamám Shud: The Somerton Man`).
   - `seo_title`: `<headline> Case File | Precision & Instinct`.
   - `description`: one or two sentences, about 155 characters, facts only from the episode's source notes.
   - `og_image`: the image shown when the link is shared. Objects, places or documents only for sensitive cases, never a victim.
   - `feature`: `img`, `alt`, `place`, `blurb` for the "Latest case file" box. The newest episode must have one.
   - `h1_word_em` (only if the headline has one very long word, like HAMMARSKJÖLD): the width of the longest word in em units, so it fits on small phones. Ask Claude to measure it.
5. **Swap the teaser.** Edit `tools/coming.json` to the **next** episode (number, title, date, hook) and put that episode's icon in `img/icons/`. After the last episode, replace the file's contents with `{}`.
6. **Build:** `python3 tools/build_site.py --all-released`
   This rewrites the home page, every case page, the sitemap and `robots.txt`, so the "Latest" box, the grid and every "Next case file" link stay correct.
7. **Check, then merge.** `python3 tools/golive_check.py`, open the new page on a phone and a desktop, play a clip, then merge to `main`.
8. Send the Sunday email (MailerLite, from `tools/email/sunday-email.html`).

## "Coming Sunday" teaser

Shows the next unreleased episode and nothing else: episode number, title, release date, a one- or two-sentence hook
that does not reveal the debate or the facts, and the episode's small icon (the only image allowed before release).
No case text, clips, audio paths, case art or links to a case page. Unreleased episodes have **no row** in the `eps` list.
`tools/coming.json` holds `number`, `title`, `date` (a future date) and `hook`; the build refuses anything else.

## Old links, sitemap, robots

- Old `/#case-slug` links forward to the new case page (a small script in the home page head, built from the case map).
- `sitemap.xml` lists the home page and every case page; `robots.txt` points to it and blocks `/tools/`.

## Analytics (Plausible)

The script is added to every page by the build, using `tools/site-config.json` (`plausible`). Goals:

| Goal | How it fires |
|---|---|
| Where to listen | Any link to the Taplink page (tagged with a class by the build) |
| Hear the whole debate | The RSS.com link card, and a click inside the embedded player (`assets/track.js`) |
| Signup | After a successful signup (`assets/signup.js`) |

Every Taplink and RSS.com link carries UTM tags: `utm_source=precisionandinstinct.com`, `utm_medium=website`,
`utm_campaign=<home or the case's slug>`, `utm_content=<nav, page or player-fallback>`.
Create the site in Plausible and add these three custom-event goals by name. Links to the notes site are not tagged (same organisation).

## Signup (MailerLite) and the mailing address

The Sunday-email box is built from `tools/site-config.json`:

- `signup.live` (false until everything below is true), `signup.mailerlite_account_id`, `signup.mailerlite_form_id`, `mailing_address`.
- While `live` is false, the box and the address line are **left out of the live site**. Preview builds show them with a clear "PREVIEW ONLY" note and a placeholder address.
- The build refuses `live: true` without both MailerLite ids and a real address.
- Before going live, add MailerLite's SPF, DKIM and DMARC records in GoDaddy DNS (never change the website records).

## AI-voice disclosure

Every page's footer carries: "The hosts' voices in these episodes are AI-generated. All research, writing, and production are done by a human team." (set in `tools/build_site.py`).

## Building the pages

```
python3 tools/build_site.py --all-released                     # rebuild everything
python3 tools/build_site.py --only 01 02                       # just these case pages (home and sitemap always rebuild)
python3 tools/build_site.py --all-released --preview-dir DIR   # private preview copy (relative links, noindex, no analytics)
python3 tools/golive_check.py                                  # run before merging to main
```

The builder stops with a plain message if a settings entry is missing, a slug repeats, an episode is unreleased,
the teaser is wrong, or any image/audio path would break.
