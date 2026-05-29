#!/usr/bin/env python3
"""Verifies GEMINI_API_KEY is set and valid. Called by monthly-blog.yml."""
import os, sys, requests

key = os.environ.get("GEMINI_API_KEY", "")
if not key:
    print("ERROR: GEMINI_API_KEY is empty")
    sys.exit(1)

url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
r = requests.get(url, timeout=15)
if r.status_code == 200:
    print("API key VALID")
else:
    print(f"ERROR: {r.status_code}: {r.text[:200]}")
    sys.exit(1)
