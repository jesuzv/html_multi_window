# html_multi_window

Generates a GitHub Pages site with **one HTML page per bus route** from `routes.txt`.

Each route page opens **Bus Status** tabs for:
- **Now** (inbound + outbound)
- A **future date range** (inbound + outbound per day)
- **This weekend** (Sat–Sun, London time)

## Live site
- Index: https://jesuzv.github.io/html_multi_window/
- Example: https://jesuzv.github.io/html_multi_window/1.html

## Source of truth
- `routes.txt` controls which pages exist and their order.
- `generate.py` builds:
  - `index.html`
  - `<route>.html` per route (sanitized filename)
  - `.run-state/last_success.json` (run-once-per-day marker)

## Branches
- `main`: generator + config (`generate.py`, `routes.txt`, workflows)
- `gh-pages`: generated output only (what GitHub Pages serves)

Do not hand-edit `gh-pages`; change `routes.txt` and let the workflow publish.

## Automation
GitHub Actions runs on multiple daily schedules for reliability, but publishes **at most once per London calendar day** using the marker file on `gh-pages`.

## Notes
Browsers often block popups on first use — allow popups for `*.github.io`.
