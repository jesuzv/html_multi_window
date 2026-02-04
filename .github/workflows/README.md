# GitHub Actions workflows

This folder contains the automation that builds and publishes the
**html_multi_window** GitHub Pages site.

---

## daily.yml

The primary workflow responsible for:

- running the HTML generator
- publishing output to the `gh-pages` branch

### Triggers

- `workflow_dispatch` (manual run)
- multiple daily `schedule` cron entries

Multiple schedules exist intentionally to increase reliability.

---

## Why multiple cron schedules?

GitHub cron schedules are **best-effort**, not guaranteed.

This workflow may be triggered several times per day, but:

- the generator publishes **at most once per London calendar day**
- a success marker stored on `gh-pages` prevents duplicate runs

Later runs detect the marker and exit early.

---

## Authentication

The workflow uses GitHub’s built-in token:

- `GITHUB_TOKEN`
- permissions: `contents: write`

No Personal Access Token (PAT) is required.

---

## Branch behavior

- Source branch: `main`
- Output branch: `gh-pages`

The workflow commits generated HTML directly to `gh-pages`.
No pull requests are created.

---

## Notes for maintainers

- Skipped runs still appear as **successful** in the Actions UI
- Look inside the step logs for a “Skip: already succeeded today” notice
- The absence of a new commit on `gh-pages` confirms a skip
