#!/usr/bin/env python3
"""
test_keys_summary.py
Writes the GitHub Actions Step Summary table.
Run via: python3 scripts/test_keys_summary.py
"""

import os

gemini = "✅ Set" if os.environ.get("GEMINI_API_KEY") else "❌ Missing"
repo   = os.environ.get("GITHUB_REPOSITORY", "")

summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "")
if summary_path:
    with open(summary_path, "a") as f:
        f.write(f"""## 🔑 API Key Test Results

| Secret | Status | Notes |
|--------|--------|-------|
| `GEMINI_API_KEY` | {gemini} | Required — blog generation |
| `GITHUB_TOKEN` | ✅ Always present | Built-in Actions token |

> See the job log above for detailed test output and any specific error messages.
> No email notifications — check the preview URL in the monthly-blog.yml run summary instead.

### Fix links
- **Gemini key:** https://aistudio.google.com/app/apikey
- **Add GitHub secrets:** https://github.com/{repo}/settings/secrets/actions
""")
    print("Step summary written.")
else:
    print("GITHUB_STEP_SUMMARY not set — skipping (normal when running locally).")
