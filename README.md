# html_multi_window

Generates a GitHub Pages site with **one HTML page per bus route** from `routes.txt`.

Each route page opens **Bus Status** tabs for:
- **Now** (inbound + outbound)
- A **future date range** (inbound + outbound per day)
- **This weekend** (Sat–Sun, London time)

**Project family**
- **html_multi_window (V1 / Daily Full Coverage):** Generates one page per route and opens tabs for “now” plus a date range (and weekend). Best for daily checks when you need the full span.
- **html_multi_window_grouped (V2 / Weekend-Optimized):** Refactor that groups ~10 routes per page and focuses on weekend dates to reduce load and speed up checks. Best on days when you only need weekend availability fast.

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

Do not hand-edit `gh-pages`; change `routes.txt` and let the workflow publish. Any manual edits in `gh-pages` will be overwritten by the next automated workflow run.

## Automation
GitHub Actions runs on multiple daily schedules for reliability, but publishes **at most once per London calendar day** using the marker file on `gh-pages`.

- **Workflow details (triggers, run-once marker, permissions):** [./.github/workflows/README.md](./.github/workflows/README.md)

## Notes
Browsers often block popups on first use — allow popups for `*.github.io`.

## Disclaimer
The generated HTML files may link to or open third-party web content via URLs. That third-party content is owned by its respective owner(s) and is not covered by this repository’s license; this project only generates and publishes the HTML/URL structure.
