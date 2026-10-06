# Precision & Instinct case files

Public companion site for the Precision & Instinct podcast: one scroll-through "case file" page per episode.
Hosted on GitHub Pages at precisionandinstinct.com (publishes from the `main` branch, repo root).

## What lives where

| Path | What it is |
|---|---|
| `index.html` | Home page, plus the full markup of every released case file (spliced in by `render.py` between `<!--CASE:NN-->` markers). The single source of truth for case content. |
| `cases/<slug>/index.html` | One standalone page per released case. **Generated. Do not edit by hand.** |
| `assets/site.css`, `assets/case.js` | Shared style and script for the case pages. Generated from `index.html`. |
| `tools/cases.json` | Per-episode page settings (see below). |
| `tools/build_case_pages.py` | The page builder. |
| `audio/`, `img/` | Clips, music beds and images, one folder per episode (`NN-slug`). |
| `favicon.ico`, `apple-touch-icon.png` | Site icon (split navy/rust square with the italic ampersand). |

## Rule: unreleased episodes are never in this repo

This repo is public, and GitHub Pages serves every file in it. An episode's text, clips, images, `cases.json` entry
and page are added **on its release day, not before**. Until then the episode lives only in the Dropbox episode folder.
(Hiding something with a date check in the page is not hiding it: anyone can read the files.)
The page builder refuses to build, or accept a `cases.json` entry for, an episode that is not released.

## Release day: adding a new episode

Do these on the episode's Sunday, after it is live on RSS.com.

1. **Add the files.** Copy the episode's `audio/NN-slug/` and `img/NN-slug/` folders from the Dropbox pipeline output into the repo.
2. **Splice the case into `index.html`** with `render.py`, as for every episode.
3. **Register it in `index.html`:** its row in the `eps` list (title, years, status, notes slug; no date; leave off the date field so it shows at once), its line in `CASEFILES` (`render.py` adds this), and its entry in the "latest case file" list (`FEATURE`).
4. **Add its entry to `tools/cases.json`:**
   - `slug`: the URL ending, led by what people search for (e.g. `mad-gasser-of-mattoon`).
   - `h1`: the page headline, also led by the search term (e.g. `Tamám Shud: The Somerton Man`).
   - `seo_title`: `<headline> Case File | Precision & Instinct`.
   - `description`: one or two sentences, about 150 characters, facts only from the episode's source notes.
   - `og_image`: the image shown when the link is shared. For sensitive cases use an object, place or document, never a victim.
   - `h1_word_em` (only if the headline has one very long word, like HAMMARSKJÖLD): the width of the longest word in em units, so it fits on small phones. Ask Claude to measure it.
5. **Build the pages:** `python3 tools/build_case_pages.py --all-released`
   This rewrites every case page, so all "Next case file" links stay correct.
6. **Swap the teaser** (see below).
7. **Check, then publish.** Open the new page on a phone and a desktop, play a clip, then merge to `main`.

## "Coming Sunday" teaser

The home page shows one small teaser for the next unreleased episode, and nothing else about it:
episode number, title, release date, a one- or two-sentence hook that does not reveal the debate or the facts,
and the episode's small icon (`img/icons/epNN.png`, the only image allowed before release).
No case text, clips, audio paths, case art or links to a case page. Unreleased episodes have **no row** in the `eps` list.

The teaser is a tiny separate file, `tools/coming.json` (number, title, date, hook), kept apart from the case content.
`python3 tools/build_coming.py` writes it into the block between `<!--COMING-->` and `<!--/COMING-->` in `index.html`.
The script refuses a past date, extra fields, or an episode that already has a case file.

On release day the swap is:

1. Add the released episode's full case file (steps 1 to 5 above). Its teaser is replaced by its card in the grid.
2. Edit `tools/coming.json` to the **next** episode: number, title, date, hook. Put that episode's icon in `img/icons/`
   (only the icon; its art and case files stay in Dropbox).
3. Run `python3 tools/build_coming.py`. After the last episode, empty the block by hand.

## Building the pages

```
python3 tools/build_case_pages.py --all-released                # every released episode in cases.json
python3 tools/build_case_pages.py --only 01 02                  # just these
python3 tools/build_case_pages.py --all-released --preview-dir DIR   # private preview copy (relative links, noindex)
```

The builder reads `index.html` and writes the pages, so run it again after any change to a case in `index.html`.
It stops with a plain message if a settings entry is missing, a slug repeats, an episode is unreleased,
or any image/audio path would break.
