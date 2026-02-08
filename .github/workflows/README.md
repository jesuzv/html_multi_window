# GitHub Actions workflows

This folder contains automation that generates and publishes the GitHub Pages site.

## daily.yml
Runs `generate.py` and commits output to the `gh-pages` branch.

### Triggers
- `workflow_dispatch`
- multiple daily `schedule` cron entries (reliability)

### Run-once-per-day behavior
Even if triggered multiple times, the generator publishes **once per London day** by checking a success marker on `gh-pages`:
- `.run-state/last_success.json`

Later runs exit early with a “Skip: already succeeded today” message.

### Auth / permissions
Uses GitHub’s built-in token:
- `GITHUB_TOKEN`
- `permissions: contents: write`

No PAT is required.
