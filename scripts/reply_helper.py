#!/usr/bin/env python3
"""Reply helper: Robert pastes a comment someone left on his LinkedIn post, gets three reply options.

Usage: python3 scripts/reply_helper.py "<the comment>" [post_filename]   (run from the repo root)
Writes blog/staging/reply.json {comment, replies[3], generated_at}; the nothing-pending page shows it.
Replies are plain text, short, first person, never sell, never invent facts about Robert's own clients or data.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from promo_kit import OWN_DATA, _call_model, _extract  # noqa: E402

OUT = "blog/staging/reply.json"


def build_prompt(comment, context):
    return f"""You draft LinkedIn replies for Robert Simon, an independent AI consultant in Montreal (AI with Robert for Business). Someone commented on his post. Write THREE different reply options in his voice: warm, direct, practical, one to three short sentences each, under 400 characters. Option 1 is brief and gracious. Option 2 adds one useful point or example drawn from the issue below. Option 3 ends with a short question that keeps the conversation going. Plain text, no emoji, no hashtags, no links. Never sell or mention his services or prices. Never claim clients, data or results of his own. If the comment is a disagreement, acknowledge the point honestly instead of being defensive. If it is spam or abusive, reply with exactly NO REPLY on each option.

THE COMMENT:
{comment}

CONTEXT (the issue he posted about; use only facts from it):
{context}

OUTPUT FORMAT, exactly, labels on their own line ending with a colon:
REPLY 1:
<text>
REPLY 2:
<text>
REPLY 3:
<text>"""


def parse(raw):
    parts = _extract(raw, {"REPLY 1", "REPLY 2", "REPLY 3"})
    if len(parts) < 3:
        raise ValueError("reply did not contain REPLY 1, 2 and 3")
    out = []
    for n in (1, 2, 3):
        t = re.sub(r"\*\*|__", "", parts[f"REPLY {n}"]).strip()
        if t.upper() != "NO REPLY":
            if not 10 <= len(t) <= 450:
                raise ValueError(f"reply {n} is {len(t)} characters (allowed 10 to 450)")
            if "http" in t.lower() or OWN_DATA.search(t):
                raise ValueError(f"reply {n} has a link or claims Robert's own data")
        out.append(t)
    return out


def generate(comment, filename="", call=None):
    call = call or _call_model
    comment = comment.strip()[:1500]
    if len(comment) < 3:
        raise ValueError("no comment to answer")
    context = ""
    if filename and os.path.isfile(os.path.join("blog/posts", filename)):
        from linkedin_post import issue_text
        title, text = issue_text(os.path.join("blog/posts", filename))
        context = f"{title}\n{text[:3500]}"
    prompt = build_prompt(comment, context or "(none)")
    err = None
    for _ in range(3):
        raw = call(prompt)
        try:
            replies = parse(raw)
            break
        except ValueError as e:
            err = e
            prompt += f"\n\nYour last reply was rejected: {e}. Follow the rules and format exactly."
    else:
        raise err
    data = {"comment": comment, "replies": replies,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.write("\n")
    return data


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    try:
        import runlog
    except Exception:
        runlog = None
    try:
        generate(argv[0], os.path.basename(argv[1]) if len(argv) > 1 else "")
        from write_nothing_pending_placeholder import write_page
        write_page()
        if runlog:
            runlog.ok("reply", "Reply options ready")
        return 0
    except Exception as e:
        print(f"Reply helper failed: {e}")
        if runlog:
            try:
                runlog.fail("reply", "PROMO_REJECTED" if isinstance(e, ValueError) else runlog.classify(e), detail=str(e))
            except Exception:
                pass
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
