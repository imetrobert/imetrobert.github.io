#!/usr/bin/env python3
"""
Test script to debug Perplexity API connection
Run this to test your API key and connection before running the main script
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
    
    # Test with minimal payload
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Start with the most basic request possible
    test_payloads = [
        {
            "model": "llama-3.1-sonar-small-128k-online",
            "messages": [{"role": "user", "content": "Hello, write a brief paragraph about AI."}],
            "max_tokens": 100
        },
        {
            "model": "llama-3.1-sonar-large-128k-online",
            "messages": [{"role": "user", "content": "Hello, write a brief paragraph about AI."}],
            "max_tokens": 100
        },
        {
            "model": "llama-3.1-8b-instruct",
            "messages": [{"role": "user", "content": "Hello, write a brief paragraph about AI."}],
            "max_tokens": 100
        }
    ]
    
    for i, payload in enumerate(test_payloads):
        print(f"\n🧪 Test {i+1}: {payload['model']}")
        print(f"📤 Request URL: {url}")
        print(f"📋 Payload: {json.dumps(payload, indent=2)}")
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            print(f"📊 Status Code: {response.status_code}")
            print(f"📄 Response Headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                data = response.json()
                print("✅ Success!")
                print(f"🎯 Response: {json.dumps(data, indent=2)}")
                return True
            else:
                print(f"❌ Error {response.status_code}")
                print(f"📝 Response: {response.text}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")
        except json.JSONDecodeError as e:
            print(f"❌ JSON decode error: {e}")
            print(f"📝 Raw response: {response.text}")
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
        print("1. Verify your API key is correct")
        print("2. Check your Perplexity Pro account status")
        print("3. Ensure you have API access enabled")
        print("4. Try different models if some are restricted")
