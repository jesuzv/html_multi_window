import os
import re
import json
import html
import requests
import pandas as pd

# ---------- Config ----------
OWNER = "jesuzv"
REPO = "html_multi_window"

SOURCE_BRANCH = "main"     # routes.txt lives here
OUTPUT_BRANCH = "gh-pages" # generated HTML goes here (GitHub Pages publishes this)

ROUTE_FILE_PATH = "routes.txt"
TARGET_DIR = ""            # keep "" to preserve URLs like /1.html, /SL10.html

# London local dynamic date range: today → today+12 (inclusive)
tz = "Europe/London"
today_local = pd.Timestamp.now(tz=tz).normalize()
start_dt = today_local.tz_localize(None)
end_dt = (today_local + pd.Timedelta(days=12)).tz_localize(None)

# ---------- Helpers ----------
def safe_name(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s)

def url_for(route: str, direction: str) -> str:
    r = route.strip()
    return f"https://tfl.gov.uk/bus/status/?input={r}&lineIds={r}&direction={direction}"

def day_bounds_encoded(day: pd.Timestamp):
    return f"{day:%Y-%m-%d}T00%3A00%3A00", f"{day:%Y-%m-%d}T23%3A59%3A59"

def weekend_bounds_encoded(today: pd.Timestamp):
    wd = today.weekday()  # Mon=0..Sun=6
    offset_to_sat = (5 - wd) % 7
    sat = (today + pd.Timedelta(days=offset_to_sat)).tz_localize(None)
    sun = sat + pd.Timedelta(days=1)
    s, e = day_bounds_encoded(sat), day_bounds_encoded(sun)
    return s[0], e[1]  # Sat 00:00 .. Sun 23:59

def open_plan_for_route(
    route: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    today_for_weekend: pd.Timestamp,
):
    """
    Returns a list of tuples: (url, delay_ms), preserving the exact opening order/timing.
    """
    base_in = url_for(route, "inbound")
    base_out = url_for(route, "outbound")

    plan = []

    # 1) NOW (no dates)
    plan.append((base_in, 0))
    plan.append((base_out, 60))

    # 2) Date range: 2 tabs per day
    days = pd.date_range(start_date, end_date, freq="D")
    base_delay = 200
    for i, d in enumerate(days):
        s, e = day_bounds_encoded(d)
        url_in = f"{base_in}&dateTypeSelect=Future%20date&startDate={s}&endDate={e}"
        url_out = f"{base_out}&dateTypeSelect=Future%20date&startDate={s}&endDate={e}"
        delay = base_delay + i * 350
        plan.append((url_in, delay))
        plan.append((url_out, delay + 60))

    # 3) THIS WEEKEND
    wk_start, wk_end = weekend_bounds_encoded(today_for_weekend)
    w_in = f"{base_in}&startDate={wk_start}&endDate={wk_end}&dateTypeSelect=This%20weekend"
    w_out = f"{base_out}&startDate={wk_start}&endDate={wk_end}&dateTypeSelect=This%20weekend"
    wk_delay = base_delay + len(days) * 350 + 200
    plan.append((w_in, wk_delay))
    plan.append((w_out, wk_delay + 60))

    return plan

