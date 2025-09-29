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
    """Remove citation numbers and clean up Perplexity response formatting with COMPREHENSIVE fixes"""
    # Remove citation markers like [1], [2], etc.
    content = re.sub(r'\[\d+\]', '', content)
    
    # Remove standalone citation references at end of sentences
    content = re.sub(r'\s*\(\d+\)\s*', ' ', content)
    
    # CRITICAL: Fix broken formatting patterns that appear in your output
    # Remove stray bullets and dashes that shouldn't be there
    content = re.sub(r'•\s*[-–—]\s*', '', content)  # Remove "• -" patterns
    content = re.sub(r'[-–—]\s*•\s*', '', content)  # Remove "- •" patterns
    content = re.sub(r'•\s*•', '•', content)        # Remove double bullets
    content = re.sub(r':\s*•', ':', content)        # Remove ":•" patterns
    content = re.sub(r'•\s*:', ':', content)        # Remove "•:" patterns
    
    # Fix title formatting issues - remove stray bullets around titles
    content = re.sub(r'^•\s*(.*?)\s*•\s*$', r'\1', content, flags=re.MULTILINE)
    
    # Fix decimal number breaking (Claude 4.1 -> Claude 4 and 1)
    # Restore common version numbers and decimals
    content = re.sub(r'Claude Opus 4\s+1', 'Claude Opus 4.1', content)
    content = re.sub(r'Claude Sonnet 4\s+1', 'Claude Sonnet 4.1', content)
    content = re.sub(r'GPT-4\s+1', 'GPT-4.1', content)
    content = re.sub(r'(\d+)\s+(\d+)%', r'\1.\2%', content)  # Fix broken percentages
    
    # Handle line-by-line cleaning with better logic
    lines = content.split('\n')
    cleaned_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            cleaned_lines.append(line)
            continue
            
        # Check if this is a REAL numbered list item
        list_pattern = r'^(\d+)\.\s+([A-Z].*)'
        
        if re.match(list_pattern, line):
            # This is a real list item - keep as is
            cleaned_lines.append(line)
        else:
            # Clean up problematic formatting
            # Remove leading/trailing stray bullets
            line = re.sub(r'^[•\-–—]+\s*', '', line)
            line = re.sub(r'\s*[•\-–—]+$', '', line)
            
            # Remove weird colon-bullet combinations
            line = re.sub(r':\s*[•\-–—]+\s*([A-Z])', r': \1', line)
            line = re.sub(r'[•\-–—]+\s*:\s*([A-Z])', r': \1', line)
            
            # Clean up section headers that got mangled
            line = re.sub(r'^:\s*([A-Z][^:]*?)\s*:•', r'\1:', line)
            
            if line:  # Only add non-empty lines
                cleaned_lines.append(line)
    
    content = '\n'.join(cleaned_lines)
    
    # Final cleanup
    content = re.sub(r' +', ' ', content)  # Multiple spaces
    content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)  # Multiple newlines
    
    return content.strip()
