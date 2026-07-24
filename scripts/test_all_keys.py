#!/usr/bin/env python3
"""
test_all_keys.py
Run via: python3 scripts/test_all_keys.py
Tests GEMINI_API_KEY and GITHUB_TOKEN.
"""

import os
import sys
import requests

GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
BLUE   = "\033[34m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):     print(f"  {GREEN}✅ PASS{RESET}  {msg}")
def fail(msg):   print(f"  {RED}❌ FAIL{RESET}  {msg}")
def warn(msg):   print(f"  {YELLOW}⚠️  WARN{RESET}  {msg}")
def info(msg):   print(f"  {BLUE}ℹ️  INFO{RESET}  {msg}")
def header(msg): print(f"\n{BOLD}{'─'*55}\n  {msg}\n{'─'*55}{RESET}")

results = {}


# ══════════════════════════════════════════════════════════════════
# 1. GEMINI API KEY
# ══════════════════════════════════════════════════════════════════
header("1 / 2  —  Gemini API Key  (GEMINI_API_KEY)")

gemini_key = os.environ.get("GEMINI_API_KEY", "")

if not gemini_key:
    fail("GEMINI_API_KEY secret is not set — this is REQUIRED")
    results["gemini"] = False
else:
    info(f"Key present  (prefix: {gemini_key[:8]}...  length: {len(gemini_key)})")

    if not gemini_key.startswith("AIza"):
        warn("Key doesn't start with 'AIza' — Gemini keys usually do. Double-check.")

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={gemini_key}"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            models = r.json().get("models", [])
            generative = [
                m["name"] for m in models
                if "generateContent" in m.get("supportedGenerationMethods", [])
            ]
            gemini2 = [m for m in generative if "gemini-2" in m]
            ok(f"Key is valid — {len(generative)} generative models available")
            if gemini2:
                ok(f"Gemini 2.x models found: {', '.join(gemini2[:3])}")
            else:
                warn("No Gemini 2.x models found — blog generator prefers gemini-2.5-flash")
            results["gemini"] = True
        elif r.status_code == 400:
            fail("Key rejected (400 Bad Request) — key is malformed or invalid")
            info(f"Response: {r.text[:300]}")
            results["gemini"] = False
        elif r.status_code == 403:
            fail("Forbidden (403) — key may be restricted by IP or domain policy")
            info(f"Response: {r.text[:300]}")
            results["gemini"] = False
        elif r.status_code == 429:
            warn("Rate limited (429) — key is valid but daily quota may be exhausted")
            info("Check: https://aistudio.google.com/app/apikey (bar chart icon)")
            results["gemini"] = True
        else:
            fail(f"Unexpected status {r.status_code}")
            info(f"Response: {r.text[:300]}")
            results["gemini"] = False
    except requests.exceptions.Timeout:
        fail("Request timed out — network issue from GitHub Actions")
        results["gemini"] = False
    except Exception as e:
        fail(f"Exception: {e}")
        results["gemini"] = False

    if results.get("gemini"):
        print()
        info("Running a quick generation test with gemini-2.0-flash...")
        gen_url = (
            "https://generativelanguage.googleapis.com/v1beta/models"
            f"/gemini-2.0-flash:generateContent?key={gemini_key}"
        )
        payload = {
            "contents": [{"role": "user", "parts": [{"text": "Reply with exactly: KEY_WORKS"}]}],
            "generationConfig": {"maxOutputTokens": 10, "temperature": 0}
        }
        try:
            r = requests.post(gen_url, json=payload, timeout=30)
            if r.status_code == 200:
                text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                ok(f"Generation test passed — model replied: '{text}'")
            elif r.status_code == 429:
                warn("Generation rate-limited (429) — quota exhausted for today")
            else:
                warn(f"Generation test returned {r.status_code}: {r.text[:200]}")
        except Exception as e:
            warn(f"Generation test exception: {e}")


