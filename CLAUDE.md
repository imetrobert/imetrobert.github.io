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
| `WHAT THIS MEANS FOR CANADIAN BUSINESS` | 3 paragraphs |
| `STRATEGIC ACTIONS FOR THIS MONTH` | 5 actions + `OWNER`/`PRIORITY`/`EFFORT`/`IMPACT` |
| `ADOPTION SNAPSHOT` | 5 Canadian stats |
| `AI MYTH OF THE MONTH` | `Myth:` / `Reality:` |
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

- **Only the five judgment sections are redraftable**, registered in
  `gemini.REDRAFTABLE_SECTIONS`: the Desk, Executive Summary, Myth, Looking
  Ahead, One Question. The reported sections are deliberately excluded — their
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
  (`_build_summary_section`, `_build_myth_section`, …) so the redraft rebuilds a
  block identical to a full render.
- **`find_block()` counts div tokens** rather than regex-matching the block.
  These sections nest divs several deep and a non-greedy regex stops at the
  first inner `</div>`.
- **The FAQ is refreshed when a section it quotes is redrafted.** The Myth and
  Looking Ahead both feed FAQ answers, which exist twice — visible `.faq-a` and
  FAQPage JSON-LD. `FAQ_FED_BY` in `redraft_section.py` updates both, using
  `renderer.faq_plain` / `faq_join` so the scrubbing rules match exactly.
  Its question strings must match `faq_candidates` in `renderer.py` verbatim.
- **Nothing is written unless the redraft parsed and rendered.** A response that
  does not fit the section's format leaves the issue untouched.
- The preview picker is generated from `REDRAFTABLE_SECTIONS`, but the
  `workflow_dispatch` choice list in `redraft-section.yml` is hand-maintained —
  Actions cannot generate it. Adding a section means editing both.

### Sharing — always the permalink, never `latest.html`

Posts carry a share row under "The Bottom Line" (`_build_share_row` in
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
- The "Copy the full issue text" button strips `.share-row` along with
  `.prompts-section` — button labels are noise in text meant for an assistant.
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
