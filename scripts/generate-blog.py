import argparse
import os
import requests
import json
import re
import sys
import time
from datetime import datetime
from bs4 import BeautifulSoup

def clean_filename(title):
    clean_title = re.sub('<.*?>', '', title)
    clean_title = re.sub(r'[^a-zA-Z0-9\s]', '', clean_title)
    clean_title = re.sub(r'\s+', '-', clean_title.strip())
    return clean_title.lower()

def clean_perplexity_content(content):
    """Cleans citations and specific formatting from AI responses"""
    content = re.sub(r'\[\d+\]', '', content)
    content = re.sub(r'\s*\(\d+\)\s*', ' ', content)
    content = re.sub(r'^\s*#{1,6}\s*', '', content, flags=re.MULTILINE)
    content = re.sub(r'•\s*[-–—]\s*', '', content)
    content = re.sub(r'[-–—]\s*•\s*', '', content)
    content = re.sub(r'•\s*•', '•', content)
    content = re.sub(r':\s*•', ':', content)
    content = re.sub(r'•\s*:', ':', content)
    content = re.sub(r'^•\s*(.*?)\s*•\s*$', r'\1', content, flags=re.MULTILINE)
    # Updated to handle March 2026 model naming conventions
    content = re.sub(r'Claude Opus 4\s+1', 'Claude Opus 4.1', content)
    content = re.sub(r'Claude Sonnet 4\s+1', 'Claude Sonnet 4.1', content)
    content = re.sub(r'GPT-4\s+1', 'GPT-4.1', content)
    content = re.sub(r'(\d+)\s+(\d+)%', r'\1.\2%', content)
    lines = content.split('\n')
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            cleaned_lines.append(line)
            continue
        list_pattern = r'^(\d+)\.\s+([A-Z].*)'
        if re.match(list_pattern, line):
            cleaned_lines.append(line)
        else:
            line = re.sub(r'^[•\-–—]+\s*', '', line)
            line = re.sub(r'\s*[•\-–—]+$', '', line)
            line = re.sub(r':\s*[•\-–—]+\s*([A-Z])', r': \1', line)
            line = re.sub(r'[•\-–—]+\s*:\s*([A-Z])', r': \1', line)
            line = re.sub(r'^:\s*([A-Z][^:]*?)\s*:•', r'\1:', line)
            if line:
                cleaned_lines.append(line)
    content = '\n'.join(cleaned_lines)
    content = re.sub(r' +', ' ', content)
    content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)
    return content.strip()

def generate_blog_with_gemini(api_key, topic=None):
    """Generate blog content using Gemini API via direct HTTP requests"""
    current_date = datetime.now()
    month_year = current_date.strftime("%B %Y")

    if not topic:
        topic_type = "monthly_ai"
    else:
        topic_lower = topic.lower()
        ai_keywords = ['ai', 'artificial intelligence', 'machine learning',
                       'automation', 'technology', 'digital', 'innovation']
        topic_type = "custom_ai" if any(k in topic_lower for k in ai_keywords) else "custom_business"

    BASE = "https://generativelanguage.googleapis.com/v1beta/models"
    
    # UPDATED FOR MARCH 2026: Using current stable and preview models
    # 3.1 Flash-Lite launched March 3, 2026, offering high speed for free tier
    models_to_try = [
        "gemini-3.1-flash-lite-preview", 
        "gemini-2.5-flash-lite", 
        "gemini-2.5-flash"
    ]

    if topic_type == "monthly_ai":
        prompt = f"""You are Robert Simon, AI Evangelist at Bell Canada, writing a monthly AI insights blog post for {month_year}.
Write in plain text only. Do not use any markdown, hashtags, asterisks, or special formatting symbols.
Structure the post with these plain-text section headings on their own lines:

Key AI Developments This Month
Impact on Canadian Businesses
Strategic Recommendations for Canadian Leaders
Canadian Business AI Adoption Metrics
Conclusion

Begin with one introduction paragraph before the first heading.
Key AI Developments This Month: list 10 AI news items from {month_year} with dates and company names.
Impact on Canadian Businesses: write 1-2 paragraphs on business implications for Canada.
Strategic Recommendations for Canadian Leaders: write 5 recommendations beginning with action verbs.
Canadian Business AI Adoption Metrics: include 3-5 Canadian AI adoption statistics with specific percentages.
Conclusion: write one strategic paragraph for Canadian business leaders."""
    else:
        prompt = f"""You are Robert Simon, AI Evangelist at Bell Canada, writing an AI blog post about: {topic}
Write in plain text only. No markdown, no hashtags, no asterisks.
Structure with the standard sections including Key AI Developments, Canadian Impact, and Metrics.
Plain text only throughout."""

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": 2048,
            "temperature": 0.7
        }
    }

    for attempt, model in enumerate(models_to_try):
        if attempt > 0:
            print(f"  Waiting 30s before trying next model to respect free tier RPM...")
            time.sleep(30)

        print(f"Trying model: {model} (attempt {attempt+1}/{len(models_to_try)})")
        url = f"{BASE}/{model}:generateContent?key={api_key}"

        try:
            response = requests.post(url, json=payload, timeout=120)
            
            if response.status_code == 429:
                print(f"  Rate limited on {model}. Switching models...")
                continue
            
            if response.status_code != 200:
                print(f"  Error {response.status_code}: {response.text[:200]}")
                continue

            data = response.json()
            raw_text = data['candidates'][0]['content']['parts'][0]['text'].strip()
            
            cleaned = clean_perplexity_content(raw_text)
            print(f"  SUCCESS: Generated {len(cleaned)} chars using {model}")
            
            return {
                "content": cleaned,
                "model_used": model,
                "topic_type": topic_type
            }

        except Exception as e:
            print(f"  Connection error with {model}: {e}")
            continue

    raise Exception("All current Gemini models failed. Check your API key or wait for quota reset.")

# Helper functions for file saving (as per your original script)
def extract_title_and_excerpt(content):
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    title = lines[0] if lines else "AI Insights"
    excerpt = lines[1][:150] + "..." if len(lines) > 1 else ""
    return title, excerpt

def create_html_blog_post(content, title, excerpt):
    return f"""<!DOCTYPE html><html><head><title>{title}</title></head>
    <body><h1>{title}</h1><p><i>{excerpt}</i></p><div class='content'>{content.replace('\\n', '<br>')}</div></body></html>"""

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", help="Optional blog topic")
    parser.add_argument("--output", default="posts", help="Output subdirectory")
    args = parser.parse_args()

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY not found in environment variables.")
        sys.exit(1)

    try:
        result = generate_blog_with_gemini(api_key, args.topic)
        title, excerpt = extract_title_and_excerpt(result["content"])
        html_content = create_html_blog_post(result["content"], title, excerpt)
        
        current_date = datetime.now().strftime("%Y-%m-%d")
        filename = f"{current_date}-{clean_filename(title)}.html"
        
        os.makedirs(os.path.join("blog", args.output), exist_ok=True)
        path = os.path.join("blog", args.output, filename)
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        print(f"Blog post saved successfully to {path}")
        
    except Exception as e:
        print(f"Workflow Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
