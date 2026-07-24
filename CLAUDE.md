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

## Everything else

- `favicon.svg`, `cover-2027.png`, `profile.jpg`, `blog/og-blog.jpg` — static
  assets, replace in place, no code changes needed.
- `CNAME` — GitHub Pages custom domain config, essentially never changes.
- `scripts/test_*.py`, `scripts/verify_gemini_key.py` — dev/ops tooling for
  the blog pipeline, unrelated to site content.
