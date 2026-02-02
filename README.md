# html_multi_window

A tiny generator that publishes a GitHub Pages site containing **one HTML page per route**.  
Each route page opens multiple inbound/outbound status tabs for:

- **Now**
- A **future date range** (one inbound + one outbound per day)
- **This weekend**

The generator runs on a schedule and republishes the site daily.

## Live site

- Index: https://jesuzv.github.io/html_multi_window/
- Example route page: https://jesuzv.github.io/html_multi_window/1.html

Route pages are named **exactly** like the route in `routes.txt`.  
The target URLs opened by each route page are defined in `generate.py`.

## Third-party links

This project generates HTML that may open external websites. Any content accessed via those links is owned by its respective owners and is not covered by this repository’s license.

## How to use

1. Open the index page.
2. Click a route.
3. Your browser will likely block pop-ups the first time.  
   Allow pop-ups for `jesuzv.github.io` if you want the “open all tabs” behavior.

⚠️ Note: each route page intentionally triggers a lot of `window.open()` calls, so pop-up blockers are expected.

## routes.txt is the source of truth

The file `routes.txt` (on the `main` branch) defines:

- which route pages exist
- the **exact order** they appear in the index

Edit `routes.txt` to add/remove/reorder routes. The generator will publish the updated index + pages on the next run.

## Repo layout

This repo is intentionally split:

- **main** — source of truth (generator + route list + workflow)
  - `generate.py`
  - `routes.txt`
  - `.github/workflows/*`
- **gh-pages** — generated output only (the published HTML site)

This keeps `main` readable and keeps the generated HTML noise out of the source branch.

## Automation

The site is regenerated automatically using GitHub Actions:

- scheduled daily (UTC cron; chosen to always run after midnight in London)
- can also be run manually via `workflow_dispatch`

### Required secret: PAGES_PAT

The workflow needs a Personal Access Token saved as a repo secret:

- Secret name: `PAGES_PAT`
- Permissions: **Contents: Read and write** on this repo

This token is used to push the generated output to the `gh-pages` branch.

## Development notes

- The generated HTML is an *artifact*; the generator is the product.
- If you see an old index, it’s usually browser/CDN caching — open in a private window to confirm the latest.

---
Start at the index page and click a route (pop-up permissions may be required).
