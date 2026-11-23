# Common edits (read this instead of exploring the repo)

Two surfaces: the hand-edited homepage (`index.html` + `css/style.css`) and the generated blog (never hand-edit `blog/`, `sitemap.xml`, `feed.xml`, `llms.txt`). For blog problems go to `docs/DIAGNOSE.md` and `docs/RUNBOOK.md` instead.

## 1. Change the phone number or email
Phone `514-250-8491` and email `robert@imetrobert.com` each appear in two places in `index.html`: the JSON-LD Person block near the top (`"email"`, `"telephone"`, about lines 68-69) and the `.contact-bar` in the body (about line 228). Find them with `grep -n "514-250-8491\|robert@imetrobert.com" index.html` and change every hit. Commit to `main`; Pages redeploys in about a minute.

## 2. Reword the bio, a stat or a section
`grep -n 'id="story"' index.html` (also `impact`, `ebook`, `video`, `blog`, `journey`, `skills`), read only that `<section>`, edit the text, commit. "25+ years" is written separately in the `<meta name="description">` (line 18) and in `#impact`: change both.

## 3. Add or change an award
Awards live only in the JSON-LD `"award": [...]` list (about line 84). Edit that list; nothing else mentions them.

## 4. Styling
Edit `css/style.css` only. Never add inline `<style>` blocks to `index.html`. No emoji on visitor-facing pages: use the inline SVG icons (see `docs/site-rules.md`, "Icons").

## 5. Replace the cover, photo or social image
Replace `cover-2027.png`, `profile.jpg` or `blog/og-blog.jpg` in place with the same file name. Do not touch `favicon.svg` (see "Brand mark" in `docs/site-rules.md`).

## 6. Blog wording, voice or sections
That is a prompt or code change in `scripts/` (`gemini.py` emits, `parser.py` splits, `renderer.py` renders: change all three together), never an edit of a published post. Read "Audience and focus since the December 2026 issue" at the top of `docs/blog-pipeline.md` first. Use `grep -n` on the big scripts; do not read them whole.

## 7. Never do
- Hand-edit anything under `blog/posts/`, `blog/index.html`, `sitemap.xml`, `feed.xml`, `llms.txt`.
- Index `/blog/staging/` (robots Disallow and noindex on every page there).
- Share `latest.html`; always the post permalink.
- Delete a published post by hand: use the rollback button (`rollback-blog.yml`).

## Check after a change
Open www.imetrobert.com on the phone and reload. For script changes: `python3 -W ignore scripts/test_pipeline.py` (the "Blog tests" workflow also runs on every push to `scripts/`).
