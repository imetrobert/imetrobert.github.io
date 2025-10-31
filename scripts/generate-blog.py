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

SECTION 4 - HEADING "Strategic Recommendations for Canadian Leaders": Provide exactly 5 actionable recommendations. Write each recommendation as a separate paragraph starting with an action verb like "Prioritize", "Invest", "Develop", "Establish", or "Implement".

SECTION 5 - HEADING "Canadian Business AI Adoption Metrics": Provide 3-5 separate data points with percentages. Write each metric as a separate sentence or paragraph. Examples:
- "15.2% of Canadian businesses have adopted AI, up from 12.8% in August 2025"
- "Personal AI usage in Canada reached 38.5% in September 2025"
- "Financial services lead adoption at 24.3%, followed by technology at 22.1%"
- "Manufacturing sector adoption grew 3.2 percentage points to 18.7%"

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
Write 3-5 SEPARATE statistics about Canadian AI adoption. Each must include percentages. Format each as a separate sentence:

"15.2% of Canadian businesses have adopted AI, up from 12.8% last month."
"Personal AI usage in Canada reached 38.5%."
"Financial services adoption is at 24.3%."
"Manufacturing adoption grew to 18.7%."
"Healthcare sector adoption reached 16.2%."

DO NOT SKIP SECTION 5. It must have real statistics with percentage numbers."""

    elif topic_type == "custom_ai":
        system_prompt = f"""You are Robert Simon, an AI expert and digital transformation leader with 25+ years of experience, writing for Canadian business leaders.

Create an AI insights post about "{topic}" with EXACTLY these 6 sections in this EXACT order:

SECTION 1 - NO HEADING: Write 1 paragraph introduction (do NOT include a heading like "Introduction")

SECTION 2 - HEADING "Key AI Developments": List 8-10 major points or developments related to "{topic}". Write each as a separate paragraph.

SECTION 3 - HEADING "Impact on Canadian Businesses": Write 1-2 paragraphs analyzing how "{topic}" affects Canadian businesses

SECTION 4 - HEADING "Strategic Recommendations for Canadian Leaders": Provide exactly 5 actionable recommendations. Write each as a separate paragraph starting with action verbs.

SECTION 5 - HEADING "Canadian Business AI Adoption Metrics": Provide 3-5 data points with percentages about AI adoption in Canada related to "{topic}". Write each as a separate sentence with percentages.

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

SECTION 5 - HEADING "Canadian Business AI Adoption Metrics": Provide 3-5 data points with percentages about how Canadian businesses are adopting or implementing aspects of "{topic}". Write each as a separate sentence with percentages.

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

