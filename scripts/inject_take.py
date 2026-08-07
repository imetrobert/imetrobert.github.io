"""
inject_take.py
Replaces the "From Robert's Desk" body in a staged post with text typed in the
preview page, so the one section that claims to be Robert's own voice can
actually be his.

The section was called "Robert's Take" and ran two or three sentences; it is now
the signature section of the issue at 300-450 words. The CSS class names did not
change with the rename, so this file still finds the block through
.roberts-header / .roberts-body — see the note in renderer._build_roberts_desk.

Called by approve-blog.yml with the text the reviewer typed. It rewrites the
staging file in place BEFORE promotion, so the published post and latest.html
both carry it — the promotion step is a byte copy and would otherwise ship
whatever the model wrote.

Doing nothing is always safe: no text, or a file that does not look like it has
the section, leaves the draft exactly as it was.

    python3 scripts/inject_take.py <html_path> "<take text>"
"""

import html as H
import re
import sys

# Matches whichever of the two states the renderer produced: the placeholder
# box when the model wrote nothing usable, or the drafted section itself.
#
# The paragraph branch repeats. The Desk is now several paragraphs, and matching
# only the first one would leave the model's remaining paragraphs sitting
# underneath the reviewer's replacement — publishing both versions, under
# Robert's byline, with no visible error.
BODY_RE = re.compile(
    r'(<div class="roberts-header">.*?</div>\s*</div>\s*)'      # keep the byline block
    r'(?:<div class="roberts-placeholder">.*?</div>'            # ...then either the placeholder
    r'|(?:<p class="roberts-body">.*?</p>\s*)+)',               # ...or every drafted paragraph
    re.S,
)


def clean(text):
    """Plain prose only. This lands inside a <p>, and the text arrives from a
    web form, so any markup in it would be markup in the published page."""
    t = re.sub(r"<[^>]+>", "", text or "")
    t = re.sub(r"\*\*(.*?)\*\*", r"\1", t)
    t = re.sub(r"\*(.*?)\*", r"\1", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return t


def to_html(text):
    """Blank lines become paragraphs, matching what the renderer emits.

    No curly quotes. Quotation marks framed the old two-sentence take as an
    aside, which is wrong for a 400-word essay that is the centrepiece of the
    issue — and a typed take has to look identical to a generated one, so the
    two must agree.
    """
    paras = [p.strip().replace("\n", " ") for p in text.split("\n\n") if p.strip()]
    if not paras:
        return ""
    return "".join(
        f'<p class="roberts-body">{H.escape(p, quote=False)}</p>' for p in paras
    )


def inject(path, text):
    text = clean(text)
    if not text:
        print("  No take supplied — leaving the draft's own text in place.")
        return False
    if len(text) < 20:
        print(f"  Take is only {len(text)} characters — too short to be meant seriously; ignoring.")
        return False

    with open(path, encoding="utf-8") as f:
        src = f.read()

    if not BODY_RE.search(src):
        print("  Could not locate the From Robert's Desk block — leaving the file untouched.")
        return False

    body = to_html(text)
    updated = BODY_RE.sub(lambda m: m.group(1) + body, src, count=1)

    if updated == src:
        print("  Nothing changed.")
        return False

    with open(path, "w", encoding="utf-8") as f:
        f.write(updated)
    words = len(text.split())
    print(f"  From Robert's Desk replaced with the reviewer's own text ({words} words).")
    if words < 200:
        print(f"  NOTE: {words} words is short for this section — it is meant to run 300-450.")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("usage: inject_take.py <html_path> <text>")
        sys.exit(0)                      # never fail the publish over this
    try:
        inject(sys.argv[1], sys.argv[2])
    except Exception as e:
        print(f"  Take injection skipped ({e})")
