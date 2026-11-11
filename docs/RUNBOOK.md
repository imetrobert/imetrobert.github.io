# Runbook: keeping the blog running with minimal effort (iPhone-friendly)

For routine upkeep without an AI agent. Everything is done in the GitHub web UI.

## Monthly cycle
1. The monthly run generates on the last day of the month (and on the 1st if it was missed). You get an email with the preview link.
2. Open the preview page. Read it, write "From Robert's Desk", use Redraft/Regenerate if needed, press Approve.
3. Check the live blog (blog/index.html). Previous Issues must have no gaps.

If no email arrives by the 2nd: GitHub > Actions > "Generate Monthly AI Blog Post" > Run workflow. Turn on `force_run` and set `coverage_month` to the month that just ended.

## The two things that expire (put both in your calendar)
- **GitHub token used by the preview page** (stored in your browser as "blog_preview_pat"). If buttons say 401 or "token rejected", create a new token as described in BLOG_PREVIEW_SETUP.md (classic token with the `repo` and `workflow` scopes). A fine-grained token also works if limited to imetrobert.github.io with Actions: read and write and Contents: read and write. Paste it into the box on the preview page. Choose the longest expiry allowed.
- **Gemini API key** (repo secret `GEMINI_API_KEY`). If a run fails with 403, replace it: Repo > Settings > Secrets and variables > Actions.

## When something looks wrong
| Symptom | Do this |
|---|---|
| Preview page shows an old issue | Press Force Refresh (it bypasses the cache). |
| A redraft/regenerate "failed" message | The message names the failing step and links the run log. Read the last 20 lines of that step. Try once more. |
| Run succeeded but page unchanged after ~8 min | GitHub Pages is slow; wait 2 minutes and press Force Refresh. |
| Run fails at "Push" | It retries automatically; if it still fails, re-run the workflow. |
| Model problems (429 / 404) | Actions > Model Scout > Run workflow, or Pin a different proven model on the preview page. |
| Post is live but missing from the index | Actions > Rebuild Blog Index > Run workflow. |

## Models
Do nothing: the weekly Model Scout picks the best working free Gemini model. On the preview page you can Pin a model or press "Test for new models now". The scout log is in `blog/model-config.json` (`scout.log`).

## Free-chat-AI prompt (no repo access)
Paste only the file or section you are changing, never the whole repo. Open `CLAUDE.md` in this repo first; it says which file to touch and which are generated and must never be hand-edited. For the blog scripts, search for the function name on GitHub and paste just that function.
