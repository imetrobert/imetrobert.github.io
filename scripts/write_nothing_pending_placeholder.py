#!/usr/bin/env python3
"""
write_nothing_pending_placeholder.py
Writes a friendly "nothing pending" page to blog/staging/preview.html.
Used by approve-blog.yml and discard-blog.yml whenever the staging draft
they were operating on is gone and nothing is left to review — otherwise
that URL would show a bare 404 until the next draft is generated.

generate-preview-page.py unconditionally overwrites this file the next
time a real draft is generated, so this placeholder is self-clearing.
"""

import os
import sys
from datetime import date, timedelta


def next_generation_date():
    # Last day of the CURRENT month — the same date monthly-blog.yml's own
    # schedule check fires on.
    today = date.today()
    next_month, next_year = today.month + 1, today.year
    if next_month > 12:
        next_month, next_year = 1, next_year + 1
    last_day = date(next_year, next_month, 1) - timedelta(days=1)
    return last_day.strftime("%B %-d, %Y")


REPO = "imetrobert/imetrobert.github.io"

# Shared by both modes: token box + dispatch helper. Token is the same localStorage
# key the review and health pages use, so it is usually already saved.
_JS = """
const REPO = "%(repo)s", API = "https://api.github.com";
const $ = id => document.getElementById(id);
function say(t, bad) { const m = $("msg"); m.textContent = t; m.style.color = bad ? "#b91c1c" : "#166534"; }
function savePat() {
  const v = $("pat").value.trim();
  if (v.length < 20) { say("That does not look like a token.", true); return; }
  localStorage.setItem("blog_preview_pat", v); $("patbox").style.display = "none"; say("Token saved. Tap the button again.");
}
async function run(wf, inputs, okText) {
  const pat = localStorage.getItem("blog_preview_pat");
  if (!pat) { $("patbox").style.display = "block"; say("Add your GitHub token first.", true); return; }
  say("Sending...");
  try {
    const r = await fetch(API + "/repos/" + REPO + "/actions/workflows/" + wf + "/dispatches", {method: "POST",
      headers: {Authorization: "Bearer " + pat, Accept: "application/vnd.github+json", "Content-Type": "application/json"},
      body: JSON.stringify({ref: "main", inputs})});
    if (r.status === 204) { say(okText); return; }
    if (r.status === 401) { localStorage.removeItem("blog_preview_pat"); $("patbox").style.display = "block";
      say("GitHub rejected the token. Paste a new one (see the Pipeline health page for links).", true); return; }
    say("GitHub answered " + r.status + ". Check the token has Actions: read and write.", true);
  } catch (e) { say("Network error. Try again.", true); }
}
"""

_STYLE = """
  body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 560px; margin: 4rem auto; padding: 0 1.5rem; line-height: 1.7; color: #1e293b; text-align: center; }
  h1 { color: #2563eb; font-size: 1.4rem; }
  a.btn, button.btn { display: inline-block; margin-top: 1.2rem; background: linear-gradient(135deg, #2563eb, #06b6d4); color: white; text-decoration: none; padding: 0.7rem 1.5rem; border-radius: 25px; font-weight: 600; font-size: 0.9rem; border: 0; cursor: pointer; font-family: inherit; }
  button.warn { background: #b45309; }
  .card { margin-top: 2rem; padding: 1rem; border: 1px solid #e2e8f0; border-radius: 10px; text-align: left; font-size: 0.85rem; }
  #msg { margin-top: 1rem; font-size: 0.85rem; min-height: 1.2rem; }
  #patbox { display: none; margin-top: 1rem; } #patbox input { width: 80%; padding: 0.5rem; font-size: 16px; }
"""

_HEAD = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>%(title)s - Robert Simon</title>
<meta name="robots" content="noindex, nofollow">
<script src="/blog/staging/gate.js"></script>
<style>%(style)s</style></head>
<body>
"""

_TAIL = """<div id="msg"></div>
<div id="patbox"><input id="pat" type="password" autocomplete="off" placeholder="Paste GitHub token"> <button class="btn" onclick="savePat()">Save</button></div>
<script>%(js)s</script>
</body></html>
"""


def latest_issue():
    """(filename, label) of the newest published issue, or None."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from rollback_post import published_issues, coverage_of
        issues = published_issues()
        if len(issues) < 2:
            return None
        label, _, _ = coverage_of(os.path.join("blog/posts", issues[0]))
        return issues[0], label
    except Exception:
        return None


def build_html(next_date, latest=None):
    head = _HEAD % {"title": "No post pending", "style": _STYLE}
    body = f"""<h1>Nothing pending review right now</h1>
<p>There's no draft waiting for approval at the moment.</p>
<p>The next draft generates automatically on <strong>{next_date}</strong> and will appear here for review.</p>
<a href="https://www.imetrobert.com/blog/" class="btn">View the live blog</a>
<br><a href="/blog/staging/health.html" class="btn" style="background:#0f172a;">Pipeline health and run log</a>
"""
    if latest:
        fn, label = latest
        body += f"""<div class="card"><strong>Found a big fault in the published issue?</strong><br>
Roll back <strong>{label}</strong>: it disappears from the blog, the feed, the sitemap and the AI summaries, and any shared link goes to the blog home. You then get a button to rerun the same month.<br>
<button class="btn warn" onclick="if (confirm('Roll back the {label} issue? It will be taken offline now.')) run('rollback-blog.yml', {{post_filename: '{fn}'}}, 'Rollback started. Refresh this page in about two minutes.')">Roll back {label}</button></div>
"""
    return head + body + _TAIL % {"js": _JS % {"repo": REPO}}


def build_rolled_back_html(label, cov_month, cov_year):
    head = _HEAD % {"title": "Issue rolled back", "style": _STYLE}
    body = f"""<h1>{label} was rolled back</h1>
<p>It is no longer on the blog, in the feed, the sitemap or the AI summaries. Old links to it go to the blog home.</p>
<p>Rerun it to get fresh content? The rerun covers <strong>{cov_month} {cov_year}</strong> only, the same month as before, whatever today's date is.</p>
<button class="btn" onclick="run('monthly-blog.yml', {{force_run: 'true', coverage_month: '{cov_month}', coverage_year: '{cov_year}'}}, 'Rerun started. The new draft appears on this page in a few minutes. Refresh to check.')">Rerun {cov_month} {cov_year}</button>
<br><a href="/blog/staging/health.html" class="btn" style="background:#0f172a;">Pipeline health and run log</a>
"""
    return head + body + _TAIL % {"js": _JS % {"repo": REPO}}


def write_page(rolled_back=None):
    os.makedirs("blog/staging", exist_ok=True)
    if rolled_back:
        html = build_rolled_back_html(*rolled_back)
    else:
        html = build_html(next_generation_date(), latest_issue())
    with open("blog/staging/preview.html", "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    write_page()
    print(f"Wrote 'nothing pending' placeholder - next generation: {next_generation_date()}")