def generate_blog_with_perplexity(api_key, topic=None):
    """Generate blog content using Perplexity API with flexible topic handling"""
    current_date = datetime.now()
    month_year = current_date.strftime("%B %Y")
    
    # SMART TOPIC HANDLING: Adapt prompts based on topic type
    if not topic:
        # DEFAULT: Monthly AI insights
        topic_type = "monthly_ai"
        topic = f"Latest AI developments and technology launches since last month - {month_year} focus on Canadian business impact"
    else:
        # CUSTOM TOPIC: Determine if it's AI-related or general business
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
    
    models_to_try = [
        "sonar-pro",
        "sonar-medium-online", 
        "sonar-small-online"
    ]
    
    # ADAPTIVE SYSTEM PROMPTS based on topic type
    if topic_type == "monthly_ai":
        # Your existing excellent system prompt for monthly AI insights
        system_prompt = f"""You are Robert Simon, an AI expert and digital transformation leader with 25+ years of experience, writing for Canadian business leaders.

Create a monthly AI insights post for {month_year} following this EXACT structure:

1. INTRODUCTION: Brief overview of the month's key AI developments (1 paragraph)

2. KEY AI DEVELOPMENTS: List 15 major AI technology launches, updates, or breakthroughs from the past month with SPECIFIC DATES and company details:
   - Each item MUST include the exact date (e.g., "September 25, 2025")
   - Include company names, product names, version numbers
   - Focus on major announcements, product launches, partnerships, funding rounds
   - Cover diverse areas: LLMs, enterprise AI, developer tools, research breakthroughs, hardware, regulations

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
CRITICAL REQUIREMENTS:
- Key AI Developments: EXACTLY 15 items, each with specific dates (e.g., "September 25, 2025")
- Include diverse AI developments: major model releases, enterprise partnerships, funding announcements, research papers, regulatory updates, hardware launches
- Each development MUST have: Company name, specific date, clear description
- Focus on developments from the past 30 days

Structure:
- Introduction: Overview of this month's key AI developments 
- Key AI Developments: 15 specific items with exact dates and company details
- Canadian Business Impact: How these affect Canadian businesses specifically
- Strategic Recommendations: 5 actionable steps for Canadian business leaders
- Conclusion: Strategic imperative for Canadian businesses

Examples of the format I want:
"September 25, 2025: Microsoft announced Claude integration into Office 365..."
"September 18, 2025: OpenAI released GPT-4.5 with improved reasoning..."
"September 12, 2025: Google DeepMind published breakthrough research on..."

Make sure every single development has a specific date in {month_year}.
- Canadian Business Impact: How these affect Canadian businesses specifically
- Strategic Recommendations: 5 actionable steps for Canadian business leaders
- Conclusion: Strategic imperative for Canadian businesses

Focus on developments from the past 30 days. Include specific company names, product launches, and real dates."""

    elif topic_type == "custom_ai":
        # Custom AI topic - force into structured format
        system_prompt = f"""You are Robert Simon, an AI expert and digital transformation leader with 25+ years of experience, writing for Canadian business leaders.

Create an AI insights post about "{topic}" following this EXACT structure:

1. INTRODUCTION: Brief overview of the topic and its relevance to Canadian businesses (1 paragraph)

2. KEY DEVELOPMENTS: List 4-5 major points, developments, or aspects related to "{topic}" with specific details, companies, or examples

3. CANADIAN BUSINESS IMPACT: Analyze how "{topic}" specifically affects Canadian businesses, considering:
   - Canadian market conditions
   - Regulatory environment (PIPEDA, AIDA considerations)
   - Cross-border business implications
   - Currency and economic factors
   - Competitive positioning vs US/global markets

4. STRATEGIC RECOMMENDATIONS: Provide 5 specific, actionable recommendations for Canadian business leaders regarding "{topic}"

5. CONCLUSION: Strategic imperative for Canadian businesses related to "{topic}" (1 paragraph)

Write in a professional, authoritative tone. Be specific and provide practical, actionable insights."""
        
        user_prompt = f"""Write an AI insights blog post for Canadian business leaders about "{topic}".

You MUST follow this exact structure:
- Introduction: Overview of "{topic}" and its business relevance
- Key Developments: 4-5 major points or aspects about "{topic}" with specific details
- Canadian Business Impact: How "{topic}" specifically affects Canadian businesses
- Strategic Recommendations: 5 actionable steps for Canadian business leaders
- Conclusion: Strategic imperative for Canadian businesses

Focus on practical insights and real-world applications. Include specific examples where possible."""

    else:  # custom_business
        # General business topic - adapt structure
        system_prompt = f"""You are Robert Simon, a digital transformation leader with 25+ years of experience, writing for Canadian business leaders.

Create a business insights post about "{topic}" following this EXACT structure:

1. INTRODUCTION: Brief overview of "{topic}" and its relevance to Canadian businesses (1 paragraph)

2. KEY INSIGHTS: List 4-5 major points, trends, or developments related to "{topic}" with specific details and examples

3. CANADIAN BUSINESS IMPACT: Analyze how "{topic}" specifically affects Canadian businesses, considering:
   - Canadian market conditions
   - Regulatory environment and compliance considerations
   - Economic and competitive factors
   - Cross-border implications where relevant

4. STRATEGIC RECOMMENDATIONS: Provide 5 specific, actionable recommendations for Canadian business leaders regarding "{topic}"

5. CONCLUSION: Strategic imperative for Canadian businesses related to "{topic}" (1 paragraph)

Write in a professional, authoritative tone. Be specific and provide practical, actionable insights."""
        
        user_prompt = f"""Write a business insights blog post for Canadian business leaders about "{topic}".

You MUST follow this exact structure:
- Introduction: Overview of "{topic}" and its business relevance
- Key Insights: 4-5 major points or developments about "{topic}" with specific details
- Canadian Business Impact: How "{topic}" specifically affects Canadian businesses  
- Strategic Recommendations: 5 actionable steps for Canadian business leaders
- Conclusion: Strategic imperative for Canadian businesses

Focus on practical insights and real-world applications. Include specific examples and data where possible."""

    # Rest of the function - try models and generate content
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
                
                # Clean the content
                cleaned_content = clean_perplexity_content(content)
                
                print(f"Content received from model {model} ({len(cleaned_content)} characters)")
                return {
                    "content": cleaned_content,
                    "citations": data.get("citations", []),
                    "usage": data.get("usage", {}),
                    "topic_type": topic_type  # Include topic type for potential use
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
    """Enhanced parsing that works with both AI insights and custom topics"""
    sections = {
        'introduction': '',
        'developments': [],
        'canadian_impact': '',
        'recommendations': [],
        'conclusion': ''
    }
    
    # Clean up the content first
    content = re.sub(r'\*\*(.*?)\*\*', r'\1', content)
    content = re.sub(r'\*(.*?)\*', r'\1', content)
    
    print("DEBUG: Starting enhanced content parsing...")
    print(f"DEBUG: Content length: {len(content)}")
    
    content_lower = content.lower()
    
    # FLEXIBLE SECTION DETECTION - works for both AI and general business topics
    dev_patterns = [
        'key ai development', 'ai development', 'major development', 
        'technological advance', 'key developments', 'major ai',
        'key insights', 'main insights', 'major insights',  # For business topics
        'key points', 'main points', 'major points'
    ]
    
    impact_patterns = [
        'canadian business impact', 'impact on canadian', 'canadian impact',
        'canadian business', 'impact on canada', 'business impact'
    ]
    
    rec_patterns = [
        'strategic recommendation', 'recommendation', 'strategic action',
        'action step', 'strategic step', 'recommendations for'
    ]
    
    conclusion_patterns = [
        'conclusion', 'strategic imperative', 'final thought',
        'in conclusion', 'finally', 'key takeaway'
    ]
    
    # Find section boundaries
    dev_start = -1
    dev_end = -1
    impact_start = -1
    impact_end = -1
    rec_start = -1
    rec_end = -1
    conclusion_start = -1
    
    # Look for development/insights section
    for pattern in dev_patterns:
        pos = content_lower.find(pattern)
        if pos != -1:
            dev_start = pos
            break
    
    # Look for Canadian impact section
    for pattern in impact_patterns:
        pos = content_lower.find(pattern)
        if pos != -1 and pos > dev_start:
            impact_start = pos
            dev_end = pos
            break
    
    # Look for recommendations section
    for pattern in rec_patterns:
        pos = content_lower.find(pattern)
        if pos != -1 and pos > impact_start:
            rec_start = pos
            impact_end = pos
            break
    
    # Look for conclusion section
    for pattern in conclusion_patterns:
        pos = content_lower.find(pattern)
        if pos != -1 and pos > rec_start:
            conclusion_start = pos
            rec_end = pos
            break
    
    print(f"DEBUG: Section positions - dev:{dev_start}, impact:{impact_start}, rec:{rec_start}, conclusion:{conclusion_start}")
    
    # Extract sections based on found positions
    if dev_start > 0:
        sections['introduction'] = content[:dev_start].strip()
    
    if dev_start != -1 and dev_end != -1:
        dev_text = content[dev_start:dev_end].strip()
        sections['developments'] = parse_development_items(dev_text)
    
    if impact_start != -1 and impact_end != -1:
        impact_text = content[impact_start:impact_end].strip()
        # Remove the section header
        for pattern in impact_patterns:
            if pattern in impact_text.lower():
                impact_text = re.sub(re.escape(pattern), '', impact_text, flags=re.IGNORECASE).strip()
                break
        sections['canadian_impact'] = impact_text
    
    if rec_start != -1 and rec_end != -1:
        rec_text = content[rec_start:rec_end].strip()
        sections['recommendations'] = parse_recommendation_items(rec_text)
    
    if conclusion_start != -1:
        conclusion_text = content[conclusion_start:].strip()
        # Remove the section header
        for pattern in conclusion_patterns:
            if pattern in conclusion_text.lower():
                conclusion_text = re.sub(re.escape(pattern), '', conclusion_text, flags=re.IGNORECASE).strip()
                break
        sections['conclusion'] = conclusion_text
    
    # FALLBACK PARSING if structured parsing fails
    if not any([sections['developments'], sections['canadian_impact'], sections['recommendations']]):
        print("WARNING: Primary parsing failed, trying enhanced paragraph-based parsing")
        
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip() and len(p.strip()) > 50]
        
        current_section = 'introduction'
        for para in paragraphs:
            para_lower = para.lower()
            
            # Check if this paragraph is a section header
            if any(pattern in para_lower for pattern in dev_patterns):
                current_section = 'developments'
                continue
            elif any(pattern in para_lower for pattern in impact_patterns):
                current_section = 'canadian_impact'
                continue
            elif any(pattern in para_lower for pattern in rec_patterns):
                current_section = 'recommendations'
                continue
            elif any(pattern in para_lower for pattern in conclusion_patterns):
                current_section = 'conclusion'
                continue
            
            # Add content to current section
            if current_section == 'introduction' and not sections['introduction']:
                sections['introduction'] = para
            elif current_section == 'developments':
                bullet_items = extract_bullets_from_paragraph(para)
                sections['developments'].extend(bullet_items)
            elif current_section == 'canadian_impact' and not sections['canadian_impact']:
                sections['canadian_impact'] = para
            elif current_section == 'recommendations':
                rec_items = extract_bullets_from_paragraph(para)
                sections['recommendations'].extend(rec_items)
            elif current_section == 'conclusion' and not sections['conclusion']:
                sections['conclusion'] = para
    
    print(f"DEBUG: Final parsed sections - intro: {bool(sections['introduction'])}, dev: {len(sections['developments'])}, impact: {bool(sections['canadian_impact'])}, rec: {len(sections['recommendations'])}, conc: {bool(sections['conclusion'])}")
    
    return sections

