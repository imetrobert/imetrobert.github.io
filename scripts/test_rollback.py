#!/usr/bin/env python3
"""Offline tests for scripts/rollback_post.py (no network, no secrets)."""
import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
import rollback_post as rb

fails = []
def check(name, ok):
    print(("ok   " if ok else "FAIL ") + name)
    if not ok: fails.append(name)

# 1. survey undo: an added wave is removed, a replaced wave is restored
w = lambda lab, n: {"label": lab, "date": "2026-01-01", "n": n}
now = {"waves": [w("W1", 10), w("W2", 20)]}
waves, touched = rb.changed_waves(now, {"waves": [w("W1", 10)]}, {"waves": [w("W1", 10), w("W2", 20)]})
check("added wave removed", [x["label"] for x in waves] == ["W1"] and touched == ["W2"])
waves, _ = rb.changed_waves({"waves": [w("W1", 99)]}, {"waves": [w("W1", 10)]}, {"waves": [w("W1", 99)]})
check("replaced wave restored", waves == [w("W1", 10)])
waves, touched = rb.changed_waves(now, {"waves": now["waves"]}, {"waves": now["waves"]})
check("untouched survey stays", len(waves) == 2 and touched == [])

# 2. stub is recognised as a stub (so index/sitemap/feed skip it)
d = tempfile.mkdtemp()
p = os.path.join(d, "x.html")
open(p, "w").write(rb.stub_html("December 2026"))
check("stub detected", rb.is_stub(p))

# 3. refusals leave everything untouched
cwd = os.getcwd(); os.chdir(tempfile.mkdtemp())
os.makedirs("blog/posts"); os.makedirs("blog/staging")
page = "<html><body><h1>AI Insights for {m} 2026</h1></body></html>"
for f, m in (("2026-10-31-a.html", "November"), ("2026-11-30-b.html", "December")):
    open("blog/posts/" + f, "w").write(page.format(m=m))
def refuses(fn):
    try: rb.rollback(fn); return False
    except rb.RollbackError: return True
check("refuses an older issue", refuses("2026-10-31-a.html"))
open("blog/staging/draft.html", "w").write("x")
check("refuses while a draft is pending", refuses("2026-11-30-b.html"))
os.remove("blog/staging/draft.html")
open("blog/posts/2026-10-31-a.html", "w").write(rb.stub_html("x"))
check("refuses when no earlier issue remains", refuses("2026-11-30-b.html"))
os.chdir(cwd)

print("\nALL PASSED" if not fails else f"\n{len(fails)} FAILED")
sys.exit(1 if fails else 0)
