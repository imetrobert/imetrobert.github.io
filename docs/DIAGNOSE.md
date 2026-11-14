# Diagnosing the blog pipeline (start here when something goes wrong)

Written for a chat with a small token budget and NO knowledge of this repo. Do not explore the repo. Do not read the big
scripts (generate-preview-page.py 111 KB, renderer.py 80 KB, gemini.py 74 KB, parser.py 47 KB, utils.py 49 KB).

## Step 1: get the report (30 seconds, from a phone)
GitHub > imetrobert/imetrobert.github.io > Actions > **Blog health report** > Run workflow. Open the finished run, copy the
summary text. That report holds: the last 8 pipeline events, the most recent failure with a plain explanation and next step,
the last runs of every blog workflow, which Gemini model will lead, today's request count, and what is staged.
Paste it into the chat. (Claude Code: `python3 scripts/diagnose.py` gives the same report.)

The raw log behind it is `blog/staging/run-log.json` (newest last, capped at 150 events). Every redraft, regeneration and
monthly run writes one entry with a code, what happened, the next step and a detail line. It is committed even when the run fails.

## Step 2: read the error code
| Code | Meaning | Do this |
|---|---|---|
| QUOTA_EXHAUSTED | Gemini 429s: free limits hit | Wait (a minute for per-minute limits, until midnight Pacific for daily); run again |
| API_KEY_REJECTED | Google returned 403 | New key in Google AI Studio; replace secret GEMINI_API_KEY; run again |
| NO_API_KEY | Secret missing in this run | Check repo secrets |
| MODEL_UNAVAILABLE | Model 404/400 | Approval page: Back to Auto or pin another; Model Scout also repairs it |
| UNGROUNDED_REJECTED | No search-backed answer; nothing changed on purpose | Run again later |
| ALL_MODELS_FAILED | Every model in the fallback list failed | Look for 429/500/503/timeout lines in the run; usually temporary |
| JUNK_OUTPUT / TOO_SHORT / FORMAT_MISMATCH | Model returned notes, a stub or the wrong format; the issue was NOT changed (after one automatic retry) | Run again; add a specific direction; pin a stronger model |
| TOO_SIMILAR | New draft almost identical to the current one; not applied | Add a direction saying what angle to take |
| VERIFY_FAILED | Edit written but the post-write check failed; rolled back automatically | Nothing changed; open the run, read which check failed |
| BLOCK_NOT_FOUND | Section not found in the staged page | Page layout changed; regenerate the issue |
| SECTION_NOT_REDRAFTABLE | Only 4 judgment sections can be redrafted | Regenerate the whole issue for the reported sections |

The full wording lives in `scripts/runlog.py` (CATALOGUE). `python3 scripts/runlog.py explain <CODE>` prints one.

## Known behaviours that look like bugs (they are not)
- **Preview looks unchanged after a redraft**: GitHub Pages takes 2 to 3 minutes. Reload with `?v=<run id>` or wait. Check
  `run-log.json`: a line with status ok and "% different from before" means it did change.
- **A reported section will not redraft**: only the Desk, Executive Summary, Looking Ahead and One Question are redraftable (the reported
  sections went through date and source rules). To change those, regenerate the whole issue.
- **Redraft says rejected, issue unchanged**: working as designed. The quality gate (junk, too short, wrong format, copy of the current text)
  refused a bad draft and kept the good one. It retries once by itself.
- **Funky model output**: the weaker lite models flatten the judgment sections. The log line "LITE MODEL" says when one answered.
- **A 429 on the first model with almost no requests today** usually means that model has no free quota on this key. Weekly Model Scout demotes it.

## Step 3: tests (run before and after any code change)
`python3 -W ignore scripts/test_pipeline.py` (redraft path with a stubbed Gemini: good drafts, junk, too short, copies, malformed, retries,
rollback, run log) and `python3 scripts/test_model_scout.py`. Both are offline and take seconds. The **Blog tests** workflow runs them
on every push to `scripts/` and every Monday; a red run means something drifted.

## Which file for what (only open the range you need; `grep -n "def name"`)
- Redraft logic and quality gates: `scripts/redraft_section.py` (check_text, verify_written, redraft)
- Error codes and the run log: `scripts/runlog.py`
- Prompts and the section specs: `scripts/gemini.py` (`_SPEC_*`, `generate_section_redraft`, `_call_gemini`)
- Model order and scouting: `utils.resolve_model_order`, `scripts/model_scout.py`, `blog/model-config.json`
- Vendor research for "New in Your AI Subscription": `scripts/plan_research.py`
- Review page: `scripts/generate-preview-page.py`
- Workflows: `.github/workflows/` (redraft-section, regenerate-blog, monthly-blog, approve-blog, discard-blog, model-scout, blog-tests, blog-health)

## Changing a section list
The redraftable sections live in `gemini.REDRAFTABLE_SECTIONS` AND the hand-kept choice list in `redraft-section.yml`; `test_pipeline.py`
fails if they disagree.

## Pipeline health page (from the review page, in both states)
`/blog/staging/health.html` (hand-kept static page, never regenerated by the pipeline). Linked from the review page top bar
("Pipeline health") and from the "Nothing pending" page. It shows the last run's result or failure with the plain next step,
the latest run of every blog workflow, the last 20 events from `run-log.json`, and buttons to run the health report, the tests and the model scout.
