import argparse
import os
import requests
import json
from datetime import datetime
import re
import sys

def clean_filename(title):
    """Convert title to a clean filename"""
    clean_title = re.sub('<.*?>', '', title)
    clean_title = re.sub(r'[^a-zA-Z0-9\s]', '', clean_title)
    clean_title = re.sub(r'\s+', '-', clean_title.strip())
    return clean_title.lower()

def generate_blog_with_perplexity(api_key, topic=None):
    """Generate blog content using Perplexity API"""
    current_date = datetime.now().strftime("%B %Y")
    if not topic:
        topic = f"Latest AI innovations and breakthroughs in business applications for {current_date}"
    
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    models_to_try = [
        "sonar-pro",
        "sonar-medium-online", 
        "sonar-small-online",
        "sonar-medium-chat",
        "sonar-small-chat"
    ]
    
    for model in models_to_try:
        print(f"Trying Perplexity model: {model}")
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are Robert Simon, an AI expert and digital transformation leader "
                        "with 25+ years of experience. Write authoritative, insightful blog posts "
                        "about AI innovations and practical business applications."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"Write a comprehensive blog post about: {topic}. "
                        "Include key technological advances, business applications, real-world use cases, "
                        "and implementation guidance. Target audience: business leaders and executives."
                    )
                }
            ],
            "max_tokens": 2000,
            "temperature": 0.7
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            print(f"API status code: {response.status_code}")
            
            if response.status_code != 200:
                print(f"❌ Failed model {model}: {response.text}")
                continue
            
            data = response.json()
            if 'choices' in data and len(data['choices']) > 0:
                content = data['choices'][0]['message']['content'].strip()
                if not content:
                    print("❌ API returned empty content")
                    continue
                
                print(f"✅ Content received from model {model} ({len(content)} characters)")
                return {
                    "content": content,
                    "citations": data.get("citations", []),
                    "usage": data.get("usage", {})
                }
            else:
                print(f"❌ Unexpected response structure: {data}")
                continue
        
        except requests.exceptions.RequestException as e:
            print(f"❌ Request exception with model {model}: {e}")
            continue
        except Exception as e:
            print(f"❌ Unexpected error with model {model}: {e}")
            continue
    
    raise Exception("All Perplexity models failed to generate content")

def extract_title_and_excerpt(content):
    """Extract title and excerpt from generated content"""
    lines = content.split("\n")
    title = "AI Insights"
    excerpt = ""
    for line in lines:
        line = line.strip()
        if line and not title.startswith("AI Insights"):
            if line.startswith("#") or (len(line) < 100 and not line.endswith(".")):
                title = line.lstrip("# ").strip()
        if line and len(line) > 50 and not excerpt:
            excerpt = line[:200] + "..." if len(line) > 200 else line
            break
    if not excerpt:
        excerpt = "Insights into the latest AI innovations and their practical business applications."
    return title, excerpt

def create_html_blog_post(content, title, excerpt, citations=None):
    """Convert content to HTML format using the blog template"""
    current_date = datetime.now().strftime("%B %d, %Y")
    template_path = "blog/templates/blog-template.html"
    
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()
    except FileNotFoundError:
        template = create_basic_template()
    
    def format_content(text):
        text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
        text = re.sub(r'\n\n', '</p><p>', text)
        return f"<p>{text}</p>"
    
    html_content = template.replace("{{TITLE}}", title)
    html_content = html_content.replace("{{DATE}}", current_date)
    html_content = html_content.replace("{{EXCERPT}}", excerpt)
    html_content = html_content.replace("{{TECH_ADVANCES}}", format_content(content))
    html_content = html_content.replace("{{BUSINESS_APPS}}", format_content(content))
    html_content = html_content.replace("{{USE_CASES}}", format_content(content))
    html_content = html_content.replace("{{IMPLEMENTATION}}", format_content(content))
    
    return html_content

def create_basic_template():
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{TITLE}} - Robert Simon AI Insights</title>
</head>
<body>
    <h1>{{TITLE}}</h1>
    <p>Published on {{DATE}}</p>
    <p><em>{{EXCERPT}}</em></p>
    <div>{{TECH_ADVANCES}}</div>
    <div>{{BUSINESS_APPS}}</div>
    <div>{{USE_CASES}}</div>
    <div>{{IMPLEMENTATION}}</div>
</body>
</html>"""

def main():
    parser = argparse.ArgumentParser(description="Generate blog using Perplexity API")
    parser.add_argument("--topic", help="Custom topic for the blog post")
    parser.add_argument("--output", default="staging", choices=["staging", "posts"],
                        help="Output directory (staging for review, posts for direct publish)")
    args = parser.parse_args()
    
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        print("❌ PERPLEXITY_API_KEY environment variable not set")
        sys.exit(1)
    
    try:
        print("Generating blog post with Perplexity AI...")
        result = generate_blog_with_perplexity(api_key, args.topic)
        
        title, excerpt = extract_title_and_excerpt(result["content"])
        print(f"Title extracted: {title}")
        
        html_content = create_html_blog_post(result["content"], title, excerpt, result.get("citations"))
        
        current_date = datetime.now().strftime("%Y-%m-%d")
        filename_html = f"{current_date}-{clean_filename(title)}.html"
        filename_md = f"{current_date}-{clean_filename(title)}.md"
        
        output_dir = os.path.join("blog", args.output)
        os.makedirs(output_dir, exist_ok=True)
        
        path_html = os.path.join(output_dir, filename_html)
        path_md = os.path.join(output_dir, filename_md)
        
        with open(path_html, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        with open(path_md, "w", encoding="utf-8") as f:
            f.write(f"# {title}\n\n{excerpt}\n\n{result['content']}")
        
        print(f"✅ Blog post HTML saved to: {path_html}")
        print(f"✅ Blog post Markdown saved to: {path_md}")
        
        if result.get("citations"):
            print(f"Sources cited: {len(result['citations'])}")
        
        print("Blog post generation complete!")
    
    except Exception as e:
        print(f"❌ Failed to generate blog post: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