def extract_bullets_from_paragraph(paragraph):
    """Extract bullet points from a paragraph that contains dashes or bullets"""
    items = []
    
    # Look for items that start with bullet markers
    lines = paragraph.split('. ')
    for line in lines:
        line = line.strip()
        
        # Skip if too short
        if len(line) < 30:
            continue
            
        # Remove unwanted dashes at the start
        line = re.sub(r'^[-•*]\s*[-•*]\s*', '', line)
        line = re.sub(r'^[-•*]\s*', '', line)
            
        # Look for patterns that suggest bullet points
        if any(marker in line for marker in ['Microsoft', 'Google', 'OpenAI', 'Anthropic', 'NVIDIA']):
            # Clean up the line further
            clean_line = re.sub(r'^\d+\.\s*', '', line)
            
            if clean_line and len(clean_line) > 20:
                items.append(clean_line)
    
    return items

def parse_development_items(text):
    """Parse development items with SMART period handling for abbreviations and version numbers"""
    items = []
    
    # Split by actual list markers, but preserve decimal numbers in content
    lines = text.split('\n')
    current_item = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Check if this starts a new list item (number + period + space + capital letter)
        # But exclude obvious decimal numbers (like "4.1%" or "version 2.3")
        list_start_pattern = r'^(\d+)\.\s+([A-Z].*)'
        
        if re.match(list_start_pattern, line) and not re.search(r'\d+\.\d+', line[:10]):
            # Save previous item if exists
            if current_item:
                item_text = ' '.join(current_item).strip()
                if len(item_text) > 50:
                    items.append(item_text)
            
            # Start new item (remove the number prefix)
            current_item = [re.sub(r'^\d+\.\s*', '', line)]
        else:
            # Continue current item
            if current_item:
                current_item.append(line)
            elif len(line) > 50:  # Start new item if substantial
                current_item = [line]
    
    # Add final item
    if current_item:
        item_text = ' '.join(current_item).strip()
        if len(item_text) > 50:
            items.append(item_text)
    
    # If we still don't have good items, try SMART sentence-based extraction
    if len(items) < 5:
        # Use smarter splitting that preserves abbreviations and version numbers
        smart_items = []
        
        # Replace common abbreviations temporarily to protect them
        protected_text = text
        abbreviations = {
            'U.S.': 'USPROTECTED',
            'U.K.': 'UKPROTECTED', 
            'E.U.': 'EUPROTECTED',
            'A.I.': 'AIPROTECTED',
            'U.N.': 'UNPROTECTED',
            'Inc.': 'IncPROTECTED',
            'Corp.': 'CorpPROTECTED',
            'Ltd.': 'LtdPROTECTED',
            'Co.': 'CoPROTECTED',
            'vs.': 'vsPROTECTED',
            'etc.': 'etcPROTECTED',
            'Dr.': 'DrPROTECTED',
            'Mr.': 'MrPROTECTED',
            'Ms.': 'MsPROTECTED',
            'Mrs.': 'MrsPROTECTED'
        }
        
        # Protect version numbers (like 4.1, 2.5, etc.)
        version_pattern = r'\b(\d+\.\d+)\b'
        version_matches = re.findall(version_pattern, protected_text)
        version_replacements = {}
        for i, version in enumerate(version_matches):
            replacement = f'VERSION{i}PROTECTED'
            version_replacements[replacement] = version
            protected_text = protected_text.replace(version, replacement)
            # ENHANCED protection for common patterns