def parse_structured_content(content):
    """Enhanced parsing that works with both AI insights and custom topics"""
    sections = {
        'introduction': '',
        'developments': [],
        'canadian_impact': '',
        'recommendations': [],
        'adoption_metrics': [],
        'conclusion': ''
    }
    
    content = re.sub(r'\*\*(.*?)\*\*', r'\1', content)
    content = re.sub(r'\*(.*?)\*', r'\1', content)
    
    print("DEBUG: Starting enhanced content parsing...")
    print(f"DEBUG: Content length: {len(content)}")
    
    content_lower = content.lower()
    
    dev_patterns = [
        'key ai development', 'ai development', 'major development', 
        'technological advance', 'key developments', 'major ai',
        'key insights', 'main insights', 'major insights',
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
    
    adoption_patterns = [
        'canadian business ai adoption', 'ai adoption metrics', 'adoption metrics',
        'canadian ai adoption', 'adoption data', 'adoption statistics'
    ]
    
    conclusion_patterns = [
        'conclusion', 'strategic imperative', 'final thought',
        'in conclusion', 'finally', 'key takeaway'
    ]
    
    dev_start = -1
    dev_end = -1
    impact_start = -1
    impact_end = -1
    rec_start = -1
    rec_end = -1
    adoption_start = -1
    adoption_end = -1
    conclusion_start = -1
    
    for pattern in dev_patterns:
        pos = content_lower.find(pattern)
        if pos != -1:
            dev_start = pos
            break
    
    for pattern in impact_patterns:
        pos = content_lower.find(pattern)
        if pos != -1 and pos > dev_start:
            impact_start = pos
            dev_end = pos
            break
    
    for pattern in rec_patterns:
        pos = content_lower.find(pattern)
        if pos != -1 and (impact_start == -1 or pos > impact_start):
            rec_start = pos
            if impact_start != -1:
                impact_end = pos
            break
    
    for pattern in adoption_patterns:
        pos = content_lower.find(pattern)
        if pos != -1 and (rec_start == -1 or pos > rec_start):
            adoption_start = pos
            if rec_start != -1:
                rec_end = pos
            break
    
    for pattern in conclusion_patterns:
        pos = content_lower.find(pattern)
        if pos != -1 and (adoption_start == -1 or pos > adoption_start):
            conclusion_start = pos
            if adoption_start != -1:
                adoption_end = pos
            break
    
    if rec_start != -1 and rec_end == -1:
        if conclusion_start != -1:
            rec_end = conclusion_start
        else:
            rec_end = len(content)
    
    if adoption_start != -1 and adoption_end == -1:
        adoption_end = len(content)
    
    print(f"DEBUG: Section positions - dev:{dev_start}, impact:{impact_start}, rec:{rec_start}, adoption:{adoption_start}, conclusion:{conclusion_start}")
    
    if dev_start != -1:
        print(f"DEBUG: Dev section header: '{content[dev_start:dev_start+50]}'")
    if impact_start != -1:
        print(f"DEBUG: Impact section header: '{content[impact_start:impact_start+50]}'")
    if rec_start != -1:
        print(f"DEBUG: Rec section header: '{content[rec_start:rec_start+50]}'")
    if adoption_start != -1:
        print(f"DEBUG: Adoption section header: '{content[adoption_start:adoption_start+50]}'")
    if conclusion_start != -1:
        print(f"DEBUG: Conclusion section header: '{content[conclusion_start:conclusion_start+50]}'")
    
    if dev_start > 0:
        sections['introduction'] = content[:dev_start].strip()
    
    if dev_start != -1 and dev_end != -1:
        dev_text = content[dev_start:dev_end].strip()
        sections['developments'] = parse_development_items(dev_text)
    
    if impact_start != -1 and impact_end != -1:
        impact_text = content[impact_start:impact_end].strip()
        for pattern in impact_patterns:
            if pattern in impact_text.lower():
                impact_text = re.sub(re.escape(pattern), '', impact_text, flags=re.IGNORECASE).strip()
                break
        sections['canadian_impact'] = impact_text
    
    if rec_start != -1 and rec_end != -1:
        rec_text = content[rec_start:rec_end].strip()
        print(f"DEBUG: Raw rec text length: {len(rec_text)}")
        print(f"DEBUG: First 200 chars of rec text: '{rec_text[:200]}'")
        sections['recommendations'] = parse_recommendation_items(rec_text)
        print(f"DEBUG: Parsed {len(sections['recommendations'])} recommendations")
    else:
        print(f"DEBUG: Recommendations section NOT FOUND - rec_start={rec_start}, rec_end={rec_end}")
    
    if adoption_start != -1 and adoption_end != -1:
        adoption_text = content[adoption_start:adoption_end].strip()
        print(f"DEBUG: Found adoption section from pos {adoption_start} to {adoption_end}")
        print(f"DEBUG: Adoption text preview: {adoption_text[:200]}...")
        sections['adoption_metrics'] = parse_adoption_metrics(adoption_text)
    else:
        print("DEBUG: Adoption metrics section NOT FOUND in content")
        print(f"DEBUG: Looking for patterns: {adoption_patterns}")
        if 'adoption' in content_lower:
            print("DEBUG: Word 'adoption' exists in content but section not matched")
            adoption_mentions = [i for i, word in enumerate(content_lower.split()) if 'adoption' in word]
            print(f"DEBUG: 'adoption' appears at word positions: {adoption_mentions[:5]}")
    
    if conclusion_start != -1:
        conclusion_text = content[conclusion_start:].strip()
        for pattern in conclusion_patterns:
            if pattern in conclusion_text.lower():
                conclusion_text = re.sub(re.escape(pattern), '', conclusion_text, flags=re.IGNORECASE).strip()
                break
        sections['conclusion'] = conclusion_text
    
    if not any([sections['developments'], sections['canadian_impact'], sections['recommendations']]):
        print("WARNING: Primary parsing failed, trying enhanced paragraph-based parsing")
        
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip() and len(p.strip()) > 50]
        
        current_section = 'introduction'
        for para in paragraphs:
            para_lower = para.lower()
            
            if any(pattern in para_lower for pattern in dev_patterns):
                current_section = 'developments'
                continue
            elif any(pattern in para_lower for pattern in impact_patterns):
                current_section = 'canadian_impact'
                continue
            elif any(pattern in para_lower for pattern in rec_patterns):
                current_section = 'recommendations'
                continue
            elif any(pattern in para_lower for pattern in adoption_patterns):
                current_section = 'adoption_metrics'
                continue
            elif any(pattern in para_lower for pattern in conclusion_patterns):
                current_section = 'conclusion'
                continue
            
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
            elif current_section == 'adoption_metrics':
                adoption_items = extract_bullets_from_paragraph(para)
                sections['adoption_metrics'].extend(adoption_items)
            elif current_section == 'conclusion' and not sections['conclusion']:
                sections['conclusion'] = para
    
    print(f"DEBUG: Final parsed sections - intro: {bool(sections['introduction'])}, dev: {len(sections['developments'])}, impact: {bool(sections['canadian_impact'])}, rec: {len(sections['recommendations'])}, adoption: {len(sections['adoption_metrics'])}, conc: {bool(sections['conclusion'])}")
    
    return sections

def extract_bullets_from_paragraph(paragraph):
    """Extract bullet points from a paragraph that contains dashes or bullets"""
    items = []
    
    lines = paragraph.split('. ')
    for line in lines:
        line = line.strip()
        
        if len(line) < 30:
            continue
            
        line = re.sub(r'^[-•*]\s*[-•*]\s*', '', line)
        line = re.sub(r'^[-•*]\s*', '', line)
            
        if any(marker in line for marker in ['Microsoft', 'Google', 'OpenAI', 'Anthropic', 'NVIDIA']):
            clean_line = re.sub(r'^\d+\.\s*', '', line)
            
            if clean_line and len(clean_line) > 20:
                items.append(clean_line)
    
    return items

