#!/usr/bin/env python3
"""
send-notification.py
Sends an email notification when a new blog post is ready for review.
Uses Resend.com (free, permanent tier — 100 emails/day, no expiry).
Falls back to GitHub Actions Step Summary if RESEND_API_KEY is not set.
"""

import os
import requests
from datetime import datetime


def send_resend(api_key: str, to_email: str, subject: str, html_body: str) -> bool:
    """Send via Resend API — https://resend.com"""
    url = "https://api.resend.com/emails"
    payload = {
        "from": "Robert Simon Blog <noreply@imetrobert.com>",
        "to": [to_email],
        "subject": subject,
        "html": html_body
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        if r.status_code in (200, 201):
            print(f"✅ Email sent via Resend to {to_email}")
            return True
        else:
            print(f"⚠️  Resend returned {r.status_code}: {r.text[:300]}")
            return False
    except Exception as e:
        print(f"⚠️  Resend error: {e}")
        return False


def build_email_html(month_year: str, preview_url: str, staging_filename: str, github_repo: str) -> str:
    """Build the HTML email body."""
    actions_url = f"https://github.com/{github_repo}/actions"
    now = datetime.now().strftime("%B %d, %Y at %I:%M %p UTC")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Blog Review Ready — {month_year}</title>
</head>
<body style="margin:0;padding:0;background:#f0f4ff;font-family:Inter,-apple-system,sans-serif;">

<table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4ff;padding:40px 20px;">
  <tr><td align="center">
    <table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:20px;overflow:hidden;box-shadow:0 8px 32px rgba(0,0,0,0.10);">

      <!-- Header -->
      <tr>
        <td style="background:linear-gradient(135deg,#2563eb 0%,#1a7fb5 50%,#06b6d4 100%);padding:40px 40px 32px;text-align:center;">
          <div style="display:inline-block;background:rgba(255,255,255,0.18);border:1px solid rgba(255,255,255,0.3);padding:4px 14px;border-radius:20px;font-size:11px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:white;margin-bottom:14px;">📝 Monthly Blog Ready</div>
          <h1 style="color:white;font-size:26px;font-weight:800;margin:0 0 8px;letter-spacing:-0.02em;">Your {month_year} Post<br>is Ready to Review</h1>
          <p style="color:rgba(255,255,255,0.85);font-size:14px;margin:0;">Generated: {now}</p>
        </td>
      </tr>

      <!-- Body -->
      <tr>
        <td style="padding:36px 40px;">

          <p style="font-size:15px;color:#475569;line-height:1.7;margin:0 0 24px;">
            Your monthly AI insights post for <strong style="color:#0f172a;">{month_year}</strong> has been generated and is waiting in staging. Review it, regenerate with a prompt if needed, then approve to publish — all from the preview page.
          </p>

          <!-- CTA -->
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td align="center" style="padding:8px 0 28px;">
                <a href="{preview_url}"
                   style="display:inline-block;background:linear-gradient(135deg,#2563eb,#06b6d4);color:white;text-decoration:none;padding:14px 32px;border-radius:12px;font-size:15px;font-weight:700;letter-spacing:-0.01em;box-shadow:0 4px 16px rgba(37,99,235,0.3);">
                  👁 Review &amp; Approve Post →
                </a>
              </td>
            </tr>
          </table>

          <!-- What you can do -->
          <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;border-radius:12px;margin-bottom:24px;">
            <tr>
              <td style="padding:20px 24px;">
                <p style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#94a3b8;margin:0 0 12px;">On the preview page you can</p>
                <table cellpadding="0" cellspacing="0">
                  <tr><td style="padding:4px 0;font-size:14px;color:#475569;">✅ &nbsp;Read the full post in an iframe</td></tr>
                  <tr><td style="padding:4px 0;font-size:14px;color:#475569;">🔄 &nbsp;Regenerate with a custom Gemini prompt</td></tr>
                  <tr><td style="padding:4px 0;font-size:14px;color:#475569;">📤 &nbsp;Approve &amp; publish in one click</td></tr>
                </table>
              </td>
            </tr>
          </table>

          <!-- File info -->
          <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e2e8f0;border-radius:10px;margin-bottom:28px;">
            <tr style="border-bottom:1px solid #e2e8f0;">
              <td style="padding:10px 16px;font-size:12px;color:#94a3b8;font-weight:600;width:120px;">FILE</td>
              <td style="padding:10px 16px;font-size:12px;color:#0f172a;font-family:monospace;">{staging_filename}</td>
            </tr>
            <tr style="border-bottom:1px solid #e2e8f0;">
              <td style="padding:10px 16px;font-size:12px;color:#94a3b8;font-weight:600;">PREVIEW</td>
              <td style="padding:10px 16px;font-size:12px;"><a href="{preview_url}" style="color:#2563eb;">{preview_url}</a></td>
            </tr>
            <tr>
              <td style="padding:10px 16px;font-size:12px;color:#94a3b8;font-weight:600;">ACTIONS</td>
              <td style="padding:10px 16px;font-size:12px;"><a href="{actions_url}" style="color:#2563eb;">GitHub Actions →</a></td>
            </tr>
          </table>

          <!-- Reminder -->
          <table width="100%" cellpadding="0" cellspacing="0" style="background:#fef3c7;border:1px solid #fde68a;border-radius:10px;margin-bottom:8px;">
            <tr>
              <td style="padding:14px 18px;font-size:13px;color:#92400e;line-height:1.6;">
                <strong>Don't forget:</strong> Add your personal "Robert's Take" paragraph before approving — it's the E-E-A-T signal that makes the post yours. Use the regenerate prompt on the preview page to include it.
              </td>
            </tr>
          </table>

        </td>
      </tr>

      <!-- Footer -->
      <tr>
        <td style="background:#f8fafc;border-top:1px solid #e2e8f0;padding:20px 40px;text-align:center;">
          <p style="font-size:12px;color:#94a3b8;margin:0;">
            imetrobert.com &nbsp;·&nbsp; Monthly AI Insights Blog &nbsp;·&nbsp; Montreal, QC
          </p>
        </td>
      </tr>

    </table>
  </td></tr>
</table>

</body>
</html>"""


def main():
    resend_key     = os.environ.get("RESEND_API_KEY", "")
    to_email       = os.environ.get("NOTIFICATION_EMAIL", "")
    month_year     = os.environ.get("MONTH_YEAR", "")
    preview_url    = os.environ.get("PREVIEW_URL", "https://www.imetrobert.com/blog/staging/preview.html")
    staging_file   = os.environ.get("STAGING_FILENAME", "")
    github_repo    = os.environ.get("GITHUB_REPO", "imetrobert/imetrobert.github.io")

    print(f"Month:   {month_year}")
    print(f"Preview: {preview_url}")
    print(f"File:    {staging_file}")

    subject = f"✅ Review Ready: AI Insights — {month_year}"
    html    = build_email_html(month_year, preview_url, staging_file, github_repo)

    # ── Try Resend ─────────────────────────────────────────────────
    if resend_key and to_email:
        success = send_resend(resend_key, to_email, subject, html)
        if success:
            return
        print("Resend failed — falling back to GitHub Step Summary.")
    else:
        print("RESEND_API_KEY or NOTIFICATION_EMAIL not set — skipping email.")
        print("Add these as GitHub repo secrets to enable email notifications.")

    # ── GitHub Actions Step Summary fallback ───────────────────────
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "")
    if summary_path:
        with open(summary_path, "a") as f:
            f.write(f"""## 📝 Blog Ready for Review — {month_year}

| Item | Detail |
|------|--------|
| Month | {month_year} |
| Staging file | `{staging_file}` |
| Preview URL | [{preview_url}]({preview_url}) |

### Next steps
1. Visit [{preview_url}]({preview_url}) to review
2. Optionally regenerate with a custom prompt from the preview UI
3. Click **Approve & Publish** on the preview page

> 💡 Add your personal "Robert's Take" paragraph before approving.
""")
        print("GitHub Step Summary updated as fallback.")


if __name__ == "__main__":
    main()
