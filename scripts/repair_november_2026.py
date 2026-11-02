#!/usr/bin/env python3
"""
repair_november_2026.py  (run once, from the repo root; safe to run again)

On 2026-11-01 the November issue was swapped by hand: the pipeline-published post
was deleted and a different one uploaded, and blog/index.html was edited by hand.
Everything the approve workflow normally does around a publish was skipped, so:

  * the featured card on the index showed the new post, but its LinkedIn / Email /
    Copy link / Share buttons still pointed at the deleted one
  * latest.html was still a copy of the deleted post
  * sitemap.xml, feed.xml, llms.txt and the adoption page still listed the deleted URL
  * the uploaded post was labelled "Issue #16, December 2026, covering November"
    (it was generated on Nov 1 as if November were the month being covered), which
    would collide with the real December issue next month
  * the stale October 31 version of the November issue was still live and indexed
  * blog/staging still held a copy, and model-config still listed a failed model

This script puts all of that back into the state the approve workflow would have
left, then checks its own work and exits non-zero (so nothing is committed) if any
reference to a deleted page survives.
"""
import json
import os
import re
import shutil
import subprocess
import sys

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)
sys.path.insert(0, os.path.join(os.getcwd(), "scripts"))

BASE = "https://www.imetrobert.com"
POSTS = "blog/posts"
NEW = "2026-11-01-ottawa-commits-16b-to-cohere-boosting-canadian-ai-sovereignty.html"
GONE = [   # pages that must no longer be reachable as content or listed anywhere
    "2026-10-31-practical-ai-for-canadian-business-november-2026.html",
    "2026-11-01-openai-cuts-enterprise-ai-costs-by-half-canada-commits-16b-to-cohere.html",
]
NEW_URL = f"{BASE}/blog/posts/{NEW}"

# Ordered: coverage-month phrases first, so the December -> November step below
# cannot be mistaken for one of them.
RELABEL = [
    ("Issue #16",                                        "Issue #15"),
    ("Covering November",                                "Covering October"),
    ("November 2026 AI recap",                           "October 2026 AI recap"),
    ("Canadian businesses in November 2026?",            "Canadian businesses in October 2026?"),
    ("December 2026",                                    "November 2026"),
    ("December%202026",                                  "November%202026"),   # mailto subject
]

STUB = """<!DOCTYPE html>
<html lang="en-CA">
<head>
<meta charset="utf-8">
<meta name="robots" content="noindex, follow">
<meta http-equiv="refresh" content="0; url={url}">
<link rel="canonical" href="{url}">
<title>This issue has moved | Practical AI for Canadian Business</title>
</head>
<body>
<p>This issue has moved. <a href="{url}">Read the November 2026 issue</a>.</p>
</body>
</html>
"""


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def fail(msg):
    print(f"\nFAILED: {msg}")
    sys.exit(1)


def main():
    new_path = os.path.join(POSTS, NEW)
    if not os.path.exists(new_path):
        fail(f"{new_path} is missing; nothing to repair around.")

    # 1. Label the uploaded post as the November issue it is.
    html = read(new_path)
    for old, new in RELABEL:
        n = html.count(old)
        html = html.replace(old, new)
        print(f"  relabel {old!r:46} -> {new!r}  ({n} found)")
    write(new_path, html)

    # 2. latest.html is a byte copy of the newest dated post (as approve-blog does).
    shutil.copyfile(new_path, os.path.join(POSTS, "latest.html"))
    print("  latest.html now mirrors the November issue")

    # 3. Redirect stubs where the replaced pages used to be, so a link already
    #    shared (LinkedIn, email) lands on the real issue instead of a 404.
    for name in GONE:
        write(os.path.join(POSTS, name), STUB.format(url=NEW_URL))
        print(f"  redirect stub written: {name}")

    # 4. Staging: drop the leftover copy and show "nothing pending".
    leftover = os.path.join("blog/staging", NEW)
    if os.path.exists(leftover):
        os.remove(leftover)
        print("  removed leftover blog/staging copy")
    subprocess.run([sys.executable, os.path.join(_here, "write_nothing_pending_placeholder.py")],
                   check=True)

    # 5. Model order back to the models this pipeline has proven on.
    cfg_path = "blog/model-config.json"
    if os.path.exists(cfg_path):
        cfg = json.loads(read(cfg_path))
        cfg["order"] = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"]
        write(cfg_path, json.dumps(cfg, indent=2) + "\n")
        print(f"  model order: {cfg['order']}")

    # 6. Everything the approve workflow regenerates after a publish.
    from blog_index import update_blog_index
    posts = update_blog_index()
    print(f"  index, feed, llms.txt and adoption page rebuilt ({len(posts)} issues)")
    subprocess.run([sys.executable, os.path.join(_here, "regenerate_sitemap.py")], check=True)

    # 7. Check the work. A reference to a deleted page left anywhere is a failure.
    title = re.search(r"<h1>(.*?)</h1>", read(new_path), re.S).group(1).strip()
    problems = []
    for path in ["blog/index.html", "blog/feed.xml", "llms.txt", "sitemap.xml",
                 "blog/canadian-ai-adoption.html", "blog/posts/latest.html", new_path]:
        text = read(path)
        for name in GONE:
            if name.replace(".html", "") in text:
                problems.append(f"{path} still mentions {name}")
    idx = read("blog/index.html")
    feat = re.search(r'<section class="latest-post-section">.*?</section>', idx, re.S)
    if not feat:
        problems.append("index has no featured section")
    else:
        block = feat.group(0)
        urls = re.findall(r"imetrobert\.com(?:%2F|/)blog(?:%2F|/)posts(?:%2F|/)([^\"&?%]+?\.html)", block)
        if not urls or any(u != NEW for u in urls):
            problems.append(f"featured share links do not all point at the new post: {sorted(set(urls))}")
    if "Issue #15" not in read(new_path) or "December 2026" in re.sub(r"December \d+, 2026", "", read(new_path)):
        problems.append("November post still carries December/#16 labels")
    if NEW not in read("sitemap.xml"):
        problems.append("sitemap does not list the new post")
    for name in GONE:
        if name in read("sitemap.xml"):
            problems.append(f"sitemap still lists {name}")
    if problems:
        print("\n".join("  - " + p for p in problems))
        fail("repair did not come out clean; nothing should be committed.")

    print(f"\nOK. Featured: {title!r}")
    print("Previous Issues:")
    for t in re.findall(r'class="older-post-title">(.*?)</div>', idx, re.S)[:4]:
        print("   ", re.sub(r"<[^>]+>", "", t))


if __name__ == "__main__":
    main()