def parse_development_items(text):
    """Parse development items with SMART period handling for abbreviations and version numbers"""
    items = []
    
    lines = text.split('\n')
    current_item = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        list_start_pattern = r'^(\d+)\.\s+([A-Z].*)'
        
        if re.match(list_start_pattern, line) and not re.search(r'\d+\.\d+', line[:10]):
            if current_item:
                item_text = ' '.join(current_item).strip()
                if len(item_text) > 50:
                    items.append(item_text)
            
            current_item = [re.sub(r'^\d+\.\s*', '', line)]
        else:
            if current_item:
                current_item.append(line)
            elif len(line) > 50:
                current_item = [line]
    
    if current_item:
        item_text = ' '.join(current_item).strip()
        if len(item_text) > 50:
            items.append(item_text)
    
    if len(items) < 5:
        smart_items = []
        
        protected_text = text
        abbreviations = {
            'U.S.': 'USPROTECTED',
            'U.K.': 'UKPROTECTED', 
            'E.U.': 'EUPROTECTED',
            'A.I.': 'AIPROTECTED',
            'Inc.': 'IncPROTECTED',
            'Corp.': 'CorpPROTECTED'
        }
        
        version_pattern = r'\b(\d+\.\d+)\b'
        version_matches = re.findall(version_pattern, protected_text)
        version_replacements = {}
        for i, version in enumerate(version_matches):
            replacement = f'VERSION{i}PROTECTED'
            version_replacements[replacement] = version
            protected_text = protected_text.replace(version, replacement)
        
        for abbrev, replacement in abbreviations.items():
            protected_text = protected_text.replace(abbrev, replacement)

        sentences = re.split(r'[.!?]+', protected_text)
        
        for sentence in sentences:
            sentence = sentence.strip()
            
            for replacement, original in abbreviations.items():
                sentence = sentence.replace(replacement, original)
            for replacement, original in version_replacements.items():
                sentence = sentence.replace(replacement, original)
            
            if (len(sentence) > 50 and 
                any(company in sentence for company in ['Microsoft', 'OpenAI', 'Google', 'Anthropic', 'NVIDIA', 'Meta', 'Amazon', 'Apple']) and
                not re.match(r'^\d+\.\s', sentence)):
                smart_items.append(sentence)
        
        if len(smart_items) >= len(items):
            items = smart_items
    
    filtered_items = []
    for item in items:
        item_lower = item.lower()
        if not any(header in item_lower for header in ['key ai development', 'major development', 'key insights']):
            filtered_items.append(item)
            
    return filtered_items[:15]

def parse_recommendation_items(text):
    """Parse recommendation items - handles both numbered lists AND paragraph-separated items"""
    items = []
    
    header_keywords = [
        'strategic recommendation', 
        'recommendations for canadian leaders',
        'recommendations for', 
        'strategic action',
        'for canadian leaders',
        'for canadian business',
        'action steps'
    ]
    
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        line_lower = line.strip().lower()
        if line_lower and not any(line_lower == header or line_lower.startswith(header + ':') for header in header_keywords):
            cleaned_lines.append(line.strip())
    
    text = '\n'.join(cleaned_lines)
    
    current_item = []
    
    for line in cleaned_lines:
        if not line:
            continue
        
        list_start_pattern = r'^(\d+)\.\s+([A-Z].*)'
        is_list_number = re.match(list_start_pattern, line) and not re.search(r'^\d+\.\d+', line[:15])
        
        if is_list_number:
            if current_item:
                item_text = ' '.join(current_item).strip()
                if len(item_text) > 30:
                    items.append(item_text)
            
            current_item = [re.sub(r'^\d+\.\s*', '', line)]
        else:
            if len(line) > 30 and ':' in line and not current_item:
                current_item = [line]
            elif current_item:
                current_item.append(line)
            elif len(line) > 30:
                current_item = [line]
    
    if current_item:
        item_text = ' '.join(current_item).strip()
        if len(item_text) > 30:
            items.append(item_text)
    
    if len(items) < 3:
        print("DEBUG: Numbered list parsing found < 3 items, trying paragraph-based parsing")
        
        paragraphs = []
        current_para = []
        
        for line in cleaned_lines:
            if not line:
                if current_para:
                    paragraphs.append(' '.join(current_para))
                    current_para = []
            else:
                if current_para and len(line) > 30 and line[0].isupper():
                    paragraphs.append(' '.join(current_para))
                    current_para = [line]
                else:
                    current_para.append(line)
        
        if current_para:
            paragraphs.append(' '.join(current_para))
        
        paragraph_items = []
        for para in paragraphs:
            para = para.strip()
            if len(para) > 30:
                action_words = ['prioritize', 'invest', 'develop', 'establish', 'implement', 
                               'create', 'build', 'focus', 'ensure', 'adopt', 'enhance',
                               'strengthen', 'leverage', 'foster', 'collaborate']
                
                para_lower = para.lower()
                if any(word in para_lower for word in action_words):
                    paragraph_items.append(para)
        
        if len(paragraph_items) > len(items):
            items = paragraph_items
    
    print(f"DEBUG parse_recommendation_items: Found {len(items)} items")
    for i, item in enumerate(items[:3]):
        print(f"DEBUG rec item {i+1}: {item[:100]}...")
    
    return items[:5]

