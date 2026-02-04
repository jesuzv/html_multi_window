# html_multi_window — Generated site

This branch contains the **generated HTML output** for the  
**html_multi_window** project and is published via **GitHub Pages**.

➡️ **Live site:** https://jesuzv.github.io/html_multi_window/

---

## What this is

- One HTML page per route listed in `routes.txt`
- Each route page opens multiple **TfL Bus Status** tabs:
  - **Now** (inbound + outbound)
  - **Future date range** (one inbound + one outbound per day)
  - **This weekend**

These files are **automatically generated** and committed by GitHub Actions.

---

## Important

⚠️ **Do not edit files in this branch manually**

Any manual changes will be overwritten on the next automated run.

---

## Where the source lives

All source code, configuration, and documentation live on the **`main` branch**:

https://github.com/jesuzv/html_multi_window/tree/main

That branch contains:

- the generator (`generate.py`)
- the route list (`routes.txt`)
- the GitHub Actions workflow

---

## About pop-ups

Route pages intentionally open many tabs using `window.open()`.

Most browsers will block this the first time.

To use the site as intended:
- allow pop-ups for `jesuzv.github.io`
- then reload the page and use the one-click opener

---

## Automation note

The site is regenerated **at most once per London calendar day**.

Multiple scheduled runs exist for reliability, but only the first successful run
publishes output; later runs skip automatically.
