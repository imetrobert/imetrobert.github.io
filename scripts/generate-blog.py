#!/usr/bin/env python3
"""
AI Blog Generator for Robert Simon's Website
Automatically generates monthly AI insight blog posts using free AI services
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
        
        # Free AI service endpoints
        self.ai_services = {
            'gemini': {
                'url': 'https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent',
                'key': os.getenv('GEMINI_API_KEY'),
                'available': True
            },
            'huggingface': {
                'url': 'https://api-inference.huggingface.co/models/microsoft/DialoGPT-large',
                'key': os.getenv('HUGGINGFACE_API_KEY'),
                'available': True
            }
        }
    
    def fetch_ai_news(self, days_back=30) -> List[Dict]:
        """Fetch AI-related news from the past month"""
        news_items = []
        
        # Simple RSS feed parser (you might want to use feedparser library)
        for source in self.sources:
            try:
                response = requests.get(source, timeout=10)
                if response.status_code == 200:
                    # Extract basic info from RSS (simplified)
                    content = response.text
                    # This is a basic implementation - you'd want proper RSS parsing
                    titles = re.findall(r'<title>(.*?)</title>', content)
                    descriptions = re.findall(r'<description>(.*?)</description>', content)
                    
                    for title, desc in zip(titles[:5], descriptions[:5]):  # Take top 5 from each source
                        if any(keyword in title.lower() for keyword in ['ai', 'artificial intelligence', 'machine learning', 'automation']):
                            news_items.append({
                                'title': title,
                                'description': desc,
                                'source': source
                            })
                            
                time.sleep(1)  # Be respectful to servers
            except Exception as e:
                print(f"Error fetching from {source}: {e}")
                continue
        
        return news_items[:20]  # Return top 20 items
    
    def generate_content_with_gemini(self, prompt: str) -> Optional[str]:
        """Generate content using Google's Gemini API (free tier)"""
        if not self.ai_services['gemini']['key']:
            return None
            
        try:
            headers = {'Content-Type': 'application/json'}
            data = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }]
            }
            
            url = f"{self.ai_services['gemini']['url']}?key={self.ai_services['gemini']['key']}"
            response = requests.post(url, json=data, headers=headers, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                return result['candidates'][0]['content']['parts'][0]['text']
            else:
                print(f"Gemini API error: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Error with Gemini API: {e}")
            return None
    
    def generate_content_with_huggingface(self, prompt: str) -> Optional[str]:
        """Generate content using Hugging Face API (free tier)"""
        if not self.ai_services['huggingface']['key']:
            return None
            
        try:
            headers = {'Authorization': f"Bearer {self.ai_services['huggingface']['key']}"}
            data = {"inputs": prompt}
            
            response = requests.post(
                self.ai_services['huggingface']['url'], 
                headers=headers, 
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result[0]['generated_text'] if result else None
            else:
                print(f"HuggingFace API error: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Error with HuggingFace API: {e}")
            return None
    
    def create_blog_prompt(self, news_items: List[Dict]) -> str:
        """Create a comprehensive prompt for AI content generation"""
        news_summary = "\n".join([f"- {item['title']}: {item['description'][:200]}..." for item in news_items[:10]])
        
        prompt = f"""
        Based on the following AI news from the past month, create a comprehensive business-focused blog post.

        Recent AI News:
        {news_summary}

        Please write a professional blog post with exactly these four sections:

        1. KEY TECHNOLOGICAL ADVANCES (200 words):
        Highlight the most significant AI technological breakthroughs from the news above. Focus on innovations that have real business potential.

        2. KEY BUSINESS APPLICATIONS (200 words):
        Explain how these technological advances can be applied in business contexts. Be specific about industries and use cases.

        3. USE CASES AND BENEFITS (200 words):
        Provide concrete examples of how businesses can benefit from these AI advances. Include measurable benefits and ROI potential.

        4. BEST STEPS TO IMPLEMENT (200 words):
        Give actionable, step-by-step guidance for business leaders on how to start implementing these AI solutions.

        Write in a professional but accessible tone for business owners and tech-savvy business users. Focus on practical value and actionable insights.

        Also provide:
        - A compelling blog post title
        - A 2-sentence excerpt/summary
        - 3-5 relevant tags

        Format your response as JSON with keys: title, excerpt, tech_advances, business_apps, use_cases, implementation, tags
        """
        
        return prompt
    
    def generate_blog_content(self, news_items: List[Dict]) -> Optional[Dict]:
        """Generate blog content using available AI services"""
        prompt = self.create_blog_prompt(news_items)
        
        # Try Gemini first (usually more reliable for structured content)
        content = self.generate_content_with_gemini(prompt)
        
        # If Gemini fails, try HuggingFace
        if not content:
            content = self.generate_content_with_huggingface(prompt)
        
        if not content:
            return None
        
        try:
            # Try to parse as JSON
            if content.strip().startswith('{'):
                return json.loads(content)
            else:
                # If not JSON, try to extract structured content
                return self.parse_unstructured_content(content)
        except:
            return self.parse_unstructured_content(content)
    
    def parse_unstructured_content(self, content: str) -> Dict:
        """Parse unstructured AI response into sections"""
        sections = {
            'title': 'AI Innovations This Month: Business Implementation Guide',
            'excerpt': 'Discover the latest AI breakthroughs and learn how to implement them in your business.',
            'tech_advances': '',
            'business_apps': '',
            'use_cases': '',
            'implementation': '',
            'tags': ['AI', 'Business', 'Innovation', 'Technology', 'Implementation']
        }
        
        # Basic section extraction (you might want to improve this)
        lines = content.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if any(keyword in line.lower() for keyword in ['technological advance', 'tech advance']):
                current_section = 'tech_advances'
            elif any(keyword in line.lower() for keyword in ['business application', 'business app']):
                current_section = 'business_apps'
            elif any(keyword in line.lower() for keyword in ['use case', 'benefit']):
                current_section = 'use_cases'
            elif any(keyword in line.lower() for keyword in ['implement', 'step']):
                current_section = 'implementation'
            elif current_section and line:
                sections[current_section] += line + '\n'
        
        return sections
    
    def create_html_post(self, content: Dict) -> str:
        """Create HTML blog post from content"""
        # Load template
        template_path = 'blog/templates/blog-template.html'
        if os.path.exists(template_path):
            with open(template_path, 'r') as f:
                template = f.read()
        else:
            # Fallback basic template
            template = self.get_basic_template()
        
        # Replace placeholders
        current_date = datetime.now().strftime("%B %d, %Y")
        slug = self.create_slug(content['title'])
        
        html = template.replace('{{TITLE}}', content['title'])
        html = html.replace('{{DATE}}', current_date)
        html = html.replace('{{EXCERPT}}', content['excerpt'])
        html = html.replace('{{TECH_ADVANCES}}', self.format_section(content['tech_advances']))
        html = html.replace('{{BUSINESS_APPS}}', self.format_section(content['business_apps']))
        html = html.replace('{{USE_CASES}}', self.format_section(content['use_cases']))
        html = html.replace('{{IMPLEMENTATION}}', self.format_section(content['implementation']))
        
        return html
    
    def format_section(self, text: str) -> str:
        """Format section text with proper HTML"""
        paragraphs = text.split('\n\n')
        formatted = ''
        for para in paragraphs:
            if para.strip():
                formatted += f'<p>{para.strip()}</p>\n'
        return formatted
    
    def create_slug(self, title: str) -> str:
        """Create URL-friendly slug from title"""
        slug = re.sub(r'[^\w\s-]', '', title.lower())
        slug = re.sub(r'[-\s]+', '-', slug)
        return slug.strip('-')
    
    def get_basic_template(self) -> str:
        """Basic HTML template fallback"""
        return """<!DOCTYPE html>
<html><head><title>{{TITLE}}</title></head>
<body>
<h1>{{TITLE}}</h1>
<p><em>{{DATE}}</em></p>
<p>{{EXCERPT}}</p>
<h2>Tech Advances</h2>
{{TECH_ADVANCES}}
<h2>Business Applications</h2>
{{BUSINESS_APPS}}
<h2>Use Cases</h2>
{{USE_CASES}}
<h2>Implementation</h2>
{{IMPLEMENTATION}}
</body></html>"""
    
    def save_post(self, content: Dict, html: str) -> str:
        """Save blog post and return filename"""
        slug = self.create_slug(content['title'])
        current_date = datetime.now()
        filename = f"{current_date.strftime('%Y-%m')}-{slug}.html"
        
        # Create staging directory if it doesn't exist
        os.makedirs('blog/staging', exist_ok=True)
        
        # Save HTML file
        filepath = f'blog/staging/{filename}'
        with open(filepath, 'w') as f:
            f.write(html)
        
        # Save metadata
        metadata = {
            'filename': filename,
            'title': content['title'],
            'excerpt': content['excerpt'],
            'date': current_date.isoformat(),
            'tags': content.get('tags', []),
            'slug': slug
        }
        
        with open(f'blog/staging/{slug}.json', 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return filename
    
    def generate_monthly_post(self) -> Optional[str]:
        """Main function to generate monthly blog post"""
        print("Starting AI blog generation...")
        
        # Step 1: Fetch recent AI news
        print("Fetching AI news...")
        news_items = self.fetch_ai_news()
        
        if not news_items:
            print("No AI news found. Aborting.")
            return None
        
        print(f"Found {len(news_items)} AI news items")
        
        # Step 2: Generate content
        print("Generating blog content...")
        content = self.generate_blog_content(news_items)
        
        if not content:
            print("Failed to generate content. Aborting.")
            return None
        
        print("Content generated successfully")
        
        # Step 3: Create HTML post
        print("Creating HTML post...")
        html = self.create_html_post(content)
        
        # Step 4: Save to staging
        filename = self.save_post(content, html)
        
        print(f"Blog post saved as: {filename}")
        print("Post is ready for manual review and approval!")
        
        return filename

if __name__ == "__main__":
    generator = AIBlogGenerator()
    generator.generate_monthly_post()
