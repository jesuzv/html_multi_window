# html_multi_window

A tiny generator that publishes a GitHub Pages site containing  
**one HTML page per route**.

Each route page opens multiple inbound/outbound **TfL Bus Status** tabs for:

- **Now**
- A **future date range** (one inbound + one outbound per day)
- **This weekend**

The generator runs automatically and republishes the site daily.

---

## Live site

- Index: https://jesuzv.github.io/html_multi_window/
- Example route page: https://jesuzv.github.io/html_multi_window/1.html

Route pages are named **exactly** like the route in `routes.txt`.

---

## How it works (high level)

- `routes.txt` defines which routes exist and their order
- `generate.py` builds:
  - one HTML page per route
  - an index page linking to them
- GitHub Actions runs the generator and commits output to `gh-pages`
- GitHub Pages serves the site from `gh-pages`

The generated HTML is an **artifact**; the generator is the product.

---

## routes.txt is the source of truth

The file `routes.txt` (on the `main` branch) defines:

- which route pages exist
- the **exact order** they appear in the index

Edit `routes.txt` to add, remove, or reorder routes.

The next successful workflow run will publish the updated site.

---

## Repo layout

This repository is intentionally split:

- **`main`** — source of truth
  - `generate.py`
  - `routes.txt`
  - `.github/workflows/`
- **`gh-pages`** — generated output only
  - published HTML
  - no hand-edited files

This keeps generated noise out of the source branch.

---

## Automation

The site is regenerated using **GitHub Actions**:

- triggered by multiple daily schedules (for reliability)
- can also be run manually via `workflow_dispatch`

### Run-once-per-day logic

Although several cron schedules exist, the generator:

- publishes **at most once per London calendar day**
- stores a success marker on `gh-pages`
- later runs automatically skip if a successful run already happened

This prevents unnecessary duplicate commits.

---

## Authentication

The workflow uses GitHub’s built-in automation token:

- **`GITHUB_TOKEN`**
- scoped to **contents: write**

No Personal Access Token is required.

---

## Usage notes

1. Open the index page
2. Click a route
3. Your browser will likely block pop-ups the first time  
   → allow pop-ups for `jesuzv.github.io`

⚠️ Each route page intentionally opens many tabs.

---

## Development notes

- Time calculations are done in **Europe/London**
- Date ranges automatically adjust for DST
- If you see stale content, it’s usually browser/CDN caching  
  → try a private window

---

Start at the index page and click a route.
