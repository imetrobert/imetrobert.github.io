# Job Match — setup

A private, login-gated job matcher: it pulls postings from job APIs and company
ATS boards, scores each one against your profile with an LLM, ranks them, explains
why each fits, and drafts a tailored cover letter and CV on demand.

Built to sit alongside your invoicing and ETF apps on the **same Supabase project**
— same login, tables namespaced `job_` so they can't collide.

```
1st of the month (or you click "Refresh now")
    │
    ▼
job-scan.yml runs
    │
    ├── Fetches from Adzuna / Jooble / your ATS company boards
    ├── Normalizes → dedupes (same role across 3 feeds = 1 row)
    ├── Prefilters out obvious misses (wrong level, deal-breakers)
    ├── Scores the rest with Claude or Gemini → score, why it fits, gaps, pitch angle
    └── Writes to Supabase
    │
    ▼
You open jobs.imetrobert.com, sign in, read the ranked list
    │
    └── "Draft cover letter + CV" on anything you like
            └── generate-application edge function → both documents, downloadable
```

---

## Why not LinkedIn and Indeed

Both block automated access and prohibit it in their terms — LinkedIn returns
`403` to anything without a browser session. A scraper would break within weeks
and put your name on a ToS complaint while you're job hunting.

You lose less than it sounds. LinkedIn and Indeed are themselves aggregators
pulling from the same ATS feeds this app reads directly — often getting the
posting *later* than the source. Adzuna and Jooble cover the broad market
legitimately; company boards give you the sharp edge (see step 6).

If you want literal LinkedIn/Indeed-sourced rows, JSearch resells Google-for-Jobs
results as a paid API — add `JSEARCH_RAPIDAPI_KEY` and it turns on. Optional.

---

## One-time setup

Roughly 30 minutes, most of it waiting on signups.

### 1. Create the database tables

Supabase Dashboard → your shared project → **SQL Editor** → paste all of
`supabase/schema.sql` → Run.

Safe to re-run. Everything is `IF NOT EXISTS` / `ON CONFLICT DO NOTHING`, and
the `job_` prefix keeps it clear of your invoicing and `etf_` tables.

### 2. Get the job feed keys

