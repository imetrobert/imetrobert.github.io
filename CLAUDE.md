# imetrobert.github.io — content editing guide

Static personal site + AI-generated blog (custom domain `www.imetrobert.com`,
served via GitHub Pages, `.nojekyll`). Two very different content surfaces —
read the right section below before editing.

## `index.html` — the homepage (hand-edited)

This is the only file on the site meant to be edited by hand. All CSS now
lives in `css/style.css` (extracted from three inline `<style>` blocks that
used to make up ~62% of the file — pure formatting move, no visual change).
**Edit `css/style.css` for styling, `index.html` for content — you should
almost never need to touch both for a content change.**

Sections, in document order (each has an `id` you can jump to with grep):

| id | Section |
|----|---------|
| `#impact` | "Impact at a Glance" stats (25+ years, awards count, etc.) |
| `#ebook` | Book/ebook promo |
| `#story` | "The Story" — bio narrative |
| `#video` | "AI Thought Leadership" video embed |
| `#blog` | "Latest AI Insights" — links out to `/blog/`, not the posts themselves |
| `#journey` | "Journey Highlights" — career timeline |
| `#skills` | "Arsenal" — skill tags |

Example: `grep -n 'id="story"' index.html` to jump straight to the bio text.

### Facts repeated in more than one place

- Phone `514-250-8491` and email `robert@imetrobert.com`: JSON-LD Person
  schema near the top of `<head>` (~line 67) **and** the `.contact-bar` div
  in the body (~line 908). Update both.
