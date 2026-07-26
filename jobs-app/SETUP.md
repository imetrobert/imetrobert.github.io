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

### 3. The scorer — Gemini, free tier

Set **`GEMINI_API_KEY`** — the same key your blog pipeline already uses. That's it.

**Nothing in this system requires a paid Claude subscription, a Claude Code seat,
or any paid Anthropic account** — not to install it, run it, or maintain it. There
is no Anthropic package in `package.json`. Once deployed, it runs unattended on
GitHub Actions, Supabase and Gemini; you never need an AI coding assistant to keep
it working.

The design is sized to stay inside Gemini's free tier rather than merely tolerate it:

| Lever | Effect |
|---|---|
| **Prefilter before scoring** | Wrong seniority, deal-breakers and wrong geography are rejected by plain code. Those postings never cost a request. |
| **Batched scoring** (`SCORE_BATCH_SIZE`, default 5) | 120 postings become **~24 requests**, not 120. It also sends your resume once per batch instead of once per job, cutting token use several-fold. |
| **Paced queue** (`GEMINI_RPM`, default 12/min) | Every call is serialized through one queue with a minimum gap, so a scan can't trip the per-minute limit. |
| **Retry with backoff** | Per-minute 429s back off (4s → 32s) and retry, then fall through the model chain: `gemini-2.5-flash` → `flash-lite` → `2.0-flash`. |
| **Graceful daily-quota stop** | If the daily quota does run out, the scan saves everything scored so far, logs why, and finishes the rest on the next run. It does not fail. |
| **`MAX_SCORES_PER_RUN`** (default 120) | Hard ceiling per run. |

A typical monthly scan is **around 24 Gemini requests over roughly two minutes**,
plus one request each time you draft a cover letter. That leaves ample headroom
even with several on-demand refreshes in the same day.

If you ever want sharper reasoning, adding `ANTHROPIC_API_KEY` switches the scorer
to Claude with no other change. Purely optional — leave it unset and nothing
degrades.

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

| Secret | Used by | Required |
|---|---|---|
| `VITE_SUPABASE_URL` | site build | yes |
| `VITE_SUPABASE_ANON_KEY` | site build | yes |
| `SUPABASE_URL` | scan job | yes |
| `SUPABASE_SERVICE_ROLE_KEY` | scan job | yes |
| `GEMINI_API_KEY` | scoring | yes |
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | Adzuna feed | recommended |
| `JOOBLE_API_KEY` | Jooble feed | optional |
| `JSEARCH_RAPIDAPI_KEY` | JSearch feed | optional |
| `ANTHROPIC_API_KEY` | scoring upgrade | **no — leave unset** |

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

Sign in at `jobs.imetrobert.com` with your existing Supabase credentials and go to
**Profile**.

**Use whichever source is most current for the Experience box — LinkedIn is fine,
and beats a stale CV.** The scorer reads plain text and doesn't care about
formatting; it cares about evidence. Fastest route: LinkedIn → your profile →
*More* → *Save to PDF*, then paste the text in. Then add what LinkedIn omits —
team sizes, budgets, P&L scope, and outcomes with real numbers.

Match quality is almost entirely downstream of this. Both the scorer and the
letter writer are forbidden from inventing experience, so thin input doesn't
produce wrong claims — it produces vague, hedged ones. Anything you leave out
simply isn't considered.

Then set:
- **Target titles** — these literally become the search queries sent to the feeds.
- **Locations** and **minimum seniority**.
- **Compensation** — see below.
- **Deal breakers** — anything matching is filtered out before it costs an LLM call.

#### Compensation is judged on the total package

The floor is on **total compensation, not base salary**. A role advertising 110k
base can clear a 128k floor once bonus, employer pension contributions, benefits
and equity are counted — so base is never used to reject a posting anywhere in
the system, and compensation never moves the fit score.

Fill in three fields:

| Field | What it does |
|---|---|
| **Total compensation floor** | The actual bar, e.g. `128000`. |
| **What counts toward that total** | Free text — bonus target %, pension match, benefits, equity. The more specific, the better the estimate on roles that publish only a base range. |
| **Hard floor on base alone** | Usually blank. Only fill it if a low base is a non-starter regardless of package. |

Each match then reports a **Total compensation** verdict, separate from the score:

- **above / at / below** — an estimate of the whole package against your floor,
  with reasoning.
- **unclear** — pay wasn't disclosed. This is the *most common* answer and is
  neutral, not a warning. The scorer is explicitly told that guessing from a job
  title is the error, not diligence.

One subtlety worth knowing: Adzuna *estimates* a salary when the employer
publishes none. Those are captured as estimates and shown as `~120,000 (est.)`,
and the scorer is told plainly that they're a guess — so an inferred number never
gets treated as a disclosed band.

Generated cover letters and CVs never mention a figure, ask for one, or state
expectations, even if the posting asks. That conversation belongs somewhere you
control the framing, not in a first-pass screening document.

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

Each card gives you five things:

