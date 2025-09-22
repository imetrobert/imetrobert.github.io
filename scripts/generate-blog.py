#!/usr/bin/env python3
"""
AI Blog Generator for Robert Simon's Website
Automatically generates monthly AI insight blog posts using Gemini AI (free tier)
"""

import os
import json
import requests
from datetime import datetime, timedelta
import re
from typing import List, Dict, Optional
import time
import random

class AIBlogGenerator:
    def __init__(self):
        self.sources = [
            "https://feeds.feedburner.com/oreilly/radar",
            "https://techcrunch.com/category/artificial-intelligence/feed/",
            "https://www.artificialintelligence-news.com/feed/",
            "https://venturebeat.com/ai/feed/",
            "https://www.technologyreview.com/feed/",
        ]
        
        # Gemini AI service
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        self.gemini_url = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent'
        
        if not self.gemini_api_key:
            print("⚠️ WARNING: GEMINI_API_KEY not found. Please add it to GitHub secrets.")
    
    def fetch_ai_news(self, days_back=30) -> List[Dict]:
        """Fetch AI-related news from the past month"""
        news_items = []
        
        print("Fetching AI news from RSS feeds...")
        
        for source in self.sources:
            try:
                print(f"Fetching from: {source}")
                response = requests.get(source, timeout=15, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                
                if response.status_code == 200:
                    content = response.text
                    
                    # Extract titles and descriptions from RSS
                    titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', content)
                    if not titles:
                        titles = re.findall(r'<title>(.*?)</title>', content)
                    
                    descriptions = re.findall(r'<description><!\[CDATA\[(.*?)\]\]></description>', content)
                    if not descriptions:
                        descriptions = re.findall(r'<description>(.*?)</description>', content)
                    
                    # Filter for AI-related content
                    for i, (title, desc) in enumerate(zip(titles[:8], descriptions[:8])):
                        if any(keyword in title.lower() for keyword in ['ai', 'artificial intelligence', 'machine learning', 'automation', 'chatgpt', 'openai', 'google', 'microsoft']):
                            # Clean up HTML tags
                            clean_title = re.sub(r'<[^>]+>', '', title).strip()
                            clean_desc = re.sub(r'<[^>]+>', '', desc).strip()[:300]
                            
                            news_items.append({
                                'title': clean_title,
                                'description': clean_desc,
                                'source': source
                            })
                            
                            if len(news_items) >= 15:  # Limit total items
                                break
                
                time.sleep(2)  # Be respectful to servers
                
            except Exception as e:
                print(f"Error fetching from {source}: {e}")
                continue
        
        print(f"Found {len(news_items)} AI-related news items")
        return news_items[:15]  # Return top 15 items
    
    def generate_content_with_gemini(self, prompt: str) -> Optional[str]:
        """Generate content using Google's Gemini API (free tier)"""
        if not self.gemini_api_key:
            print("❌ No Gemini API key available")
            return None
            
        try:
            headers = {'Content-Type': 'application/json'}
            data = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }]
            }
            
            url = f"{self.gemini_url}?key={self.gemini_api_key}"
            print("Calling Gemini API...")
            
            response = requests.post(url, json=data, headers=headers, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                
                if 'candidates' in result and len(result['candidates']) > 0:
                    content = result['candidates'][0]['content']['parts'][0]['text']
                    print("✅ Gemini API call successful")
                    return content
                else:
                    print("❌ No content in Gemini response")
                    return None
            else:
                print(f"❌ Gemini API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error with Gemini API: {e}")
            return None
    
    def create_blog_prompt(self, news_items: List[Dict]) -> str:
        """Create a comprehensive prompt for AI content generation"""
        if not news_items:
            # Fallback prompt if no news found
            news_summary = "Recent AI developments include continued advances in large language models, computer vision improvements, and increased business adoption of AI tools."
        else:
            news_summary = "\n".join([f"- {item['title']}: {item['description'][:200]}..." for item in news_items[:10]])
        
        prompt = f"""Based on recent AI developments, write a comprehensive business-focused blog post for tech-savvy business leaders.

Recent AI News Context:
{news_summary}

Please create a well-structured blog post with EXACTLY these four sections (approximately 200 words each):

**1. KEY TECHNOLOGICAL ADVANCES**
Highlight the most significant AI technological breakthroughs from recent developments. Focus on innovations that have real business potential like new AI models, improved capabilities, hardware advances, or breakthrough research.

**2. KEY BUSINESS APPLICATIONS** 
Explain how these technological advances can be applied in business contexts. Be specific about industries (healthcare, finance, retail, manufacturing, etc.) and concrete use cases. Focus on practical applications that business leaders can understand and relate to.

**3. USE CASES AND BENEFITS**
Provide concrete examples of how businesses can benefit from these AI advances. Include measurable benefits like cost reduction, efficiency gains, revenue opportunities, and competitive advantages. Use real-world scenarios that demonstrate tangible ROI potential.

**4. BEST STEPS TO IMPLEMENT**
Give actionable, step-by-step guidance for business leaders on how to start implementing these AI solutions. Include practical advice about team building, technology selection, pilot projects, risk management, and scaling strategies.

Also provide:
- A compelling, professional blog post title (under 80 characters)
- A compelling 2-sentence excerpt/summary for social media
- 4-5 relevant tags for categorization

Write in a professional but accessible tone. Focus on practical value and actionable insights that business owners can immediately apply.

Format your response as clean JSON with these exact keys:
{{
  "title": "Your compelling title here",
  "excerpt": "Two sentence summary here.",
  "tech_advances": "Content for section 1...",
  "business_apps": "Content for section 2...", 
  "use_cases": "Content for section 3...",
  "implementation": "Content for section 4...",
  "tags": ["tag1", "tag2", "tag3", "tag4"]
}}"""
        
        return prompt
    
    def generate_blog_content(self, news_items: List[Dict]) -> Optional[Dict]:
        """Generate blog content using Gemini AI"""
        prompt = self.create_blog_prompt(news_items)
        
        print("Generating blog content with Gemini...")
        content = self.generate_content_with_gemini(prompt)
        
        if not content:
            print("❌ Failed to generate content with Gemini")
            return None
        
        try:
            # Clean up the response - sometimes AI includes markdown formatting
            content = content.strip()
            if content.startswith('```json'):
                content = content.replace('```json', '').replace('```', '').strip()
            elif content.startswith('```'):
                content = content.replace('```', '').strip()
            
            # Try to parse as JSON
            parsed_content = json.loads(content)
            print("✅ Successfully parsed AI-generated content")
            return parsed_content
            
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse AI response as JSON: {e}")
            print(f"Raw response: {content[:500]}...")
            
            # Fallback: try to extract content manually
            return self.parse_unstructured_content(content)
    
    def parse_unstructured_content(self, content: str) -> Dict:
        """Parse unstructured AI response into sections"""
        print("Attempting to parse unstructured content...")
        
        sections = {
            'title': 'AI Innovations This Month: Business Implementation Guide',
            'excerpt': 'Discover the latest AI breakthroughs and learn how to implement them in your business for competitive advantage.',
            'tech_advances': 'Recent technological advances in AI continue to reshape the business landscape with improved language models, computer vision capabilities, and automated decision-making systems.',
            'business_apps': 'These AI technologies can be applied across industries for customer service automation, predictive analytics, content generation, and operational efficiency improvements.',
            'use_cases': 'Businesses are seeing measurable benefits including 30-50% cost reduction in customer support, improved sales forecasting accuracy, and enhanced customer personalization leading to increased revenue.',
            'implementation': 'To implement AI successfully, start with a clear use case, assemble a cross-functional team, run pilot projects, measure results, and scale gradually while ensuring proper governance and training.',
            'tags': ['AI', 'Business Strategy', 'Digital Transformation', 'Implementation', 'Innovation']
        }
        
        # Try to extract better content from the raw response
        lines = content.split('\n')
        current_section = None
        section_content = ""
        
        for line in lines:
            line = line.strip()
            if any(keyword in line.lower() for keyword in ['title:', 'titel:']):
                if 'title' not in sections or len(line) > 10:
                    sections['title'] = re.sub(r'^[^:]*:', '', line).strip().strip('"')
            elif any(keyword in line.lower() for keyword in ['technological advance', 'tech advance', 'advances']):
                current_section = 'tech_advances'
                section_content = ""
            elif any(keyword in line.lower() for keyword in ['business application', 'business app']):
                current_section = 'business_apps'
                section_content = ""
            elif any(keyword in line.lower() for keyword in ['use case', 'benefit']):
                current_section = 'use_cases'  
                section_content = ""
            elif any(keyword in line.lower() for keyword in ['implement', 'step']):
                current_section = 'implementation'
                section_content = ""
            elif current_section and line and not line.startswith('#'):
                section_content += line + " "
                if len(section_content) > 50:  # Only update if we have substantial content
                    sections[current_section] = section_content.strip()
        
        return sections
    
    def create_html_post(self, content: Dict) -> str:
        """Create HTML blog post from content"""
        # Load template
        template_path = 'blog/templates/blog-template.html'
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                template = f.read()
        else:
            print("⚠️ Template not found, using basic template")
            template = self.get_basic_template()
        
        # Replace placeholders
        current_date = datetime.now().strftime("%B %d, %Y")
        
        html = template.replace('{{TITLE}}', content['title'])
        html = html.replace('{{DATE}}', current_date)
        html = html.replace('{{EXCERPT}}', content['excerpt'])
        html = html.replace('{{TECH_ADVANCES}}', self.format_section(content['tech_advances']))
        html = html.replace('{{BUSINESS_APPS}}', self.format_section(content['business_apps']))
        html = html.replace('{{USE_CASES}}', self.format_section(content['use_cases']))
        html = html.replace('{{IMPLEMENTATION}}', self.format_section(content['implementation']))
        
        return html
    
    def format_section(self, text: str) -> str:
        """Format section text with proper HTML paragraphs"""
        if not text:
            return "<p>Content will be added here.</p>"
            
        # Split into paragraphs and clean up
        paragraphs = []
        for para in text.split('\n\n'):
            para = para.strip()
            if para:
                # Remove any existing HTML tags and add paragraph tags
                para = re.sub(r'<[^>]+>', '', para)
                paragraphs.append(f'<p>{para}</p>')
        
        return '\n'.join(paragraphs) if paragraphs else f"<p>{text}</p>"
    
    def create_slug(self, title: str) -> str:
        """Create URL-friendly slug from title"""
        slug = re.sub(r'[^\w\s-]', '', title.lower())
        slug = re.sub(r'[-\s]+', '-', slug)
        return slug.strip('-')[:50]  # Limit length
    
    def get_basic_template(self) -> str:
        """Basic HTML template fallback"""
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{TITLE}} - Robert Simon AI Insights</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 2rem; }
        h1 { color: #2563eb; }
        h2 { color: #1e293b; margin-top: 2rem; }
        p { line-height: 1.6; margin-bottom: 1rem; }
    </style>
</head>
<body>
    <h1>{{TITLE}}</h1>
    <p><em>Published on {{DATE}} by Robert Simon</em></p>
    <p><strong>{{EXCERPT}}</strong></p>
    
    <h2>🚀 Key Technological Advances</h2>
    {{TECH_ADVANCES}}
    
    <h2>💼 Key Business Applications</h2>
    {{BUSINESS_APPS}}
    
    <h2>✅ Use Cases and Benefits</h2>
    {{USE_CASES}}
    
    <h2>🎯 Best Steps to Implement</h2>
    {{IMPLEMENTATION}}
    
    <p><a href="../">← Back to AI Insights</a></p>
</body>
</html>"""
    
    def save_post(self, content: Dict, html: str) -> str:
        """Save blog post and return filename"""
        slug = self.create_slug(content['title'])
        current_date = datetime.now()
        filename = f"{current_date.strftime('%Y-%m')}-{slug}.html"
        
        # Create staging directory if it doesn't exist
        os.makedirs('blog/staging', exist_ok=True)
        
        # Save HTML file
        filepath = f'blog/staging/{filename}'
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"✅ Saved HTML file: {filepath}")
        
        # Save metadata
        metadata = {
            'filename': filename,
            'title': content['title'],
            'excerpt': content['excerpt'],
            'date': current_date.isoformat(),
            'tags': content.get('tags', []),
            'slug': slug
        }
        
        metadata_file = f'blog/staging/{slug}.json'
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"✅ Saved metadata: {metadata_file}")
        
        return filename
    
    def generate_monthly_post(self) -> Optional[str]:
        """Main function to generate monthly blog post"""
        print("🚀 Starting AI blog generation...")
        
        # Step 1: Fetch recent AI news
        news_items = self.fetch_ai_news()
        
        if not news_items:
            print("⚠️ No AI news found, proceeding with general prompt")
        
        # Step 2: Generate content
        content = self.generate_blog_content(news_items)
        
        if not content:
            print("❌ Failed to generate content. Aborting.")
            return None
        
        print("✅ Content generated successfully")
        
        # Step 3: Create HTML post
        print("Creating HTML post...")
        html = self.create_html_post(content)
        
        # Step 4: Save to staging
        filename = self.save_post(content, html)
        
        print(f"🎉 Blog post saved as: {filename}")
        print("📝 Post is ready for manual review and approval!")
        
        return filename

if __name__ == "__main__":
    generator = AIBlogGenerator()
    result = generator.generate_monthly_post()
    if result:
        print(f"✅ SUCCESS: Generated {result}")
    else:
        print("❌ FAILED: No blog post generated")
        exit(1)