- Awards list ("Webby Award Winner", "Bell Bravo Award", "Execution
  Excellence Award", "Boomerang Award"): only in the JSON-LD Person schema
  (`"award": [...]`) — not duplicated in visible body text currently.
- "25+ years" appears in the meta description (`<head>`) and in the
  `#impact` stats card — both are independent hand-written strings, not
  templated from one source, so check both if the number changes.

JSON-LD blocks (Person/Blog/WebSite schemas, top of `<head>`) are already
pretty-printed one field per line — safe to copy/paste just the field you
need.

## `blog/` — do NOT hand-edit posts

Blog posts are **generated, not written**: a monthly GitHub Action calls
Gemini to draft a post, stages it, emails you a preview link, and only
publishes to `blog/posts/` after you click Approve in the preview UI. Full
details in `BLOG_PREVIEW_SETUP.md` — read that before touching anything
under `blog/` or `scripts/`.

- `blog/posts/*.html` — published posts. Generated + approved via the
  workflow, not edited directly.
- `blog/posts/latest.html`, `blog/index.html`, `sitemap.xml` — regenerated
  automatically by `scripts/blog_index.py` / `scripts/regenerate_sitemap.py`
  as part of that same pipeline. Don't hand-edit these either — changes
  will be overwritten on the next run.
- If you want to influence the *voice* of future posts (not fix a typo in
  a past one), that's a prompt/generation change in `scripts/generate-blog.py`
  or `scripts/renderer.py`, not a content edit.

### The issue structure is a three-file contract

`gemini.py` emits plain text under ALL-CAPS section headers → `parser.py`
splits on `SECTION_HEADERS` → `renderer.py` renders one block per section.
**Adding, renaming or removing a section means editing all three**, plus the
CSS in `renderer.py`. Change one and the section silently disappears from the
published page — the parser returns `""` and the renderer skips it, with no
error anywhere.

Sections, in the order they appear in an issue:

| Section | Carries |
|---------|---------|
| `HEADLINE` / `INTRODUCTION` | Title + 3-sentence opener |
| `EXECUTIVE SUMMARY` | 3 conclusions, numbered |
| `KEY AI DEVELOPMENTS` | 5-6 stories; the **first 3** carry `STRATEGIC READ` + `IMPORTANCE`/`HORIZON`/`ATTENTION` |
| `CANADIAN SPOTLIGHT` | 3 items, government items mandatory here |
| `FROM ROBERTS DESK` | 300-450 words, the signature section |
| `STRATEGIC ACTIONS FOR THIS MONTH` | 5 actions + `OWNER`/`PRIORITY`/`EFFORT`/`IMPACT` |
| `ADOPTION SNAPSHOT` | 5 Canadian stats |
| `LOOKING AHEAD: THREE PREDICTIONS` | `One month:` / `Six months:` / `One year:` |
| `ONE QUESTION FOR YOUR LEADERSHIP TEAM` | One question |

Rules that keep this working:

- **Ratings are inline labels ending in a full stop, before `Source:`.** The
  source regex anchors on a period or newline preceding the word "Source", so
  `ATTENTION: Yes. Source: Reuters | ...` parses and
  `ATTENTION: Yes | Source: ...` does not.
- **Every rating is optional in the parser.** A story with no ratings renders
  as a compact log entry, an action with no owner renders without badges. That
  is what lets an old-format post, or a bad month, degrade instead of shipping
  empty badge rows.
- **Section headers must start their own line.** `parse_sections` anchors on
  line starts precisely because "Looking ahead" and "Executive summary" are
  ordinary English — an unanchored match would cut the document at the first
  prose use and swallow everything after it. Both phrases are banned from prose
  in the prompt for the same reason.
- `SECTION_ALIASES` in `parser.py` maps old and misspelled headers to the
  canonical one. `ROBERTS TAKE` is there so posts written before the rename
  still parse.

### `From Robert's Desk` — the one section that must be Robert's

It was "Robert's Take" (2-3 sentences) and is now the signature section. The
CSS classes did **not** change with the rename: `.roberts-take`,
`.roberts-header`, `.roberts-body` are load bearing, because
`inject_take.py` finds the block through them to substitute the text typed in
the preview page. Rename those classes and injection silently no-ops — and the
failure mode is the *model's* draft publishing under Robert's byline.

The preview page pre-fills its textarea with the model's draft
(`_extract_desk_draft` in `generate-preview-page.py`), so the monthly job is
editing rather than writing from nothing. A `localStorage` draft still wins
over the pre-fill.

### Redrafting one section (`scripts/redraft_section.py`)

The preview page can send a single section back to Gemini instead of
regenerating the whole issue — pick the section, optionally type a steer, and
the block is rewritten in place. The staging filename does not change, so every
other section and the preview URL survive.

- **Only the four judgment sections are redraftable**, registered in
  `gemini.REDRAFTABLE_SECTIONS`: the Desk, Executive Summary, Looking Ahead,
  One Question. The reported sections are deliberately excluded — their
  items passed date rules, source-quality rules and cross-section deduplication
  during the monthly run, and a one-section rewrite reproduces none of that.
- **The redraft call is ungrounded** (no `google_search`). It works only from
  the issue as already written, so it can sharpen an argument but cannot
  introduce an event or statistic that never went through the sourcing rules.
- **Section specs live once**, as `_SPEC_*` constants in `gemini.py`, and are
  interpolated into both the monthly prompt and the redraft prompt. Never
  paraphrase a spec into the redraft path — the two would drift, and a
  redrafted section quietly following different rules is invisible.
- **Each redraftable section is rendered by exactly one function**
  (`_build_summary_section`, `_build_predictions_section`, …) so the redraft rebuilds a
  block identical to a full render.
- **`find_block()` counts div tokens** rather than regex-matching the block.
  These sections nest divs several deep and a non-greedy regex stops at the
  first inner `</div>`.
- **The FAQ is refreshed when a section it quotes is redrafted.** Looking Ahead
  feeds an FAQ answer, which exists twice — visible `.faq-a` and
  FAQPage JSON-LD. `FAQ_FED_BY` in `redraft_section.py` updates both, using
  `renderer.faq_plain` / `faq_join` so the scrubbing rules match exactly.
  Its question strings must match `faq_candidates` in `renderer.py` verbatim.
- **Nothing is written unless the redraft parsed and rendered.** A response that
  does not fit the section's format leaves the issue untouched.
- The preview picker is generated from `REDRAFTABLE_SECTIONS`, but the
  `workflow_dispatch` choice list in `redraft-section.yml` is hand-maintained —
  Actions cannot generate it. Adding a section means editing both.

### Adopting a new Gemini model without a code change

`blog/model-config.json` holds the model order and per-model daily limits.
`gemini.py` reads it via `load_model_config()`; `MODELS_TO_TRY` and
`MODEL_DAILY_LIMITS` are only the fallback for a repo with no config yet. The
approval page reads the file and writes it back through the GitHub Contents API
with the same PAT that dispatches workflows — which is what makes adopting a
newly launched model a UI decision instead of an edit here.

What can and cannot be discovered drives the whole design:

- **The model list can be.** `GET /v1beta/models?key=…` returns everything the
  key can call, so a new model appears on the next run and is recorded in
  `available`.
- **Rate limits cannot.** That response carries names and token limits but no
  RPD/RPM/TPM and no free-tier flag, and no other Google API exposes them. So
  the page *asks* for the new model's daily limit and refuses to adopt without
  one. Do not invent a default for an unknown model. `_quota_help_html()` renders
  the how-to-find-it steps, written once and used beside **both** limit inputs so
  the two cannot drift — and it leads with the project selector, because quotas
  are per Cloud project and that is the step people miss.
- **Whether a new model is better cannot be either.** flash-lite was available
  and produced a materially worse issue. So a new model is **offered, never
  adopted automatically**, and adopting it pushes the old order down into the
  fallback chain rather than replacing it — a bad new model degrades to what
  was already working.

Other things that matter:

- **The offer is filtered hard, and only ever shows models NEWER than the
  current leader.** A first run listed seventeen "new" models: image
  generators, the Gemma family, `-latest` aliases, `-001` version pins, and
  `2.0-flash-lite`, which is *older* than what we lead with. An offer that long
  is noise, and noise gets dismissed unread. `is_text_generation_model()` plus a
  version comparison cut that to four. `_MODEL_EXCLUDE_TOKENS` is a token
  denylist rather than a name list, so a future `gemini-4.2-flash-image` is
  filtered by `-image` with no edit.
- **`-latest` aliases are excluded deliberately.** `gemini-flash-latest` would
  track the newest flash automatically — which sounds like the longevity goal,
  but it would change the model under a published issue with no decision point,
  and the whole reason a new model is offered rather than adopted is that
  availability is not quality.
- **The question is not "is it newer" but "does it cost headroom".** Free-tier
  Pro limits are tens of requests a day against Flash's thousands, so adopting
  a Pro model would remove most of the daily budget. The panel shows the
  CURRENT model's limit beside the new one, computes the delta live as the
  number is typed (green for a gain, amber under 50% loss, red beyond), and
  `modelTierRisk()` warns from the model NAME before any lookup — pro and lite
  each get a specific caution. A cut of more than half needs an explicit
  `confirm()`; it is an informed decision, not a blocked one, because the
  budget does not recover until midnight Pacific.
- **The panel hands over a COPY-PASTE PROMPT, not instructions.** Step-by-step
  console directions told the reviewer where to click; the prompt answers the
  question. It is built from the models actually in play, names the current
  model and its recorded limit, asks for RPD/RPM/TPM plus the percentage change,
  and asks for uncertainty to be stated rather than estimated — a confidently
  wrong RPD drives a quota bar that is confidently wrong too.
- **RPM is captured but is not the constraint.** This pipeline peaks at roughly
  three requests inside a minute (the 400/404 retry is immediate, the transient
  retry waits 45s, the fallback waits 30s) and the `blog-pipeline` concurrency
  group serialises runs, so anything from about 5 RPM up is untouchable. The
  field exists because free-tier RPD is often IDENTICAL across candidate models —
  all four offered in one run were 1500 RPD — so RPM is sometimes the only
  number that differentiates them, and because a future low-RPM model would
  throttle a single generation.
- **The JS lives inside a Python f-string.** `"\n"` there is interpreted at
  render time and becomes a real newline inside a JS string literal, which kills
  the entire script block — every button on the page, silently. Write `"\\n"`.
  Run `node --check` on the extracted `<script>` after touching this file.
- **The help block leads with the rate-limits doc, not the console.** For a
  model the project has never called there is usually no console quota row yet,
  so `_RATE_LIMIT_DOC` is the only place the number exists *before* adoption —
  which is exactly when the decision is made. The console step follows, to
  confirm what the project actually has.
- **The offer is a dropdown, not a label.** Discovery can return several newer
  models at once, and a single "Lead with it" button taking the first would
  adopt something never chosen.
- **Discovery runs after the issue is generated and fails silently.** It is a
  convenience; it must never be able to stop a run.
- **A malformed config falls back to the constants** rather than raising —
  verified for broken JSON and for wrong types.
- **`dismissed` is permanent** for that model, so declining an offer does not
  re-prompt every month.

### Gemini quota — requests per day, on the approval page

The free tier is **not a monthly token pool**. It is rate limits: requests per
minute, tokens per minute, and requests per **day**. Repeated test runs hit the
daily request count long before anything else, so that is the only number the
preview page shows.

- **A run is not a request.** One generation can fire several — a 503 buys the
  same model a second attempt, a fallback tries the next model, a 400/404
  retries without grounding. `record_gemini_request()` is called at the HTTP
  call itself in `_call_gemini`, so redrafts and regenerations count too.
- **The ledger is `blog/staging/usage.json`**, committed by all three workflows
  (`git add blog/` and `git add blog/staging/`), keyed by **Pacific** date
  because that is when Google resets the quota. Keeps 60 days.
- **Writing it can never lose an issue**: every failure path returns quietly
  with a NOTE in the log.
- **The page re-fetches the ledger on load** rather than trusting the value
  baked in at generation time — a redraft makes requests without regenerating
  the page.
- **Limits are PER MODEL and separate.** `MODEL_DAILY_LIMITS` in `utils.py`
  carries the free-tier defaults (flash 1500, flash-lite 1000). Ten flash
  requests and five lite requests are `10/1500` and `5/1000`, not fifteen
  against one number — a combined bar would misreport both, and would hide that
  a fallback run does not spend the leader's quota. The panel renders one row
  per model used today, each with its own bar and its own editable limit.
- **Defaults are overridable per model**, kept in `localStorage`, because Google
  assigns quotas per Cloud PROJECT and no longer publishes a universal table. Free-tier limits vary
  by model and change over time; inventing a number would produce a confident
  percentage that is wrong. Saved in `localStorage`, and until it is set the
  panel shows the raw count and asks for it. Green under 60%, amber to 85%, red
  above.
- **It counts only this pipeline, and says so on the page.** An API key belongs
  to one Google Cloud project and every app using that key draws on the same
  quota, so anything else is invisible here. The authoritative view is Cloud
  Console → APIs & Services → Generative Language API → Quotas, linked from the
  panel.

**What of Robert's own writing reaches Google.** Only the redraft steer box.
`inject_take.py` runs in `approve-blog.yml` — at approval, after every Gemini
call — so the Desk text goes straight into the published HTML and is never sent.
The redraft guidance field IS sent with the issue on every redraft, and the free
tier permits human review and training on submitted data, so the box carries a
warning saying exactly that. Keep it that way if the redraft path changes.

### The approval page must never reload itself with `location.reload()`

`blog/staging/preview.html` sits at a fixed URL and is **replaced on every
run**, while GitHub Pages serves it with a ten-minute `max-age` that cannot be
overridden from the repo. So a same-URL reload can legitimately be answered
from cache, and the reviewer is left looking at the previous run's issue with
the previous run's "Generated" stamp.

**Every reload path in `generate-preview-page.py` goes through
`forceRefresh()`**, which navigates to `location.pathname + "?v=" + Date.now()`
— a URL never requested before cannot be in any cache, browser or CDN. It is
built from `pathname`, not `href`, so repeat presses don't stack params.

- The Force Refresh button used to re-point only the **iframe** `src`. That
  reloads the draft but leaves the approval page itself — including the stamp,
  which is rendered server-side — exactly as cached. The one control meaning
  "show me the current version" could not change the one field you would check
  to see whether it had worked.
- The regenerate poller is the same trap in reverse: it proves a new page
  exists with a cache-busted `fetch`, announces "New version ready", and then
  must not reload in a way that can be served the old one.
- `forceRefresh()` calls `flushTake()` first. The Desk textarea saves on a
  400ms debounce, so the last keystrokes before a refresh would otherwise be
  lost — and the Desk is the one section that is genuinely Robert's.
- `checkForStalePage()` compares the baked-in stamp against a `no-store` fetch
  of the live page and raises the amber bar. It guards on `#stale-bar` so two
  warnings can't stack.
- The iframe's load handler is attached in JS. As an `onload=` attribute it
  threw `ReferenceError` on every load, because an iframe with an empty `src`
  fires `load` for `about:blank` while the page is still parsing — before the
  script at the end of `<body>` exists.

### Canadian Spotlight leads with brands the reader knows

The section kept filling with federal programs and AI vendors (Cohere, Ada,
Coveo, Mila). Both are credible; neither is a name a reader meets in daily life,
so the one section meant to feel local read like industry trade press.

`CANADIAN_HOUSEHOLD_BRANDS` in `utils.py` is the single source — banks,
telecoms, retailers, airlines, energy, food. It is used **twice**: interpolated
into the Spotlight spec so the model knows the universe, and matched by
`is_household_canadian_brand()` so `renderer.py` orders those items first. Same
pattern as `STOCK_VOICE_PHRASES`; if the two drifted, the prompt would ask for
one thing and the ordering would reward another.

- **The spec selects in priority order**: household-name adopters first (aim for
  2 of 3), government second (still routed here, but at most one slot unless
  brand stories are short), Canadian AI vendors last.
- **What earns a slot is a described deployment**, not an investment. "Bank X
  launched an assistant handling Y% of service conversations" qualifies; "Bank X
  is investing in AI" is the filler this is meant to replace.
- **The renderer sorts brands first anyway.** `sort()` is stable, so within each
  group the model's own ordering survives. This covers the case where it finds
  the right stories and lists them in the wrong order.
- **`SPOTLIGHT BRANDS:` in the run log** reports how many items named a
  household brand, and says so plainly when none did.
- **The spec tells the model HOW to search, not just what to prefer.** A priority
  list alone did not work: the first run after it produced three government items.
  A generic "Canadian AI news <month>" query returns federal announcements because
  Ottawa publishes constantly and ranks for those terms, so the spec asks for a
  separate query per company ("RBC artificial intelligence", "Telus AI customer
  service") worked through sector by sector, and says to stop and search brands
  after two government items. Same lesson as the developments section.
- **"MANDATORY here" is a routing rule, not a quota.** It means a government item
  belongs in this section rather than Key Developments — not that the section must
  be filled with them. Spelled out in the spec because the model read it the
  other way.
- **Matching is word-boundary** so "Bell Canada" cannot fire inside "Campbell".
  It is used for ordering and reporting only — nothing is ever dropped for
  failing it, which is what makes a loose match acceptable here.
- **Nothing is padded to hit the quota.** The spec says so explicitly: a brand
  item cited to a vendor blog is worse than a well-sourced government item, and
  the sourcing allowlist applies to this section unchanged.

### Sources — an allowlist, and the wire distinction

`is_acceptable_source()` in `utils.py` is an **allowlist**: a development is
dropped unless its citation is a known publication, a government or regulatory
body, the subject's own newsroom, or a press-release wire. Five issues ran on a
blocklist and each one found a new way past it ("Signal49 Research",
"BenchLM.ai", "Analytics Vidhya"), because those names are arbitrary and no
pattern can anticipate them. The cost is intended: a month with little primary
reporting yields a thin issue to regenerate, not a full one nobody can check.

**Press-release wires are acceptable sources but never independent ones.** CNW
and GlobeNewswire are how Canadian companies actually issue announcements, so
dropping them discards real primary material — but they carry a release
verbatim for a fee, so counting them as journalism would let a month of pure
corporate PR report itself as independently sourced.

- `_NEWSWIRE_NAMES` / `is_newswire()` are **deliberately separate from**
  `_KNOWN_PUBLICATIONS`. Adding a wire to the publication list would flip it to
  "independent" in the tally and silently defeat the WEAK SOURCING warning.
- Wire *journalism* is a different thing: Reuters, Bloomberg and Canadian Press
  employ reporters and stay on the publication list.
- In `renderer.py` the newswire test runs **before** the publication test, and
  scores first-party. The run log breaks it out — `5 first-party (2 via a
  press-release wire)` — because "first-party" alone hides how much of the
  month came through PR.
- `"cnw"` is exact-match only; three letters would collide with ordinary words.
- **Corporate newsrooms stay in `_KNOWN_PUBLICATIONS` but never count as
  independent.** `_FIRST_PARTY_NEWSROOMS` / `is_first_party_newsroom()` are
  tested *before* the publication branch in the tally, exactly like the wires —
  Microsoft Source reporting a Microsoft partnership has a stake in the story.
  A run scored `2 independent` on Hugging Face and Microsoft Source, which
  suppressed `ALL FIRST-PARTY` on an issue where every development was in fact
  first-party. The tally was reporting the opposite of the truth on the one
  number the reviewer steers by.

### The model sometimes writes the issue twice

`parse_sections` records only **first** occurrences, and the last section runs
to end-of-document — so a duplicated issue lands entirely inside the final
section. A real run put 9,776 characters into `ONE QUESTION FOR YOUR LEADERSHIP
TEAM`, and the closing question published with a raw ALL-CAPS header inline in
its own text.

Guarded in both places, like the future-date rule:

1. **Prompt** — `WRITE THE ISSUE EXACTLY ONCE` in the OUTPUT FORMAT block.
2. **Parser** — any header found *after* the last known header start marks a
   restart, and the document is truncated there with a `DUPLICATE ISSUE:` line
   naming how much was discarded.

Detection uses the anchored `_find_header` pattern, not a loose search, so
ordinary prose cannot trigger it.

`WEAK SOURCING` fires when a development carries **no usable source line at
all**, and it means what it says: regenerate, or cut those items. It does *not*
fire on first-party citation. It used to demand two independent publications and
call anything less "effectively unsourced", which fought the section's own
definition — `KEY AI DEVELOPMENTS` is specified as company announcements, so
first-party citation is its natural state, and Hugging Face disclosing a Hugging
Face incident is the authoritative source rather than a weak one. It fired on
accurate issues, and a warning that fires on good issues stops being read.

`ALL FIRST-PARTY` is the softer replacement: it notes when nothing in the month
was independently reported, so anything a company would have reason to spin is
uncorroborated. A prompt for a closer read, not a blocker.

**Sourcing failures started in `KEY AI DEVELOPMENTS` and have since reached the
Spotlight too.** For five runs the aggregators (BenchLM.ai ×3, Analytics Vidhya,
ThursdAI ×3) all landed in the global section while the Canadian section cited
BetaKit, Mila and the Government of Canada correctly — but a later run cited an
ISED funding program to a business-services blog and Quebec Law 25 guidance to a
marketing site, when both bodies had announced them themselves. Do not assume
the Spotlight is safe; it is still parsed **flag-only**, so a bad citation there
publishes with nothing but an `UNRECOGNISED SOURCES` line. Hence the
government-source rule in its spec: cite the body's own page.

The developments spec tells the model **how to search**:
a roundup is a lead to follow, not a result to discard — the old "discard it"
rule threw away the lead along with the bad citation, leaving nothing and a
quota of 5-6 to fill — and it asks for one search per beat rather than one
"AI news <month>" query, which returns roundups because roundups are what match
it. Prohibition alone was escalated four times and never worked.

**Regulators must be recognised by their full legal names.** Several were known
only by abbreviation, so `OSFI` passed while `Office of the Superintendent of
Financial Institutions` was flagged unrecognised — and would have been *dropped*
from a development. That is the name a regulator publishes under, and the
Spotlight spec now tells the model to cite these bodies directly, so
`is_government_entity()` has to know them or the rule generates warnings on
correct behaviour. It matches `office of the`, `superintendent of`,
`privacy commissioner`, `commission d'`, `radio-television` and similar.

**Documentation is not an announcement.** `is_documentation_source()` rejects
help centres, docs pages, `Microsoft Learn`, release notes and API references,
and it is checked *first* in `is_acceptable_source` — those names carry the
company's own name, so every other test would wave them through. A run cited a
ChatGPT Work launch to "OpenAI Help Center": undated evergreen material used as
evidence that something happened that month. Matched on specific phrases, never
on bare "learn" or "support", which would fire inside real publication names.

Two rules that keep the allowlist from refusing real journalism:

- **`_KNOWN_PUBLICATIONS` is matched on WORD BOUNDARIES, not raw substring.**
  `intel` (the chipmaker) was firing inside `futurum intelligence`, so any source
  named "… Intelligence" was silently accepted as Intel's newsroom — and
  analyst-style names ending in "Intelligence" are exactly what the allowlist
  exists to catch. Boundaries keep `CBC News` matching `cbc`. The hazard note
  below said "three-letter"; `intel` is five, which is how it survived.
- **`_KNOWN_ABBREVIATIONS` is matched exactly, and must stay out of
  `_KNOWN_PUBLICATIONS`.** That set was matched as a *substring*, so a
  three-letter key in it would fire inside unrelated names. `TNW` (The Next
  Web) carried a real story that was dropped because only the long form was
  listed.
- **A domain that names a known outlet is that outlet.** The bare-domain test
  runs *after* stripping the suffix and asking `is_recognised_publication`,
  including a camelCase split, so `Reuters.com`, `BetaKit.com` and
  `TheGlobeAndMail.com` survive while `Fintech.ca` and `BenchLM.ai` do not.
  `.ca` belongs in that TLD list — it is the likeliest bare domain a Canadian
  publication will meet, and it was missing.

### The headline must never be prompt text

A run published `Find a significant Canadian AI-related event from July 2026
that can be stated as a specific claim` as its **H1, page title, og:title and
URL slug**. The model echoed roughly a hundred lines of instructions before
writing `INTRODUCTION`; it never wrote a standalone `HEADLINE` line, so
`parse_sections` fell through to its **unanchored** search, matched the word
inside the echoed text, and made 6,340 characters the HEADLINE section.
`_clean_headline` takes the first line of that section, and the instruction it
found passed every existing check — right length, four real words, not a
generic opener.

Guarded at both ends, and neither guard alone is enough:

1. **Size.** A HEADLINE section over 400 characters is a parse failure, not a
   headline. It is rejected before `_clean_headline` sees it.
2. **Shape.** `_INSTRUCTION_OPENERS` rejects imperative openers (`find`,
   `write`, `select`, `include`, `ensure`, `do not`, …) and
   `_INSTRUCTION_PHRASES` rejects instruction wording. A news headline is
   declarative; an imperative one came from the prompt.

Both print `PROMPT ECHO:` and fall back to the month title. Rule 0 in the
prompt already bans reusing its wording — this is the parser guard for when
that does not hold, same as the date and duplicate-issue rules.

### The headline is written before the filters run

`HEADLINE` comes from the model, but the date, source-quality and dedup filters
run afterwards — so a dropped story can leave the title promising something the
page never delivers. Two diagnostics in `renderer.py`, deliberately tiered:

- `TITLE MISMATCH` — **none** of the headline's distinctive terms appears
  anywhere in the issue.
- `TITLE NOT REPORTED` — they appear only in the introduction or commentary, so
  no development or spotlight item actually covers the headline.

**Warn only when nothing matches, never when one term is missing.** Requiring
every term to appear flagged a correct headline over a synonym: the title read
"…$700M for SMEs" and the introduction said "small and medium businesses". One
match is enough to prove the headline belongs to the issue.

### Coverage month is a dropdown, and the year list needs extending

`monthly-blog.yml` takes the coverage month as two `choice` inputs
(`coverage_month` + `coverage_year`) rather than a free-text "June 2026".
Actions has **no date input type** — `string`, `choice`, `boolean` and
`environment` are the only ones, and GitHub renders the form — so a calendar
picker is not available, but a dropdown removes the typo.

That is worth more than tidiness. `generate-blog.py` parses the value with
`strptime("%B %Y")`, so `Jul 2026` or `July, 2026` raised `ValueError` and the
run silently covered the **current** month behind a single `WARNING` line,
while `July 2062` parsed cleanly and would have generated a nonsense issue.

- `'(normal run)'` and `'(current year)'` are the sentinels. A `choice` input
  always sends a value, so "blank means normal" needed an explicit option.
- Inputs are read via `env:` rather than interpolated into the shell, so a
  value arrives as data, not as code.
- A year chosen without a month prints a NOTE and is ignored — a half-finished
  override should not quietly run the current month.
- **The year list is hand-maintained** (`2026`–`2030`), like the
  `workflow_dispatch` choice list in `redraft-section.yml`. Actions cannot
  generate options. Extend it before 2031.
- Scheduled runs pass no inputs at all, so the `-n "$IN_MONTH"` guard is what
  keeps the cron path on the current month. Don't drop it.
- `regenerate-blog.yml` deliberately keeps `coverage_month` as a **string**: it
  is dispatched by the preview page's Regenerate button, which sends a composed
  `"July 2026"` through the API. Converting it would break that call.

### The fallback model degrades judgment, not facts

`MODELS_TO_TRY` leads with `gemini-2.5-flash`; the fallbacks reliably produce
the *reported* half of an issue and flatten the *judgment* half — strategic
reads, the Desk, the predictions — into restated news. Since the judgment half
is the product now, availability must not silently buy a weaker issue:

- A transient status (`_TRANSIENT_STATUSES` — 429/500/502/503/504) buys the
  same model **a second attempt after 45s** before the run falls back. A 503
  means busy, not broken; Google's own message calls the spike temporary. One
  issue was generated by flash-lite because a single 503 dropped it a tier.
- When a fallback model is used, the run log prints `FALLBACK MODEL:` naming
  which sections to read closely. Check for that line before trusting an
  issue's analysis.

### Dates — nothing may be reported before it happens

The scheduled run fires on the **last day of the month** (`monthly-blog.yml`
gates on `CURRENT_DAY = LAST_DAY`) and reports that month, so every event is
already in the past. Two paths bypass that gate and ask for a month still in
progress: `force_run: true`, and `regenerate-blog.yml`, which has no last-day
check and defaults `coverage_month` to the current month. The prompt demands
5-6 dated developments, so when the real ones run out a forward-dated item is
the obvious gap-fill.

Guarded in two places, deliberately:

1. **Prompt** — a `CRITICAL FUTURE-DATE RULE` naming today's actual date, and a
   reminder in the developments spec. It tells the model that forward-dating is
   fabrication rather than forecasting, that predictions belong in Looking
   Ahead, and that such items are discarded before publication.
2. **Parser** — `_drop_future_dated()` removes any development dated after
   today, because a prompt rule is not a guarantee.

Details worth knowing before changing it:

- Items carry no year. `_resolve_item_date()` resolves one from the coverage
  date by trying the year either side and taking the closest, so a December
  item in a January issue does not land eleven months out.
- The filter is **skipped when `coverage_date` is None** — without a year there
  is no way to resolve "August 12", and guessing is worse than not checking.
  `renderer.py` passes `coverage_date or current_date`.
- Comparison is strictly `>`, so a same-day item survives. Undated items and
  unparseable dates survive too — an unreadable date is not evidence.
- Only **developments** are filtered. Spotlight items carry no dates, and
  adoption stats carry source years, not event dates.
- Dropping is loud: the parser prints a summary explaining the mid-month cause,
  and `renderer.py` warns when fewer than 4 developments survive. The visible
  symptom is a thin issue, and without that the reviewer assumes a bug.

### Brand — one definition in `utils.py`

`BRAND` ("Practical AI for Canadian Business"), `BRAND_SHORT`
("Practical AI Canada"), `BRAND_TAGLINE` and `AUTHOR` live in `utils.py` and are
imported by every generator. **Never hardcode the publication name.**

Before this existed the publication answered to four names across its own
surfaces — "AI Insights for Canadian Business" in the feed and post nav,
"AI Insights Blog" in the h1 and breadcrumbs, "AI News for Canadians | Monthly
AI Insights Blog" in the index title, and "Robert Simon - AI Innovation" as
`og:site_name` on every share. Nothing enforced agreement, so they drifted one
edit at a time.

- `BRAND_SHORT` is a space alias, not a second brand — nav bars, breadcrumbs and
  the post SEO title, where 34 characters does not fit. The post SEO title is
  already past Google's ~60-character cut, so the short form there buys the
  headline room rather than protecting the brand.
- The social card (`og_image.py`) sets the name as a two-line lockup:
  `headline="Practical AI"` over `subhead="for Canadian Business"`.
- **The archive was deliberately not backfilled.** Posts under `blog/posts/`
  keep the old name in their nav and `og:site_name`; only new issues carry the
  new one. `blog/index.html`, `feed.xml`, `llms.txt`, `sitemap.xml` and the
  pillar page are all regenerated, so those flipped on the next run. Some old
  issues also contain the old name inside their own body copy — that is
  historical text, not branding, and is correct to leave.

### Sharing — always the permalink, never `latest.html`

Posts carry a share row at the end of the issue (`_build_share_row` in
`renderer.py`); the blog index carries one on the latest-issue card and two
buttons per archive row (`_share_hrefs` / `_permalink` in `blog_index.py`).
LinkedIn, email, copy link, and the OS share sheet on mobile.

**Every share target must be the dated permalink.** A post is served at both
`/blog/posts/YYYY-MM-DD-slug.html` and `/blog/posts/latest.html`, and
`latest.html` is a rotating alias — same URL, different article next month. So:

- Posts build their links from `canonical`, never `location.href`.
- The blog index builds them via `_permalink()`, which prefers
  `canonical_filename` — `posts[0]` is read from `latest.html` and its
  `filename` really is `latest.html`.
- This is the same reason the index already links the newest issue by its
  permalink, and why social platforms caching OG data per URL makes a shared
  alias actively wrong rather than merely stale.

Other things that are deliberate:

- LinkedIn and email are plain `href`s resolved at build time, so they work
  with JavaScript off. Only clipboard and the share sheet need scripting.
- `.share-native` renders `hidden` and is revealed only if `navigator.share`
  exists, so desktop never shows a button that would do nothing.
- Archive-row buttons sit **outside** the row's `<a>`. Interactive elements
  nested in a link are invalid, recover unpredictably, and can leave a keyboard
  user unable to reach them.
- There is no "copy the full issue text" button and no prompt cards. The
  "Work this issue with your own AI assistant" section was removed — it never
  reached a published post, so nothing in `blog/posts/` carries it.
- To fix a typo in an already-published post: `scripts/fix_old_posts.py`
  exists for bulk fixes; for a one-off, editing the specific
  `blog/posts/YYYY-MM-DD-*.html` file directly is fine since nothing
  regenerates already-published posts automatically.

## Editing without Claude Code (plain claude.ai chat, no repo access)

Same approach as other repos in this account:

1. Find the section via the id table above (`grep -n 'id="SECTION"'
   index.html` on GitHub, or Ctrl+F in the GitHub file view).
2. Copy just that `<section>...</section>` block (or the specific line for
   a fact like the phone number) into chat with your requested change.
3. Paste the result back via GitHub's web editor.
4. If it's a repeated fact (see checklist above), repeat per location —
   small individual pastes, not the whole file.
5. Never paste all of `css/style.css` for a content question — styling and
   content are separate files precisely so you don't have to.

## SEO / AEO, and what must never be indexed

Posts already carry canonical, OG/Twitter, BlogPosting + FAQPage +
BreadcrumbList schema, and the sitemap/RSS are generated. Rules to keep it that
way:

- **FAQ answers must stay visible on the page.** `scripts/renderer.py` renders
  the `.faq-section` from the *same* `faq_items` that feed the FAQPage schema.
  Schema-only FAQ violates Google's structured-data policy and gives answer
  engines nothing quotable. If you change one, change both.
- **Each FAQ question is answered from the section that addresses it** —
  developments → "what developments matter", actions → "what should executives
  do", adoption stats → "how is adoption tracking", spotlight → "which Canadian
  companies", business impact → "how do global trends affect competitiveness".
  A Q&A is dropped when the post has no content for it (answers under 60 chars).
  Don't go back to zipping questions against `actions` positionally.
- Answer text is scrubbed of URLs, `|` field separators and markdown headings,
  because answer engines quote it verbatim.
- `llms.txt` (root) is **generated** by `scripts/blog_index.py` alongside
  `blog/index.html` and `feed.xml`. Don't hand-edit it.
- `robots.txt` allows AI crawlers (GPTBot, ClaudeBot, PerplexityBot,
  Google-Extended…) on the public content — being citable is the point — and
  disallows `/blog/staging/` for all of them.

**Never indexed:** everything under `/blog/staging/` (the draft + approval
tooling). It is protected two ways on purpose:

1. `Disallow: /blog/staging/` in `robots.txt`, and
2. `<meta name="robots" content="noindex, nofollow">` in every page that lands
   there — `generate-preview-page.py`, `write_nothing_pending_placeholder.py`,
   and drafts via `renderer.py`'s `is_draft` flag.

Both are needed. **Disallow stops crawling, not indexing** — a disallowed URL
can still be listed URL-only if anything links to it, and since the crawler
never fetches the page it never sees the noindex. The meta tag is what
actually guarantees removal. Any new admin/private page must carry it.

## Icons — no emoji on visitor-facing pages

Emoji were replaced with an inline SVG icon set. **Don't reintroduce emoji into
`index.html`, `css/style.css`, or anything under `blog/`** — use an icon instead.

- Each page defines a sprite of `<symbol>`s just after `<body>`, referenced as
  `<svg class="icon"><use href="#i-pin"/></svg>`.
- Homepage sprite lives in `index.html`; the `.icon` rule is in `css/style.css`.
  Post sprite + `.icon` rule are both in `scripts/renderer.py`'s template.
- Icons stroke in `currentColor` and size in `em`, so they inherit the colour
  and size of adjacent text — that is what makes them read as one set. Add
  `.icon-solid` for a filled glyph (the list bullets).
- **On the homepage, every `<svg class="icon">` repeats size/fill/stroke as
  presentation attributes. Don't strip them as duplication.** An SVG with no
  CSS defaults to 300x150 and `fill: black`, so a visitor whose browser cached
  `style.css` from before `.icon` existed gets giant black blobs down the whole
  page. The attributes keep icons sane on their own; CSS still wins when it
  loads. Posts don't need this — their CSS is inline, so it can never go stale.
- `style.css` is linked with a `?v=` query. Bump it whenever a change to that
  file is required for the HTML to render correctly, or returning visitors keep
  the old copy.
- Homepage ids: `i-pin`, `i-mail`, `i-phone`, `i-spark`, `i-linkedin`, `i-doc`,
  `i-cart`, `i-book`. Post ids: `i-search`, `i-clock`, `i-pencil`, `i-diamond`.
- The maple leaf is **not** an icon: it is illegible below ~32px and collapses
  into a four-pointed star. It stays in the logo; small markers are geometric.
- `content: "\2713"` in `.edition-features li::before` is a typographic check
  mark, not an emoji — deliberately kept.
- Still emoji, deliberately: `scripts/generate-preview-page.py` (your private
  approval UI, where they act as status indicators) and the console output of
  `scripts/test_*.py`, `fix_old_posts.py`, `write_nothing_pending_placeholder.py`.

## Brand mark

One mark for the whole site: an "AI" monogram whose spark — the dot over the
"i" — is a maple leaf, in the site's blue → cyan palette. It replaced the older
`RS` monogram favicon (still in git history if it's ever wanted back).

- `favicon.svg` (root) — **the site-wide favicon**, linked from the homepage,
  the blog index and every post. Simplified cut of the logo: no texture, flat
  white ink, heavier strokes, scaled up so it survives at 16px.
- `apple-touch-icon.png` (root, 180px) — for platforms that won't take SVG.
- `blog/logo.svg` — the detailed mark (with neural texture), used at 76px in
  the blog header and 22-28px in the nav. **Deliberately a separate file** from
  `favicon.svg` so the small size can be tuned without compromising the large
  one — edit both if the shape changes. `blog/logo-512.png` is its raster copy.
- Regenerate the rasters after any SVG edit:
  `python3 -c "import cairosvg; cairosvg.svg2png(url='favicon.svg',
  write_to='apple-touch-icon.png', output_width=180, output_height=180)"`
- The leaf is drawn as a right half and mirrored with `<use transform="scale(-1,1)">`,
  so it stays symmetric — edit the one path, not two.
- Where it's wired in: `scripts/blog_index.py` (blog index) and
  `scripts/renderer.py` (posts) carry the `<link rel="icon">` tags, the
  `.brand-logo` / `.brand-icon` CSS, and the markup — so new posts inherit the
  brand automatically. Already-published posts under `blog/posts/` were
  backfilled by hand and keep their own copy of that CSS.
- Icon paths are absolute (`/favicon.svg`), so they resolve the same from the
  homepage and from `/blog/posts/`. Don't make them relative.

## Everything else

- `cover-2027.png`, `profile.jpg`, `blog/og-blog.jpg` — static assets, replace
  in place, no code changes needed. (`favicon.svg` is not one of these — see
  the brand mark section above before touching it.)
- `CNAME` — GitHub Pages custom domain config, essentially never changes.
- `scripts/test_*.py`, `scripts/verify_gemini_key.py` — dev/ops tooling for
  the blog pipeline, unrelated to site content.
