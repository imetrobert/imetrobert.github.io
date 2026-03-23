#!/usr/bin/env python3
"""
test_gemini.py  —  verify your Gemini API key works before running the blog generator.
Usage: run via GitHub Actions workflow_dispatch (main.yml) or locally.
"""

import os
import requests
import json

def test_gemini_api():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY environment variable not set")
        return False

    print("API Key found: " + api_key[:10] + "...")

    base_url = "https://generativelanguage.googleapis.com/v1beta/models"
    models_to_try = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.0-flash-lite"]

    for model in models_to_try:
        url = f"{base_url}/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": "Write one sentence about AI innovation in Canada."}]
                }
            ],
            "generationConfig": {
                "maxOutputTokens": 100,
                "temperature": 0.7
            }
        }

        print(f"\nTesting model: {model}")
        try:
            response = requests.post(url, json=payload, timeout=30)
            print("Status Code: " + str(response.status_code))

            if response.status_code == 200:
                data = response.json()
                text = data['candidates'][0]['content']['parts'][0]['text']
                print("SUCCESS! Response: " + text[:200])
                print("Working model: " + model)
                return True
            else:
                print("Error " + str(response.status_code) + ": " + response.text[:300])

        except Exception as e:
            print("Failed: " + str(e))

    return False

if __name__ == "__main__":
    print("Testing Gemini API Connection...")
    print("=" * 50)

    success = test_gemini_api()

    if success:
        print("\nAPI connection test PASSED!")
        print("You can now run the blog generation workflow.")
    else:
        print("\nAPI connection test FAILED!")
        print("\nTroubleshooting steps:")
        print("1. Go to https://aistudio.google.com/app/apikey")
        print("2. Create or copy your API key (starts with AIza...)")
        print("3. In GitHub: Settings > Secrets > Actions > update GEMINI_API_KEY")
        print("4. Free tier models: gemini-2.0-flash, gemini-1.5-flash, gemini-2.0-flash-lite")