| Service | Cost | Where | Env var |
|---|---|---|---|
| **Adzuna** | Free (~1,000 calls/month) | [developer.adzuna.com](https://developer.adzuna.com/) — instant, self-serve | `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` |
| **Jooble** | Free | [jooble.org/api/about](https://jooble.org/api/about) — short request form | `JOOBLE_API_KEY` |
| **JSearch** | Free tier, then paid | [RapidAPI](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch) | `JSEARCH_RAPIDAPI_KEY` |

Adzuna alone is enough to start. Skip JSearch unless you specifically want
LinkedIn/Indeed rows.

A monthly scan uses roughly 20–40 Adzuna calls, so the free tier has ample room
even with on-demand refreshes.

### 3. Pick the scorer

Set **one** of these. Claude wins if both are present.

- `ANTHROPIC_API_KEY` — better nuanced fit reasoning. Costs a few cents per scan.
- `GEMINI_API_KEY` — the key your blog already uses. Zero new setup, free tier.

Start with Gemini since you already have it; switch by adding the Anthropic key
later if the reasoning feels shallow. Nothing else changes.

### 4. Move this into its own repo

`jobs.imetrobert.com` needs its own repository, because GitHub Pages allows only
one custom domain per repo and `imetrobert.github.io` already claims
`www.imetrobert.com`.

```sh
# 1. Create an empty repo on GitHub named `jobs` (private is fine —
#    GitHub Pages serves private repos on paid plans; use public if not).

# 2. From a clone of imetrobert.github.io:
cp -r jobs-app /tmp/jobs && cd /tmp/jobs
git init && git add -A
git commit -m "Job matcher: initial import"
git branch -M main
git remote add origin https://github.com/imetrobert/jobs.git
git push -u origin main
```

The `.github/workflows/` directory travels with it and activates in the new repo.
It's intentionally inert while it sits inside `imetrobert.github.io` — workflows
only run from a repo's root.

### 5. Configure the new repo

**Settings → Secrets and variables → Actions:**

| Secret | Used by |
|---|---|
| `VITE_SUPABASE_URL` | site build |
| `VITE_SUPABASE_ANON_KEY` | site build |
| `SUPABASE_URL` | scan job |
| `SUPABASE_SERVICE_ROLE_KEY` | scan job |
| `GEMINI_API_KEY` *or* `ANTHROPIC_API_KEY` | scoring |
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | Adzuna feed |
| `JOOBLE_API_KEY` | Jooble feed (optional) |
| `JSEARCH_RAPIDAPI_KEY` | JSearch feed (optional) |

**Settings → Pages:** Source = **GitHub Actions**, Custom domain = `jobs.imetrobert.com`.

**DNS** (same place you set up `invest.imetrobert.com`): add a `CNAME` record,
host `jobs`, value `imetrobert.github.io`. Wait for the Pages check to go green,
then tick **Enforce HTTPS**.

**Deploy the edge function** — Supabase Dashboard → Edge Functions → Deploy a new
function → name it exactly `generate-application`, paste
`supabase/functions/generate-application/index.ts`, deploy. Keep **Verify JWT ON** —
that's what restricts it to your logged-in session. Then add the same
`GEMINI_API_KEY` or `ANTHROPIC_API_KEY` under Edge Functions → Secrets.

### 6. Fill in your profile — this is the part that matters

Sign in at `jobs.imetrobert.com` with your existing Supabase credentials, go to
**Profile**, and paste your full CV as plain text.

Match quality is almost entirely downstream of this. Scores are only as honest as
the evidence you give the scorer: roles, dates, scope, team sizes, budgets, and
outcomes with real numbers. A three-line summary produces three-line judgments.

Then set:
- **Target titles** — these literally become the search queries sent to the feeds.
- **Locations**, **minimum seniority**, **compensation floor**.
- **Deal breakers** — anything matching is filtered out before it costs an LLM call.

### 7. Add company boards (the sharp edge)

**Sources** tab. Aggregators cover the market broadly; company boards get you the
role the day it posts, straight from the ATS, before any aggregator indexes it.

Add the employers you'd actually leave for. Paste either the slug or the full URL:

- Greenhouse → `boards.greenhouse.io/<slug>`
- Lever → `jobs.lever.co/<slug>`
- Ashby → `jobs.ashbyhq.com/<slug>`

Free, no key, no rate limit worth worrying about. Ten good companies here will
outperform any aggregator.

### 8. Enable the Refresh button

The in-app **Refresh now** button starts the scan workflow on your behalf, so it
needs a token — the same pattern as your blog preview page.

Create one at [github.com/settings/tokens/new](https://github.com/settings/tokens/new?scopes=workflow&description=Job%20Match%20Refresh)
with the **`workflow`** scope, then paste it into the "Set up Refresh" box in the
app. It's stored in that browser's localStorage only — once per device, never
committed.

You can always skip this and run the scan from the repo's **Actions** tab instead.

---

## Reading the results

Scores are deliberately calibrated to be *unflattering*. A list where everything
is 85 is useless, so the scorer is told most postings are mediocre fits.

| Tier | Score | Meaning |
|---|---|---|
| Exceptional | 90–100 | Reads as though written for you |
| Strong | 75–89 | Clearly qualified, would likely get an interview |
| Possible | 55–74 | Plausible, but you're one of many |
| Stretch | 35–54 | Missing something material |
| Poor | 0–34 | Hidden from the list entirely |

Each card gives you **why it fits**, **the honest gaps** (read this one — it's
what an interviewer will probe), and **what to lead with**.

Generated cover letters and CVs are drafts. The prompt forbids inventing
employers, titles, dates, or metrics, but read them before sending: every claim
should be one you can defend in an interview.

---

## Running costs

| | |
|---|---|
| GitHub Pages + Actions | Free |
| Supabase | Free tier, shared with your other two apps |
| Adzuna / Jooble / ATS boards | Free |
| Gemini scoring | Free tier is generally sufficient |
| Claude scoring (if enabled) | A few cents per scan |

`MAX_SCORES_PER_RUN` (default 120) caps how many postings get scored in one run,
so a flood of new listings can't run up a bill. Anything not reached stays
unscored and is picked up next run.

---

## When something goes wrong

**"No scan has run yet"** — Profile is empty. The scan refuses to run without a
resume or summary, because scoring against nothing produces noise.

**Scan failed, "Missing ANTHROPIC_API_KEY or GEMINI_API_KEY"** — neither secret is
set on the *jobs* repo. Secrets don't carry over from `imetrobert.github.io`.

**A source shows a red error in the Sources tab** — the message is stored per
source. Usually a bad ATS slug (check the board URL loads in a browser) or an
expired key. Other sources keep working; one bad feed never fails the run.

**Refresh button says the token was rejected** — the token needs the `workflow`
scope and access to the `jobs` repo. Fine-grained tokens need
*Actions: read and write* on that repository.

**Nothing scores above 35** — usually the seniority floor or locations are too
narrow, or the resume is too thin for the scorer to find evidence. Widen
locations first; it's the most common cause.

**Roles you expected are missing** — add the company's ATS board directly in
Sources. Aggregator coverage of senior roles is genuinely patchy; company boards
are not.

---

## Layout

```
jobs-app/
├── src/                          React app (login, ranked list, profile, pipeline, sources)
├── scripts/
│   ├── run-job-scan.js           orchestrator: fetch → dedupe → prefilter → score → persist
│   ├── sources.js                one adapter per feed; add new feeds here
│   ├── scoring.js                the scoring prompt, schema, and prefilter
│   └── llm.js                    Claude / Gemini switch
├── supabase/
│   ├── schema.sql                job_* tables, RLS, the job_ranked view
│   └── functions/generate-application/   cover letter + CV edge function
└── .github/workflows/
    ├── job-scan.yml              monthly cron + on-demand dispatch
    └── deploy.yml                build and publish to Pages
```

To change the *voice* of the scoring or the letters, edit the `SYSTEM` prompt in
`scripts/scoring.js` or `supabase/functions/generate-application/index.ts`. To add
a new job feed, write one adapter in `scripts/sources.js` returning the shared
posting shape and register it in `ADAPTERS`.
