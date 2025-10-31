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
    content = re.sub(r'\[\d+\]', '', content)
    content = re.sub(r'\s*\(\d+\)\s*', ' ', content)
    content = re.sub(r'•\s*[-–—]\s*', '', content)
    content = re.sub(r'[-–—]\s*•\s*', '', content)
    content = re.sub(r'•\s*•', '•', content)
    content = re.sub(r':\s*•', ':', content)
    content = re.sub(r'•\s*:', ':', content)
    content = re.sub(r'^•\s*(.*?)\s*•\s*$', r'\1', content, flags=re.MULTILINE)
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

def generate_blog_with_perplexity(api_key, topic=None):
    """Generate blog content using Perplexity API"""
    current_date = datetime.now()
    month_year = current_date.strftime("%B %Y")
    
    if not topic:
        topic_type = "monthly_ai"
        topic = f"Latest AI developments and technology launches since last month - {month_year} focus on Canadian business impact"
    else:
        topic_lower = topic.lower()
        ai_keywords = ['ai', 'artificial intelligence', 'machine learning', 'automation', 'technology', 'digital', 'innovation']
        if any(keyword in topic_lower for keyword in ai_keywords):
            topic_type = "custom_ai"
        else:
            topic_type = "custom_business"
    
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    models_to_try = ["sonar-pro", "sonar-medium-online", "sonar-small-online"]
    
    if topic_type == "monthly_ai":
        system_prompt = f"""You are Robert Simon, an AI expert and digital transformation leader with 25+ years of experience, writing for Canadian business leaders.

Create a monthly AI insights post for {month_year} with EXACTLY these 6 sections in this EXACT order:

SECTION 1 - NO HEADING: Write 1 paragraph introduction (do NOT include a heading like "Introduction")

SECTION 2 - HEADING "Key AI Developments This Month": List exactly 15 major AI developments from the past month with specific dates and company names. Write each as a separate paragraph or bullet point.

SECTION 3 - HEADING "Impact on Canadian Businesses": Write 1-2 paragraphs analyzing how these developments affect Canadian businesses

SECTION 4 - HEADING "Strategic Recommendations for Canadian Leaders": Provide exactly 5 actionable recommendations. Write each recommendation as a separate paragraph starting with an action verb like "Prioritize", "Invest", etc.

SECTION 5 - HEADING "Canadian Business AI Adoption Metrics": Provide 3-5 separate data points with percentages. Write each metric as a separate sentence or paragraph.

SECTION 6 - HEADING "Conclusion": Write 1 paragraph strategic imperative

CRITICAL: You MUST include ALL 6 SECTIONS. Section 5 (Canadian Business AI Adoption Metrics) is MANDATORY and must contain 3-5 separate statistics with percentages."""
        
        user_prompt = f"""Write an AI insights blog post for {month_year} with EXACTLY 6 sections in this order:

1. Introduction paragraph (NO HEADING) - 1 paragraph
2. Key AI Developments This Month - 15 separate items with dates
3. Impact on Canadian Businesses - 1-2 paragraphs
4. Strategic Recommendations for Canadian Leaders - 5 separate recommendations, each starting with action words
5. Canadian Business AI Adoption Metrics - 3-5 separate statistics with percentages (THIS IS MANDATORY)
6. Conclusion - 1 paragraph

CRITICAL REQUIREMENT FOR SECTION 5:
Write 3-5 SEPARATE statistics about Canadian AI adoption. Each must include percentages. Format each as a separate sentence."""

    elif topic_type == "custom_ai":
        system_prompt = f"""You are Robert Simon, an AI expert and digital transformation leader with 25+ years of experience, writing for Canadian business leaders.

Create an AI insights post about "{topic}" with EXACTLY these 6 sections in this EXACT order:

SECTION 1 - NO HEADING: Write 1 paragraph introduction (do NOT include a heading like "Introduction")

SECTION 2 - HEADING "Key AI Developments": List 8-10 major points or developments related to "{topic}". Write each as a separate paragraph.

SECTION 3 - HEADING "Impact on Canadian Businesses": Write 1-2 paragraphs analyzing how "{topic}" affects Canadian businesses

SECTION 4 - HEADING "Strategic Recommendations for Canadian Leaders": Provide exactly 5 actionable recommendations. Write each as a separate paragraph starting with action verbs.

SECTION 5 - HEADING "Canadian Business AI Adoption Metrics": Provide 3-5 data points with percentages about AI adoption in Canada related to "{topic}". Write each as a separate sentence with percentage.

SECTION 6 - HEADING "Conclusion": Write 1 paragraph strategic imperative

CRITICAL: You MUST include ALL 6 SECTIONS including Section 5 with adoption statistics."""
        
        user_prompt = f"""Write an AI insights blog post for Canadian business leaders about "{topic}".

You MUST include EXACTLY 6 sections:
1. Introduction paragraph (NO HEADING)
2. Key AI Developments - 8-10 items about "{topic}"
3. Impact on Canadian Businesses - analysis paragraphs
4. Strategic Recommendations for Canadian Leaders - 5 separate recommendations
5. Canadian Business AI Adoption Metrics - 3-5 statistics with percentages (MANDATORY)
6. Conclusion - strategic imperative

For Section 5, include statistics like:
"X% of Canadian businesses in [sector] use AI for {topic}"
"Adoption of {topic} grew Y% in Canada"
"Z% of Canadian leaders consider {topic} a priority"

DO NOT SKIP SECTION 5."""

    else:
        system_prompt = f"""You are Robert Simon, a digital transformation leader with 25+ years of experience, writing for Canadian business leaders.

Create a business insights post about "{topic}" with EXACTLY these 6 sections in this EXACT order:

SECTION 1 - NO HEADING: Write 1 paragraph introduction (do NOT include a heading like "Introduction")

SECTION 2 - HEADING "Key Insights": List 8-10 major points, trends, or developments related to "{topic}". Write each as a separate paragraph.

SECTION 3 - HEADING "Impact on Canadian Businesses": Write 1-2 paragraphs analyzing how "{topic}" affects Canadian businesses

SECTION 4 - HEADING "Strategic Recommendations for Canadian Leaders": Provide exactly 5 actionable recommendations. Write each as a separate paragraph starting with action verbs.

SECTION 5 - HEADING "Canadian Business AI Adoption Metrics": Provide 3-5 data points with percentages about how Canadian businesses are adopting or implementing aspects of "{topic}". Write each as a separate sentence with percentage.

SECTION 6 - HEADING "Conclusion": Write 1 paragraph strategic imperative

CRITICAL: You MUST include ALL 6 SECTIONS including Section 5 with adoption statistics."""
        
        user_prompt = f"""Write a business insights blog post for Canadian business leaders about "{topic}".

You MUST include EXACTLY 6 sections:
1. Introduction paragraph (NO HEADING)
2. Key Insights - 8-10 items about "{topic}"
3. Impact on Canadian Businesses - analysis paragraphs
4. Strategic Recommendations for Canadian Leaders - 5 separate recommendations
5. Canadian Business AI Adoption Metrics - 3-5 statistics with percentages (MANDATORY)
6. Conclusion - strategic imperative

For Section 5, include statistics like:
"X% of Canadian businesses have adopted [aspect of topic]"
"Y% of Canadian companies report [metric related to topic]"
"Adoption of [topic] in Canada grew Z%"

DO NOT SKIP SECTION 5."""

    for model in models_to_try:
        print(f"Trying Perplexity model: {model} for topic type: {topic_type}")
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
                
                cleaned_content = clean_perplexity_content(content)
                
                print(f"Content received from model {model} ({len(cleaned_content)} characters)")
                return {
                    "content": cleaned_content,
                    "citations": data.get("citations", []),
                    "usage": data.get("usage", {}),
                    "topic_type": topic_type
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

# Other parsing, HTML rendering, and utility functions (parse_structured_content, extract_bullets_from_paragraph, etc.)
# Should be placed here, but for brevity, only the main structure and fixes are shown.

# Make sure all function definitions are complete, non-repetitive, and correctly indented.

# Usage example (main):
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate AI blog post for Canadian business leaders.")
    parser.add_argument('--api-key', required=True, help="Perplexity API Key")
    parser.add_argument('--topic', default=None, help="Custom topic for the blog")
    args = parser.parse_args()

    try:
        result = generate_blog_with_perplexity(args.api_key, args.topic)
        print(result["content"])
    except Exception as e:
        print(f"Blog generation failed: {e}", file=sys.stderr)
        sys.exit(1)