protected_text = re.sub(r'\bU\.S\.', 'USPROTECTED', protected_text)
protected_text = re.sub(r'\bU\.K\.', 'UKPROTECTED', protected_text)
protected_text = re.sub(r'\bE\.U\.', 'EUPROTECTED', protected_text)
protected_text = re.sub(r'\bA\.I\.', 'AIPROTECTED', protected_text)
protected_text = re.sub(r'\bGPT(\d+)\.', r'GPTVERSION\1DOT', protected_text)
protected_text = re.sub(r'\bClaude-(\d+)\.', r'CLAUDEVERSION\1DOT', protected_text)

# Replace abbreviations
for abbrev, replacement in abbreviations.items():
    protected_text = protected_text.replace(abbrev, replacement)

# Now split by sentences
sentences = re.split(r'[.!?]+', protected_text)
        
        for sentence in sentences:
            sentence = sentence.strip()
            # Restore enhanced protections
sentence = re.sub(r'USPROTECTED', 'U.S.', sentence)
sentence = re.sub(r'UKPROTECTED', 'U.K.', sentence)
sentence = re.sub(r'EUPROTECTED', 'E.U.', sentence)
sentence = re.sub(r'AIPROTECTED', 'A.I.', sentence)
sentence = re.sub(r'GPTVERSION(\d+)DOT(\d+)PROTECTED', r'GPT-\1.\2', sentence)
sentence = re.sub(r'CLAUDEVERSION(\d+)DOT(\d+)PROTECTED', r'Claude-\1.\2', sentence)
            # Restore protected text
            for replacement, original in abbreviations.items():
                sentence = sentence.replace(replacement, original)
            for replacement, original in version_replacements.items():
                sentence = sentence.replace(replacement, original)
            
            # Look for sentences mentioning companies with substantial content
            if (len(sentence) > 50 and 
                any(company in sentence for company in ['Microsoft', 'OpenAI', 'Google', 'Anthropic', 'NVIDIA', 'Meta', 'Amazon', 'Apple', 'Tesla', 'IBM', 'Intel', 'AMD']) and
                not re.match(r'^\d+\.\s', sentence)):  # Not already a numbered item
                smart_items.append(sentence)
        
        if len(smart_items) >= len(items):
            items = smart_items
    if len(smart_items) >= len(items):
            items = smart_items
    
    # Filter out section headers from items
    filtered_items = []
    for item in items:
        item_lower = item.lower()
        # Skip if this looks like a section header
        if not any(header in item_lower for header in ['key ai development', 'major development', 'key insights']):
            filtered_items.append(item)
            
    return filtered_items[:15]  # Return up to 15 items now

def parse_recommendation_items(text):
    """Parse recommendation items with better decimal handling"""
    items = []
    
    # Similar approach - look for real list items vs decimal numbers
    lines = text.split('\n')
    current_item = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Real list item pattern
        list_start_pattern = r'^(\d+)\.\s+([A-Z].*)'
        
        if re.match(list_start_pattern, line) and not re.search(r'\d+\.\d+', line[:15]):
            # Save previous item
            if current_item:
                item_text = ' '.join(current_item).strip()
                if len(item_text) > 30:
                    items.append(item_text)
            
            # Start new item
            current_item = [re.sub(r'^\d+\.\s*', '', line)]
        else:
            if current_item:
                current_item.append(line)
            elif len(line) > 30:
                current_item = [line]
    
    # Add final item
    if current_item:
        item_text = ' '.join(current_item).strip()
        if len(item_text) > 30:
            items.append(item_text)
    
    return items[:5]
