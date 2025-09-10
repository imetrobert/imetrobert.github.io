import os
import requests
from datetime import datetime, timedelta
import json
import re

class PerplexityBlogGenerator:
    def __init__(self):
        self.api_key = os.getenv('PERPLEXITY_API_KEY')
        self.base_url = "https://api.perplexity.ai/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def search_ai_news(self):
        """Use Perplexity's search to find recent AI news"""
        current_date = datetime.now().strftime('%Y-%m-%d')
        last_week = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        
        search_query = f"""Search for the most important AI and artificial intelligence news, developments, and breakthroughs from the past 7 days (since {last_week}). 

Focus on:
- Major AI company announcements and funding rounds
- New AI model releases and capabilities
- Enterprise AI adoption news
- AI regulation and policy updates
- Breakthrough AI research papers and discoveries
- AI product launches and partnerships
- Industry trends and market movements

Please provide a comprehensive summary of the top 10-15 most significant AI developments from this week, including sources and dates where available."""
        
        payload = {
            "model": "llama-3.1-sonar-large-128k-online",
            "messages": [
                {
                    "role": "user",
                    "content": search_query
                }
            ],
            "max_tokens": 4000,
            "temperature": 0.3,
            "search_domain_filter": ["techcrunch.com", "venturebeat.com", "theverge.com", "arstechnica.com", "wired.com", "artificialintelligence-news.com"],
            "return_citations": True,
            "search_recency_filter": "week"
        }
        
        try:
            response = requests.post(self.base_url, headers=self.headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content']
            
        except Exception as e:
            print(f"Error fetching AI news: {e}")
            return None
    
    def generate_blog_content(self, news_summary):
        """Generate blog post using Perplexity"""
        current_date = datetime.now().strftime('%B %d, %Y')
        
        if not news_summary:
            return self.generate_fallback_content()
        
        blog_prompt = f"""You are Robert Simon, an AI thought leader and digital transformation expert who has been shaping the digital landscape since 1996. You currently lead AI integration at Bell, transforming MyBell into Canada's #1 telecom app.

Based on the following AI news research, write a comprehensive weekly blog post for your AI insights blog.

Your writing style should be:
- Professional yet approachable, showing deep AI expertise
- Strategic focus on business implications and digital transformation
- First-person perspective as an industry veteran
- Forward-looking insights and predictions
- Connect developments to broader enterprise trends
- Show practical understanding from your experience at Bell

Blog Requirements:
- Title: "AI Weekly Insights - {current_date}"
- 1200-1600 words
- Use markdown formatting with ## for main sections
- Include relevant insights about enterprise AI adoption
- Reference your experience in digital transformation since 1996
- End with forward-looking strategic perspective
- Professional tone that establishes thought leadership

AI News Research:
{news_summary}

Write an engaging, authoritative blog post that demonstrates your expertise in AI strategy and digital transformation:"""
        
        payload = {
            "model": "llama-3.1-sonar-large-128k-online",
            "messages": [
                {
                    "role": "user", 
                    "content": blog_prompt
                }
            ],
            "max_tokens": 4000,
            "temperature": 0.7,
        }
        
        try:
            response = requests.post(self.base_url, headers=self.headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            return result['choices'][0]['message']['content']
            
        except Exception as e:
            print(f"Error generating blog content: {e}")
            return self.generate_fallback_content()
    
    def generate_fallback_content(self):
        """Generate fallback content when API calls fail"""
        current_date = datetime.now().strftime('%B %d, %Y')
        
        return f"""# AI Weekly Insights - {current_date}

## Reflecting on AI's Transformative Journey

As someone who's been navigating the digital transformation landscape since 1996, I've witnessed countless technological shifts. But the current AI revolution feels different--more profound, more immediate, and more transformative than anything we've seen before.

## Enterprise AI: Beyond the Hype

From my experience leading AI integration at Bell, I've learned that successful AI implementation isn't just about adopting the latest technology. It's about fundamentally reimagining how we deliver value to customers.

### The Bell MyBell Transformation
When we set out to transform MyBell into Canada's #1 telecom app, AI wasn't just a feature--it became the backbone of our customer experience strategy. The key lessons:

- **Personalization at Scale**: AI enabled us to deliver individualized experiences to millions of users
- **Predictive Support**: We moved from reactive customer service to predictive problem-solving
- **Continuous Learning**: Our systems improve with every interaction, creating compound value

## What I'm Watching This Week

### Enterprise Adoption Acceleration
Organizations are moving beyond pilot programs to production-scale AI deployments. The companies succeeding are those treating AI as a strategic transformation, not just operational efficiency.

### The Integration Challenge
The real challenge isn't building AI--it's integrating it seamlessly into existing business processes. This is where my decades of digital transformation experience become invaluable.

## Strategic Implications for Leaders

### 1. AI as a Competitive Moat
Organizations that successfully integrate AI aren't just improving efficiency--they're creating entirely new value propositions that competitors struggle to replicate.

### 2. The Data Advantage
Companies with rich, clean data sets have an insurmountable advantage. This isn't about having more data--it's about having better, more actionable data.

### 3. Cultural Transformation
The most successful AI implementations require cultural shifts. Teams need to embrace experimentation, accept intelligent failures, and continuously adapt.

## Looking Forward: My Predictions

Based on current trajectories and my experience in digital transformation, here's what I expect to see:

- **Hyper-Personalized Experiences**: AI will enable mass customization at unprecedented scales
- **Invisible AI**: The best AI implementations will be those customers never consciously notice
- **AI-First Organizations**: Companies will restructure around AI capabilities, not just add AI to existing processes

## The Human Element

Despite all the automation capabilities, the most successful AI implementations enhance human potential rather than replace it. At Bell, our AI systems amplify our team's abilities to deliver exceptional customer experiences.

## Final Thoughts

We're still in the early innings of the AI transformation. The organizations that will thrive are those that view AI not as a technology to be deployed, but as a fundamental shift in how business creates and delivers value.

The next decade will belong to companies that successfully blend AI capabilities with human insight to create experiences that were previously impossible.

*What AI developments are you most excited about? How is your organization approaching AI integration? I'd love to hear your perspectives.*

---
*Robert Simon is an AI thought leader and digital transformation expert who has been shaping digital experiences since 1996. He currently leads AI integration initiatives and has helped transform applications serving millions of users.*
"""
    
    def create_jekyll_post(self, content):
        """Create Jekyll markdown post file"""
        today = datetime.now()
        filename = f"_posts/{today.strftime('%Y-%m-%d')}-ai-weekly-insights.md"
        
        # Extract title from content
        title_match = re.search(r'^#\s+(.+)', content, re.MULTILINE)
        if title_match:
            title = title_match.group(1)
        else:
            title = f"AI Weekly Insights - {today.strftime('%B %d, %Y')}"
        
        # Jekyll front matter
        front_matter = f"""---
layout: post
title: "{title}"
date: {today.strftime('%Y-%m-%d %H:%M:%S')} +0000
categories: ai insights weekly
tags: artificial-intelligence digital-transformation tech-analysis business-strategy
author: "Robert Simon"
description: "Weekly insights on AI developments and digital transformation from AI thought leader Robert Simon"
---

"""
        
        # Ensure _posts directory exists
        os.makedirs('_posts', exist_ok=True)
        
        # Write the post file
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(front_matter + content)
        
        print(f"✅ Created blog post: {filename}")
        return filename

def main():
    print("🤖 Starting Perplexity AI Blog Generator...")
    generator = PerplexityBlogGenerator()
    
    print("🔍 Searching for recent AI news with Perplexity...")
    news_summary = generator.search_ai_news()
    
    if news_summary:
        print("📰 Found recent AI developments")
        print("✍️ Generating blog content...")
        content = generator.generate_blog_content(news_summary)
    else:
        print("⚠️ Using fallback content due to search issues")
        content = generator.generate_fallback_content()
    
    print("📝 Creating Jekyll post...")
    filename = generator.create_jekyll_post(content)
    
    print(f"🎉 Blog post generated successfully!")
    print(f"📄 File: {filename}")
    print("🚀 Post will be live once GitHub Pages rebuilds the site")

if __name__ == "__main__":
    main()