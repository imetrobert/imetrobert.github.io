# Job Match

Private job matcher for [imetrobert](https://www.imetrobert.com) — pulls postings
from job APIs and company ATS boards, ranks them against your profile with an LLM,
explains the fit, and drafts a tailored cover letter and CV on request.

Login-gated via Supabase Auth (same project and credentials as the invoicing and
ETF apps; tables namespaced `job_`).

**→ [SETUP.md](./SETUP.md) — start here.**

```sh
npm install
npm run dev     # local dev server
npm run build   # production build
npm run scan    # run a scan locally (needs .env — see .env.example)
```

Deliberately does not scrape LinkedIn or Indeed: both block automated access and
forbid it in their terms. Sources are documented APIs and the public ATS endpoints
that Greenhouse, Lever and Ashby publish for embedding company job boards.
See SETUP.md for what that does and doesn't cost you in coverage.