def parse_adoption_metrics(text):
    """Parse adoption metrics - handles both numbered lists AND paragraph-separated items"""
    items = []
    
    lines = text.split('\n')
    current_item = []
    
    header_keywords = [
        'canadian business ai adoption',
        'ai adoption metrics',
        'adoption metrics',
        'adoption statistics'
    ]
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        line_lower = line.lower()
        if any(header in line_lower for header in header_keywords):
            continue
            
        list_start_pattern = r'^(\d+)\.\s+([A-Z].*)'
        
        if re.match(list_start_pattern, line) and not re.search(r'\d+\.\d+', line[:15]):
            if current_item:
                item_text = ' '.join(current_item).strip()
                if len(item_text) > 20:
                    item_lower = item_text.lower()
                    if not any(header in item_lower for header in header_keywords):
                        items.append(item_text)
            
            current_item = [re.sub(r'^\d+\.\s*', '', line)]
        else:
            if current_item:
                current_item.append(line)
            elif len(line) > 20:
                current_item = [line]
    
    if current_item:
        item_text = ' '.join(current_item).strip()
        if len(item_text) > 20:
            item_lower = item_text.lower()
            if not any(header in item_lower for header in header_keywords):
                items.append(item_text)
    
    if len(items) < 2:
        print("DEBUG: Numbered list parsing found < 2 adoption items, trying sentence-based parsing")
        
        sentences = []
        current_sentence = []
        
        for line in lines:
            line = line.strip()
            line_lower = line.lower()
            
            if any(header in line_lower for header in header_keywords):
                continue
            
            if not line:
                if current_sentence:
                    sentences.append(' '.join(current_sentence))
                    current_sentence = []
            else:
                if '%' in line or 'adoption' in line_lower:
                    if current_sentence:
                        sentences.append(' '.join(current_sentence))
                    current_sentence = [line]
                elif current_sentence:
                    current_sentence.append(line)
        
        if current_sentence:
            sentences.append(' '.join(current_sentence))
        
        sentence_items = []
        for sent in sentences:
            sent = sent.strip()
            if len(sent) > 20 and ('%' in sent or 'adoption' in sent.lower()):
                sent_lower = sent.lower()
                if not any(header in sent_lower for header in header_keywords):
                    sentence_items.append(sent)
        
        if len(sentence_items) > len(items):
            items = sentence_items
    
    print(f"DEBUG parse_adoption_metrics: Found {len(items)} items")
    for i, item in enumerate(items[:3]):
        print(f"DEBUG adoption item {i+1}: {item[:100]}...")
    
    return items[:5]

def generate_dynamic_conclusion(sections):
    """Generate a dynamic Strategic Imperative based on the blog content"""
    key_themes = []
    companies = []
    
    if sections['developments']:
        for item in sections['developments']:
            item_lower = item.lower()
            
            company_names = ['Microsoft', 'OpenAI', 'Google', 'Anthropic', 'NVIDIA', 'Meta', 'Amazon', 'Apple']
            for company in company_names:
                if company.lower() in item_lower and company not in companies:
                    companies.append(company)
            
            tech_keywords = {
                'AI models': ['model', 'llm', 'gpt', 'claude', 'chatgpt'],
                'enterprise AI': ['enterprise', 'business', 'copilot', 'office'],
                'automation': ['automation', 'workflow', 'process'],
                'partnerships': ['partnership', 'collaboration', 'integration']
            }
            
            for theme, keywords in tech_keywords.items():
                if any(keyword in item_lower for keyword in keywords) and theme not in key_themes:
                    key_themes.append(theme)
    
    conclusion_parts = []
    
    if len(key_themes) >= 2:
        conclusion_parts.append(f"With significant developments in {' and '.join(key_themes[:2])}")
    elif key_themes:
        conclusion_parts.append(f"With critical advances in {key_themes[0]}")
    else:
        conclusion_parts.append("With accelerating AI innovation")
    
    if len(companies) >= 2:
        conclusion_parts.append(f"from {' and '.join(companies[:2])}")
    
    conclusion_parts.append("Canadian businesses must act decisively to harness these breakthroughs")
    conclusion_parts.append("to remain competitive in the global AI-driven economy")
    
    conclusion = ' '.join(conclusion_parts)
    
    if not conclusion.endswith('.'):
        conclusion += '.'
    
    return conclusion[0].upper() + conclusion[1:] if conclusion else "Canadian businesses must act decisively to harness AI breakthroughs while maintaining competitive advantage in the global marketplace."