def generate_dynamic_conclusion(sections):
    """Generate a dynamic Strategic Imperative based on the blog content"""
    
    # Extract key themes and technologies from developments
    key_themes = []
    technologies = []
    companies = []
    
    if sections['developments']:
        for item in sections['developments']:
            item_lower = item.lower()
            
            # Extract company names
            company_names = ['Microsoft', 'OpenAI', 'Google', 'Anthropic', 'NVIDIA', 'Meta', 'Amazon', 'Apple', 'Tesla', 'IBM', 'Intel', 'AMD']
            for company in company_names:
                if company.lower() in item_lower and company not in companies:
                    companies.append(company)
            
            # Extract technology themes
            tech_keywords = {
                'AI models': ['model', 'llm', 'gpt', 'claude', 'chatgpt', 'language model'],
                'enterprise AI': ['enterprise', 'business', 'copilot', 'office', 'productivity'],
                'AI safety': ['safety', 'alignment', 'responsible', 'ethics', 'governance'],
                'automation': ['automation', 'workflow', 'process', 'efficiency'],
                'partnerships': ['partnership', 'collaboration', 'integration', 'alliance'],
                'hardware': ['chip', 'gpu', 'processor', 'computing', 'infrastructure'],
                'research': ['research', 'breakthrough', 'innovation', 'development'],
                'regulation': ['regulation', 'policy', 'compliance', 'government'],
                'funding': ['funding', 'investment', 'capital', 'funding round']
            }
            
            for theme, keywords in tech_keywords.items():
                if any(keyword in item_lower for keyword in keywords) and theme not in key_themes:
                    key_themes.append(theme)
    
    # Extract impact areas from Canadian impact section
    impact_areas = []
    if sections['canadian_impact']:
        impact_text = sections['canadian_impact'].lower()
        
        impact_keywords = {
            'competitive advantage': ['competitive', 'advantage', 'competition'],
            'regulatory compliance': ['regulatory', 'compliance', 'pipeda', 'aida'],
            'cross-border operations': ['cross-border', 'international', 'global'],
            'market positioning': ['market', 'positioning', 'leadership'],
            'operational efficiency': ['efficiency', 'productivity', 'optimization'],
            'innovation capacity': ['innovation', 'transformation', 'modernization'],
            'talent acquisition': ['talent', 'skills', 'workforce'],
            'cost optimization': ['cost', 'savings', 'budget']
        }
        
        for area, keywords in impact_keywords.items():
            if any(keyword in impact_text for keyword in keywords) and area not in impact_areas:
                impact_areas.append(area)
    
    # Generate dynamic conclusion based on content
    conclusion_parts = []
    
    # Opening based on key themes
    if len(key_themes) >= 3:
        top_themes = key_themes[:3]
        conclusion_parts.append(f"With major advances in {', '.join(top_themes[:-1])} and {top_themes[-1]}")
    elif len(key_themes) >= 2:
        conclusion_parts.append(f"With significant developments in {' and '.join(key_themes)}")
    elif key_themes:
        conclusion_parts.append(f"With critical advances in {key_themes[0]}")
    else:
        conclusion_parts.append("With accelerating AI innovation")
    
    # Add company context if we have multiple major players
    if len(companies) >= 3:
        conclusion_parts.append(f"from industry leaders like {', '.join(companies[:3])}")
    elif len(companies) >= 2:
        conclusion_parts.append(f"from {' and '.join(companies)}")
    
    # Add the imperative action
    if impact_areas:
        primary_impact = impact_areas[0] if impact_areas else "competitive advantage"
        conclusion_parts.append(f"Canadian businesses must act decisively to maintain {primary_impact}")
        
        if len(impact_areas) >= 2:
            conclusion_parts.append(f"while strengthening {impact_areas[1]}")
    else:
        conclusion_parts.append("Canadian businesses must act decisively to harness these breakthroughs")
    
    # Add urgency and market context
    if 'enterprise AI' in key_themes or 'partnerships' in key_themes:
        conclusion_parts.append("before competitors gain insurmountable advantages in the rapidly evolving AI landscape")
    elif 'regulation' in key_themes:
        conclusion_parts.append("while navigating the evolving regulatory landscape to maintain competitive positioning")
    else:
        conclusion_parts.append("to remain competitive in the global AI-driven economy")
    
    # Combine all parts into a coherent conclusion
    conclusion = ' '.join(conclusion_parts).replace(' ,', ',')
    
    # Ensure it ends with a period
    if not conclusion.endswith('.'):
        conclusion += '.'
    
    # Capitalize the first letter
    conclusion = conclusion[0].upper() + conclusion[1:] if conclusion else "Canadian businesses must act decisively to harness AI breakthroughs while maintaining competitive advantage in the global marketplace."
    
    return conclusion

# Also update the create_html_blog_post function to use dynamic conclusion
# Find this line in create_html_blog_post():
# conclusion_text = sections['conclusion'] if sections['conclusion'] else "Canadian businesses must act decisively to harness AI breakthroughs while maintaining competitive advantage in the global marketplace."

