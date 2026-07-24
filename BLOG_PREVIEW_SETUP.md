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
    └── Pushes to GitHub → GitHub Pages serves staging/

You check in (no notification — see below) at
https://www.imetrobert.com/blog/staging/preview.html
    │
    ├── Read the post in the iframe
    ├── [Optional] Enter a prompt → "Regenerate Post"
    │       └── Triggers regenerate-blog.yml
    │           └── New post in staging + preview.html updates
    ├── Click "Approve & Publish"
    │       └── Triggers approve-blog.yml
    │           ├── Moves file → blog/posts/
    │           ├── Updates latest.html
    │           ├── Regenerates sitemap.xml
    │           ├── Updates blog/index.html
    │           └── Pings Google
    └── Click "Discard"
            └── Triggers discard-blog.yml
                └── Deletes the staging draft — nothing published,
                    preview.html shows "nothing pending" until next run
```

---

## Reliability — what keeps this running unattended

Two failure modes are quiet by nature, so they're specifically guarded against:

**GitHub auto-disables scheduled workflows after 60 days of no repository
activity.** This repo's real activity is monthly at best (one approval), so
a skipped month or two could silently kill `monthly-blog.yml`'s cron
trigger forever — it wouldn't error, it would just stop firing.
`.github/workflows/keepalive.yml` makes a trivial commit on the 1st and
15th of every month purely to keep the repo "active," independent of
whether a post was actually approved that month.

**If generation itself fails** (Gemini quota exhausted, an invalid or
rotated `GEMINI_API_KEY`, a transient network error), nothing would
normally get committed — `blog/staging/preview.html` would just stay
whatever it was after last month's approval, usually deleted. A monthly
check-in would find a blank 404 with no explanation. `monthly-blog.yml` now
has a dedicated `if: failure()` step that pushes a clear failure page to
that same URL instead, explaining the likely cause and how to retry (Force
run from the Actions tab). It's automatically replaced the next time
generation succeeds.

All four workflows (`monthly-blog`, `regenerate-blog`, `approve-blog`,
`keepalive`) share one `concurrency` group so overlapping runs queue
instead of racing on the same `git push`.

---

## No email notifications

Earlier versions of this doc described an email-notification path via Resend
(`RESEND_API_KEY` / `NOTIFICATION_EMAIL` secrets). It was never actually
wired up — `monthly-blog.yml` and `regenerate-blog.yml` never called a
sender, so no email was ever going to arrive regardless of secrets or email
provider. That path has been removed rather than fixed: the workflow runs
in the first few days of the month (last day of the prior month, per the
cron schedule), and you check `blog/staging/preview.html` yourself when
convenient — no notification needed.

If you ever want a fallback pointer without visiting the preview page
directly: the GitHub Actions **Step Summary** for the `monthly-blog.yml` run
always includes the preview URL (Actions → the run → Summary).

If `RESEND_API_KEY` / `NOTIFICATION_EMAIL` secrets still exist in your repo
settings, they're unused now — safe to delete from **Settings → Secrets and
variables → Actions**.

---

## One-time setup

### 1. GitHub Secrets to add

Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**

| Secret name | Value | Required? |
|---|---|---|
| `GEMINI_API_KEY` | Your Gemini API key | ✅ Already set |

---

### 2. Create a GitHub PAT for the preview UI

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
├── regenerate-blog.yml       ← new
└── discard-blog.yml          ← new

scripts/
├── generate-preview-page.py                ← new
└── write_nothing_pending_placeholder.py    ← new
```

Everything else in your repo stays the same.

---

## Usage

### Automatic (monthly)
`monthly-blog.yml` runs daily at 9am UTC and only generates on the last day of the month. No notification is sent — check `blog/staging/preview.html` yourself in the first few days of the following month.

### Manual trigger
Go to **Actions → Generate Monthly AI Blog Post → Run workflow**
- Optional: enter a custom topic
- Check **Force run** to bypass the date check (good for testing the whole flow end-to-end)

### Reviewing a post
1. Visit `https://www.imetrobert.com/blog/staging/preview.html`
2. Read the post in the iframe on the right
3. If you want changes, type a prompt in the sidebar and click **Regenerate Post**
   - Regenerating almost always creates a new staging filename (it's date-stamped), so **Approve & Publish**, **Regenerate Post**, and **Discard** all lock automatically the moment you trigger a regeneration — the sidebar shows an amber banner explaining why
   - The page polls every 15s for up to 10 minutes and **reloads itself automatically** once the new version is live, which re-establishes the correct filename and unlocks the buttons
   - You can dismiss the "queued" dialog — it keeps watching and reloading in the background regardless
   - If it times out (10+ min), the banner tells you to check the Actions tab, then reload manually — it stays locked until you do, on purpose, so you can't approve a filename that no longer exists
4. When satisfied, click **Approve & Publish**
   - A confirmation dialog appears showing the exact filename about to be published — check it matches what you were just reviewing
   - Confirm → workflow triggers → post is live in ~1 minute
5. If the draft isn't worth fixing with a prompt, click **Discard** instead
   - A confirmation dialog names the exact file being deleted — nothing is published, this only removes the staging draft
   - Can't be undone. Next visit to the preview URL shows "nothing pending" until the next automatic (or manually Force-run) generation

### Adding your "Robert's Take"
Include it in the regenerate prompt. For example:

> Add my personal take at the end: "The pattern I keep pointing out to clients this month is that the orgs winning with AI aren't the ones with the biggest budgets — they're the ones that picked one workflow, nailed it, and are now scaling that playbook. That's the lesson from what we're seeing at RBC and Shopify right now."

---

## Troubleshooting

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
