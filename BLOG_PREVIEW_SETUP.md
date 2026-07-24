# Blog Preview & Approval System

## How it works

```
End of month
    │
    ▼
monthly-blog.yml runs
    │
    ├── Generates post → blog/staging/{date}-{slug}.html
    ├── Generates preview UI → blog/staging/preview.html
    ├── Sends you an email with a link (via Resend)
    └── Pushes to GitHub → GitHub Pages serves staging/

You visit https://www.imetrobert.com/blog/staging/preview.html
    │
    ├── Read the post in the iframe
    ├── [Optional] Enter a prompt → "Regenerate Post"
    │       └── Triggers regenerate-blog.yml
    │           └── New post in staging + preview.html updates
    └── Click "Approve & Publish"
            └── Triggers approve-blog.yml
                ├── Moves file → blog/posts/
                ├── Updates latest.html
                ├── Regenerates sitemap.xml
                ├── Updates blog/index.html
                └── Pings Google
```

---

## One-time setup

### 1. GitHub Secrets to add

Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**

| Secret name | Value | Required? |
|---|---|---|
| `GEMINI_API_KEY` | Your Gemini API key | ✅ Already set |
| `RESEND_API_KEY` | Your Resend API key (starts with `re_`) | Optional but recommended |
| `NOTIFICATION_EMAIL` | Your email address for notifications | Optional but recommended |

**If you skip Resend:** You'll still get a notification link in the GitHub Actions Step Summary when the workflow runs. Go to Actions → the workflow run → Summary to find the preview URL.

---

### 2. Set up Resend (free, permanent — takes 5 minutes)

Resend has a permanent free tier (100 emails/day, no expiry, no credit card).

1. Go to **resend.com** and sign up (use GitHub login for speed)
2. In the dashboard, go to **API Keys → Create API Key**
   - Name: `Blog Notifications`
   - Permission: **Sending access** only
   - Click **Add** — copy the key (starts with `re_`)
3. Go to **Domains → Add Domain**
   - Enter `imetrobert.com`
   - Add the DNS records it shows you to your domain registrar
   - Click **Verify** (takes a few minutes to propagate)
4. Add two secrets to your GitHub repo:
   - `RESEND_API_KEY` → your `re_` key
   - `NOTIFICATION_EMAIL` → your email address

> **Tip:** While waiting for domain verification, you can use Resend's sandbox by sending to your own Resend-verified email. Just update `NOTIFICATION_EMAIL` to the email you signed up with.

---

### 3. Create a GitHub PAT for the preview UI

The preview page needs a token to trigger workflows on your behalf from your browser.

1. Go to: **github.com/settings/tokens/new**
2. Name it: `Blog Preview Approval`
3. Select scope: ✅ **workflow**
4. Set expiration to **No expiration** (or 1 year)
5. Click **Generate token** — copy it (starts with `ghp_`)
6. When you first visit the preview page, paste it into the **GitHub Access Token** field and click **Save**
7. It's stored in your browser's localStorage — you only do this once per device

---

## Files to add to your repo

```
.github/workflows/
├── monthly-blog.yml          ← replace your existing one
├── approve-blog.yml          ← new
└── regenerate-blog.yml       ← new

scripts/
├── generate-preview-page.py  ← new
└── send-notification.py      ← new
```

Everything else in your repo stays the same.

---

## Usage

### Automatic (monthly)
`monthly-blog.yml` runs daily at 9am UTC and only generates on the last day of the month. You'll get an email with a direct link to the preview page.

### Manual trigger
Go to **Actions → Generate Monthly AI Blog Post → Run workflow**
- Optional: enter a custom topic
- Check **Force run** to bypass the date check (good for testing the whole flow end-to-end)

### Reviewing a post
1. Visit `https://www.imetrobert.com/blog/staging/preview.html`
2. Read the post in the iframe on the right
3. If you want changes, type a prompt in the sidebar and click **Regenerate Post**
   - Regenerating almost always creates a new staging filename (it's date-stamped), so **Approve & Publish** and **Regenerate Post** lock automatically the moment you trigger a regeneration — the sidebar shows an amber banner explaining why
   - The page polls every 15s for up to 10 minutes and **reloads itself automatically** once the new version is live, which re-establishes the correct filename and unlocks the buttons
   - You can dismiss the "queued" dialog — it keeps watching and reloading in the background regardless
   - If it times out (10+ min), the banner tells you to check the Actions tab, then reload manually — it stays locked until you do, on purpose, so you can't approve a filename that no longer exists
4. When satisfied, click **Approve & Publish**
   - A confirmation dialog appears showing the exact filename about to be published — check it matches what you were just reviewing
   - Confirm → workflow triggers → post is live in ~1 minute

### Adding your "Robert's Take"
Include it in the regenerate prompt. For example:

> Add my personal take at the end: "The pattern I keep pointing out to clients this month is that the orgs winning with AI aren't the ones with the biggest budgets — they're the ones that picked one workflow, nailed it, and are now scaling that playbook. That's the lesson from what we're seeing at RBC and Shopify right now."

---

## Troubleshooting

**Email not arriving**
- Check the GitHub Actions run summary for the preview URL as a fallback
- In Resend dashboard → Logs, you can see if the send attempt was made and why it may have failed
- Make sure your domain is verified in Resend (Settings → Domains)

**"Workflow not found" error in preview UI**
- Make sure your PAT has `workflow` scope
- Confirm all three workflow `.yml` files are committed to the `main` branch

**Preview page blank or showing old content**
- GitHub Pages takes 2-3 minutes to rebuild after a push
- Check the Actions tab to confirm the generation workflow completed successfully

**Regeneration auto-refresh not triggering**
- It polls every 15 seconds for up to 10 minutes, checking for the "🔄 Regenerated with custom prompt" badge on the freshly-pushed `preview.html`
- On success it reloads the whole page automatically (not just the preview frame) — this is deliberate, since regenerating renames the staging file and only a full reload picks up the new name
- If it times out, the sidebar banner stays up with a link to the Actions tab — check there first (it may have actually failed), then use the banner's "Reload page now" button once you've confirmed a new version exists

**Approve & Regenerate buttons are greyed out**
- This is the lock banner, not a bug — it means a regeneration is in flight (or timed out) and this page's known filename may be stale
- Wait for the automatic reload, or check the Actions tab and use "Reload page now" in the banner once you've confirmed the run finished

**Approve button does nothing**
- Check your PAT is saved (the "Token saved" message should appear in the sidebar)
- Make sure the PAT hasn't expired
- A toast now reports network errors and specific GitHub API error codes (401/403/404) instead of failing silently — read it for the actual cause
- Check browser console for any CORS errors as a last resort
