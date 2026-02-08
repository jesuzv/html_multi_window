import os
import re
import json
import html
import subprocess
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

import requests

# ---------- Config ----------
# OWNER/REPO are auto-detected (Actions, env override, or local git remote)
SOURCE_BRANCH = "main"     # routes.txt lives here
OUTPUT_BRANCH = "gh-pages" # generated HTML goes here (GitHub Pages publishes this)

ROUTE_FILE_PATH = "routes.txt"
TARGET_DIR = ""            # keep "" to preserve URLs like /1.html, /SL10.html

# Durable "already succeeded today?" marker stored on gh-pages
STATE_PATH = ".run-state/last_success.json"

# London local dynamic date range: today → today+12 (inclusive)
TZ = ZoneInfo("Europe/London")
today_local: date = datetime.now(TZ).date()
start_dt: date = today_local
end_dt: date = today_local + timedelta(days=12)

# ---------- Repo detection ----------
def detect_owner_repo() -> tuple[str, str]:
    """
    Priority:
      1) Explicit override: GITHUB_OWNER + GITHUB_REPO
      2) GitHub Actions: GITHUB_REPOSITORY = "owner/repo"
      3) Local git: parse `git remote get-url origin`
    """
    owner = os.environ.get("GITHUB_OWNER")
    repo = os.environ.get("GITHUB_REPO")
    if owner and repo:
        return owner, repo

    gh_repo = os.environ.get("GITHUB_REPOSITORY")
    if gh_repo and "/" in gh_repo:
        o, r = gh_repo.split("/", 1)
        return o, r

    # Local fallback: try git remote
    try:
        url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()

        # Handles:
        #   https://github.com/owner/repo.git
        #   git@github.com:owner/repo.git
        m = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)", url)
        if m:
            return m.group("owner"), m.group("repo")
    except Exception:
        pass

    raise RuntimeError(
        "Could not detect owner/repo. Set env vars GITHUB_OWNER and GITHUB_REPO, "
        "or run inside a git repo with an 'origin' remote, or on GitHub Actions."
    )

# ---------- Helpers ----------
def safe_name(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s)

def url_for(route: str, direction: str) -> str:
    r = route.strip()
    return f"https://tfl.gov.uk/bus/status/?input={r}&lineIds={r}&direction={direction}"

def day_bounds_encoded(day: date):
    d = day.strftime("%Y-%m-%d")
    return f"{d}T00%3A00%3A00", f"{d}T23%3A59%3A59"

def weekend_bounds_encoded(today: date):
    wd = today.weekday()  # Mon=0..Sun=6
    offset_to_sat = (5 - wd) % 7
    sat = today + timedelta(days=offset_to_sat)
    sun = sat + timedelta(days=1)
    s0, _ = day_bounds_encoded(sat)
    _, e1 = day_bounds_encoded(sun)
    return s0, e1  # Sat 00:00 .. Sun 23:59

def london_today_iso() -> str:
    return datetime.now(TZ).date().isoformat()

def already_succeeded_today(owner: str, repo: str, branch: str) -> bool:
    """
    Checks a committed marker file on the output branch to see if we already
    successfully published for today's London date.

    If the check fails (network, parse error), we DO NOT skip (safer to run again).
    """
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{STATE_PATH}"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 404:
            return False
        r.raise_for_status()
        data = r.json()
        return data.get("date") == london_today_iso() and data.get("status") == "success"
    except Exception:
        return False

def success_state_payload(range_hint: str) -> str:
    return json.dumps(
        {
            "date": london_today_iso(),
            "status": "success",
            "range": range_hint,
            "updated_at": datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S %Z"),
        },
        ensure_ascii=False,
        indent=2,
    ) + "\n"