# ══════════════════════════════════════════════════════════════════
# 2. GITHUB TOKEN + file checks
# ══════════════════════════════════════════════════════════════════
header("2 / 2  —  GitHub Token & Workflow Permissions  (GITHUB_TOKEN)")

repo     = os.environ.get("REPO", "")
gh_token = os.environ.get("GITHUB_TOKEN_TEST", "")

if not gh_token:
    fail("GITHUB_TOKEN is missing — this should never happen in GitHub Actions")
    results["github"] = False
else:
    info(f"GITHUB_TOKEN present (length: {len(gh_token)})")

    try:
        r = requests.get(
            f"https://api.github.com/repos/{repo}",
            headers={
                "Authorization": f"Bearer {gh_token}",
                "Accept": "application/vnd.github+json"
            },
            timeout=15
        )
        if r.status_code == 200:
            ok(f"Repo access confirmed: {r.json().get('full_name')}")
        else:
            warn(f"Repo check returned {r.status_code} — token may have limited scope")
    except Exception as e:
        warn(f"Repo check exception: {e}")

    print()
    info("Checking required workflow files exist in repo...")
    for wf in ["approve-blog.yml", "regenerate-blog.yml", "monthly-blog.yml", "test-api-keys.yml"]:
        try:
            r = requests.get(
                f"https://api.github.com/repos/{repo}/contents/.github/workflows/{wf}",
                headers={
                    "Authorization": f"Bearer {gh_token}",
                    "Accept": "application/vnd.github+json"
                },
                timeout=10
            )
            if r.status_code == 200:
                ok(f".github/workflows/{wf} exists")
            elif r.status_code == 404:
                fail(f".github/workflows/{wf} NOT FOUND — upload this file to your repo")
            else:
                warn(f".github/workflows/{wf} — check returned {r.status_code}")
        except Exception as e:
            warn(f"Could not check {wf}: {e}")

    print()
    info("Checking required script files exist in repo...")
    for sc in [
        "scripts/generate-blog.py",
        "scripts/generate-preview-page.py",
        "scripts/test_all_keys.py",
        "scripts/requirements.txt"
    ]:
        try:
            r = requests.get(
                f"https://api.github.com/repos/{repo}/contents/{sc}",
                headers={
                    "Authorization": f"Bearer {gh_token}",
                    "Accept": "application/vnd.github+json"
                },
                timeout=10
            )
            if r.status_code == 200:
                ok(f"{sc} exists")
            elif r.status_code == 404:
                fail(f"{sc} NOT FOUND — upload this file to your repo")
            else:
                warn(f"{sc} — check returned {r.status_code}")
        except Exception as e:
            warn(f"Could not check {sc}: {e}")

    results["github"] = True


# ══════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════
print(f"\n{BOLD}{'='*55}")
print("  SUMMARY")
print(f"{'='*55}{RESET}\n")

checks = [
    ("GEMINI_API_KEY", results.get("gemini"), "required", "Blog generation will fail without this"),
    ("GITHUB_TOKEN",   results.get("github"), "required", "Workflow triggering won't work"),
]

all_required_pass = True
for name, result, importance, consequence in checks:
    if result is True:
        print(f"  {GREEN}✅{RESET}  {BOLD}{name}{RESET}")
    elif result is False:
        print(f"  {RED}❌{RESET}  {BOLD}{name}{RESET}  ({importance})")
        print(f"       → {consequence}")
        if importance == "required":
            all_required_pass = False
    else:
        print(f"  {YELLOW}—{RESET}   {BOLD}{name}{RESET}  (not set — optional)")
        print(f"       → {consequence}")

print()

if all_required_pass:
    print(f"{GREEN}{BOLD}All required keys are working. Your blog system is ready to go.{RESET}")
    print(f"{YELLOW}No email notifications — check the preview URL in the Actions run summary each month.{RESET}")
else:
    print(f"{RED}{BOLD}One or more required keys failed. Fix the issues above.{RESET}")
    sys.exit(1)
