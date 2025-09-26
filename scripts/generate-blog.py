import argparse
import os
import requests
import json
from datetime import datetime
import re

def clean_filename(title):
    """Convert title to a clean filename"""
    # Remove HTML tags if any
    clean_title = re.sub('<.*?>', '', title)
    # Replace spaces and special characters with hyphens
    clean_title = re.sub(r'[^a-zA-Z0-9\s]', '', clean_title)
    clean_title = re.sub(r'\s+', '-', clean_title.strip())
    return clean_title.lower()

def generate_blog_with_perplexity(api_key, topic=None):
    """Generate blog content using Perplexity API"""
    
    # Use current date context for timely content
    current_date = datetime.now().strftime("%B %Y")
    
    # Default topic focused on AI business insights
    if not topic:
        topic = f"Latest AI innovations and breakthroughs in business applications for {current_date}"
    
    url = "https://api.perplexity.ai/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "llama-3.1-sonar-large-128k-online",  # Using online model for current info
        "messages": [
            {
                "role": "system",
                "content": """You are Robert Simon, an AI expert and digital transformation leader with 25+ years of experience. You write authoritative, insightful blog posts about AI innovations and their practical business applications. 

Your writing style is:
- Professional but approachable
- Focuses on practical implementation
- Uses real-world examples
- Provides actionable insights
- Maintains thought leadership authority

Write comprehensive blog posts with clear structure including:
1. Engaging title
2. Brief excerpt (2-3 sentences)
3. Main content organized into clear sections
4. Practical takeaways and implementation steps
5. Forward-looking insights

Format your response as a structured blog post that would be appropriate for a business executive's website."""
            },
            {
                "role": "user",
                "content": f"""Write a comprehensive blog post about: {topic}

The blog post should cover:
- Key technological advances (what's new and important)
- Business applications (how companies can use these advances)
- Real-world use cases and benefits
- Step-by-step implementation guidance
- Future outlook and recommendations

Target audience: Business leaders, executives, and decision-makers interested in practical AI implementation.

Please structure the content to be informative, authoritative, and actionable."""
            }
        ],
        "max_tokens": 3000,
        "temperature": 0.7,
        "top_p": 0.9,
        "return_citations": True,
        "return_related_questions": False,
        "search_recency_filter": "month"  # Get recent information
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        
        data = response.json()
        content = data['choices'][0]['message']['content']
        
        # Extract citations if available
        citations = data.get('citations', [])
        
        return {
            'content': content,
            'citations': citations,
            'usage': data.get('usage', {})
        }
        
    except requests.exceptions.RequestException as e:
        raise Exception(f"Perplexity API request failed: {e}")
    except KeyError as e:
        raise Exception(f"Unexpected API response structure: {e}")

def extract_title_and_excerpt(content):
    """Extract title and excerpt from generated content"""
    lines = content.split('\n')
    
    title = "AI Insights"  # Default title
    excerpt = ""
    
    for line in lines:
        line = line.strip()
        if line and not title_found:
            # Look for title patterns
            if line.startswith('#') or (len(line) < 100 and not line.endswith('.')):
                title = line.lstrip('# ').strip()
                title_found = True
                continue
        
        # Look for excerpt (first meaningful paragraph)
        if line and len(line) > 50 and not excerpt:
            excerpt = line[:200] + "..." if len(line) > 200 else line
            break
    
    # Clean up title
    title = re.sub(r'^#+\s*', '', title)  # Remove markdown headers
    
    if not excerpt:
        excerpt = "Insights into the latest AI innovations and their practical business applications."
    
    return title, excerpt

