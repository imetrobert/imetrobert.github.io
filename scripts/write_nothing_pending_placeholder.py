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


def build_html(next_date):
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>No post pending — Robert Simon</title>
<meta name="robots" content="noindex, nofollow">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 560px; margin: 5rem auto; padding: 0 1.5rem; line-height: 1.7; color: #1e293b; text-align: center; }}
  h1 {{ color: #2563eb; font-size: 1.4rem; }}
  a.btn {{ display: inline-block; margin-top: 1.5rem; background: linear-gradient(135deg, #2563eb, #06b6d4); color: white; text-decoration: none; padding: 0.7rem 1.5rem; border-radius: 25px; font-weight: 600; font-size: 0.9rem; }}
</style></head>
<body>
<h1>✅ Nothing pending review right now</h1>
<p>There's no draft waiting for approval at the moment.</p>
<p>The next draft generates automatically on <strong>{next_date}</strong> and will appear here for review.</p>
<a href="https://www.imetrobert.com/blog/" class="btn">View the live blog →</a>
</body></html>
"""


if __name__ == "__main__":
    os.makedirs("blog/staging", exist_ok=True)
    next_date = next_generation_date()
    with open("blog/staging/preview.html", "w", encoding="utf-8") as f:
        f.write(build_html(next_date))
    print(f"Wrote 'nothing pending' placeholder — next generation: {next_date}")