def html_for_route(
    route: str,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    today_for_weekend: pd.Timestamp,
) -> str:
    plan = open_plan_for_route(route, start_date, end_date, today_for_weekend)

    # Safe JS literals (handles quotes, unicode, etc.)
    urls_js = json.dumps([u for (u, _) in plan], ensure_ascii=False)
    delays_js = json.dumps([d for (_, d) in plan])

    route_esc = html.escape(route)

    js = f"""
const urls = {urls_js};
const delays = {delays_js};

function openScheduled(startIdx) {{
  const t0 = delays[startIdx] || 0;
  for (let i = startIdx; i < urls.length; i++) {{
    const d = Math.max(0, delays[i] - t0);
    setTimeout(() => window.open(urls[i], "_blank", "noopener"), d);
  }}
}}

function showFallback() {{
  const box = document.getElementById("blocked");
  box.style.display = "block";
  document.getElementById("tabCount").textContent = String(urls.length);
  document.getElementById("openAll").onclick = () => openScheduled(0);
}}

window.onload = function() {{
  try {{
    // Probe: if this is blocked, show button instead of silently failing.
    const w = window.open(urls[0], "_blank", "noopener");
    if (!w) {{
      showFallback();
      return;
    }}
    // Already opened index 0, so replay the rest using the schedule.
    openScheduled(1);
  }} catch (e) {{
    showFallback();
  }}
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
  <strong>Popups were blocked.</strong><br>
  Intended to open <span id="tabCount">?</span> tabs.<br><br>
  <button id="openAll">Open all tabs</button>
  <p style="margin-top:10px; color:#555;">
    To keep it one-click forever, allow popups for this site in your browser settings.
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

def main():
    # 1) Load routes.txt from main (exact order)
    raw_url = f"https://raw.githubusercontent.com/{OWNER}/{REPO}/{SOURCE_BRANCH}/{ROUTE_FILE_PATH}"
    resp = requests.get(raw_url, timeout=30)
    resp.raise_for_status()

    routes = [ln.strip() for ln in resp.text.splitlines() if ln.strip()]
    if not routes:
        raise RuntimeError("routes.txt loaded but contained no routes.")
    if len(routes) != len(set(routes)):
        raise RuntimeError("Duplicate routes found in routes.txt.")

    dates_list = [d.strftime("%Y-%m-%d") for d in pd.date_range(start_dt, end_dt, freq="D")]
    generated_at = pd.Timestamp.now(tz=tz).strftime("%Y-%m-%d %H:%M %Z")
    range_hint = f"{dates_list[0]} → {dates_list[-1]}"

    # 2) Build output files
    files_to_commit = {}
    for r in routes:
        page_html = html_for_route(r, start_dt, end_dt, today_local)
        fname = f"{safe_name(r)}.html"
        relpath = f"{TARGET_DIR}/{fname}" if TARGET_DIR else fname
        files_to_commit[relpath] = page_html

    files_to_commit["index.html"] = index_html_exact(routes, start_dt, end_dt, generated_at, range_hint)

    # 3) Auth (use PAT from Actions secret)
    token = os.environ.get("PAGES_PAT")
    if not token:
        raise RuntimeError("Missing PAGES_PAT env var (set it as a repo secret and pass via workflow).")

    gh = requests.Session()
    gh.headers.update({
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })

    # 4) Get gh-pages HEAD
    out_ref = gh_req(gh, "GET", f"{API}/repos/{OWNER}/{REPO}/git/ref/heads/{OUTPUT_BRANCH}")
    out_head_sha = out_ref["object"]["sha"]

    # 5) Create tree containing ONLY published site files
    tree_items = [{"path": p, "mode": "100644", "type": "blob", "content": c}
                  for p, c in files_to_commit.items()]

    commit_message = (
        f"Daily HTML update: {range_hint} (+now,+weekend; {len(routes)} routes + index)"
    )

    new_tree = gh_req(gh, "POST", f"{API}/repos/{OWNER}/{REPO}/git/trees", json={
        "tree": tree_items
    })
    new_tree_sha = new_tree["sha"]

    # 6) Create commit
    new_commit = gh_req(gh, "POST", f"{API}/repos/{OWNER}/{REPO}/git/commits", json={
        "message": commit_message,
        "tree": new_tree_sha,
        "parents": [out_head_sha],
    })
    new_commit_sha = new_commit["sha"]

    # 7) Update gh-pages ref
    gh_req(gh, "PATCH", f"{API}/repos/{OWNER}/{REPO}/git/refs/heads/{OUTPUT_BRANCH}", json={
        "sha": new_commit_sha,
        "force": False
    })

    print(f"OK: committed {len(routes)} routes + index to {OUTPUT_BRANCH}: {new_commit_sha}")

if __name__ == "__main__":
    main()
