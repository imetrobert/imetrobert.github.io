import argparse
import os
import requests

def generate_blog(model_name, api_key):
    url = "https://api.gemini.google/v1beta/generateContent"
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "model": model_name,
        "prompt": "Write a blog post about using AI in business.",
        "maxTokens": 1024,
    }

    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json()["content"]
    else:
        raise Exception(f"Gemini API error {response.status_code}: {response.text}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate blog using Gemini API")
    parser.add_argument("--model", default="gemini-2.5-flash-lite", help="Gemini model to use")
    args = parser.parse_args()
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise Exception("GEMINI_API_KEY environment variable not set")

    try:
        blog_content = generate_blog(args.model, api_key)
        with open("blog/posts/latest.md", "w") as f:
            f.write(blog_content)
        print("Blog post generated successfully!")
    except Exception as e:
        print(f"Failed to generate blog post: {e}")
        exit(1)