def extract_title_and_excerpt(content):
    """Enhanced title and excerpt extraction with ROBUST cleaning"""
    current_date = datetime.now()
    month_year = current_date.strftime("%B %Y")
    
    clean_content = clean_perplexity_content(content)
    lines = [line.strip() for line in clean_content.split("\n") if line.strip()]
    
    potential_title = None
    for line in lines[:5]:
        if line and len(line) > 10 and len(line) < 100:
            line_lower = line.lower()
            if not line_lower.startswith(('introduction', 'key', 'major', '1.', '2.', '•', '-')):
                clean_title = re.sub(r'^[•\-–—:]+\s*', '', line)
                clean_title = re.sub(r'\s*[•\-–—:]+$', '', clean_title)
                clean_title = re.sub(r'[•\-–—]', '', clean_title)
                clean_title = clean_title.strip()
                
                if clean_title and len(clean_title) > 10:
                    potential_title = clean_title
                    break
    
    if potential_title and not potential_title.lower().startswith('ai insights'):
        title = potential_title
    else:
        title = f"AI Insights for {month_year}"
    
    excerpt = ""
    for line in lines:
        if line and len(line) > 100 and not line.startswith(('#', '1.', '2.', '3.', '4.', '5.', '•', '-', '*')):
            header_keywords = ['key ai development', 'canadian business impact', 'strategic recommendation', 'conclusion', 'key insights', 'major points']
            if not any(header in line.lower() for header in header_keywords):
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
def create_html_blog_post(content, title, excerpt):
    """Create complete HTML blog post with PROPERLY FORMATTED content sections"""
    current_date = datetime.now()
    formatted_date = current_date.strftime("%B %d, %Y")
    month_year = current_date.strftime("%B %Y")
    
    sections = parse_structured_content(content)
    content_html = []
    
    # Introduction section
    if sections['introduction']:
        content_html.append(f'<div class="section"><p>{sections["introduction"]}</p></div>')

    # Key Developments section
    if sections['developments']:
        content_html.append('<div class="section">')
        content_html.append('<h2 class="section-title">Key AI Developments This Month</h2>')
        content_html.append('<ul class="bullet-list">')
        for item in sections['developments']:
            content_html.append(f'<li>{item}</li>')
        content_html.append('</ul></div>')

    # Canadian Impact section
    if sections['canadian_impact']:
        content_html.append('<div class="section">')
        content_html.append('<h2 class="section-title">Impact on Canadian Businesses</h2>')
        content_html.append(f'<p>{sections["canadian_impact"]}</p>')
        content_html.append('</div>')

    # Strategic Recommendations section
    if sections['recommendations']:
        content_html.append('<div class="section">')
        content_html.append('<h2 class="section-title">Strategic Recommendations for Canadian Leaders</h2>')
        content_html.append('<ul class="bullet-list numbered">')
        for item in sections['recommendations']:
            content_html.append(f'<li>{item}</li>')
        content_html.append('</ul></div>')

    # Adoption Metrics section
    if sections['adoption_metrics']:
        content_html.append('<div class="section">')
        content_html.append('<h2 class="section-title">Canadian Business AI Adoption Metrics</h2>')
        content_html.append('<ul class="bullet-list">')
        for item in sections['adoption_metrics']:
            content_html.append(f'<li>{item}</li>')
        content_html.append('</ul></div>')
    
    # Extract or generate conclusion
    if sections['conclusion']:
        conclusion_text = sections['conclusion']
    else:
        conclusion_text = generate_dynamic_conclusion(sections)
    
    # Clean up conclusion text
    conclusion_text = re.sub(r'[-•*]\s*[-•*]\s*', '', conclusion_text)
    conclusion_text = re.sub(r'^\s*[-•*]\s*', '', conclusion_text)
    
    all_content = '\n'.join(content_html)
    
    html_template = f'''<!DOCTYPE html>
    # ... rest of the HTML template ...
    '''
    
    return html_template
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} | Robert Simon - AI Insights</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet" />
    <style>
        :root {{
            --primary-blue: #2563eb;
            --accent-cyan: #06b6d4;
            --dark-navy: #1e293b;
            --medium-gray: #64748b;
            --white: #ffffff;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Inter', sans-serif; background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%); color: var(--dark-navy); line-height: 1.6; }}
        .nav-bar {{ background: var(--white); padding: 1rem 0; box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05); position: sticky; top: 0; z-index: 100; }}
        .nav-content {{ max-width: 1200px; margin: 0 auto; padding: 0 2rem; display: flex; justify-content: space-between; align-items: center; gap: 2rem; }}
        .nav-link {{ color: white; text-decoration: none; font-weight: 600; padding: 0.5rem 1.25rem; font-size: 0.9rem; border-radius: 20px; background: linear-gradient(135deg, var(--primary-blue), var(--accent-cyan)); transition: all 0.3s ease; flex-shrink: 0; }}
        .nav-link:hover {{ transform: translateY(-2px); box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); }}
        .blog-meta {{ font-size: 0.85rem; color: var(--medium-gray); display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }}
        .header {{ background: linear-gradient(135deg, var(--primary-blue) 0%, var(--accent-cyan) 100%); color: white; padding: 4rem 0 3rem; text-align: center; }}
        .header-content {{ max-width: 1000px; margin: 0 auto; padding: 0 2rem; }}
        .header h1 {{ font-size: 2.8rem; font-weight: 700; margin-bottom: 0.5rem; }}
        .header .subtitle {{ font-size: 1.2rem; font-weight: 500; opacity: 0.9; margin-bottom: 1.5rem; }}
        .header .intro {{ font-size: 1.05rem; opacity: 0.85; max-width: 800px; margin: 0 auto; }}
        .container {{ max-width: 1000px; margin: 0 auto; padding: 3rem 2rem 4rem; }}
        .article-container {{ background: white; border-radius: 20px; box-shadow: 0 20px 25px -5px rgb(0 0 0 / 0.1); overflow: hidden; }}
        .article-content {{ padding: 3rem; }}
        .section {{ margin-bottom: 3rem; }}
        .section-title {{ font-size: 2rem; color: var(--dark-navy); margin-bottom: 1.5rem; margin-top: 2rem; font-weight: 700; padding-left: 1.5rem; position: relative; }}
        .section-title::before {{ content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 4px; background: var(--primary-blue); border-radius: 2px; }}
        .bullet-list {{ margin-bottom: 2rem; padding-left: 0; list-style: none; }}
        .bullet-list li {{ margin-bottom: 1.5rem; line-height: 1.8; color: var(--medium-gray); position: relative; padding-left: 2.5rem; }}
        .bullet-list li::before {{ content: '●'; position: absolute; left: 0; color: var(--primary-blue); font-weight: bold; top: 0.1rem; }}
        .bullet-list.numbered {{ counter-reset: list-counter; }}
        .bullet-list.numbered li {{ counter-increment: list-counter; }}
        .bullet-list.numbered li::before {{ content: counter(list-counter) '.'; background: var(--primary-blue); color: white; width: 1.8rem; height: 1.8rem; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 600; font-size: 0.85rem; }}
        p {{ margin-bottom: 1.2rem; line-height: 1.7; color: var(--medium-gray); }}
        strong {{ color: var(--dark-navy); font-weight: 600; }}
        .conclusion {{ background: linear-gradient(135deg, var(--primary-blue) 0%, var(--accent-cyan) 100%); color: white; padding: 2.5rem; border-radius: 15px; margin-top: 3rem; }}
        .conclusion p {{ color: rgba(255, 255, 255, 0.95); font-size: 1.1rem; font-weight: 500; margin-bottom: 0; }}
        .conclusion strong {{ color: white; }}
        @media (max-width: 768px) {{ 
            .header h1 {{ font-size: 2.2rem; }} 
            .container {{ padding: 2rem 1rem 3rem; }} 
            .article-content {{ padding: 2rem 1.5rem; }}
            .nav-content {{ flex-direction: column; gap: 1rem; align-items: flex-start; }}
            .blog-meta {{ width: 100%; }}
        }}
    </style>
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-Y0FZTVVLBS"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', 'G-Y0FZTVVLBS');
</script>
</head>
<body>
    <nav class="nav-bar">
        <div class="nav-content">
            <a href="https://www.imetrobert.com/blog/" class="nav-link">
                ← Back to Blog Homepage
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
            <div class="intro">{excerpt}</div>
        </div>
    </header>

    <div class="container">
        <article class="article-container">
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

