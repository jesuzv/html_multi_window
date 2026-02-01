import os
import re
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

def opens_js_for_route(route: str, start_date: pd.Timestamp, end_date: pd.Timestamp, today_for_weekend: pd.Timestamp):
    base_in = url_for(route, "inbound")
    base_out = url_for(route, "outbound")

    lines = []
    # 1) NOW (no dates)
    lines.append(f"setTimeout(function(){{window.open('{base_in}');}}, 0);")
    lines.append(f"setTimeout(function(){{window.open('{base_out}');}}, 60);")

    # 2) Date range: 2 tabs per day
    days = pd.date_range(start_date, end_date, freq="D")
    base_delay = 200
    for i, d in enumerate(days):
        s, e = day_bounds_encoded(d)
        url_in  = f"{base_in}&dateTypeSelect=Future%20date&startDate={s}&endDate={e}"
        url_out = f"{base_out}&dateTypeSelect=Future%20date&startDate={s}&endDate={e}"
        delay = base_delay + i * 350
        lines.append(f"setTimeout(function(){{window.open('{url_in}');}}, {delay});")
        lines.append(f"setTimeout(function(){{window.open('{url_out}');}}, {delay+60});")

    # 3) THIS WEEKEND
    wk_start, wk_end = weekend_bounds_encoded(today_for_weekend)
    w_in  = f"{base_in}&startDate={wk_start}&endDate={wk_end}&dateTypeSelect=This%20weekend"
    w_out = f"{base_out}&startDate={wk_start}&endDate={wk_end}&dateTypeSelect=This%20weekend"
    wk_delay = base_delay + len(days) * 350 + 200
    lines.append(f"setTimeout(function(){{window.open('{w_in}');}}, {wk_delay});")
    lines.append(f"setTimeout(function(){{window.open('{w_out}');}}, {wk_delay+60});")

    return "\n".join(lines)

def html_for_route(route: str, start_date: pd.Timestamp, end_date: pd.Timestamp, today_for_weekend: pd.Timestamp) -> str:
    opens = opens_js_for_route(route, start_date, end_date, today_for_weekend)
    return f"""<!doctype html><html lang="en">
<head><meta charset="utf-8"><title>Route {route}</title>
<script>
window.onload = function(){{
{opens}
}};
</script>
</head>
<body>
<p>
  Opening tabs for route {route}.<br>
  • Now (inbound + outbound)<br>
  • Date range: {start_date:%Y-%m-%d} → {end_date:%Y-%m-%d} (inbound + outbound per day)<br>
  • This weekend (Sat 00:00 → Sun 23:59, London)
</p>
</body>
</html>"""

def index_html_exact(routes, start_date, end_date, generated_at, range_hint):
    items = []
    for r in routes:
        fname = f"{safe_name(r)}.html"
        href = f"{TARGET_DIR}/{fname}" if TARGET_DIR else fname
        items.append(f'<li><a href="{href}" target="_blank" rel="noopener">{r}</a></li>')
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
        html = html_for_route(r, start_dt, end_dt, today_local)
        fname = f"{safe_name(r)}.html"
        relpath = f"{TARGET_DIR}/{fname}" if TARGET_DIR else fname
        files_to_commit[relpath] = html

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

    # 5) Create tree containing ONLY published site files (keeps gh-pages clean)
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
