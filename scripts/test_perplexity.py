#!/usr/bin/env python3
"""
Test script to debug Perplexity API connection.
Run this to verify your API key and connection before running the main script.
"""

import os
import requests
import json

def test_perplexity_api():
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        print("❌ Error: PERPLEXITY_API_KEY environment variable not set")
        return False

    print(f"🔑 API Key found: {api_key[:10]}...")

    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # FIX: Updated to current valid Perplexity Sonar model names (2026)
    # The llama-3.1-sonar-* and pplx-* identifiers have been deprecated.
    # Current Sonar family: sonar, sonar-pro, sonar-reasoning, sonar-reasoning-pro, sonar-deep-research
    test_payloads = [
        {
            "model": "sonar-pro",
            "messages": [{"role": "user", "content": "Write one sentence about AI innovation in Canada."}],
            "max_tokens": 100
        },
        {
            "model": "sonar",
            "messages": [{"role": "user", "content": "Write one sentence about AI innovation in Canada."}],
            "max_tokens": 100
        },
        {
            "model": "sonar-reasoning",
            "messages": [{"role": "user", "content": "Write one sentence about AI innovation in Canada."}],
            "max_tokens": 100
        }
    ]

    for i, payload in enumerate(test_payloads):
        print(f"\n🧪 Test {i+1}: {payload['model']}")
        print(f"📤 Request URL: {url}")

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)

            print(f"📊 Status Code: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
                print(f"✅ Success! Response: {content[:200]}")
                print(f"   Model working: {payload['model']}")
                return True
            else:
                print(f"❌ Error {response.status_code}: {response.text[:300]}")

        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")
        except json.JSONDecodeError as e:
            print(f"❌ JSON decode error: {e}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")

    return False

if __name__ == "__main__":
    print("🚀 Testing Perplexity API Connection...")
    print("=" * 50)

    success = test_perplexity_api()

    if success:
        print("\n✅ API connection test PASSED!")
        print("You can now run the main blog generation script.")
    else:
        print("\n❌ API connection test FAILED!")
        print("\nTroubleshooting steps:")
        print("1. Verify your PERPLEXITY_API_KEY GitHub Actions secret is current")
        print("2. Check your Perplexity account billing / API credits at perplexity.ai")
        print("3. Confirm API access is enabled in your Perplexity dashboard")
        print("4. Current valid model names: sonar-pro, sonar, sonar-reasoning")
        print("   (Old names like llama-3.1-sonar-* and sonar-medium-online are deprecated)")