def create_html_blog_post(content, title, excerpt, citations=None):
    """Convert content to HTML format using the blog template"""
    
    current_date = datetime.now().strftime("%B %d, %Y")
    
    # Read the HTML template
    template_path = "blog/templates/blog-template.html"
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            template = f.read()
    except FileNotFoundError:
        # Fallback basic template if the template file is missing
        template = create_basic_template()
    
    # Split content into sections - this is a simple implementation
    # You might want to enhance this based on how Perplexity structures the content
    sections = content.split('\n\n')
    
    tech_advances = ""
    business_apps = ""
    use_cases = ""
    implementation = ""
    
    current_section = ""
    for section in sections:
        section = section.strip()
        if not section:
            continue
            
        # Simple heuristic to categorize content
        section_lower = section.lower()
        
        if any(keyword in section_lower for keyword in ['technolog', 'advance', 'innovation', 'breakthrough']):
            if not tech_advances:
                tech_advances = section
            else:
                tech_advances += f"\n\n{section}"
        elif any(keyword in section_lower for keyword in ['business', 'application', 'enterprise', 'company']):
            if not business_apps:
                business_apps = section
            else:
                business_apps += f"\n\n{section}"
        elif any(keyword in section_lower for keyword in ['use case', 'benefit', 'example', 'real-world']):
            if not use_cases:
                use_cases = section
            else:
                use_cases += f"\n\n{section}"
        elif any(keyword in section_lower for keyword in ['implement', 'step', 'how to', 'getting started']):
            if not implementation:
                implementation = section
            else:
                implementation += f"\n\n{section}"
        else:
            # Default to tech advances if we can't categorize
            if not tech_advances:
                tech_advances = section
            else:
                tech_advances += f"\n\n{section}"
    
    # Fallback content if sections are empty
    if not tech_advances:
        tech_advances = content[:len(content)//4]
    if not business_apps:
        business_apps = content[len(content)//4:len(content)//2]
    if not use_cases:
        use_cases = content[len(content)//2:3*len(content)//4]
    if not implementation:
        implementation = content[3*len(content)//4:]
    
    # Convert markdown-like formatting to HTML
    def format_content(text):
        # Simple markdown to HTML conversion
        text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
        text = re.sub(r'\n\n', '</p><p>', text)
        text = f'<p>{text}</p>'
        return text
    
    # Replace template placeholders
    html_content = template.replace('{{TITLE}}', title)
    html_content = html_content.replace('{{DATE}}', current_date)
    html_content = html_content.replace('{{EXCERPT}}', excerpt)
    html_content = html_content.replace('{{TECH_ADVANCES}}', format_content(tech_advances))
    html_content = html_content.replace('{{BUSINESS_APPS}}', format_content(business_apps))
    html_content = html_content.replace('{{USE_CASES}}', format_content(use_cases))
    html_content = html_content.replace('{{IMPLEMENTATION}}', format_content(implementation))
    
    return html_content

def create_basic_template():
    """Fallback template if template file is missing"""
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
        raise Exception("PERPLEXITY_API_KEY environment variable not set")

    try:
        print("Generating blog post with Perplexity AI...")
        result = generate_blog_with_perplexity(api_key, args.topic)
        
        print(f"Generated {result['usage'].get('total_tokens', 'unknown')} tokens")
        
        # Extract title and excerpt
        title, excerpt = extract_title_and_excerpt(result['content'])
        print(f"Title: {title}")
        
        # Create HTML version
        html_content = create_html_blog_post(
            result['content'], 
            title, 
            excerpt, 
            result['citations']
        )
        
        # Generate filename
        current_date = datetime.now().strftime("%Y-%m-%d")
        filename = f"{current_date}-{clean_filename(title)}.html"
        
        # Ensure output directory exists
        output_dir = f"blog/{args.output}"
        os.makedirs(output_dir, exist_ok=True)
        
        # Save the blog post
        output_path = os.path.join(output_dir, filename)
        with open(output_path, "w", encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"Blog post saved to: {output_path}")
        
        # Also save raw markdown for reference
        markdown_filename = f"{current_date}-{clean_filename(title)}.md"
        markdown_path = os.path.join(output_dir, markdown_filename)
        with open(markdown_path, "w", encoding='utf-8') as f:
            f.write(f"# {title}\n\n{excerpt}\n\n{result['content']}")
        
        if result['citations']:
            print(f"Sources cited: {len(result['citations'])}")
            
        print("Blog post generated successfully!")
        
    except Exception as e:
        print(f"Failed to generate blog post: {e}")
        exit(1)

if __name__ == "__main__":
    main()
