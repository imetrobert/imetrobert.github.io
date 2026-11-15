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

import html as _html
import json
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
async function copyBox(id, btn) {
  const t = $(id).value;
  try { await navigator.clipboard.writeText(t); }
  catch (e) { const el = $(id); el.focus(); el.select(); el.setSelectionRange(0, 999999); document.execCommand("copy"); }
  const old = btn.textContent; btn.textContent = "Copied"; setTimeout(() => { btn.textContent = old; }, 1800);
}
async function redoLinkedIn(file) {
  const fb = $("li-feedback").value.trim();
  if (fb.length < 5) { say("Write what to change first (for example: shorter, punchier hook, mention pricing).", true); return; }
  const was = $("li-card").dataset.gen;
  await run("linkedin-post.yml", {post_filename: file, feedback: fb}, "Rewriting. The new version appears here in about 2 minutes.");
  if ($("msg").style.color === "rgb(185, 28, 28)") return;
  for (let i = 0; i < 40; i++) {
    await new Promise(r => setTimeout(r, 8000));
    try {
      const r = await fetch("/blog/staging/linkedin.json?t=" + Date.now(), {cache: "no-store"});
      const d = await r.json();
      if (d.generated_at && d.generated_at !== was) {
        $("li-post").value = d.post; $("li-comment").value = d.first_comment;
        $("li-card").dataset.gen = d.generated_at; $("li-feedback").value = "";
        say("New version ready below. Copy it, or add more comments."); return;
      }
    } catch (e) {}
  }
  say("Still working. Refresh this page in a minute.", true);
}
async function pollJson(path, key, was, apply, doneText) {
  for (let i = 0; i < 45; i++) {
    await new Promise(r => setTimeout(r, 8000));
    try {
      const r = await fetch(path + "?t=" + Date.now(), {cache: "no-store"});
      const d = await r.json();
      if (d.generated_at && d.generated_at !== was) { apply(d); say(doneText); return; }
    } catch (e) {}
  }
  say("Still working. Refresh this page in a minute.", true);
}
async function buildPromo(file) {
  const was = ($("pk-card") || {dataset: {}}).dataset.gen || "";
  await run("promo-kit.yml", {post_filename: file}, "Building. Refresh this page in about 3 minutes.");
}
async function askReply(file) {
  const c = $("rp-comment").value.trim();
  if (c.length < 3) { say("Paste the comment you want to answer first.", true); return; }
  const was = $("rp-card").dataset.gen || "";
  await run("reply-helper.yml", {comment: c, post_filename: file}, "Drafting replies. They appear below in about 2 minutes.");
  if ($("msg").style.color === "rgb(185, 28, 28)") return;
  await pollJson("/blog/staging/reply.json", "reply", was, d => {
    $("rp-card").dataset.gen = d.generated_at;
    d.replies.forEach((t, i) => { $("rp-" + (i + 1)).value = t; });
  }, "Three reply options are ready below.");
}
function addReminder(btn) {
  const b = new Blob([btn.dataset.ics], {type: "text/calendar"});
  const u = URL.createObjectURL(b); const a = document.createElement("a");
  a.href = u; a.download = "linkedin-post.ics"; document.body.appendChild(a); a.click();
  setTimeout(() => { URL.revokeObjectURL(u); a.remove(); }, 2000);
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
  .li textarea { width: 100%; box-sizing: border-box; font: 16px/1.5 -apple-system, sans-serif; padding: 0.7rem; border: 1px solid #cbd5e1; border-radius: 8px; }
  .li h2 { font-size: 1.05rem; margin: 0 0 0.3rem; color: #0a66c2; } .li small { color: #64748b; }
  button.li-btn { background: #0a66c2; margin: 0.4rem 0.4rem 0 0; padding: 0.55rem 1.1rem; }
  .pk textarea, .rp textarea { width: 100%; box-sizing: border-box; font: 16px/1.5 -apple-system, sans-serif; padding: 0.7rem; border: 1px solid #cbd5e1; border-radius: 8px; margin-top: 0.3rem; }
  .pk h2, .rp h2 { font-size: 1.05rem; margin: 0 0 0.3rem; color: #0a66c2; } .pk h3 { font-size: 0.95rem; margin: 1.3rem 0 0.1rem; } .pk small, .rp small { color: #64748b; }
  .pk button.li-btn, .rp button.li-btn { background: #0a66c2; margin: 0.4rem 0.4rem 0 0; padding: 0.55rem 1.1rem; }
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
    except Exception as e:
        print(f"WARNING: could not read the published issues, so the rollback and LinkedIn cards are left out: {e}")
        return None


def linkedin_card(d):
    e = _html.escape
    post, comment = e(d.get("post", "")), e(d.get("first_comment", ""))
    n = len(d.get("post", ""))
    return f"""<div class="card li" id="li-card" data-gen="{e(d.get('generated_at', ''))}">
<h2>LinkedIn post for {e(d.get('title', 'this issue'))}</h2>
<small>Ready to paste. Post it first, then add the comment below as your first comment (LinkedIn shows posts without a link to more people). <span id="li-count">{n} characters</span>.</small>
<textarea id="li-post" rows="14" readonly>{post}</textarea>
<button class="btn li-btn" onclick="copyBox('li-post', this)">Copy post</button>
<a class="btn li-btn" href="https://www.linkedin.com/feed/" target="_blank" rel="noopener">Open LinkedIn</a>
<p style="margin:1rem 0 0.2rem;"><strong>First comment (with the link)</strong></p>
<textarea id="li-comment" rows="4" readonly>{comment}</textarea>
<button class="btn li-btn" onclick="copyBox('li-comment', this)">Copy comment</button>
<p style="margin:1.2rem 0 0.2rem;"><strong>Not quite right? Tell me what to change</strong></p>
<textarea id="li-feedback" rows="3" placeholder="e.g. Punchier hook, shorter, lead with the pricing change, less formal"></textarea>
<button class="btn li-btn" onclick="redoLinkedIn('{e(d.get('post_file', ''))}')">Rewrite with my comments</button>
</div>
"""



def _ics(day_iso, offset, n, title):
    """A one-event calendar file (09:00 local, 15-minute alert) that iOS offers to add to Calendar."""
    from datetime import date, timedelta
    try:
        d = date.fromisoformat(day_iso) + timedelta(days=offset)
    except Exception:
        return ""
    stamp = d.strftime("%Y%m%d")
    return "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//imetrobert blog//EN", "BEGIN:VEVENT",
        f"UID:linkedin-{day_iso}-{n}@imetrobert.com", f"DTSTAMP:{stamp}T090000",
        f"DTSTART:{stamp}T090000", f"DTEND:{stamp}T091500",
        f"SUMMARY:Post LinkedIn follow-up {n}: {title[:60]}",
        "DESCRIPTION:Open https://www.imetrobert.com/blog/staging/preview.html and copy follow-up post " + str(n) + ".",
        "BEGIN:VALARM", "TRIGGER:-PT0M", "ACTION:DISPLAY", "DESCRIPTION:Post the LinkedIn follow-up", "END:VALARM",
        "END:VEVENT", "END:VCALENDAR", ""])


def _box(id_, text, rows):
    return f'<textarea id="{id_}" rows="{rows}" readonly>{_html.escape(text)}</textarea><button class="btn li-btn" onclick="copyBox(\'{id_}\', this)">Copy</button>'


def promo_card(p):
    e = _html.escape
    out = [f'<div class="card pk" id="pk-card" data-gen="{e(p.get("generated_at", ""))}"><h2>More promotion for this issue</h2>'
           '<small>Hook options for the main post, a French version, and three follow-up posts over the next weeks. Each follow-up links to the matching page on the Business site.</small>']
    out.append('<h3>Other opening lines for the main post</h3><small>Replace the first line of the post above with one of these.</small>')
    for i, h in enumerate(p.get("hooks", []), 1):
        out.append(_box(f"pk-h{i}", h, 2))
    fr = p.get("french") or {}
    if fr:
        out.append('<h3>French version (Quebec)</h3>' + _box("pk-fr", fr.get("post", ""), 12)
                   + '<p style="margin:0.8rem 0 0;"><strong>French first comment (with the link)</strong></p>' + _box("pk-frc", fr.get("first_comment", ""), 4))
    for n, d in enumerate(p.get("drip", []), 1):
        ics = _ics(p.get("published", ""), d.get("day", 0), n, p.get("title", ""))
        rem = f'<button class="btn li-btn" data-ics="{e(ics)}" onclick="addReminder(this)">Add reminder to my calendar</button>' if ics else ""
        out.append(f'<h3>Follow-up {n}: post around day {d.get("day")} after publishing</h3>'
                   + _box(f"pk-p{n}", d.get("post", ""), 10)
                   + '<p style="margin:0.8rem 0 0;"><strong>First comment (with the link)</strong></p>' + _box(f"pk-c{n}", d.get("comment", ""), 4) + rem)
    out.append(f'<p style="margin-top:1.4rem;"><button class="btn li-btn" onclick="buildPromo(\'{e(p.get("post_file", ""))}\')">Redo all of this</button></p></div>')
    return "\n".join(out)


def promo_missing_card(filename):
    e = _html.escape
    return (f'<div class="card pk"><h2>More promotion for this issue</h2><small>Hook options, a French version and three follow-up posts with calendar reminders. Takes about 3 minutes to build.</small><br>'
            f'<button class="btn li-btn" onclick="buildPromo(\'{e(filename)}\')">Build the promo kit</button></div>')


def reply_card(r, filename):
    e = _html.escape
    reps = (r or {}).get("replies", ["", "", ""])
    boxes = "".join(f'<p style="margin:0.8rem 0 0;"><strong>Option {i}</strong></p>' + _box(f"rp-{i}", reps[i - 1] if i <= len(reps) else "", 3) for i in (1, 2, 3))
    return f"""<div class="card rp" id="rp-card" data-gen="{e((r or {}).get('generated_at', ''))}"><h2>Reply to a comment</h2>
<small>Paste a comment someone left on your LinkedIn post. You get three reply options in your voice.</small>
<textarea id="rp-comment" rows="3" placeholder="Paste their comment here" style="background:#fff;">{e((r or {}).get('comment', ''))}</textarea>
<button class="btn li-btn" onclick="askReply('{e(filename)}')">Draft replies</button>
{boxes}</div>
"""

def build_html(next_date, latest=None, linkedin=None, promo=None, reply=None):
    head = _HEAD % {"title": "No post pending", "style": _STYLE}
    body = f"""<h1>Nothing pending review right now</h1>
<p>There's no draft waiting for approval at the moment.</p>
<p>The next draft generates automatically on <strong>{next_date}</strong> and will appear here for review.</p>
<a href="https://www.imetrobert.com/blog/" class="btn">View the live blog</a>
<br><a href="/blog/staging/health.html" class="btn" style="background:#0f172a;">Pipeline health and run log</a>
"""
    if linkedin:
        body += linkedin_card(linkedin)
        body += promo_card(promo) if promo else promo_missing_card(linkedin.get("post_file", ""))
        body += reply_card(reply, linkedin.get("post_file", ""))
    if latest:
        fn, label = latest
        body += f"""<div class="card"><strong>Found a big fault in the published issue?</strong><br>
Roll back <strong>{label}</strong>: it disappears from the blog, the feed, the sitemap and the AI summaries, and any shared link goes to the blog home. You then get a button to rerun the same month.<br>
<button id="rb-open" class="btn warn" onclick="document.getElementById('rb-confirm').style.display='block'; this.style.display='none'">Roll back {label}</button>
<div id="rb-confirm" style="display:none; margin-top:1rem; padding:0.9rem; border:2px solid #b45309; border-radius:10px; background:#fffbeb;">
<strong>Are you sure?</strong><br>
The <strong>{label}</strong> issue will disappear from your blog right away. Anyone opening a shared link will land on the blog home. The review page will then open again so you can regenerate this issue.<br>
<button class="btn warn" onclick="run('rollback-blog.yml', {{post_filename: '{fn}'}}, 'Rollback started. Refresh this page in about two minutes.')">Yes, roll back {label}</button>
<button class="btn" style="background:#64748b;" onclick="document.getElementById('rb-confirm').style.display='none'; document.getElementById('rb-open').style.display='inline-block'">Cancel</button>
</div>
</div>
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
        latest = latest_issue()
        li = None
        try:
            with open("blog/staging/linkedin.json", encoding="utf-8") as f:
                li = json.load(f)
            if not latest or li.get("post_file") != latest[0]:
                li = None                      # a draft for an older issue is not shown
        except Exception:
            li = None
        promo = reply = None
        for name in ("promo", "reply"):
            try:
                with open(f"blog/staging/{name}.json", encoding="utf-8") as f:
                    d = json.load(f)
                if name == "promo" and li and d.get("post_file") == li.get("post_file"):
                    promo = d
                if name == "reply":
                    reply = d
            except Exception:
                pass
        html = build_html(next_generation_date(), latest, li, promo, reply)
    with open("blog/staging/preview.html", "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    write_page()
    print(f"Wrote 'nothing pending' placeholder - next generation: {next_generation_date()}")
