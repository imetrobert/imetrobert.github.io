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

