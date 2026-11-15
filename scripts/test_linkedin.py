#!/usr/bin/env python3
"""Offline tests for scripts/linkedin_post.py and its card on the nothing-pending page (stubbed model)."""
import json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import linkedin_post as lp
import write_nothing_pending_placeholder as ph

fails = []
def check(name, ok):
    print(("ok   " if ok else "FAIL ") + name)
    if not ok: fails.append(name)

link = lp.permalink("2026-12-03-x.html")
good = "POST:\n" + ("Most small businesses overpay for AI.\n\nHere is why that matters for you. " * 12) + "\n\nWhat do you pay for today?\n\n#AI #SmallBusiness\nFIRST COMMENT:\nFull issue here:\n" + link
post, comment = lp.parse(good, link)
check("parses post and comment", post.startswith("Most small") and link in comment)
for name, bad in (("rejects wrong format", "just text"),
                  ("rejects link in post", good.replace("Here is why", "see https://x.com Here is why")),
                  ("rejects too short", "POST:\nshort\nFIRST COMMENT:\nhi")):
    try: lp.parse(bad, link); check(name, False)
    except ValueError: check(name, True)

cwd = os.getcwd(); os.chdir(tempfile.mkdtemp())
os.makedirs("blog/posts"); os.makedirs("blog/staging")
open("blog/posts/2026-12-03-x.html", "w").write(
    '<html><body><h1>AI Insights for December 2026</h1><div class="article-content"><p>' + "Plan prices fell. " * 40 + "</p></div></body></html>")
calls = []
def fake(prompt): calls.append(prompt); return good
d = lp.generate("2026-12-03-x.html", call=fake)
check("first draft saved", os.path.exists("blog/staging/linkedin.json") and d["post"])
check("first draft has no revise block", "ROBERT'S COMMENTS" not in calls[0])
d2 = lp.generate("2026-12-03-x.html", "make the hook punchier", call=fake)
check("redraft sends previous post and comments", "make the hook punchier" in calls[1] and "YOUR PREVIOUS DRAFT" in calls[1])
check("comments kept in history", d2["history"] == ["make the hook punchier"])
html = ph.build_html("Dec 31", ("2026-12-03-x.html", "December 2026"), d2)
check("page shows copy buttons and rewrite box", "copyBox('li-post'" in html and "li-feedback" in html and "linkedin-post.yml" in html)
os.chdir(cwd)
print("\nALL PASSED" if not fails else f"\n{len(fails)} FAILED")
sys.exit(1 if fails else 0)
