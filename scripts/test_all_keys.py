#!/usr/bin/env python3
"""
test_all_keys.py
Run via: python3 scripts/test_all_keys.py
Tests GEMINI_API_KEY, RESEND_API_KEY, NOTIFICATION_EMAIL, and GITHUB_TOKEN.
"""

import os
import re
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
header("1 / 4  —  Gemini API Key  (GEMINI_API_KEY)")

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
# 2. RESEND API KEY
# ══════════════════════════════════════════════════════════════════
header("2 / 4  —  Resend Email Key  (RESEND_API_KEY)")

resend_key = os.environ.get("RESEND_API_KEY", "")

if not resend_key:
    warn("RESEND_API_KEY is not set — email notifications will be skipped")
    info("Set this secret to receive monthly email reminders to review your blog post")
    info("Sign up free at: https://resend.com")
    results["resend"] = None
else:
    info(f"Key present  (prefix: {resend_key[:6]}...  length: {len(resend_key)})")

    if not resend_key.startswith("re_"):
        warn("Key doesn't start with 're_' — Resend keys should. Double-check.")

    try:
        r = requests.get(
            "https://api.resend.com/domains",
            headers={"Authorization": f"Bearer {resend_key}"},
            timeout=15
        )
        if r.status_code == 200:
            domains = r.json().get("data", [])
            ok(f"Key is valid — account has {len(domains)} domain(s) configured")
            if domains:
                for d in domains:
                    status = d.get("status", "unknown")
                    name   = d.get("name", "?")
                    if status == "verified":
                        ok(f"Domain '{name}' is verified")
                    else:
                        warn(f"Domain '{name}' status: {status} — emails may not send until verified")
                        info("Go to resend.com → Domains to complete verification")
            else:
                warn("No domains configured — you must verify a sending domain")
                info("Go to resend.com → Domains → Add Domain → add imetrobert.com")
            results["resend"] = True
        elif r.status_code == 401:
            fail("Unauthorized (401) — key is invalid or has been revoked")
            info("Create a new key at: https://resend.com/api-keys")
            results["resend"] = False
        elif r.status_code == 403:
            fail("Forbidden (403) — key may lack required permissions")
            info("Re-create the key with 'Full access' or 'Sending access'")
            results["resend"] = False
        else:
            fail(f"Unexpected status {r.status_code}: {r.text[:200]}")
            results["resend"] = False
    except Exception as e:
        fail(f"Exception: {e}")
        results["resend"] = False


# ══════════════════════════════════════════════════════════════════
# 3. NOTIFICATION EMAIL
# ══════════════════════════════════════════════════════════════════
header("3 / 4  —  Notification Email  (NOTIFICATION_EMAIL)")

notif_email = os.environ.get("NOTIFICATION_EMAIL", "")

if not notif_email:
    warn("NOTIFICATION_EMAIL is not set — required alongside RESEND_API_KEY")
    info("Add your email address as a GitHub secret named NOTIFICATION_EMAIL")
    results["email"] = None
else:
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    if re.match(pattern, notif_email):
        ok(f"Email address looks valid: {notif_email}")
        results["email"] = True
    else:
        fail(f"Email address looks malformed: '{notif_email}'")
        info("Expected format: you@example.com")
        results["email"] = False

    if results.get("resend") and not notif_email:
        warn("RESEND_API_KEY is set but NOTIFICATION_EMAIL is missing — no emails will send")
    if notif_email and not resend_key:
        warn("NOTIFICATION_EMAIL is set but RESEND_API_KEY is missing — no emails will send")


# ══════════════════════════════════════════════════════════════════
# 4. GITHUB TOKEN + file checks
# ══════════════════════════════════════════════════════════════════
header("4 / 4  —  GitHub Token & Workflow Permissions  (GITHUB_TOKEN)")

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
        "scripts/send-notification.py",
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
    ("GEMINI_API_KEY",     results.get("gemini"), "required", "Blog generation will fail without this"),
    ("RESEND_API_KEY",     results.get("resend"), "optional", "Email notifications won't work"),
    ("NOTIFICATION_EMAIL", results.get("email"),  "optional", "Email notifications won't work"),
    ("GITHUB_TOKEN",       results.get("github"), "required", "Workflow triggering won't work"),
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
    if results.get("resend") and results.get("email"):
        print(f"{GREEN}Email notifications are configured and will fire at end of month.{RESET}")
    else:
        print(f"{YELLOW}Email notifications are not fully configured (optional).{RESET}")
        print(f"{YELLOW}You'll still see the preview URL in the Actions run summary.{RESET}")
else:
    print(f"{RED}{BOLD}One or more required keys failed. Fix the issues above.{RESET}")
    sys.exit(1)