def open_plan_for_route(
    route: str,
    start_date: date,
    end_date: date,
    today_for_weekend: date,
):
    """
    Returns a list of tuples: (label, url, delay_ms), preserving the exact opening order/timing.
    """
    base_in = url_for(route, "inbound")
    base_out = url_for(route, "outbound")

    plan = []

    # 1) NOW (no dates)
    plan.append(("Now — inbound", base_in, 0))
    plan.append(("Now — outbound", base_out, 60))

    # 2) Date range: 2 tabs per day (inclusive)
    day_count = (end_date - start_date).days
    days = [start_date + timedelta(days=i) for i in range(day_count + 1)]

    base_delay = 200
    for i, d in enumerate(days):
        s, e = day_bounds_encoded(d)
        day_label = d.strftime("%Y-%m-%d")
        url_in = f"{base_in}&dateTypeSelect=Future%20date&startDate={s}&endDate={e}"
        url_out = f"{base_out}&dateTypeSelect=Future%20date&startDate={s}&endDate={e}"
        delay = base_delay + i * 350
        plan.append((f"{day_label} — inbound", url_in, delay))
        plan.append((f"{day_label} — outbound", url_out, delay + 60))

    # 3) THIS WEEKEND
    wk_start, wk_end = weekend_bounds_encoded(today_for_weekend)
    w_in = f"{base_in}&startDate={wk_start}&endDate={wk_end}&dateTypeSelect=This%20weekend"
    w_out = f"{base_out}&startDate={wk_start}&endDate={wk_end}&dateTypeSelect=This%20weekend"
    wk_delay = base_delay + len(days) * 350 + 200
    plan.append(("This weekend — inbound", w_in, wk_delay))
    plan.append(("This weekend — outbound", w_out, wk_delay + 60))

    return plan

def html_for_route(
    route: str,
    start_date: date,
    end_date: date,
    today_for_weekend: date,
) -> str:
    plan = open_plan_for_route(route, start_date, end_date, today_for_weekend)

    labels = [lbl for (lbl, _, _) in plan]
    urls = [u for (_, u, _) in plan]
    delays = [d for (_, _, d) in plan]

    labels_js = json.dumps(labels, ensure_ascii=False)
    urls_js = json.dumps(urls, ensure_ascii=False)
    delays_js = json.dumps(delays)

    route_esc = html.escape(route)

    # Notes:
    # - Auto-open uses window.open(url)
    # - If anything is blocked, stop and show fallback.
    # - Fallback "Open all tabs" uses the same schedule, but ONLY after verifying popups are allowed.
    js = f"""
const labels = {labels_js};
const urls = {urls_js};
const delays = {delays_js};

let timeouts = [];

function clearSchedule() {{
  for (const id of timeouts) clearTimeout(id);
  timeouts = [];
}}

function setStatus(msg) {{
  const el = document.getElementById("status");
  if (el) el.textContent = msg;
}}

function renderPlannedList() {{
  const ol = document.getElementById("plannedList");
  if (!ol) return;
  ol.innerHTML = "";
  for (let i = 0; i < labels.length; i++) {{
    const li = document.createElement("li");

    const labelSpan = document.createElement("span");
    labelSpan.textContent = labels[i];

    const link = document.createElement("a");
    link.href = urls[i];
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = "open";

    li.appendChild(labelSpan);
    li.appendChild(document.createTextNode(" "));
    li.appendChild(link);
    ol.appendChild(li);
  }}
}}

function showFallback() {{
  clearSchedule();
  const box = document.getElementById("blocked");
  box.style.display = "block";
  document.getElementById("tabCount").textContent = String(urls.length);
  renderPlannedList();
  setStatus("Popups are blocked. Allow popups for this site, then click “Open all tabs” to open everything in order.");

  document.getElementById("openAll").onclick = () => {{
    setStatus("Checking popup permission…");
    // Must succeed on *this click* (user gesture). If blocked here, schedule will also fail.
    const test = window.open(urls[0]);
    if (!test) {{
      setStatus("Still blocked. Allow popups for this site first — otherwise the browser will open 0–1 tab.");
      return;
    }}

    setStatus("Popups allowed — opening tabs in order…");
    // We already opened index 0 in the permission test, so schedule the rest preserving spacing.
    scheduleFrom(1, delays[1] || 0);
  }};
}}

function scheduleFrom(startIdx, t0Delay) {{
  for (let i = startIdx; i < urls.length; i++) {{
    const d = Math.max(0, (delays[i] || 0) - t0Delay);
    const id = setTimeout(() => {{
      const w = window.open(urls[i]);
      if (!w) {{
        // If the browser starts blocking mid-stream, fall back immediately.
        showFallback();
      }}
    }}, d);
    timeouts.push(id);
  }}
}}

window.onload = function() {{
  // Auto-open path (works when the site is allowed, like your original code).
  const w0 = window.open(urls[0]);
  if (!w0) {{
    showFallback();
    return;
  }}
  // Keep your intended timing for the rest.
  scheduleFrom(1, delays[1] || 0);
}};
""".strip()

    return f"""<!doctype html><html lang="en">
<head><meta charset="utf-8"><title>Route {route_esc}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 24px; line-height: 1.4; }}
  .blocked {{
    display:none; margin-top:16px; padding:12px 14px;
    border:1px solid #e5e5e5; border-radius:12px; background:#fafafa;
  }}
  button {{
    font-size:18px; padding:10px 14px; border-radius:12px;
    border:1px solid #ccc; cursor:pointer;
  }}
  ol {{ margin-top: 12px; padding-left: 20px; }}
  li {{ margin: 6px 0; }}
  a {{ margin-left: 6px; }}
  .note {{ margin-top:10px; color:#555; }}
  #status {{ margin-top:10px; color:#333; }}
</style>
<script>
{js}
</script>
</head>
<body>
<p>
  Opening tabs for route {route_esc}.<br>
  • Now (inbound + outbound)<br>
  • Date range: {start_date:%Y-%m-%d} → {end_date:%Y-%m-%d} (inbound + outbound per day)<br>
  • This weekend (Sat 00:00 → Sun 23:59, London)
</p>

<div id="blocked" class="blocked">
  <strong>Popups are blocked for this site.</strong><br>
  Planned tabs: <span id="tabCount">?</span>.<br>
  Allow popups for this site <em>first</em>, then click “Open all tabs” to open everything in order.<br>
  Otherwise the browser may open only 0–1 tab.<br><br>

  <button id="openAll">Open all tabs</button>
  <div id="status"></div>

  <p class="note">
    Manual option (intended order):
  </p>
  <ol id="plannedList"></ol>

  <p class="note">
    Best experience: allow popups for this site to enable the one-click opener.
  </p>
</div>
</body>
</html>"""

