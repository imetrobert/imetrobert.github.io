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

def clean_perplexity_content(content):
    """Remove citation numbers and clean up Perplexity response formatting"""
    # Remove citation markers like [1], [2], etc.
    content = re.sub(r'\[\d+\]', '', content)
    
    # Remove standalone citation references at end of sentences
    content = re.sub(r'\s*\(\d+\)\s*', ' ', content)
    
    # Clean up multiple spaces
    content = re.sub(r'\s+', ' ', content)
    
    # Clean up bullet points and formatting
    content = re.sub(r'^\s*[-*•]\s*', '• ', content, flags=re.MULTILINE)
    
    return content.strip()

def generate_blog_with_perplexity(api_key, topic=None):
    """Generate blog content using Perplexity API with Canadian business focus"""
    current_date = datetime.now()
    month_year = current_date.strftime("%B %Y")
    
    if not topic:
        topic = f"Latest AI developments and technology launches since last month - {month_year} focus on Canadian business impact"
    
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    models_to_try = [
        "sonar-pro",
        "sonar-medium-online", 
        "sonar-small-online"
    ]
    
    system_prompt = f"""You are Robert Simon, an AI expert and digital transformation leader with 25+ years of experience, writing for Canadian business leaders.

Create a monthly AI insights post for {month_year} following this EXACT structure:

1. INTRODUCTION: Brief overview of the month's key AI developments (1 paragraph)

2. KEY AI DEVELOPMENTS: List 4-5 major AI technology launches, updates, or breakthroughs from the past month with specific company names, product names, and dates

3. CANADIAN BUSINESS IMPACT: Analyze how these developments specifically affect Canadian businesses, considering:
   - Canadian market conditions
   - Regulatory environment (PIPEDA, AIDA considerations)
   - Cross-border business implications
   - Currency and economic factors
   - Competitive positioning vs US/global markets

4. STRATEGIC RECOMMENDATIONS: Provide 5 specific, actionable recommendations for Canadian business leaders

5. CONCLUSION: Strategic imperative for Canadian businesses (1 paragraph)

Write in a professional, authoritative tone. Be specific about companies, technologies, and dates. Focus on practical, actionable insights."""

    user_prompt = f"""Write an AI insights blog post for Canadian business leaders covering the latest developments in {month_year}.

Structure:
- Introduction: Overview of this month's key AI developments 
- Key AI Developments: 4-5 specific technology launches/updates from major companies (OpenAI, Google, Microsoft, Anthropic, etc.) with dates and details
- Canadian Business Impact: How these affect Canadian businesses specifically
- Strategic Recommendations: 5 actionable steps for Canadian business leaders
- Conclusion: Strategic imperative for Canadian businesses

Focus on developments from the past 30 days. Include specific company names, product launches, and real dates."""

    for model in models_to_try:
        print(f"Trying Perplexity model: {model}")
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": 3000,
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
                
                # Clean the content
                cleaned_content = clean_perplexity_content(content)
                
                print(f"Content received from model {model} ({len(cleaned_content)} characters)")
                return {
                    "content": cleaned_content,
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
    """Parse the structured content into sections with improved parsing"""
    sections = {
        'introduction': '',
        'developments': [],
        'canadian_impact': '',
        'recommendations': [],
        'conclusion': ''
    }
    
    # Split content into paragraphs and lines for better parsing
    lines = content.split('\n')
    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
    
    current_section = 'introduction'
    
    print("DEBUG: Parsing content sections...")
    
    # First pass: identify sections by headers
    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        
        if any(phrase in line_lower for phrase in ['key ai development', 'ai development', 'major development', 'technological advance']):
            current_section = 'developments'
            print(f"Found developments section at line {i}: {line[:50]}")
            continue
        elif any(phrase in line_lower for phrase in ['canadian business impact', 'impact on canadian', 'canadian impact']):
            current_section = 'canadian_impact'
            print(f"Found canadian impact section at line {i}: {line[:50]}")
            continue
        elif any(phrase in line_lower for phrase in ['strategic recommendation', 'recommendation', 'action', 'step']):
            current_section = 'recommendations'
            print(f"Found recommendations section at line {i}: {line[:50]}")
            continue
        elif any(phrase in line_lower for phrase in ['conclusion', 'strategic imperative', 'final', 'summary']):
            current_section = 'conclusion'
            print(f"Found conclusion section at line {i}: {line[:50]}")
            continue
        
        # Process content based on current section
        if line.strip():  # Non-empty line
            if current_section == 'introduction' and not sections['introduction'] and len(line) > 50:
                sections['introduction'] = line.strip()
            elif current_section == 'conclusion' and not sections['conclusion'] and len(line) > 50:
                sections['conclusion'] = line.strip()
            elif current_section == 'canadian_impact' and not sections['canadian_impact'] and len(line) > 50:
                sections['canadian_impact'] = line.strip()
            elif current_section == 'developments' and (line.startswith(('•', '-', '*', '1.', '2.', '3.', '4.', '5.')) or ':' in line):
                clean_item = re.sub(r'^[•\-*\d.]\s*', '', line).strip()
                if clean_item and len(clean_item) > 20:
                    sections['developments'].append(clean_item)
            elif current_section == 'recommendations' and (line.startswith(('•', '-', '*', '1.', '2.', '3.', '4.', '5.')) or ':' in line):
                clean_item = re.sub(r'^[•\-*\d.]\s*', '', line).strip()
                if clean_item and len(clean_item) > 20:
                    sections['recommendations'].append(clean_item)
    
    print(f"DEBUG: Parsed sections: intro={bool(sections['introduction'])}, dev={len(sections['developments'])}, impact={bool(sections['canadian_impact'])}, rec={len(sections['recommendations'])}, conc={bool(sections['conclusion'])}")
    
    return sections

def create_html_blog_post(content, title, excerpt):
    """Create complete HTML blog post with FULL content sections"""
    current_date = datetime.now()
    formatted_date = current_date.strftime("%B %d, %Y")
    month_year = current_date.strftime("%B %Y")
    
    # Parse all content sections
    sections = parse_structured_content(content)
    
    # Build content HTML with ALL sections
    content_html = []
    
    # Introduction section
    if sections['introduction']:
        content_html.append(f'''
                <div class="section">
                    <p>{sections['introduction']}</p>
                </div>''')
    
    # Key developments section
    if sections['developments']:
        dev_items = []
        for item in sections['developments']:
            if ':' in item:
                parts = item.split(':', 1)
                dev_items.append(f'<li><strong>{parts[0].strip()}:</strong> {parts[1].strip()}</li>')
            else:
                dev_items.append(f'<li>{item}</li>')
        
        if dev_items:
            content_html.append(f'''
                <div class="section">
                    <h2 class="section-title">Key AI Developments This Month</h2>
                    <ul>
                        {chr(10).join(dev_items)}
                    </ul>
                </div>''')
    
    # Canadian business impact section
    if sections['canadian_impact']:
        content_html.append(f'''
                <div class="section">
                    <h2 class="section-title">Impact on Canadian Businesses</h2>
                    <p>{sections['canadian_impact']}</p>
                </div>''')
    
    # Strategic recommendations section
    if sections['recommendations']:
        rec_items = []
        for i, item in enumerate(sections['recommendations']):
            if ':' in item:
                parts = item.split(':', 1)
                rec_items.append(f'<li><strong>{parts[0].strip()}:</strong> {parts[1].strip()}</li>')
            else:
                rec_items.append(f'<li><strong>Action {i+1}:</strong> {item}</li>')
        
        if rec_items:
            content_html.append(f'''
                <div class="section">
                    <h2 class="section-title">Strategic Recommendations for Canadian Leaders</h2>
                    <ol>
                        {chr(10).join(rec_items)}
                    </ol>
                </div>''')
    
    # If we don't have structured content, use the raw content
    if not any([sections['introduction'], sections['developments'], sections['canadian_impact'], sections['recommendations']]):
        print("WARNING: Structured parsing failed, using raw content")
        # Split content into paragraphs and create basic structure
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip() and len(p.strip()) > 50]
        for para in paragraphs[:8]:  # Limit to avoid overwhelming
            content_html.append(f'''
                <div class="section">
                    <p>{para}</p>
                </div>''')
    
    conclusion_text = sections['conclusion'] if sections['conclusion'] else "Canadian businesses must act decisively to harness AI breakthroughs while maintaining competitive advantage in the global marketplace."
    
    # Combine all content sections
    all_content = '\n'.join(content_html)
    
    print(f"DEBUG: Generated {len(content_html)} content sections, total length: {len(all_content)}")
    
    # Complete HTML template
    html_template = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} | Robert Simon - AI Insights</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
    <style>
        :root {{
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
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: var(--font-primary);
            background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
            color: var(--dark-navy);
            line-height: 1.6;
            min-height: 100vh;
            overflow-x: hidden;
        }}

        .parallax-bg {{
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
        }}

        @keyframes slowFloat {{
            0%, 100% {{ transform: translate(0px, 0px) rotate(0deg); }}
            25% {{ transform: translate(-5px, -10px) rotate(0.5deg); }}
            50% {{ transform: translate(5px, -5px) rotate(-0.3deg); }}
            75% {{ transform: translate(-3px, 8px) rotate(0.2deg); }}
        }}

        .ai-circuit {{
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
        }}

        @keyframes aiFlow {{
            0%, 100% {{ transform: translateX(0) translateY(0); }}
            25% {{ transform: translateX(10px) translateY(-5px); }}
            50% {{ transform: translateX(-5px) translateY(10px); }}
            75% {{ transform: translateX(5px) translateY(-10px); }}
        }}

        .nav-bar {{
            background: var(--white);
            padding: 1rem 0;
            box-shadow: var(--shadow-sm);
            position: sticky;
            top: 0;
            z-index: 100;
            backdrop-filter: blur(10px);
        }}

        .nav-content {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .nav-link {{
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
        }}

        .nav-link:hover {{
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg);
        }}

        .blog-meta {{
            font-family: var(--font-mono);
            font-size: 0.85rem;
            color: var(--medium-gray);
            display: flex;
            align-items: center;
            gap: 1rem;
        }}

        .header {{
            background: var(--gradient-ai);
            color: white;
            padding: 4rem 0 3rem;
            position: relative;
            overflow: hidden;
        }}

        .header::before {{
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
        }}

        .header-content {{
            max-width: 1000px;
            margin: 0 auto;
            padding: 0 2rem;
            text-align: center;
            position: relative;
            z-index: 1;
        }}

        .header h1 {{
            font-size: 2.8rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
            background: linear-gradient(45deg, #ffffff, #e0f2fe);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}

        .header .subtitle {{
            font-size: 1.2rem;
            font-weight: 500;
            opacity: 0.9;
            margin-bottom: 1.5rem;
        }}

        .header .intro {{
            font-size: 1.05rem;
            opacity: 0.85;
            max-width: 800px;
            margin: 0 auto;
            font-weight: 300;
            line-height: 1.7;
        }}

        .container {{
            max-width: 1000px;
            margin: 0 auto;
            padding: 3rem 2rem 4rem;
        }}

        .article-container {{
            background: var(--gradient-card);
            border-radius: 20px;
            box-shadow: var(--shadow-xl);
            overflow: hidden;
            border: 1px solid rgba(37, 99, 235, 0.1);
            position: relative;
        }}

        .article-content {{
            padding: 3rem;
            background: white;
        }}

        .section {{
            margin-bottom: 3rem;
        }}

        .section-title {{
            font-size: 1.8rem;
            color: var(--dark-navy);
            margin-bottom: 1.5rem;
            font-weight: 600;
            position: relative;
            padding-left: 1.5rem;
            line-height: 1.3;
        }}

        .section-title::before {{
            content: '';
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 4px;
            background: var(--gradient-primary);
            border-radius: 2px;
        }}

        p {{
            margin-bottom: 1.2rem;
            text-align: justify;
            word-spacing: normal;
            line-height: 1.7;
            color: var(--medium-gray);
            font-size: 1rem;
        }}

        ul {{
            margin-bottom: 1.5rem;
            padding-left: 0;
        }}

        li {{
            margin-bottom: 1.2rem;
            line-height: 1.7;
            color: var(--medium-gray);
            list-style: none;
            position: relative;
            padding-left: 2rem;
        }}

        li::before {{
            content: '▸';
            position: absolute;
            left: 0;
            color: var(--primary-blue);
            font-weight: 600;
            font-size: 1.1rem;
        }}

        ol {{
            margin-bottom: 1.5rem;
            padding-left: 0;
            counter-reset: list-counter;
        }}

        ol li {{
            counter-increment: list-counter;
            padding-left: 3rem;
            position: relative;
        }}

        ol li::before {{
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
        }}

        strong {{
            color: var(--dark-navy);
            font-weight: 600;
        }}

        .conclusion {{
            background: var(--gradient-ai);
            color: white;
            padding: 2.5rem;
            border-radius: 15px;
            margin-top: 3rem;
            position: relative;
            overflow: hidden;
        }}

        .conclusion::before {{
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
        }}

        .conclusion p {{
            color: rgba(255, 255, 255, 0.95);
            font-size: 1.1rem;
            font-weight: 500;
            position: relative;
            z-index: 1;
            margin-bottom: 0;
            text-align: left;
        }}

        .conclusion strong {{
            color: white;
        }}

        @media (max-width: 768px) {{
            .header h1 {{
                font-size: 2.2rem;
            }}

            .header .subtitle {{
                font-size: 1.1rem;
            }}

            .container {{
                padding: 2rem 1rem 3rem;
            }}

            .article-content {{
                padding: 2rem 1.5rem;
            }}

            .section-title {{
                font-size: 1.5rem;
            }}

            .nav-content {{
                padding: 0 1rem;
                flex-direction: column;
                gap: 1rem;
                text-align: center;
            }}
        }}

        .fade-in {{
            opacity: 0;
            transform: translateY(30px);
            animation: fadeInUp 0.8s ease forwards;
        }}

        @keyframes fadeInUp {{
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}
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
                <span>AI Insights for Canadian Business</span>
                <span>•</span>
                <span>{formatted_date}</span>
            </div>
        </div>
    </nav>

    <header class="header">
        <div class="header-content">
            <h1>AI Insights for {month_year}</h1>
            <div class="subtitle">Key AI Developments & Canadian Business Impact</div>
            <div class="intro">
                {excerpt}
            </div>
        </div>
        <div class="ai-circuit"></div>
    </header>

    <div class="container">
        <article class="article-container fade-in">
            <div class="article-content">
                {all_content}

                <div class="conclusion">
                    <p><strong>Strategic Imperative for Canadian Businesses:</strong> {conclusion_text}</p>
                </div>
            </div>
        </article>
    </div>
</body>
</html>'''
    
    return html_template

def extract_title_and_excerpt(content):
    """Extract title and excerpt from generated content"""
    current_date = datetime.now()
    month_year = current_date.strftime("%B %Y")
    
    title = f"AI Insights for {month_year}"
    
    lines = [line.strip() for line in content.split("\n") if line.strip()]
    excerpt = ""
    
    # Look for introduction paragraph
    for line in lines:
        if line and len(line) > 100 and not line.startswith(('#', '1.', '2.', '3.', '4.', '5.', '•', '-', '*')):
            excerpt = line[:200] + "..." if len(line) > 200 else line
            break
    
    if not excerpt:
        excerpt = f"Monthly analysis of key AI developments and their strategic impact on Canadian businesses for {month_year}."
    
    return title, excerpt

def extract_post_info(html_file):
    """Extract title, date, and excerpt from an HTML blog post"""
    with open(html_file, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    # Extract title
    title_tag = None
    header_content = soup.find("div", class_="header-content")
    if header_content:
        title_tag = header_content.find("h1")
    else:
        title_tag = soup.find("h1")
    
    title = title_tag.get_text(strip=True) if title_tag else "AI Insights"

    # Extract date
    date_text = None
    
    blog_meta = soup.find("div", class_="blog-meta")
    if blog_meta:
        meta_text = blog_meta.get_text()
        if "•" in meta_text:
            date_text = meta_text.split("•")[-1].strip()
    
    if not date_text:
        subtitle = soup.find("div", class_="subtitle")
        if subtitle:
            subtitle_text = subtitle.get_text()
            date_match = re.search(r'([A-Za-z]+ \d{1,2}, \d{4})', subtitle_text)
            if date_match:
                date_text = date_match.group(1)
    
    if not date_text:
        basename = os.path.basename(html_file)
        match = re.match(r"(\d{4}-\d{2}-\d{2})-", basename)
        if match:
            date_obj = datetime.strptime(match.group(1), "%Y-%m-%d")
            date_text = date_obj.strftime("%B %d, %Y")
        else:
            date_text = datetime.now().strftime("%B %d, %Y")

    # Extract excerpt
    excerpt = None
    
    intro_div = soup.find("div", class_="intro")
    if intro_div:
        excerpt = re.sub(r'\s+', ' ', intro_div.get_text()).strip()
    
    if not excerpt:
        article_content = soup.find("div", class_="article-content")
        if article_content:
            p_tag = article_content.find("p")
            if p_tag:
                excerpt = re.sub(r'\s+', ' ', p_tag.get_text()).strip()
    
    if not excerpt:
        excerpt = "Read the latest AI insights and business applications."

    if len(excerpt) > 200:
        excerpt = excerpt[:200] + "..."

    return {
        "title": title,
        "date": date_text,
        "excerpt": excerpt,
        "filename": os.path.basename(html_file)
    }

def create_blog_index_html(posts):
    """Create a beautiful blog index page matching your homepage design"""
    if not posts:
        return None
    
    latest_post = posts[0]
    older_posts = posts[1:] if len(posts) > 1 else []
    
    # Create posts HTML for older posts
    older_posts_html = ""
    for post in older_posts:
        older_posts_html += f'''
                <div class="older-post-item">
                    <a href="/blog/posts/{post['filename']}" class="older-post-link">
                        <div class="older-post-title">{post['title']}</div>
                        <div class="older-post-date">{post['date']}</div>
                    </a>
                </div>'''
    
    blog_index_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Insights Blog - Robert Simon | Digital Innovation & AI Strategy</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
    <style>
        :root {{
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
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: var(--font-primary);
            background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
            color: var(--dark-navy);
            line-height: 1.6;
            min-height: 100vh;
            overflow-x: hidden;
        }}

        .parallax-bg {{
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
        }}

        @keyframes slowFloat {{
            0%, 100% {{ transform: translate(0px, 0px) rotate(0deg); }}
            25% {{ transform: translate(-5px, -10px) rotate(0.5deg); }}
            50% {{ transform: translate(5px, -5px) rotate(-0.3deg); }}
            75% {{ transform: translate(-3px, 8px) rotate(0.2deg); }}
        }}

        .ai-circuit {{
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
        }}

        @keyframes aiFlow {{
            0%, 100% {{ transform: translateX(0) translateY(0); }}
            25% {{ transform: translateX(10px) translateY(-5px); }}
            50% {{ transform: translateX(-5px) translateY(10px); }}
            75% {{ transform: translateX(5px) translateY(-10px); }}
        }}

        .ai-accent {{
            background: var(--gradient-ai) !important;
            background-size: 200% 200% !important;
            animation: aiGradient 4s ease infinite;
        }}

        @keyframes aiGradient {{
            0% {{ background-position: 0% 50%; }}
            50% {{ background-position: 100% 50%; }}
            100% {{ background-position: 0% 50%; }}
        }}

        .nav-bar {{
            background: var(--white);
            padding: 1rem 0;
            box-shadow: var(--shadow-sm);
            position: sticky;
            top: 0;
            z-index: 100;
            backdrop-filter: blur(10px);
        }}

        .nav-content {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 2rem;
            display: flex;
            justify-content: center;
            align-items: center;
        }}

        .nav-link {{
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
        }}

        .nav-link:hover {{
            transform: translateY(-3px);
            box-shadow: var(--shadow-lg);
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }}

        header {{
            background: var(--gradient-ai);
            color: white;
            padding: 4rem 0;
            text-align: center;
            margin-bottom: 3rem;
            position: relative;
            overflow: hidden;
            border-radius: 20px;
        }}

        header::before {{
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
        }}

        h1 {{
            font-size: 3.5rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
            background: linear-gradient(45deg, #ffffff, #e0f2fe);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            position: relative;
            z-index: 1;
        }}

        .subtitle {{
            font-size: 1.4rem;
            font-weight: 500;
            opacity: 0.95;
            position: relative;
            z-index: 1;
            margin-bottom: 1rem;
        }}

        .header-description {{
            font-size: 1.1rem;
            opacity: 0.9;
            position: relative;
            z-index: 1;
            max-width: 800px;
            margin: 0 auto;
        }}

        .latest-post-section {{
            background: var(--gradient-ai);
            color: white;
            padding: 3rem;
            border-radius: 20px;
            margin-bottom: 3rem;
            position: relative;
            overflow: hidden;
        }}

        .latest-post-section::before {{
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
        }}

        .latest-post-content {{
            position: relative;
            z-index: 1;
        }}

        .latest-badge {{
            background: rgba(255, 255, 255, 0.25);
            color: white;
            padding: 0.5rem 1rem;
            border-radius: 20px;
            font-size: 0.9rem;
            font-weight: 600;
            display: inline-block;
            margin-bottom: 1rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .latest-post-title {{
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 1rem;
            color: white;
        }}

        .latest-post-date {{
            font-size: 1rem;
            opacity: 0.9;
            margin-bottom: 1rem;
            font-family: var(--font-mono);
        }}

        .latest-post-excerpt {{
            font-size: 1.1rem;
            line-height: 1.7;
            opacity: 0.95;
            margin-bottom: 2rem;
        }}

        .read-latest-btn {{
            background: rgba(255, 255, 255, 0.2);
            color: white;
            border: 2px solid rgba(255, 255, 255, 0.3);
            padding: 0.75rem 2rem;
            border-radius: 25px;
            text-decoration: none;
            font-weight: 600;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            transition: all 0.3s ease;
            backdrop-filter: blur(10px);
        }}

        .read-latest-btn:hover {{
            background: rgba(255, 255, 255, 0.3);
            transform: translateY(-2px);
            box-shadow: var(--shadow-lg);
        }}

        .older-posts-section {{
            background: white;
            border-radius: 20px;
            padding: 2.5rem;
            box-shadow: var(--shadow-xl);
            border: 1px solid rgba(37, 99, 235, 0.1);
        }}

        .older-posts-title {{
            font-size: 1.8rem;
            color: var(--dark-navy);
            margin-bottom: 2rem;
            font-weight: 600;
            text-align: center;
        }}

        .older-posts-grid {{
            display: grid;
            gap: 1.5rem;
        }}

        .older-post-item {{
            border: 1px solid var(--light-gray);
            border-radius: 12px;
            transition: all 0.3s ease;
        }}

        .older-post-item:hover {{
            transform: translateY(-3px);
            box-shadow: var(--shadow-md);
            border-color: var(--primary-blue);
        }}

        .older-post-link {{
            display: block;
            padding: 1.5rem;
            text-decoration: none;
            color: inherit;
        }}

        .older-post-title {{
            font-size: 1.3rem;
            font-weight: 600;
            color: var(--dark-navy);
            margin-bottom: 0.5rem;
            line-height: 1.4;
        }}

        .older-post-date {{
            font-size: 0.9rem;
            color: var(--medium-gray);
            font-family: var(--font-mono);
        }}

        @media (max-width: 768px) {{
            .container {{
                padding: 1rem;
            }}
            
            h1 {{
                font-size: 2.5rem;
            }}
            
            .latest-post-section {{
                padding: 2rem;
            }}
            
            .latest-post-title {{
                font-size: 1.5rem;
            }}
            
            .nav-content {{
                padding: 0 1rem;
            }}

            .older-posts-section {{
                padding: 2rem 1.5rem;
            }}
        }}

        .fade-in {{
            opacity: 0;
            transform: translateY(30px);
            animation: fadeInUp 0.8s ease forwards;
        }}

        @keyframes fadeInUp {{
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}
    </style>
</head>
<body>
    <div class="parallax-bg"></div>
    
    <nav class="nav-bar">
        <div class="nav-content">
            <a href="/" class="nav-link">
                ← Back to Robert Simon's Portfolio
            </a>
        </div>
    </nav>
    
    <div class="container">
        <header>
            <h1>AI Insights Blog</h1>
            <p class="subtitle">Strategic Intelligence for Digital Leaders</p>
            <p class="header-description">Monthly deep-dives into AI innovations, practical business applications, and strategic implementation guidance from 25+ years of digital transformation experience.</p>
            <div class="ai-circuit"></div>
        </header>

        <!-- Latest Post Section -->
        <section class="latest-post-section fade-in">
            <div class="latest-post-content">
                <div class="latest-badge">Latest</div>
                <h2 class="latest-post-title">{latest_post['title']}</h2>
                <div class="latest-post-date">{latest_post['date']}</div>
                <p class="latest-post-excerpt">{latest_post['excerpt']}</p>
                <a href="/blog/posts/{latest_post['filename']}" class="read-latest-btn">
                    Read Full Analysis →
                </a>
            </div>
            <div class="ai-circuit"></div>
        </section>

        # Older Posts Section (conditional)
        older_posts_section = ""
        if older_posts:
            older_posts_section = f'''<section class="older-posts-section fade-in">
            <h3 class="older-posts-title">Previous Insights</h3>
            <div class="older-posts-grid">
                {older_posts_html}
            </div>
        </section>'''

        <!-- Older Posts Section -->
        {older_posts_section}
    </div>
</body>
</html>'''

    return blog_index_html

def update_blog_index():
    """Update ONLY the blog index page with proper styling"""
    posts_dir = "blog/posts"
    index_file = "blog/index.html"
    
    print(f"DEBUG: Checking posts directory: {posts_dir}")
    print(f"DEBUG: Checking blog index file: {index_file}")
    
    if not os.path.exists(posts_dir):
        print(f"ERROR: Posts directory {posts_dir} does not exist")
        return []
    
    if not os.path.exists(index_file):
        print(f"ERROR: Blog index file {index_file} not found")
        return []
    
    posts = []
    html_files = [f for f in os.listdir(posts_dir) if f.endswith(".html") and f != "index.html"]
    
    print(f"DEBUG: Found HTML files: {html_files}")
    
    if not html_files:
        print("WARNING: No HTML files found in posts directory")
        return []

    print(f"Processing {len(html_files)} HTML files in posts directory")

    for file in sorted(html_files, reverse=True):
        file_path = os.path.join(posts_dir, file)
        try:
            post_info = extract_post_info(file_path)
            posts.append(post_info)
            print(f"✅ Processed: {file} -> {post_info['title']}")
        except Exception as e:
            print(f"❌ Error processing {file}: {e}")
            continue

    if not posts:
        print("ERROR: No valid posts could be processed")
        return []

    # Create beautiful blog index HTML
    new_blog_index = create_blog_index_html(posts)
    if not new_blog_index:
        print("ERROR: Failed to create blog index HTML")
        return posts
    
    # Write the new blog index
    try:
        with open(index_file, "w", encoding="utf-8") as f:
            f.write(new_blog_index)
        print(f"✅ Blog index completely recreated with beautiful styling and {len(posts)} posts")
    except Exception as e:
        print(f"❌ Error writing blog index: {e}")
    
    return posts

def main():
    parser = argparse.ArgumentParser(description="COMPLETE FIX - Blog Content & Styling")
    parser.add_argument("--topic", help="Custom topic for the blog post")
    parser.add_argument("--output", default="posts", choices=["staging", "posts"],
                        help="Output directory (staging for review, posts for direct publish)")
    parser.add_argument("--fix-only", action="store_true", 
                        help="Only fix existing blog index and posts (skip content generation)")
    args = parser.parse_args()
    
    print("🔧 RUNNING COMPLETE FIX - Blog Content & Styling")
    print("=" * 60)
    
    # If fix-only, just update the blog index
    if args.fix_only:
        print("🛠️  FIX MODE: Only updating blog index with proper styling...")
        try:
            posts = update_blog_index()
            print(f"✅ Fix completed: {len(posts)} posts processed with beautiful styling")
            return
        except Exception as e:
            print(f"❌ Fix failed: {e}")
            return
    
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        print("❌ PERPLEXITY_API_KEY environment variable not set")
        sys.exit(1)
    
    try:
        print("🤖 Generating comprehensive AI insights blog post...")
        print("📍 SCOPE: Blog pages only (NO homepage changes)")
        
        result = generate_blog_with_perplexity(api_key, args.topic)
        
        title, excerpt = extract_title_and_excerpt(result["content"])
        print(f"✅ Title extracted: {title}")
        
        html_content = create_html_blog_post(result["content"], title, excerpt)
        print(f"✅ HTML content generated with FULL article content ({len(html_content)} characters)")
        
        current_date = datetime.now().strftime("%Y-%m-%d")
        filename_html = f"{current_date}-{clean_filename(title)}.html"
        
        output_dir = os.path.join("blog", args.output)
        os.makedirs(output_dir, exist_ok=True)
        
        path_html = os.path.join(output_dir, filename_html)
        
        # Write the individual post file
        with open(path_html, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"✅ Blog post saved: {path_html}")
        
        # Always update latest.html with COMPLETE content
        latest_path = os.path.join("blog", "posts", "latest.html")
        os.makedirs(os.path.dirname(latest_path), exist_ok=True)
        with open(latest_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"✅ Latest post updated: {latest_path}")
        
        if result.get("citations"):
            print(f"📚 Sources processed: {len(result['citations'])} (citations cleaned)")
        
        # Update blog index with beautiful new design
        try:
            posts = update_blog_index()
            print(f"✅ Blog index recreated with stunning design and {len(posts)} total posts")
            print("📍 NOTE: Homepage unchanged (as requested)")
            
        except Exception as e:
            print(f"❌ Failed to update blog index: {e}")
            import traceback
            traceback.print_exc()
        
        print("🎉 COMPLETE FIX APPLIED SUCCESSFULLY!")
        print("🔗 Check your blog at: /blog/ (now with beautiful styling)")
        print("🔗 Latest post at: /blog/posts/latest.html (now with full content)")
        
    except Exception as e:
        print(f"💥 Blog generation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