# Replace it with:
# Generate dynamic conclusion based on content
# if sections['conclusion']:
#     conclusion_text = sections['conclusion']
# else:
#     conclusion_text = generate_dynamic_conclusion(sections)
def create_html_blog_post(content, title, excerpt):
    """Create complete HTML blog post with PROPERLY FORMATTED content sections"""
    current_date = datetime.now()
    formatted_date = current_date.strftime("%B %d, %Y")
    month_year = current_date.strftime("%B %Y")
    
    # Parse all content sections
    sections = parse_structured_content(content)
    
    # Build content HTML with ALL sections PROPERLY FORMATTED
    content_html = []
    
    # Introduction section
    if sections['introduction']:
        # Clean up any unwanted dashes in introduction
        intro_clean = re.sub(r'[-•*]\s*[-•*]\s*', '', sections['introduction'])
        intro_clean = re.sub(r'^\s*[-•*]\s*', '', intro_clean)
        content_html.append(f'''
                <div class="section">
                    <p>{intro_clean}</p>
                </div>''')
    
    # Key developments section
    if sections['developments']:
        dev_items = []
        for item in sections['developments']:
            # Clean up the item and remove unwanted dashes
            clean_item = item.strip()
            clean_item = re.sub(r'^[-•*]\s*[-•*]\s*', '', clean_item)
            clean_item = re.sub(r'^[-•*]\s*', '', clean_item)
            
            if ':' in clean_item:
                parts = clean_item.split(':', 1)
                dev_items.append(f'<li><strong>{parts[0].strip()}:</strong> {parts[1].strip()}</li>')
            else:
                # Try to extract company name for bolding
                words = clean_item.split()
                if len(words) > 0:
                    # Look for company names to bold
                    company_names = ['Microsoft', 'OpenAI', 'Google', 'Anthropic', 'NVIDIA', 'Meta', 'Amazon', 'Apple']
                    for company in company_names:
                        if company in clean_item:
                            clean_item = clean_item.replace(company, f'<strong>{company}</strong>')
                            break
                    dev_items.append(f'<li>{clean_item}</li>')
        
        if dev_items:
            content_html.append(f'''
                <div class="section">
                    <h2 class="section-title">Key AI Developments This Month</h2>
                    <ul class="bullet-list">
                        {chr(10).join(['                        ' + item for item in dev_items])}
                    </ul>
                </div>''')
    
    # Canadian business impact section - convert to bullet points if it contains multiple points
    if sections['canadian_impact']:
        impact_text = sections['canadian_impact']
        # Clean unwanted dashes
        impact_text = re.sub(r'[-•*]\s*[-•*]\s*', '', impact_text)
        impact_text = re.sub(r'^\s*[-•*]\s*', '', impact_text)
        
        # Check if the text contains natural bullet points or can be split into points
        if any(marker in impact_text for marker in ['-', '•', 'First', 'Second', 'Additionally', 'Furthermore', 'Moreover']):
            # Try to split into bullet points
            # Split by sentences and look for logical breaks
            sentences = [s.strip() + '.' for s in impact_text.split('.') if s.strip()]
            impact_items = []
            
            current_point = []
            for sentence in sentences:
                current_point.append(sentence)
                # If we have a substantial point (100+ chars), make it a bullet
                if len(' '.join(current_point)) > 100:
                    point_text = ' '.join(current_point).strip()
                    if point_text:
                        # Remove any remaining unwanted dashes
                        point_text = re.sub(r'^[-•*]\s*', '', point_text)
                        impact_items.append(f'<li>{point_text}</li>')
                    current_point = []
            
            # Add any remaining content
            if current_point:
                point_text = ' '.join(current_point).strip()
                if point_text:
                    point_text = re.sub(r'^[-•*]\s*', '', point_text)
                    impact_items.append(f'<li>{point_text}</li>')
            
            if len(impact_items) >= 2:  # Use bullets if we have multiple points
                content_html.append(f'''
                <div class="section">
                    <h2 class="section-title">Impact on Canadian Businesses</h2>
                    <ul class="bullet-list">
                        {chr(10).join(['                        ' + item for item in impact_items])}
                    </ul>
                </div>''')
            else:
                # Fall back to paragraph format
                content_html.append(f'''
                <div class="section">
                    <h2 class="section-title">Impact on Canadian Businesses</h2>
                    <p>{impact_text}</p>
                </div>''')
        else:
            # Use paragraph format for single coherent text
            content_html.append(f'''
                <div class="section">
                    <h2 class="section-title">Impact on Canadian Businesses</h2>
                    <p>{impact_text}</p>
                </div>''')
    
    # Strategic recommendations section
    if sections['recommendations']:
        rec_items = []
        for i, item in enumerate(sections['recommendations']):
            clean_item = item.strip()
            # Remove unwanted dashes
            clean_item = re.sub(r'^[-•*]\s*[-•*]\s*', '', clean_item)
            clean_item = re.sub(r'^[-•*]\s*', '', clean_item)
            
            if ':' in clean_item:
                parts = clean_item.split(':', 1)
                rec_items.append(f'<li><strong>{parts[0].strip()}:</strong> {parts[1].strip()}</li>')
            else:
                # Add a generic title if none exists
                if not clean_item.startswith(('1.', '2.', '3.', '4.', '5.')):
                    rec_items.append(f'<li><strong>Strategic Action {i+1}:</strong> {clean_item}</li>')
                else:
                    # Remove numbering and use as bullet
                    clean_item = re.sub(r'^\d+\.\s*', '', clean_item)
                    rec_items.append(f'<li>{clean_item}</li>')
        
        if rec_items:
            content_html.append(f'''
                <div class="section">
                    <h2 class="section-title">Strategic Recommendations for Canadian Leaders</h2>
                    <ul class="bullet-list numbered">
                        {chr(10).join(['                        ' + item for item in rec_items])}
                    </ul>
                </div>''')
    
    # If we don't have enough structured content, fall back to paragraphs
    if len(content_html) < 3:
        print("WARNING: Insufficient structured parsing, using paragraph fallback")
        # Split content into paragraphs and create basic structure
        clean_content = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', content)
        clean_content = re.sub(r'\*(.*?)\*', r'<em>\1</em>', clean_content)
        # Remove unwanted dashes from fallback content too
        clean_content = re.sub(r'[-•*]\s*[-•*]\s*', '• ', clean_content)
        clean_content = re.sub(r'^\s*[-•*]\s*[-•*]\s*', '• ', clean_content, flags=re.MULTILINE)
        
        paragraphs = [p.strip() for p in clean_content.split('\n\n') if p.strip() and len(p.strip()) > 50]
        content_html = []
        for para in paragraphs[:6]:  # Limit to avoid overwhelming
            content_html.append(f'''
                <div class="section">
                    <p>{para}</p>
                </div>''')
    
    # Generate dynamic conclusion based on content
    if sections['conclusion']:
        conclusion_text = sections['conclusion']
    else:
        conclusion_text = generate_dynamic_conclusion(sections)
    
    # Clean conclusion text too
    conclusion_text = re.sub(r'[-•*]\s*[-•*]\s*', '', conclusion_text)
    conclusion_text = re.sub(r'^\s*[-•*]\s*', '', conclusion_text)
    
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
            font-size: 2rem;
            color: var(--dark-navy);
            margin-bottom: 1.5rem;
            margin-top: 2rem;
            font-weight: 700;
            position: relative;
            padding-left: 1.5rem;
            line-height: 1.2;
            border-bottom: 3px solid var(--primary-blue);
            padding-bottom: 0.5rem;
            display: block;
        }}

        .section-title::before {{
            content: '';
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0.5rem;
            width: 4px;
            background: var(--gradient-primary);
            border-radius: 2px;
        }}

        .bullet-list {{
            margin-bottom: 2rem;
            padding-left: 0;
            list-style: none;
        }}

        .bullet-list li {{
            margin-bottom: 1.5rem;
            line-height: 1.8;
            color: var(--medium-gray);
            position: relative;
            padding-left: 2.5rem;
            font-size: 1.05rem;
        }}

        .bullet-list li::before {{
            content: '●';
            position: absolute;
            left: 0;
            color: var(--primary-blue);
            font-weight: bold;
            font-size: 1.2rem;
            top: 0.1rem;
        }}

        .bullet-list.numbered li {{
            counter-increment: list-counter;
        }}

        .bullet-list.numbered li::before {{
            content: counter(list-counter) '.';
            background: var(--gradient-primary);
            color: white;
            width: 1.8rem;
            height: 1.8rem;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            font-size: 0.85rem;
            top: 0.1rem;
        }}

        .bullet-list.numbered {{
            counter-reset: list-counter;
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
    """Enhanced title and excerpt extraction with ROBUST cleaning"""
    current_date = datetime.now()
    month_year = current_date.strftime("%B %Y")
    
    # FIRST: Clean the content thoroughly before processing
    clean_content = clean_perplexity_content(content)
    
    # Split into lines for analysis
    lines = [line.strip() for line in clean_content.split("\n") if line.strip()]
    
    # Look for a clear title in the first few lines
    potential_title = None
    for line in lines[:5]:
        if line and len(line) > 10 and len(line) < 100:
            # Skip obvious headers/markers and problematic formatting
            line_lower = line.lower()
            if not line_lower.startswith(('introduction', 'key', 'major', '1.', '2.', '•', '-')):
                # Additional cleaning for title
                clean_title = re.sub(r'^[•\-–—:]+\s*', '', line)  # Remove leading symbols
                clean_title = re.sub(r'\s*[•\-–—:]+$', '', clean_title)  # Remove trailing symbols
                clean_title = re.sub(r'[•\-–—]', '', clean_title)  # Remove any remaining symbols
                clean_title = clean_title.strip()
                
                if clean_title and len(clean_title) > 10:
                    potential_title = clean_title
                    break
    
    # Generate appropriate title
    if potential_title and not potential_title.lower().startswith('ai insights'):
        title = potential_title
    else:
        title = f"AI Insights for {month_year}"
    
    # Extract excerpt from cleaned content
    excerpt = ""
    
    # Look for introduction paragraph
    for line in lines:
        if line and len(line) > 100 and not line.startswith(('#', '1.', '2.', '3.', '4.', '5.', '•', '-', '*')):
            # Make sure it's not a header
            header_keywords = ['key ai development', 'canadian business impact', 'strategic recommendation', 'conclusion', 'key insights', 'major points']
            if not any(header in line.lower() for header in header_keywords):
                # Clean the excerpt
                clean_excerpt = re.sub(r'^[•\-–—:]+\s*', '', line)
                clean_excerpt = re.sub(r'\s*[•\-–—:]+$', '', clean_excerpt)
                clean_excerpt = re.sub(r'[•\-–—]', '', clean_excerpt)
                clean_excerpt = clean_excerpt.strip()
                
                if clean_excerpt:
                    excerpt = clean_excerpt[:200] + "..." if len(clean_excerpt) > 200 else clean_excerpt
                    break
    
    if not excerpt:
        excerpt = f"Strategic insights and practical guidance for Canadian business leaders - {month_year} analysis."
    
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
    """Create blog index page with FILE EXISTENCE VALIDATION"""
    if not posts:
        return None
    
    # CRITICAL: Validate that post files actually exist before including them
    validated_posts = []
    posts_dir = "blog/posts"
    
    for post in posts:
        file_path = os.path.join(posts_dir, post['filename'])
        if os.path.exists(file_path):
            validated_posts.append(post)
            print(f"✅ Validated post exists: {post['filename']}")
        else:
            print(f"⚠️  Skipping missing post: {post['filename']}")
    
    if not validated_posts:
        print("WARNING: No valid post files found after validation")
        return None
    
    latest_post = validated_posts[0]
    older_posts = validated_posts[1:] if len(validated_posts) > 1 else []
    
    # Create posts HTML for older posts (only validated ones)
    older_posts_html = ""
    for post in older_posts:
        older_posts_html += f"""
                <div class="older-post-item">
                    <a href="/blog/posts/{post['filename']}" class="older-post-link">
                        <div class="older-post-title">{post['title']}</div>
                        <div class="older-post-date">{post['date']}</div>
                    </a>
                </div>"""
    
    # Create older posts section HTML only if we have validated older posts
    older_posts_section = ""
    if older_posts:
        older_posts_section = f"""<section class="older-posts-section fade-in">
            <h3 class="older-posts-title">Previous Insights</h3>
            <div class="older-posts-grid">
                {older_posts_html}
            </div>
        </section>"""
    else:
        print("INFO: No older posts to display - section will be hidden")

    blog_index_html = f"""<!DOCTYPE html>
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
            color: var(--primary-blue);
            margin-bottom: 0.5rem;
            line-height: 1.4;
            text-decoration: underline;
            text-decoration-color: var(--primary-blue);
            text-underline-offset: 3px;
            text-decoration-thickness: 1px;
        }}

        .older-post-link:hover {{
            background-color: rgba(37, 99, 235, 0.02);
        }}

        .older-post-link:hover .older-post-title {{
            text-decoration-thickness: 2px;
            color: var(--secondary-blue);
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

        <!-- Older Posts Section -->
        {older_posts_section}
    </div>
</body>
</html>"""

    return blog_index_html

def update_blog_index():
    """Update blog index with ROBUST file validation"""
    posts_dir = "blog/posts"
    index_file = "blog/index.html"
    
    print(f"DEBUG: Checking posts directory: {posts_dir}")
    
    if not os.path.exists(posts_dir):
        print(f"ERROR: Posts directory {posts_dir} does not exist")
        return []
    
    posts = []
    html_files = [f for f in os.listdir(posts_dir) if f.endswith(".html") and f != "index.html"]
    
    print(f"DEBUG: Found potential HTML files: {html_files}")
    
    # VALIDATE each file exists and is readable
    valid_files = []
    for file in html_files:
        file_path = os.path.join(posts_dir, file)
        try:
            # Double-check file exists and is readable
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                valid_files.append(file)
                print(f"✅ File validated: {file}")
            else:
                print(f"⚠️  Skipping invalid file: {file}")
        except Exception as e:
            print(f"❌ Error validating {file}: {e}")
    
    if not valid_files:
        print("WARNING: No valid HTML files found after validation")
        return []

    print(f"Processing {len(valid_files)} validated HTML files")

    for file in sorted(valid_files, reverse=True):
        file_path = os.path.join(posts_dir, file)
        try:
            post_info = extract_post_info(file_path)
            # Final validation - ensure the post_info is complete
            if post_info.get('title') and post_info.get('filename'):
                posts.append(post_info)
                print(f"✅ Processed: {file} -> {post_info['title']}")
            else:
                print(f"⚠️  Skipping incomplete post info: {file}")
        except Exception as e:
            print(f"❌ Error processing {file}: {e}")
            continue

    if not posts:
        print("ERROR: No valid posts could be processed after all validation")
        return []

    # Create blog index with validated posts only
    new_blog_index = create_blog_index_html(posts)
    if not new_blog_index:
        print("ERROR: Failed to create blog index HTML")
        return posts
    
    # Write the new blog index
    try:
        with open(index_file, "w", encoding="utf-8") as f:
            f.write(new_blog_index)
        print(f"✅ Blog index recreated with {len(posts)} VALIDATED posts")
        print("🔒 All links guaranteed to point to existing files")
    except Exception as e:
        print(f"❌ Error writing blog index: {e}")
    
    return posts

def main():
    parser = argparse.ArgumentParser(description="COMPLETE Blog Generator - Proper Start")
    parser.add_argument("--topic", help="Custom topic for the blog post")
    parser.add_argument("--output", default="posts", choices=["staging", "posts"],
                        help="Output directory (staging for review, posts for direct publish)")
    args = parser.parse_args()
    
    print("🔧 RUNNING COMPLETE BLOG GENERATOR")
    print("=" * 50)
    print(f"📂 Output directory: {args.output}")
    
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
        print(f"✅ HTML content generated with PROPERLY FORMATTED content ({len(html_content)} characters)")
        
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
        
        print("🎉 COMPLETE SCRIPT EXECUTED SUCCESSFULLY!")
        print("🔗 Check your blog at: /blog/ (now with beautiful styling)")
        print("🔗 Latest post at: /blog/posts/latest.html (now with properly structured content)")
        
    except Exception as e:
        print(f"💥 Blog generation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
