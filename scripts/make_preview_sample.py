"""
make_preview_sample.py
Writes blog/staging/preview-sample.html — a look-only copy of the review screen.

The real preview page only exists between generation and approval, which is a
few minutes once a month. That makes the review UI almost impossible to try
out, and it is the one screen that has to work on a phone.

This produces the same screen, wired to be inert:

  * the workflow dispatcher is replaced, so nothing can reach GitHub even if a
    control is somehow triggered;
  * Approve, Regenerate and Discard are disabled outright;
  * the preview frame shows the newest PUBLISHED post instead of a staging file,
    so there is something real to look at.

Everything you would actually practise stays live: the Robert's Take box with
its word count and autosave, the share-link copy button, and the survey form.

It writes to a DIFFERENT filename than preview.html, so the monthly pipeline —
which writes and clears preview.html — is untouched. The file lives under
/blog/staging/, which robots.txt disallows and which carries noindex, so it is
not indexable.

    python3 scripts/make_preview_sample.py
"""

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "blog", "staging", "preview-sample.html")

BANNER = """
<div style="background:#fef3c7;border-bottom:2px solid #f59e0b;color:#78350f;
     padding:0.75rem 1rem;font:600 0.85rem/1.5 Inter,system-ui,sans-serif;text-align:center;">
  Sample of the review screen &mdash; nothing here can publish.
  Approve, Regenerate and Discard are disabled, and the preview frame shows the
  newest published post. Try the take box, the share link and the survey form.
</div>
"""

NEUTER = """
<script>
  // Belt and braces. Disabling the buttons stops the normal path; replacing the
  // dispatcher means even an unexpected one cannot reach the GitHub API.
  window.triggerWorkflow = async function () {
    alert("This is the sample screen — actions are disabled here.");
    return null;
  };
  document.addEventListener("DOMContentLoaded", function () {
    ["approve-btn", "regenerate-btn", "discard-btn"].forEach(function (id) {
      var b = document.getElementById(id);
      if (!b) return;
      b.disabled = true;
      b.style.opacity = "0.45";
      b.style.cursor = "not-allowed";
      b.title = "Disabled on the sample screen";
    });
  });
</script>
"""


def newest_published():
    posts_dir = os.path.join(ROOT, "blog", "posts")
    names = sorted(
        f for f in os.listdir(posts_dir)
        if f.endswith(".html") and f != "latest.html" and "{" not in f
    )
    return names[-1] if names else "latest.html"


def main():
    spec = importlib.util.spec_from_file_location(
        "gp", os.path.join(HERE, "generate-preview-page.py"))
    gp = importlib.util.module_from_spec(spec)
    sys.path.insert(0, HERE)
    spec.loader.exec_module(gp)

    sample_name = newest_published()
    html = gp.build_preview_html(sample_name, "August 2026", "sample")

    # Point every staging reference at a real published post. There are two:
    # the preview frame, and the topbar's "Open Full Post" button. Missing the
    # second would leave one control on the sample opening a 404.
    html = html.replace("/blog/staging/${STAGING_FILE}",
                        "/blog/posts/" + sample_name)
    html = html.replace("<body>", "<body>" + BANNER, 1)
    html = html.replace("</body>", NEUTER + "</body>", 1)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Wrote {os.path.relpath(OUT, ROOT)}")
    print(f"  preview frame shows: blog/posts/{sample_name}")
    print("  https://www.imetrobert.com/blog/staging/preview-sample.html")


if __name__ == "__main__":
    main()