def extract_post_info(html_file):
    """Extract title, date, and excerpt from an HTML blog post"""
    # Ensure file exists and is not empty
    if not os.path.exists(html_file) or os.path.getsize(html_file) == 0:
        return None
        
    with open(html_file, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, "html.parser")

    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else "AI Insights"

    date_text = None
    blog_meta = soup.find("div", class_="blog-meta")
    if blog_meta:
        meta_text = blog_meta.get_text()
        if "•" in meta_text:
            date_text = meta_text.split("•")[-1].strip()
    
    if not date_text:
        basename = os.path.basename(html_file)
        match = re.match(r"(\d{4}-\d{2}-\d{2})-", basename)
        if match:
            date_obj = datetime.strptime(match.group(1), "%Y-%m-%d")
            date_text = date_obj.strftime("%B %d, %Y")
        else:
            date_text = datetime.now().strftime("%B %d, %Y")

    excerpt = None
    
    # FIRST: Try to get the intro from the header section (most reliable for new posts)
    intro_div = soup.find("div", class_="intro")
    if intro_div:
        excerpt = re.sub(r'\s+', ' ', intro_div.get_text()).strip()
        # Clean up any truncation markers or markdown artifacts
        excerpt = re.sub(r'\.\.\.f$', '...', excerpt)
        excerpt = re.sub(r'f\.\.\.$', '...', excerpt)
        excerpt = re.sub(r'\.\.\.$', '', excerpt).strip()  # Remove trailing ...
    
    # SECOND: If no intro div, try the first paragraph in article-content
    if not excerpt:
        article_content = soup.find("div", class_="article-content")
        if article_content:
            # Find the first section div with a paragraph
            first_section = article_content.find("div", class_="section")
            if first_section:
                p_tag = first_section.find("p")
                if p_tag:
                    excerpt = re.sub(r'\s+', ' ', p_tag.get_text()).strip()
    
    if not excerpt:
        excerpt = "Read the latest AI insights and business applications."

    # Ensure excerpt is properly truncated to 200 chars
    if len(excerpt) > 200:
        # Find a good breaking point (end of sentence or word)
        truncated = excerpt[:200].rstrip()
        excerpt = truncated + "..."
    elif not excerpt.endswith('...') and len(excerpt) < 200:
        # For shorter excerpts, add ... if it seems incomplete
        if not excerpt.endswith('.'):
            excerpt = excerpt + "..."

    return {
        "title": title,
        "date": date_text,
        "excerpt": excerpt,
        "filename": os.path.basename(html_file)
    }