def index_html_exact(routes, start_date, end_date, generated_at, range_hint):
    items = []
    for r in routes:
        fname = f"{safe_name(r)}.html"
        href = f"{TARGET_DIR}/{fname}" if TARGET_DIR else fname
        items.append(f'<li><a href="{href}" target="_blank" rel="noopener">{html.escape(r)}</a></li>')
    items_html = "\n".join(items)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Routes</title>

  <!-- Cache-busting hints (not perfect, but helps) -->
  <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
  <meta http-equiv="Pragma" content="no-cache">
  <meta http-equiv="Expires" content="0">

  <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; margin: 24px; line-height: 1.4; }}
    .meta {{ color: #555; margin: 8px 0 16px; }}
    ul {{
      list-style: none;
      padding: 0;
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(90px, 1fr));
      gap: 8px;
    }}
    li {{ border: 1px solid #e5e5e5; border-radius: 10px; padding: 8px 10px; text-align: center; }}
    a {{ text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <h1>Routes</h1>
  <div class="meta">
    Generated: <strong>{generated_at}</strong><br>
    Range: <strong>{range_hint}</strong><br>
    Total routes: <strong>{len(routes)}</strong>
  </div>

  <ul>
    {items_html}
  </ul>
</body>
</html>"""

# ---------- GitHub REST helpers ----------
API = "https://api.github.com"

def gh_req(session: requests.Session, method: str, url: str, **kwargs):
    r = session.request(method, url, **kwargs)
    if not r.ok:
        raise RuntimeError(f"{method} {url} -> {r.status_code}\n{r.text}")
    return r.json()

def _get_ref_or_none(gh: requests.Session, url: str):
    r = gh.get(url)
    if r.status_code == 404:
        return None
    if not r.ok:
        raise RuntimeError(f"GET {url} -> {r.status_code}\n{r.text}")
    return r.json()

def ensure_output_branch_exists(gh: requests.Session, owner: str, repo: str, branch: str) -> str:
    """
    Ensures OUTPUT_BRANCH exists. If missing, creates it pointing at SOURCE_BRANCH HEAD.
    Returns the branch HEAD commit SHA.
    """
    ref_url = f"{API}/repos/{owner}/{repo}/git/ref/heads/{branch}"
    ref = _get_ref_or_none(gh, ref_url)
    if ref is not None:
        return ref["object"]["sha"]

    # Create OUTPUT_BRANCH from SOURCE_BRANCH head
    src_ref = gh_req(gh, "GET", f"{API}/repos/{owner}/{repo}/git/ref/heads/{SOURCE_BRANCH}")
    src_sha = src_ref["object"]["sha"]

    gh_req(gh, "POST", f"{API}/repos/{owner}/{repo}/git/refs", json={
        "ref": f"refs/heads/{branch}",
        "sha": src_sha,
    })
    return src_sha

def main():
    owner, repo = detect_owner_repo()

    # 0) Skip if one of the earlier crons already succeeded today (London date)
    if already_succeeded_today(owner, repo, OUTPUT_BRANCH):
        print("Skip: already succeeded today (per gh-pages state file).")
        return

    # 1) Load routes.txt from main (exact order)
    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{SOURCE_BRANCH}/{ROUTE_FILE_PATH}"
    resp = requests.get(raw_url, timeout=30)
    resp.raise_for_status()

    routes = [ln.strip() for ln in resp.text.splitlines() if ln.strip()]
    if not routes:
        raise RuntimeError("routes.txt loaded but contained no routes.")
    if len(routes) != len(set(routes)):
        raise RuntimeError("Duplicate routes found in routes.txt.")

    dates_list = [(start_dt + timedelta(days=i)).strftime("%Y-%m-%d")
                  for i in range((end_dt - start_dt).days + 1)]
    generated_at = datetime.now(TZ).strftime("%Y-%m-%d %H:%M %Z")
    range_hint = f"{dates_list[0]} → {dates_list[-1]}"

    # 2) Build output files
    files_to_commit = {}
    for r in routes:
        page_html = html_for_route(r, start_dt, end_dt, today_local)
        fname = f"{safe_name(r)}.html"
        relpath = f"{TARGET_DIR}/{fname}" if TARGET_DIR else fname
        files_to_commit[relpath] = page_html

    files_to_commit["index.html"] = index_html_exact(routes, start_dt, end_dt, generated_at, range_hint)

    # 2b) Update success marker (committed to gh-pages; used for skip logic)
    files_to_commit[STATE_PATH] = success_state_payload(range_hint)

    # 3) Auth (use GitHub Actions token or local PAT)
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise RuntimeError(
            "Missing token. On GitHub Actions this is GITHUB_TOKEN. "
            "Locally, set GH_TOKEN to a PAT with repo permissions."
        )

    gh = requests.Session()
    gh.headers.update({
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })

    # 4) Ensure gh-pages exists; get its HEAD commit SHA
    out_head_sha = ensure_output_branch_exists(gh, owner, repo, OUTPUT_BRANCH)

    # 5) Create tree containing ONLY published site files
    tree_items = [{"path": p, "mode": "100644", "type": "blob", "content": c}
                  for p, c in files_to_commit.items()]

    commit_message = (
        f"Daily HTML update: {range_hint} (+now,+weekend; {len(routes)} routes + index)"
    )

    new_tree = gh_req(gh, "POST", f"{API}/repos/{owner}/{repo}/git/trees", json={
        "tree": tree_items
    })
    new_tree_sha = new_tree["sha"]

    # 6) Create commit
    new_commit = gh_req(gh, "POST", f"{API}/repos/{owner}/{repo}/git/commits", json={
        "message": commit_message,
        "tree": new_tree_sha,
        "parents": [out_head_sha],
    })
    new_commit_sha = new_commit["sha"]

    # 7) Update gh-pages ref
    gh_req(gh, "PATCH", f"{API}/repos/{owner}/{repo}/git/refs/heads/{OUTPUT_BRANCH}", json={
        "sha": new_commit_sha,
        "force": False
    })

    print(f"OK: committed {len(routes)} routes + index to {OUTPUT_BRANCH}: {new_commit_sha}")

if __name__ == "__main__":
    main()
