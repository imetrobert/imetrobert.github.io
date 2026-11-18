# Site rules — SEO/AEO, icons, brand mark (moved verbatim from CLAUDE.md)

Read only the section you are about to change: `grep -n '^## ' docs/site-rules.md`.

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

Two marks live in this repo (changed 2026-11-17):

- **The personal homepage (index.html)** keeps the "AI" monogram with the maple-leaf spark: `favicon.svg` (root, flat, site-wide favicon of the
  homepage) and `apple-touch-icon.png` (root, 180px). Regenerate the raster after any SVG edit:
  `python3 -c "import cairosvg; cairosvg.svg2png(url='favicon.svg', write_to='apple-touch-icon.png', output_width=180, output_height=180)"`.
  Icon paths are absolute (`/favicon.svg`), so they resolve from any depth.
- **The blog (everything under `/blog/`)** uses the AI with Robert for Business logo (bulb + speech bubble, navy and gold), copied from the
  aiwithrobert-biz repo (its `logo.svg` source and favicon set): `blog/logo.svg` (header 76px, nav 22px), `blog/logo-512.png` (schema logo),
  `blog/favicon-16x16.png`, `blog/favicon-32x32.png`, `blog/apple-touch-icon.png`. `scripts/renderer.py`, `blog_index.py`, `pillar_*.py` and
  `survey.py` carry the `<link rel="icon">` tags and the `.brand-logo` / `.brand-icon` CSS. If the Business logo changes, re-copy those files from that repo.

## Blog colours (since 2026-11-15)
The blog (issues, index, adoption, survey and plan-changes pages) uses the Business brand: navy #11304c (was blue #2563eb), dark gold #8a6d0b (was cyan #06b6d4; chosen over bright gold #c9a227 so white text stays readable), darker navy #0b2237, gradient midpoint #1f3b4d. The generators carry the new values; `scripts/rebrand_blog.py` (idempotent) recoloured the older pages. The personal homepage (index.html, css/style.css) and the internal review pages keep the old look on purpose. Social images made before this date stay blue.
