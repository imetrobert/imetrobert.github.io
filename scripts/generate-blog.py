import argparse
import os
import requests
import json
import re
import sys
from datetime import datetime
from bs4 import BeautifulSoup

def clean_filename(title):
    """Convert title to a clean filename"""
    clean_title = re.sub('<.*?>', '', title)
    clean_title = re.sub(r'[^a-zA-Z0-9\s]', '', clean_title)
    clean_title = re.sub(r'\s+', '-', clean_title.strip())
    return clean_title.lower()

def generate_blog_with_perplexity(api_key, topic=None):
    """Generate blog content using Perplexity API with structured format"""
    current_date = datetime.now().strftime("%B %Y")
    if not topic:
        topic = f"Latest AI innovations and breakthroughs in business applications for {current_date}"
    
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    models_to_try = [
        "llama-3.1-sonar-large-128k-online",
        "llama-3.1-sonar-small-128k-online", 
        "llama-3.1-sonar-huge-128k-online"
    ]
    
    # Enhanced prompt for structured content
    system_prompt = """You are Robert Simon, an AI expert and digital transformation leader with 25+ years of experience. Write authoritative, insightful blog posts about AI innovations and practical business applications.

IMPORTANT: Structure your response in exactly these sections:
1. INTRODUCTION: Brief overview paragraph
2. KEY TECHNOLOGICAL ADVANCES: 3-4 major technological developments
3. BUSINESS APPLICATIONS: 4-5 real-world business use cases
4. IMPLEMENTATION GUIDANCE: 5 numbered steps for business leaders
5. INSIGHTS FOR EXECUTIVES: 3 key strategic insights
6. CONCLUSION: Final strategic imperative paragraph

For each section, use clear bullet points or numbered lists. Be specific about companies, technologies, and actionable advice."""
    
    user_prompt = f"""Write a comprehensive blog post about: {topic}

Structure the content with these exact sections:
- Introduction paragraph
- Key Technological Advances (3-4 items with specific examples)
- Business Applications and Real-World Use Cases (4-5 specific examples)
- Implementation Guidance for Business Leaders (5 numbered actionable steps)  
- Insights for Executives (3 strategic insights)
- Conclusion (strategic imperative)

Focus on practical, actionable insights for business leaders. Include specific company examples and technologies where possible."""
    
    for model in models_to_try:
        print(f"Found {len(html_files)} HTML files in posts directory")

    # Sort by filename (which should include date) in reverse order for newest first
    for file in sorted(html_files, reverse=True):
        file_path = os.path.join(posts_dir, file)
        try:
            post_info = extract_post_info(file_path)
            posts.append(post_info)
            print(f"Processed: {file} -> {post_info['title']}")
        except Exception as e:
            print(f"Error processing {file}: {e}")
            continue

    if not posts:
        print("No valid posts could be processed")
        return

    # Generate JavaScript data
    posts_js = json.dumps(posts, indent=8)
    
    # Read the blog index template
    try:
        with open(index_file, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading blog index: {e}")
        return
    
    # Replace the fetchBlogPosts function with real data
    new_function = f'''async function fetchBlogPosts() {{
            return {posts_js};
        }}'''
    
    # Find and replace the fetchBlogPosts function
    pattern = r'async function fetchBlogPosts\(\) \{[^}]+\}[^}]+\}'
    content = re.sub(pattern, new_function, content, flags=re.DOTALL)
    
    # Write updated file
    try:
        with open(index_file, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Blog index updated with {len(posts)} posts")
    except Exception as e:
        print(f"Error writing blog index: {e}")

def update_homepage_preview():
    """Update homepage blog preview section"""
    posts_dir = "blog/posts"
    homepage_file = "index.html"
    
    if not os.path.exists(posts_dir) or not os.path.exists(homepage_file):
        print("Posts directory or homepage not found")
        return

    # Get posts
    posts = []
    html_files = [f for f in os.listdir(posts_dir) if f.endswith(".html")]
    
    for file in sorted(html_files, reverse=True)[:3]:  # Get latest 3 posts
        file_path = os.path.join(posts_dir, file)
        try:
            posts.append(extract_post_info(file_path))
        except Exception as e:
            print(f"Error processing {file} for homepage: {e}")
            continue

    if not posts:
        return

    # Read homepage
    try:
        with open(homepage_file, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")
    except Exception as e:
        print(f"Error reading homepage: {e}")
        return

    # Find blog-preview div
    preview_div = soup.find("div", {"id": "blog-preview"})
    if preview_div:
        # Build blog cards HTML
        cards_html = ""
        for post in posts:
            cards_html += f'''
            <div class="blog-card">
                <h4>{post['title']}</h4>
                <div class="blog-date">{post['date']}</div>
                <p class="blog-excerpt">{post['excerpt']}</p>
                <a href="/blog/posts/{post['filename']}" class="blog-read-more">Read Full Post →</a>
            </div>'''

        # Clear and update
        preview_div.clear()
        preview_div.append(BeautifulSoup(cards_html, "html.parser"))
        
        # Save updated homepage
        try:
            with open(homepage_file, "w", encoding="utf-8") as f:
                f.write(str(soup.prettify(formatter="html")))
            print(f"Homepage preview updated with {len(posts)} posts")
        except Exception as e:
            print(f"Error writing homepage: {e}")
    else:
        print("Could not find blog-preview div in homepage")

def main():
    parser = argparse.ArgumentParser(description="Generate blog using Perplexity API")
    parser.add_argument("--topic", help="Custom topic for the blog post")
    parser.add_argument("--output", default="staging", choices=["staging", "posts"],
                        help="Output directory (staging for review, posts for direct publish)")
    args = parser.parse_args()
    
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        print("PERPLEXITY_API_KEY environment variable not set")
        sys.exit(1)
    
    try:
        print("Generating blog post with Perplexity AI...")
        result = generate_blog_with_perplexity(api_key, args.topic)
        
        title, excerpt = extract_title_and_excerpt(result["content"])
        print(f"Title extracted: {title}")
        
        html_content = create_html_blog_post(result["content"], title, excerpt)
        
        current_date = datetime.now().strftime("%Y-%m-%d")
        filename_html = f"{current_date}-{clean_filename(title)}.html"
        
        output_dir = os.path.join("blog", args.output)
        os.makedirs(output_dir, exist_ok=True)
        
        path_html = os.path.join(output_dir, filename_html)
        
        with open(path_html, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        # Also save to latest.html for your current setup
        latest_path = os.path.join("blog", "posts", "latest.html")
        os.makedirs(os.path.dirname(latest_path), exist_ok=True)
        with open(latest_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        print(f"Blog post HTML saved to: {path_html}")
        print(f"Latest post updated at: {latest_path}")
        
        if result.get("citations"):
            print(f"Sources cited: {len(result['citations'])}")
        
        # Update blog index and homepage
        try:
            update_blog_index()
            print("Blog index page updated")
        except Exception as e:
            print(f"Failed to update blog index: {e}")
        
        try:
            update_homepage_preview()
            print("Homepage preview updated")
        except Exception as e:
            print(f"Failed to update homepage preview: {e}")
        
        print("Blog post generation complete!")
    
    except Exception as e:
        print(f"Failed to generate blog post: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print(f"Trying Perplexity model: {model}")
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": 2500,
            "temperature": 0.7
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            print(f"API status code: {response.status_code}")
            
            if response.status_code != 200:
                print(f"Failed model {model}: {response.text}")
                continue
            
            data = response.json()
            if 'choices' in data and len(data['choices']) > 0:
                content = data['choices'][0]['message']['content'].strip()
                if not content:
                    print("API returned empty content")
                    continue
                
                print(f"Content received from model {model} ({len(content)} characters)")
                return {
                    "content": content,
                    "citations": data.get("citations", []),
                    "usage": data.get("usage", {})
                }
            else:
                print(f"Unexpected response structure: {data}")
                continue
        
        except requests.exceptions.RequestException as e:
            print(f"Request exception with model {model}: {e}")
            continue
        except Exception as e:
            print(f"Unexpected error with model {model}: {e}")
            continue
    
    raise Exception("All Perplexity models failed to generate content")

def parse_structured_content(content):
    """Parse the structured content into sections"""
    sections = {
        'introduction': '',
        'tech_advances': [],
        'business_apps': [],
        'implementation': [],
        'insights': [],
        'conclusion': ''
    }
    
    # Split content into paragraphs
    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
    current_section = 'introduction'
    
    for para in paragraphs:
        para_lower = para.lower()
        
        # Detect section headers
        if 'key technological' in para_lower or 'technological advance' in para_lower:
            current_section = 'tech_advances'
            continue
        elif 'business application' in para_lower or 'real-world use' in para_lower:
            current_section = 'business_apps'
            continue
        elif 'implementation' in para_lower or 'guidance' in para_lower:
            current_section = 'implementation'
            continue
        elif 'insight' in para_lower and 'executive' in para_lower:
            current_section = 'insights'
            continue
        elif 'conclusion' in para_lower or 'strategic imperative' in para_lower:
            current_section = 'conclusion'
            continue
        
        # Add content to appropriate section
        if current_section == 'introduction' and not sections['introduction']:
            sections['introduction'] = para
        elif current_section == 'conclusion' and not sections['conclusion']:
            sections['conclusion'] = para
        elif current_section in ['tech_advances', 'business_apps', 'insights']:
            if para.startswith('-') or para.startswith('•') or para.startswith('*'):
                sections[current_section].append(para.lstrip('-•* '))
            elif ':' in para and len(para) > 50:  # Looks like a bullet point
                sections[current_section].append(para)
        elif current_section == 'implementation':
            if para[0].isdigit() or para.startswith('-') or para.startswith('•'):
                sections[current_section].append(para.lstrip('0123456789.-•* '))
    
    return sections

def create_html_blog_post(content, title, excerpt):
    """Convert content to HTML format using the complete template structure"""
    current_date = datetime.now().strftime("%B %d, %Y")
    
    # Parse the structured content
    sections = parse_structured_content(content)
    
    # Create the full HTML structure with embedded CSS
    html_template = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Insights - Latest Post | Robert Simon</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
    <style>
        :root {
            --primary-blue: #2563eb;
            --secondary-blue: #3b82f6;
            --accent-cyan: #06b6d4;
            --ai-purple: #8b5cf6;
            --dark-navy: #1e293b;
            --medium-gray: #64748b;
            --light-gray: #f1f5f9;
            --white: #ffffff;
            --gradient-primary: linear-gradient(135deg, #2563eb 0%, #06b6d4 100%);
            --gradient-card: linear-gradient(145deg, #ffffff 0%, #f8fafc 100%);
            --gradient-ai: linear-gradient(135deg, #2563eb 0%, #06b6d4 50%, #8b5cf6 100%);
            --font-primary: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            --font-mono: 'JetBrains Mono', 'Courier New', monospace;
            --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
            --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
            --shadow-lg: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1);
            --shadow-xl: 0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: var(--font-primary);
            background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
            color: var(--dark-navy);
            line-height: 1.6;
            min-height: 100vh;
            overflow-x: hidden;
        }

        .parallax-bg {
            position: fixed;
            top: 0;
            left: 0;
            width: 120%;
            height: 120%;
            pointer-events: none;
            z-index: -1;
            background: 
                radial-gradient(circle at 30% 70%, rgba(37, 99, 235, 0.03) 0%, transparent 50%),
                radial-gradient(circle at 70% 30%, rgba(6, 182, 212, 0.03) 0%, transparent 50%);
            animation: slowFloat 20s ease-in-out infinite;
        }

        @keyframes slowFloat {
            0%, 100% { transform: translate(0px, 0px) rotate(0deg); }
            25% { transform: translate(-5px, -10px) rotate(0.5deg); }
            50% { transform: translate(5px, -5px) rotate(-0.3deg); }
            75% { transform: translate(-3px, 8px) rotate(0.2deg); }
        }

        .ai-circuit {
            position: absolute;
            width: 100%;
            height: 100%;
            opacity: 0.08;
            background-image: 
                radial-gradient(circle at 25% 25%, #06b6d4 2px, transparent 2px),
                radial-gradient(circle at 75% 75%, #2563eb 1px, transparent 1px),
                linear-gradient(45deg, transparent 48%, rgba(6, 182, 212, 0.1) 49%, rgba(6, 182, 212, 0.1) 51%, transparent 52%),
                linear-gradient(-45deg, transparent 48%, rgba(37, 99, 235, 0.1) 49%, rgba(37, 99, 235, 0.1) 51%, transparent 52%);
            background-size: 50px 50px, 30px 30px, 20px 20px, 20px 20px;
            animation: aiFlow 15s ease-in-out infinite;
            pointer-events: none;
        }

        @keyframes aiFlow {
            0%, 100% { transform: translateX(0) translateY(0); }
            25% { transform: translateX(10px) translateY(-5px); }
            50% { transform: translateX(-5px) translateY(10px); }
            75% { transform: translateX(5px) translateY(-10px); }
        }

        .nav-bar {
            background: var(--white);
            padding: 1rem 0;
            box-shadow: var(--shadow-sm);
            position: sticky;
            top: 0;
            z-index: 100;
            backdrop-filter: blur(10px);
        }

        .nav-content {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .nav-link {
            color: var(--primary-blue);
            text-decoration: none;
            font-weight: 600;
            padding: 0.75rem 2rem;
            border-radius: 25px;
            background: linear-gradient(135deg, var(--primary-blue), var(--accent-cyan));
            color: white;
            transition: all 0.3s ease;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
        }

        .nav-link:hover {
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg);
        }

        .blog-meta {
            font-family: var(--font-mono);
            font-size: 0.85rem;
            color: var(--medium-gray);
            display: flex;
            align-items: center;
            gap: 1rem;
        }

        .header {
            background: var(--gradient-ai);
            color: white;
            padding: 4rem 0 3rem;
            position: relative;
            overflow: hidden;
        }

        .header::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: 
                radial-gradient(circle at 20% 80%, rgba(139, 92, 246, 0.3) 0%, transparent 50%),
                radial-gradient(circle at 80% 20%, rgba(6, 182, 212, 0.3) 0%, transparent 50%),
                radial-gradient(circle at 40% 40%, rgba(37, 99, 235, 0.2) 0%, transparent 50%);
            animation: aiFlow 12s ease-in-out infinite;
        }

        .header-content {
            max-width: 1000px;
            margin: 0 auto;
            padding: 0 2rem;
            text-align: center;
            position: relative;
            z-index: 1;
        }

        .header h1 {
            font-size: 3rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
            background: linear-gradient(45deg, #ffffff, #e0f2fe);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .header .subtitle {
            font-size: 1.2rem;
            font-weight: 500;
            opacity: 0.9;
            margin-bottom: 1.5rem;
        }

        .header .intro {
            font-size: 1.05rem;
            opacity: 0.85;
            max-width: 800px;
            margin: 0 auto;
            font-weight: 300;
            line-height: 1.7;
        }

        .container {
            max-width: 1000px;
            margin: 0 auto;
            padding: 3rem 2rem 4rem;
        }

        .article-container {
            background: var(--gradient-card);
            border-radius: 20px;
            box-shadow: var(--shadow-xl);
            overflow: hidden;
            border: 1px solid rgba(37, 99, 235, 0.1);
            position: relative;
        }

        .article-content {
            padding: 3rem;
            background: white;
        }

        .section {
            margin-bottom: 3rem;
        }

        .section-title {
            font-size: 1.8rem;
            color: var(--dark-navy);
            margin-bottom: 1.5rem;
            font-weight: 600;
            position: relative;
            padding-left: 1.5rem;
            line-height: 1.3;
        }

        .section-title::before {
            content: '';
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 4px;
            background: var(--gradient-primary);
            border-radius: 2px;
        }

        h3 {
            color: var(--primary-blue);
            font-size: 1.3rem;
            margin: 2rem 0 1rem 0;
            font-weight: 600;
            border-left: 4px solid var(--accent-cyan);
            padding-left: 15px;
            line-height: 1.4;
        }

        p {
            margin-bottom: 1.2rem;
            text-align: justify;
            word-spacing: normal;
            line-height: 1.7;
            color: var(--medium-gray);
            font-size: 1rem;
        }

        ul {
            margin-bottom: 1.5rem;
            padding-left: 0;
        }

        li {
            margin-bottom: 1.2rem;
            line-height: 1.7;
            color: var(--medium-gray);
            list-style: none;
            position: relative;
            padding-left: 2rem;
        }

        li::before {
            content: '▸';
            position: absolute;
            left: 0;
            color: var(--primary-blue);
            font-weight: 600;
            font-size: 1.1rem;
        }

        ol {
            margin-bottom: 1.5rem;
            padding-left: 0;
            counter-reset: list-counter;
        }

        ol li {
            counter-increment: list-counter;
            padding-left: 3rem;
            position: relative;
        }

        ol li::before {
            content: counter(list-counter);
            position: absolute;
            left: 0;
            top: 0;
            background: var(--gradient-primary);
            color: white;
            width: 2rem;
            height: 2rem;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            font-size: 0.9rem;
        }

        ol li ul li {
            margin-bottom: 0.8rem;
            padding-left: 1.5rem;
            counter-increment: none;
        }

        ol li ul li::before {
            content: '•';
            position: absolute;
            left: 0;
            color: var(--accent-cyan);
            font-weight: bold;
            background: none;
            width: auto;
            height: auto;
            border-radius: 0;
            font-size: 1.2rem;
        }

        strong {
            color: var(--dark-navy);
            font-weight: 600;
        }

        .conclusion {
            background: var(--gradient-ai);
            color: white;
            padding: 2.5rem;
            border-radius: 15px;
            margin-top: 3rem;
            position: relative;
            overflow: hidden;
        }

        .conclusion::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: 
                radial-gradient(circle at 20% 80%, rgba(139, 92, 246, 0.2) 0%, transparent 50%),
                radial-gradient(circle at 80% 20%, rgba(6, 182, 212, 0.2) 0%, transparent 50%);
            animation: aiFlow 15s ease-in-out infinite;
        }

        .conclusion p {
            color: rgba(255, 255, 255, 0.95);
            font-size: 1.1rem;
            font-weight: 500;
            position: relative;
            z-index: 1;
            margin-bottom: 0;
            text-align: left;
        }

        .conclusion strong {
            color: white;
        }

        @media (max-width: 768px) {
            .header h1 {
                font-size: 2.2rem;
            }

            .header .subtitle {
                font-size: 1.1rem;
            }

            .header .intro {
                font-size: 1rem;
            }

            .container {
                padding: 2rem 1rem 3rem;
            }

            .article-content {
                padding: 2rem 1.5rem;
            }

            .header {
                padding: 3rem 0 2rem;
            }

            .section-title {
                font-size: 1.5rem;
            }

            h3 {
                font-size: 1.2rem;
            }

            .nav-content {
                padding: 0 1rem;
                flex-direction: column;
                gap: 1rem;
                text-align: center;
            }
        }

        .fade-in {
            opacity: 0;
            transform: translateY(30px);
            animation: fadeInUp 0.8s ease forwards;
        }

        @keyframes fadeInUp {
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
    </style>
</head>
<body>
    <div class="parallax-bg"></div>

    <nav class="nav-bar">
        <div class="nav-content">
            <a href="/" class="nav-link">
                ← Back to Portfolio
            </a>
            <div class="blog-meta">
                <span>AI Innovation Series</span>
                <span>•</span>
                <span>{current_date}</span>
            </div>
        </div>
    </nav>

    <header class="header">
        <div class="header-content">
            <h1>{title}</h1>
            <div class="subtitle">{current_date} Business Intelligence Report</div>
            <div class="intro">
                {excerpt}
            </div>
        </div>
        <div class="ai-circuit"></div>
    </header>

    <div class="container">
        <article class="article-container fade-in">
            <div class="article-content">
                {content_sections}

                <div class="conclusion">
                    <p><strong>Strategic Imperative:</strong> {conclusion}</p>
                </div>
            </div>
        </article>
    </div>
</body>
</html>'''
    
    # Format content sections
    content_html = []
    
    # Introduction
    if sections['introduction']:
        content_html.append(f'''
                <div class="section">
                    <h2 class="section-title">Key Technological Advances</h2>
                    <p>{sections['introduction']}</p>
                </div>''')
    
    # Tech Advances
    if sections['tech_advances']:
        tech_items = '\n'.join([f'<li><strong>{item.split(":")[0]}:</strong> {":".join(item.split(":")[1:]).strip()}</li>' 
                               for item in sections['tech_advances'] if ':' in item])
        if tech_items:
            content_html.append(f'''
                <div class="section">
                    <h3>Key Technological Advances</h3>
                    <ul>
                        {tech_items}
                    </ul>
                </div>''')
    
    # Business Applications
    if sections['business_apps']:
        business_items = '\n'.join([f'<li><strong>{item.split(":")[0]}:</strong> {":".join(item.split(":")[1:]).strip()}</li>' 
                                   for item in sections['business_apps'] if ':' in item])
        if business_items:
            content_html.append(f'''
                <div class="section">
                    <h2 class="section-title">Business Applications and Real-World Use Cases</h2>
                    <ul>
                        {business_items}
                    </ul>
                </div>''')
    
    # Implementation Guidance
    if sections['implementation']:
        impl_items = '\n'.join([f'<li><strong>{item.split(":")[0] if ":" in item else f"Step {i+1}"}:</strong> {item.split(":", 1)[1].strip() if ":" in item else item}</li>' 
                               for i, item in enumerate(sections['implementation'])])
        if impl_items:
            content_html.append(f'''
                <div class="section">
                    <h2 class="section-title">Implementation Guidance for Business Leaders</h2>
                    <ol>
                        {impl_items}
                    </ol>
                </div>''')
    
    # Executive Insights
    if sections['insights']:
        insight_items = '\n'.join([f'<li><strong>{item.split(":")[0]}:</strong> {":".join(item.split(":")[1:]).strip()}</li>' 
                                  for item in sections['insights'] if ':' in item])
        if insight_items:
            content_html.append(f'''
                <div class="section">
                    <h2 class="section-title">Insights for Executives</h2>
                    <ul>
                        {insight_items}
                    </ul>
                </div>''')
    
    # Fill in the template
    conclusion_text = sections['conclusion'] if sections['conclusion'] else "Business leaders must act decisively to harness AI breakthroughs and drive strategic innovation."
    
    final_html = html_template.format(
        current_date=current_date,
        title=title,
        excerpt=excerpt,
        content_sections='\n'.join(content_html),
        conclusion=conclusion_text
    )
    
    return final_html

def extract_title_and_excerpt(content):
    """Extract title and excerpt from generated content"""
    lines = [line.strip() for line in content.split("\n") if line.strip()]
    title = "AI Insights"
    excerpt = ""
    
    for line in lines:
        # Look for title
        if line and not title.startswith("AI Insights"):
            if line.startswith("#") or (len(line) < 100 and not line.endswith(".")):
                title = line.lstrip("# ").strip()
                break
    
    # Find first substantial paragraph for excerpt
    for line in lines:
        if line and len(line) > 100 and not line.startswith("#"):
            excerpt = line[:250] + "..." if len(line) > 250 else line
            break
    
    if not excerpt:
        excerpt = "Transforming business through AI-driven innovation. Key technological advances, real-world applications, and strategic implementation guidance for digital leaders."
    
    return title, excerpt

def extract_post_info(html_file):
    """Extract title, date, and excerpt from an HTML blog post using new template structure"""
    with open(html_file, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    # Title: look for header h1 in the new template structure
    title_tag = None
    header_content = soup.find("div", class_="header-content")
    if header_content:
        title_tag = header_content.find("h1")
    else:
        title_tag = soup.find("h1")
    
    title = title_tag.get_text(strip=True) if title_tag else "AI Insights"

    # Date: look for blog-meta span in nav, then try other locations
    date_text = None
    
    # Try blog-meta in navigation
    blog_meta = soup.find("div", class_="blog-meta")
    if blog_meta:
        meta_text = blog_meta.get_text()
        # Extract date from "AI Innovation Series • September 26, 2025" format
        if "•" in meta_text:
            date_text = meta_text.split("•")[-1].strip()
    
    # Try subtitle in header
    if not date_text:
        subtitle = soup.find("div", class_="subtitle")
        if subtitle:
            subtitle_text = subtitle.get_text()
            # Extract date from "September 26, 2025 Business Intelligence Report" format
            date_match = re.search(r'([A-Za-z]+ \d{1,2}, \d{4})', subtitle_text)
            if date_match:
                date_text = date_match.group(1)
    
    # Fallback to filename parsing
    if not date_text:
        basename = os.path.basename(html_file)
        match = re.match(r"(\d{4}-\d{2}-\d{2})-", basename)
        if match:
            # Convert YYYY-MM-DD to readable format
            date_obj = datetime.strptime(match.group(1), "%Y-%m-%d")
            date_text = date_obj.strftime("%B %d, %Y")
        else:
            date_text = datetime.now().strftime("%B %d, %Y")

    # Excerpt: look for header intro div first, then fallback
    excerpt = None
    
    # Try header intro
    intro_div = soup.find("div", class_="intro")
    if intro_div:
        excerpt = re.sub(r'\s+', ' ', intro_div.get_text()).strip()
    
    # Try first paragraph in article content
    if not excerpt:
        article_content = soup.find("div", class_="article-content")
        if article_content:
            p_tag = article_content.find("p")
            if p_tag:
                excerpt = re.sub(r'\s+', ' ', p_tag.get_text()).strip()
    
    # Generic fallback to any paragraph
    if not excerpt:
        p_tag = soup.find("p")
        if p_tag:
            excerpt = re.sub(r'\s+', ' ', p_tag.get_text()).strip()
    
    # Final fallback
    if not excerpt:
        excerpt = "Read the latest AI insights and business applications."

    # Truncate excerpt if too long
    if len(excerpt) > 200:
        excerpt = excerpt[:200] + "..."

    return {
        "title": title,
        "date": date_text,
        "excerpt": excerpt,
        "filename": os.path.basename(html_file)
    }

def update_blog_index():
    """Update the blog index page with current posts"""
    posts_dir = "blog/posts"
    index_file = "blog/index.html"
    
    if not os.path.exists(posts_dir):
        print(f"Posts directory {posts_dir} does not exist")
        return
    
    if not os.path.exists(index_file):
        print(f"Blog index file {index_file} not found")
        return
    
    # Get all blog posts
    posts = []
    html_files = [f for f in os.listdir(posts_dir) if f.endswith(".html") and f != "index.html"]
    
    if not html_files:
        print("No HTML files found in posts directory")
        return

    print(f