- **Why this fits you** — the specific experience that maps to the role.
- **The honest gaps** — read this one; it's what an interviewer will probe.
- **Screening risk** — see below. Colour-coded green/amber/red.
- **Total compensation** — the whole package against your floor, not base.
- **Lead with** — the angle for the cover letter.

Three of those are deliberately *separate from the score*, because they answer
different questions. Fit asks "could you do this and would you lead the field?"
Screening risk asks "will you get the call?" Compensation asks "is it worth
taking?" Collapsing them into one number would hide whichever one you most need
to see.

### Screening risk is not the same as fit

This is a deliberately separate field, and it's the one most worth paying
attention to.

A deep, senior career is an asset for roles with real scope — and simultaneously
a filter risk, because hiring teams screen out candidates they read as too
senior, too expensive, or likely to leave for something bigger. Those are two
different questions, and blending them into one number would either hide the
risk or unfairly penalise good matches. So:

- **`score`** answers *could you do this job and would you be a leading
  candidate?* Depth of experience only ever helps it. Long tenure is never
  treated as a defect.
- **`overqualification_risk`** answers *will you actually get the call?* Rated
  none / low / moderate / high, with a reason. This is where a years-of-experience
  ceiling, a band below your floor, or "high-energy / digital native" language in
  the posting gets flagged.

A role scoring 88 with **high** screening risk is worth applying to *differently* —
through a referral rather than the portal, with a letter that leads hard on
current, in-demand work. That's a different action from a role scoring 88 with
low risk, and the split is what lets you tell them apart.

The generated documents are written to survive that screen without ever
misstating anything: they lead with recent and current impact rather than career
length, give full detail to roughly the last 12–15 years and compress earlier
roles into a single line, and omit graduation years. Standard executive-CV
practice — it hides nothing a hiring manager needs and removes the hooks that
trigger a reflexive filter.

They are still drafts. The prompt forbids inventing employers, titles, dates or
metrics, but read them before sending: every claim should be one you can defend
in an interview.

---

## Using this as standby readiness

If the point is to be ready to move quickly rather than to be actively job
hunting, the ordering changes:

- **Fill in the profile now, while you have time.** Reconstructing scope, budgets,
  team sizes and outcomes under pressure is slow and produces worse material than
  doing it unhurried. This is the single highest-value thing to do early, and it
  only has to be done once. Start from LinkedIn if that's what's current — a
  good-enough profile today beats a perfect one you never get to.
- **Treat the profile as the draft of your future CV.** Everything the scorer
  wants — scope, numbers, outcomes — is exactly what a strong CV needs. Filling
  this box carefully is the first pass at rewriting LinkedIn and the CV, not a
  detour from it. The tailored CVs the app generates are also useful raw
  material: they show which parts of your history land hardest against real
  postings.
- **Let the monthly scan run in the background.** The value isn't any single
  month's list — it's that the market picture and your document drafts are already
  warm on the day you need them, instead of starting cold.
- **Pre-draft documents for anything scoring "exceptional" or "strong".** They're
  saved against the posting and stay there. Even where the specific role is gone
  by the time you need it, you'll have several strong letters to adapt rather than
  a blank page.
- **Watch the screening-risk field over time.** If most strong matches come back
  moderate or high, that's a signal to adjust positioning — usually by sharpening
  the recent, current work at the top of your resume — well before it costs you
  anything real.
- **Re-run the scan the day anything changes.** One click, results in minutes.

The site is `noindex`, robots-disallowed and behind your Supabase login, so
none of this is discoverable while you're still employed.

## Running costs

| | |
|---|---|
| GitHub Pages + Actions | Free |
| Supabase | Free tier, shared with your other two apps |
| Adzuna / Jooble / ATS boards | Free |
| Gemini scoring | Free tier — ~24 requests per scan |
| **Total** | **$0/month** |
| Claude scoring | Optional, off by default. A few cents per scan if you ever enable it. |

**The steady state is free and requires no subscription of any kind.** If a scan
ever does hit the daily Gemini quota it stops cleanly, keeps what it scored, and
finishes on the next run — you lose time, never data.

To reduce request volume further, raise `SCORE_BATCH_SIZE` (8–10 still works
well; quality drifts if you push much past that) or lower `MAX_SCORES_PER_RUN`.

---

## When something goes wrong

**"No scan has run yet"** — Profile is empty. The scan refuses to run without a
resume or summary, because scoring against nothing produces noise.

**Scan failed, "Missing GEMINI_API_KEY"** — the secret isn't set on the *jobs*
repo. Secrets don't carry over from `imetrobert.github.io`.

**Log says "Gemini daily quota exhausted"** — not a failure. Everything scored
before the wall is saved, and the rest is picked up on the next run. If it keeps
happening, raise `SCORE_BATCH_SIZE` or lower `MAX_SCORES_PER_RUN`.

**Log shows "rate limited … retrying in 4s"** — normal. That's the per-minute
limiter working; it backs off and continues. Lower `GEMINI_RPM` if it's frequent.

**A batch logs "??? (no assessment returned)"** — the model skipped some postings
in that batch. They stay unscored and are retried next run. Persistent cases
usually mean `SCORE_BATCH_SIZE` is too high; drop it back toward 5.

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