def create_blog_index_html(posts):
    """Create blog index page"""
    if not posts:
        return None
    
    validated_posts = []
    posts_dir = "blog/posts"
    
    for post in posts:
        file_path = os.path.join(posts_dir, post['filename'])
        if os.path.exists(file_path):
            validated_posts.append(post)
    
    if not validated_posts:
        return None
    
    latest_post = validated_posts[0]
    older_posts = validated_posts[1:] if len(validated_posts) > 1 else []
    
    # Build older posts HTML
    older_posts_html = ""
    if older_posts:
        for post in older_posts:
            older_posts_html += f'''
                <div class="older-post-item">
                    <a href="/blog/posts/{post['filename']}" class="older-post-link">
                        <div class="older-post-title">{post['title']}</div>
                        <div class="older-post-date">{post['date']}</div>
                    </a>
                </div>'''
    else:
        older_posts_html = '<div class="no-posts-message"><p>Previous blogs will be available here</p></div>'
    
    # Always show the older posts section
    older_posts_section = f'''<section class="older-posts-section">
            <h3 class="older-posts-title">Previous Insights</h3>
            <div class="older-posts-grid">
                {older_posts_html}
            </div>
        </section>'''

    blog_index_html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Insights Blog - Robert Simon</title>
    <style>
        body {{ font-family: Inter, sans-serif; background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%); margin: 0; padding: 0; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 2rem; }}
        header {{ background: linear-gradient(135deg, #2563eb 0%, #06b6d4 50%, #8b5cf6 100%); color: white; padding: 4rem 0; text-align: center; margin-bottom: 3rem; border-radius: 20px; }}
        h1 {{ font-size: 3.5rem; font-weight: 700; margin-bottom: 0.5rem; }}
        .nav-bar {{ background: white; padding: 1rem 0; box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05); position: sticky; top: 0; z-index: 100; }}
        .nav-content {{ max-width: 1200px; margin: 0 auto; padding: 0 2rem; display: flex; justify-content: flex-start; }}
        .nav-link {{ color: white; text-decoration: none; font-weight: 600; padding: 0.5rem 1.25rem; font-size: 0.9rem; border-radius: 20px; background: linear-gradient(135deg, #2563eb, #06b6d4); }}
        .latest-post-section {{ background: linear-gradient(135deg, #2563eb 0%, #06b6d4 50%, #8b5cf6 100%); color: white; padding: 3rem; border-radius: 20px; margin-bottom: 3rem; }}
        .latest-badge {{ background: rgba(255, 255, 255, 0.25); color: white; padding: 0.5rem 1rem; border-radius: 20px; display: inline-block; margin-bottom: 1rem; }}
        .latest-post-title {{ font-size: 2rem; font-weight: 700; margin-bottom: 1rem; }}
        .read-latest-btn {{ background: rgba(255, 255, 255, 0.2); color: white; border: 2px solid rgba(255, 255, 255, 0.3); padding: 0.75rem 2rem; border-radius: 25px; text-decoration: none; display: inline-block; transition: all 0.3s ease; }}
        .read-latest-btn:hover {{ background: rgba(255, 255, 255, 0.3); transform: translateY(-2px); }}
        .older-posts-section {{ background: white; border-radius: 20px; padding: 2.5rem; box-shadow: 0 20px 25px -5px rgb(0 0 0 / 0.1); }}
        .older-posts-title {{ font-size: 1.8rem; margin-bottom: 2rem; text-align: center; color: #1e293b; }}
        .older-post-item {{ border: 1px solid #f1f5f9; border-radius: 12px; margin-bottom: 1rem; transition: all 0.3s ease; }}
        .older-post-item:hover {{ border-color: #2563eb; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); }}
        .older-post-link {{ display: block; padding: 1.5rem; text-decoration: none; color: inherit; }}
        .older-post-title {{ font-size: 1.3rem; font-weight: 600; color: #2563eb; margin-bottom: 0.5rem; text-decoration: underline; }}
        .older-post-date {{ font-size: 0.9rem; color: #64748b; }}
        .no-posts-message {{ text-align: center; padding: 2rem; color: #64748b; font-style: italic; }}
    </style>
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-Y0FZTVVLBS"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', 'G-Y0FZTVVLBS');
</script>
</head>
<body>
    <nav class="nav-bar">
        <div class="nav-content">
            <a href="https://www.imetrobert.com" class="nav-link">← Back to Homepage</a>
        </div>
    </nav>
    
    <div class="container">
        <header>
            <h1>AI Insights Blog</h1>
            <p>Strategic Intelligence for Digital Leaders</p>
        </header>

        <section class="latest-post-section">
            <div class="latest-badge">Latest</div>
            <h2 class="latest-post-title">{latest_post['title']}</h2>
            <div style="margin-bottom: 1rem; opacity: 0.9;">{latest_post['date']}</div>
            <p style="line-height: 1.6; margin-bottom: 1.5rem;">{latest_post['excerpt']}</p>
            <a href="/blog/posts/latest.html" class="read-latest-btn">Read Full Analysis →</a>
        </section>

        {older_posts_section}
    </div>
</body>
</html>'''

    return blog_index_html

def update_blog_index():
    """Update blog index"""
    posts_dir = "blog/posts"
    index_file = "blog/index.html"
    
    if not os.path.exists(posts_dir):
        return []
    
    # ALWAYS read latest.html first
    latest_path = os.path.join(posts_dir, "latest.html")
    posts = []
    
    # Extract info from latest.html first
    if os.path.exists(latest_path) and os.path.getsize(latest_path) > 100:
        try:
            latest_info = extract_post_info(latest_path)
            if latest_info and latest_info.get('title') and latest_info.get('excerpt'):
                # Change filename to latest.html for the link
                latest_info['filename'] = 'latest.html'
                posts.append(latest_info)
                print(f"✅ Loaded latest post: {latest_info['title']}")
                print(f"   Excerpt: {latest_info['excerpt'][:100]}...")
        except Exception as e:
            print(f"Warning: Could not process latest.html: {e}")
    
    # Then get all other dated posts for the "Previous" section
    html_files = [f for f in os.listdir(posts_dir) 
                  if f.endswith(".html") 
                  and f != "latest.html" 
                  and not f.startswith("{")  # Skip template files
                  and f != "index.html"]
    
    for file in sorted(html_files, reverse=True):
        file_path = os.path.join(posts_dir, file)
        try:
            if os.path.exists(file_path) and os.path.getsize(file_path) > 100:
                post_info = extract_post_info(file_path)
                if post_info and post_info.get('title') and post_info.get('filename'):
                    posts.append(post_info)
        except Exception as e:
            print(f"Warning: Could not process {file}: {e}")
            continue

    if not posts:
        print("Warning: No valid posts found")
        return []
    
    # The first post is always the latest
    latest_post = posts[0]
    
    # Filter older posts by month to show only one per month
    older_posts = []
    seen_months = set()
    
    # Add the current month from latest post to seen
    try:
        latest_date = datetime.strptime(latest_post['date'], "%B %d, %Y")
        latest_month_year = latest_date.strftime("%Y-%m")
        seen_months.add(latest_month_year)
    except:
        pass
    
    # Go through remaining posts and take one per month
    for post in posts[1:]:
        try:
            post_date = datetime.strptime(post['date'], "%B %d, %Y")
            post_month_year = post_date.strftime("%Y-%m")
            
            if post_month_year not in seen_months:
                older_posts.append(post)
                seen_months.add(post_month_year)
        except:
            # If date parsing fails, include it anyway
            older_posts.append(post)
    
    print(f"Found {len(posts)} total posts, showing latest and {len(older_posts)} from previous months")

    # Create the new index with the latest post info
    new_blog_index = create_blog_index_html([latest_post] + older_posts)
    if not new_blog_index:
        return []
    
    try:
        with open(index_file, "w", encoding="utf-8") as f:
            f.write(new_blog_index)
        print(f"✅ Blog index recreated with latest post + {len(older_posts)} previous months")
    except Exception as e:
        print(f"❌ Error writing blog index: {e}")
    
    return posts

def main():
    parser = argparse.ArgumentParser(description="Blog Generator")
    parser.add_argument("--topic", help="Custom topic")
    parser.add_argument("--output", default="posts", choices=["staging", "posts"])
    args = parser.parse_args()
    
    print("🔧 RUNNING BLOG GENERATOR")
    
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        print("❌ PERPLEXITY_API_KEY not set")
        sys.exit(1)
    
    try:
        result = generate_blog_with_perplexity(api_key, args.topic)
        title, excerpt = extract_title_and_excerpt(result["content"])
        html_content = create_html_blog_post(result["content"], title, excerpt)
        
        current_date = datetime.now().strftime("%Y-%m-%d")
        filename_html = f"{current_date}-{clean_filename(title)}.html"
        
        output_dir = os.path.join("blog", args.output)
        os.makedirs(output_dir, exist_ok=True)
        
        path_html = os.path.join(output_dir, filename_html)
        
        # Save to dated filename
        with open(path_html, "w", encoding="utf-8") as f:
            f.write(html_content)
            f.flush()  # Ensure it's written to disk
            os.fsync(f.fileno())  # Force write to disk
        print(f"✅ Blog post saved: {path_html}")
        
        # Save to latest.html
        latest_path = os.path.join("blog", "posts", "latest.html")
        os.makedirs(os.path.dirname(latest_path), exist_ok=True)
        with open(latest_path, "w", encoding="utf-8") as f:
            f.write(html_content)
            f.flush()  # Ensure it's written to disk
            os.fsync(f.fileno())  # Force write to disk
        print(f"✅ Latest post updated")
        
        # Small delay to ensure filesystem sync
        import time
        time.sleep(0.1)
        
        # Now update the blog index
        posts = update_blog_index()
        print(f"✅ Blog index updated with {len(posts)} posts")
        print("🎉 SUCCESS!")
        
    except Exception as e:
        print(f"💥 Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
