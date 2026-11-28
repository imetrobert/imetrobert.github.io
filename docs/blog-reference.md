# Reference (moved out of CLAUDE.md to keep it short)

## (from CLAUDE.md) Editing without Claude Code (plain claude.ai chat, no repo access)

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

## (from CLAUDE.md) Everything else

- `cover-2027.png`, `profile.jpg`, `blog/og-blog.jpg` — static assets, replace
  in place, no code changes needed. (`favicon.svg` is not one of these — see
  the brand mark section above before touching it.)
- `CNAME` — GitHub Pages custom domain config, essentially never changes.
- `scripts/test_*.py`, `scripts/verify_gemini_key.py` — dev/ops tooling for
  the blog pipeline, unrelated to site content.

## (from CLAUDE.md) Facts and where to look

| Need | File |
|------|------|
| Staging/approval flow, secrets | `BLOG_PREVIEW_SETUP.md` |
| Brand/logo, favicon, icons, SEO rules | `docs/site-rules.md` |
| One-off repair scripts (already run; workflows removed, scripts kept) | `scripts/fix_old_posts.py`, `scripts/repair_november_2026.py`, `scripts/add_linkedin_hint.py` |
