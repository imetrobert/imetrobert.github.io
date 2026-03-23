import argparse
import os
import requests
import json
import re
import sys
from datetime import datetime
from bs4 import BeautifulSoup

def clean_filename(title):
    clean_title = re.sub('<.*?>', '', title)
    clean_title = re.sub(r'[^a-zA-Z0-9\s]', '', clean_title)
    clean_title = re.sub(r'\s+', '-', clean_title.strip())
    return clean_title.lower()

def clean_perplexity_content(content):
    content = re.sub(r'\[\d+\]', '', content)
    content = re.sub(r'\s*\(\d+\)\s*', ' ', content)
    content = re.sub(r'^\s*#{1,6}\s*', '', content, flags=re.MULTILINE)
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
    models_to_try = ["sonar-pro", "sonar", "sonar-reasoning"]
    if topic_type == "monthly_ai":
        system_prompt = f"""You are Robert Simon, an AI expert and digital transformation leader with 25+ years of experience, writing for Canadian business leaders.

Create a monthly AI insights post for {month_year} with EXACTLY these 6 sections in this EXACT order:

SECTION 1 - NO HEADING: Write 1 paragraph introduction (do NOT include a heading like "Introduction")

SECTION 2 - HEADING "Key AI Developments This Month": List exactly 15 major AI developments from the past month with specific dates and company names. Write each as a separate paragraph or bullet point.

SECTION 3 - HEADING "Impact on Canadian Businesses": Write 1-2 paragraphs analyzing how these developments affect Canadian businesses

SECTION 4 - HEADING "Strategic Recommendations for Canadian Leaders": Provide exactly 5 actionable recommendations. Write each recommendation as a separate paragraph starting with an action verb like "Prioritize", "Invest", "Develop", "Establish", or "Implement".

SECTION 5 - HEADING "Canadian Business AI Adoption Metrics": Provide 3-5 separate data points with percentages. Write each metric as a separate sentence or paragraph.

SECTION 6 - HEADING "Conclusion": Write 1 paragraph strategic imperative

CRITICAL FORMATTING RULES:
- Do NOT use markdown heading syntax like ##, ###, or #### anywhere in your response
- Do NOT use asterisks for bold (**text**) or italic (*text*)
- Write in plain text only
- Section headings should be written as plain text on their own line, not with # symbols
- SECTION 5 (Canadian Business AI Adoption Metrics) is MANDATORY and must contain 3-5 statistics with percentages"""
        user_prompt = f"""Write an AI insights blog post for {month_year} with EXACTLY 6 sections in this order:

1. Introduction paragraph (NO HEADING) - 1 paragraph
2. Key AI Developments This Month - 15 separate items with dates
3. Impact on Canadian Businesses - 1-2 paragraphs
4. Strategic Recommendations for Canadian Leaders - 5 separate recommendations, each starting with action words
5. Canadian Business AI Adoption Metrics - 3-5 separate statistics with percentages (THIS IS MANDATORY)
6. Conclusion - 1 paragraph

IMPORTANT: Do NOT use any markdown formatting (no ##, ###, no **bold**, no *italic*). Write in plain text only.

DO NOT SKIP SECTION 5. It must have real statistics with percentage numbers."""
    elif topic_type == "custom_ai":
        system_prompt = f"""You are Robert Simon, an AI expert and digital transformation leader with 25+ years of experience, writing for Canadian business leaders.

Create an AI insights post about "{topic}" with EXACTLY these 6 sections in this EXACT order:

SECTION 1 - NO HEADING: Write 1 paragraph introduction
SECTION 2 - HEADING "Key AI Developments": List 8-10 major points related to "{topic}"
SECTION 3 - HEADING "Impact on Canadian Businesses": Write 1-2 paragraphs
SECTION 4 - HEADING "Strategic Recommendations for Canadian Leaders": 5 actionable recommendations
SECTION 5 - HEADING "Canadian Business AI Adoption Metrics": 3-5 data points with percentages (MANDATORY)
SECTION 6 - HEADING "Conclusion": 1 paragraph strategic imperative

CRITICAL: Do NOT use markdown heading syntax (##, ###). Write section headings as plain text only."""
        user_prompt = f"""Write an AI insights blog post for Canadian business leaders about "{topic}".

Include EXACTLY 6 sections. Do NOT use markdown formatting (no ##, ###, no **bold**). Write in plain text.

DO NOT SKIP SECTION 5 (Canadian Business AI Adoption Metrics)."""
    else:
        system_prompt = f"""You are Robert Simon, a digital transformation leader with 25+ years of experience, writing for Canadian business leaders.

Create a business insights post about "{topic}" with EXACTLY these 6 sections in this EXACT order:

SECTION 1 - NO HEADING: Write 1 paragraph introduction
SECTION 2 - HEADING "Key Insights": List 8-10 major points related to "{topic}"
SECTION 3 - HEADING "Impact on Canadian Businesses": Write 1-2 paragraphs
SECTION 4 - HEADING "Strategic Recommendations for Canadian Leaders": 5 actionable recommendations
SECTION 5 - HEADING "Canadian Business AI Adoption Metrics": 3-5 data points with percentages (MANDATORY)
SECTION 6 - HEADING "Conclusion": 1 paragraph strategic imperative

CRITICAL: Do NOT use markdown heading syntax (##, ###). Write section headings as plain text only."""
        user_prompt = f"""Write a business insights blog post for Canadian business leaders about "{topic}".

Include EXACTLY 6 sections. Do NOT use markdown formatting. Write in plain text.

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
                print(f"Failed model {model}: {response.text[:500]}")
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
    raise Exception("All Perplexity models failed to generate content. Check your PERPLEXITY_API_KEY secret and billing status.")

def parse_structured_content(content):
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
    dev_patterns = ['key ai development', 'ai development', 'major development', 'technological advance', 'key developments', 'major ai', 'key insights', 'main insights', 'major insights', 'key points', 'main points', 'major points']
    impact_patterns = ['canadian business impact', 'impact on canadian', 'canadian impact', 'canadian business', 'impact on canada', 'business impact']
    rec_patterns = ['strategic recommendation', 'recommendation', 'strategic action', 'action step', 'strategic step', 'recommendations for']
    adoption_patterns = ['canadian business ai adoption', 'ai adoption metrics', 'adoption metrics', 'canadian ai adoption', 'adoption data', 'adoption statistics']
    conclusion_patterns = ['conclusion', 'strategic imperative', 'final thought', 'in conclusion', 'finally', 'key takeaway']
    dev_start = -1; dev_end = -1; impact_start = -1; impact_end = -1; rec_start = -1; rec_end = -1; adoption_start = -1; adoption_end = -1; conclusion_start = -1
    for pattern in dev_patterns:
        pos = content_lower.find(pattern)
        if pos != -1:
            dev_start = pos
            break
    for pattern in impact_patterns:
        pos = content_lower.find(pattern)
        if pos != -1 and pos > dev_start:
            impact_start = pos; dev_end = pos; break
    for pattern in rec_patterns:
        pos = content_lower.find(pattern)
        if pos != -1 and (impact_start == -1 or pos > impact_start):
            rec_start = pos
            if impact_start != -1: impact_end = pos
            break
    for pattern in adoption_patterns:
        pos = content_lower.find(pattern)
        if pos != -1 and (rec_start == -1 or pos > rec_start):
            adoption_start = pos
            if rec_start != -1: rec_end = pos
            break
    for pattern in conclusion_patterns:
        pos = content_lower.find(pattern)
        if pos != -1 and (adoption_start == -1 or pos > adoption_start):
            conclusion_start = pos
            if adoption_start != -1: adoption_end = pos
            break
    if rec_start != -1 and rec_end == -1:
        rec_end = conclusion_start if conclusion_start != -1 else len(content)
    if adoption_start != -1 and adoption_end == -1:
        adoption_end = len(content)
    print(f"DEBUG: Section positions - dev:{dev_start}, impact:{impact_start}, rec:{rec_start}, adoption:{adoption_start}, conclusion:{conclusion_start}")
    if dev_start > 0:
        sections['introduction'] = content[:dev_start].strip()
    if dev_start != -1 and dev_end != -1:
        sections['developments'] = parse_development_items(content[dev_start:dev_end].strip())
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
        sections['recommendations'] = parse_recommendation_items(rec_text)
        print(f"DEBUG: Parsed {len(sections['recommendations'])} recommendations")
    else:
        print(f"DEBUG: Recommendations section NOT FOUND - rec_start={rec_start}, rec_end={rec_end}")
    if adoption_start != -1 and adoption_end != -1:
        sections['adoption_metrics'] = parse_adoption_metrics(content[adoption_start:adoption_end].strip())
    else:
        print("DEBUG: Adoption metrics section NOT FOUND in content")
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
            if any(pattern in para_lower for pattern in dev_patterns): current_section = 'developments'; continue
            elif any(pattern in para_lower for pattern in impact_patterns): current_section = 'canadian_impact'; continue
            elif any(pattern in para_lower for pattern in rec_patterns): current_section = 'recommendations'; continue
            elif any(pattern in para_lower for pattern in adoption_patterns): current_section = 'adoption_metrics'; continue
            elif any(pattern in para_lower for pattern in conclusion_patterns): current_section = 'conclusion'; continue
            if current_section == 'introduction' and not sections['introduction']: sections['introduction'] = para
            elif current_section == 'developments': sections['developments'].extend(extract_bullets_from_paragraph(para))
            elif current_section == 'canadian_impact' and not sections['canadian_impact']: sections['canadian_impact'] = para
            elif current_section == 'recommendations': sections['recommendations'].extend(extract_bullets_from_paragraph(para))
            elif current_section == 'adoption_metrics': sections['adoption_metrics'].extend(extract_bullets_from_paragraph(para))
            elif current_section == 'conclusion' and not sections['conclusion']: sections['conclusion'] = para
    print(f"DEBUG: Final parsed sections - intro: {bool(sections['introduction'])}, dev: {len(sections['developments'])}, impact: {bool(sections['canadian_impact'])}, rec: {len(sections['recommendations'])}, adoption: {len(sections['adoption_metrics'])}, conc: {bool(sections['conclusion'])}")
    return sections

def extract_bullets_from_paragraph(paragraph):
    items = []
    lines = paragraph.split('. ')
    for line in lines:
        line = line.strip()
        if len(line) < 30: continue
        line = re.sub(r'^[-•*]\s*[-•*]\s*', '', line)
        line = re.sub(r'^[-•*]\s*', '', line)
        if any(marker in line for marker in ['Microsoft', 'Google', 'OpenAI', 'Anthropic', 'NVIDIA']):
            clean_line = re.sub(r'^\d+\.\s*', '', line)
            if clean_line and len(clean_line) > 20: items.append(clean_line)
    return items

def parse_development_items(text):
    items = []
    lines = text.split('\n')
    current_item = []
    for line in lines:
        line = line.strip()
        if not line: continue
        list_start_pattern = r'^(\d+)\.\s+([A-Z].*)'
        if re.match(list_start_pattern, line) and not re.search(r'\d+\.\d+', line[:10]):
            if current_item:
                item_text = ' '.join(current_item).strip()
                if len(item_text) > 50: items.append(item_text)
            current_item = [re.sub(r'^\d+\.\s*', '', line)]
        else:
            if current_item: current_item.append(line)
            elif len(line) > 50: current_item = [line]
    if current_item:
        item_text = ' '.join(current_item).strip()
        if len(item_text) > 50: items.append(item_text)
    if len(items) < 5:
        smart_items = []
        protected_text = text
        abbreviations = {'U.S.': 'USPROTECTED', 'U.K.': 'UKPROTECTED', 'E.U.': 'EUPROTECTED', 'A.I.': 'AIPROTECTED', 'Inc.': 'IncPROTECTED', 'Corp.': 'CorpPROTECTED'}
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
            for replacement, original in abbreviations.items(): sentence = sentence.replace(replacement, original)
            for replacement, original in version_replacements.items(): sentence = sentence.replace(replacement, original)
            if (len(sentence) > 50 and any(company in sentence for company in ['Microsoft', 'OpenAI', 'Google', 'Anthropic', 'NVIDIA', 'Meta', 'Amazon', 'Apple']) and not re.match(r'^\d+\.\s', sentence)):
                smart_items.append(sentence)
        if len(smart_items) >= len(items): items = smart_items
    filtered_items = []
    for item in items:
        item_lower = item.lower()
        if not any(header in item_lower for header in ['key ai development', 'major development', 'key insights']):
            filtered_items.append(item)
    return filtered_items[:15]

def parse_recommendation_items(text):
    items = []
    header_keywords = ['strategic recommendation', 'recommendations for canadian leaders', 'recommendations for', 'strategic action', 'for canadian leaders', 'for canadian business', 'action steps']
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        line_lower = line.strip().lower()
        if line_lower and not any(line_lower == header or line_lower.startswith(header + ':') for header in header_keywords):
            cleaned_lines.append(line.strip())
    current_item = []
    for line in cleaned_lines:
        if not line: continue
        list_start_pattern = r'^(\d+)\.\s+([A-Z].*)'
        is_list_number = re.match(list_start_pattern, line) and not re.search(r'^\d+\.\d+', line[:15])
        if is_list_number:
            if current_item:
                item_text = ' '.join(current_item).strip()
                if len(item_text) > 30: items.append(item_text)
            current_item = [re.sub(r'^\d+\.\s*', '', line)]
        else:
            if len(line) > 30 and ':' in line and not current_item: current_item = [line]
            elif current_item: current_item.append(line)
            elif len(line) > 30: current_item = [line]
    if current_item:
        item_text = ' '.join(current_item).strip()
        if len(item_text) > 30: items.append(item_text)
    if len(items) < 3:
        paragraphs = []
        current_para = []
        for line in cleaned_lines:
            if not line:
                if current_para: paragraphs.append(' '.join(current_para)); current_para = []
            else:
                if current_para and len(line) > 30 and line[0].isupper(): paragraphs.append(' '.join(current_para)); current_para = [line]
                else: current_para.append(line)
        if current_para: paragraphs.append(' '.join(current_para))
        paragraph_items = []
        for para in paragraphs:
            para = para.strip()
            if len(para) > 30:
                action_words = ['prioritize', 'invest', 'develop', 'establish', 'implement', 'create', 'build', 'focus', 'ensure', 'adopt', 'enhance', 'strengthen', 'leverage', 'foster', 'collaborate']
                if any(word in para.lower() for word in action_words): paragraph_items.append(para)
        if len(paragraph_items) > len(items): items = paragraph_items
    return items[:5]

def parse_adoption_metrics(text):
    items = []
    lines = text.split('\n')
    current_item = []
    header_keywords = ['canadian business ai adoption', 'ai adoption metrics', 'adoption metrics', 'adoption statistics']
    for line in lines:
        line = line.strip()
        if not line: continue
        line_lower = line.lower()
        if any(header in line_lower for header in header_keywords): continue
        list_start_pattern = r'^(\d+)\.\s+([A-Z].*)'
        if re.match(list_start_pattern, line) and not re.search(r'\d+\.\d+', line[:15]):
            if current_item:
                item_text = ' '.join(current_item).strip()
                if len(item_text) > 20 and not any(h in item_text.lower() for h in header_keywords): items.append(item_text)
            current_item = [re.sub(r'^\d+\.\s*', '', line)]
        else:
            if current_item: current_item.append(line)
            elif len(line) > 20: current_item = [line]
    if current_item:
        item_text = ' '.join(current_item).strip()
        if len(item_text) > 20 and not any(h in item_text.lower() for h in header_keywords): items.append(item_text)
    if len(items) < 2:
        sentence_items = []
        for line in lines:
            line = line.strip()
            line_lower = line.lower()
            if any(header in line_lower for header in header_keywords): continue
            if len(line) > 20 and ('%' in line or 'adoption' in line.lower()):
                if not any(header in line.lower() for header in header_keywords): sentence_items.append(line)
        if len(sentence_items) > len(items): items = sentence_items
    return items[:5]

def generate_dynamic_conclusion(sections):
    key_themes = []
    companies = []
    if sections['developments']:
        for item in sections['developments']:
            item_lower = item.lower()
            for company in ['Microsoft', 'OpenAI', 'Google', 'Anthropic', 'NVIDIA', 'Meta', 'Amazon', 'Apple']:
                if company.lower() in item_lower and company not in companies: companies.append(company)
            for theme, keywords in {'AI models': ['model', 'llm', 'gpt', 'claude', 'chatgpt'], 'enterprise AI': ['enterprise', 'business', 'copilot', 'office'], 'automation': ['automation', 'workflow', 'process'], 'partnerships': ['partnership', 'collaboration', 'integration']}.items():
                if any(keyword in item_lower for keyword in keywords) and theme not in key_themes: key_themes.append(theme)
    conclusion_parts = []
    if len(key_themes) >= 2: conclusion_parts.append(f"With significant developments in {' and '.join(key_themes[:2])}")
    elif key_themes: conclusion_parts.append(f"With critical advances in {key_themes[0]}")
    else: conclusion_parts.append("With accelerating AI innovation")
    if len(companies) >= 2: conclusion_parts.append(f"from {' and '.join(companies[:2])}")
    conclusion_parts.append("Canadian businesses must act decisively to harness these breakthroughs")
    conclusion_parts.append("to remain competitive in the global AI-driven economy")
    conclusion = ' '.join(conclusion_parts)
    if not conclusion.endswith('.'): conclusion += '.'
    return conclusion[0].upper() + conclusion[1:] if conclusion else "Canadian businesses must act decisively to harness AI breakthroughs while maintaining competitive advantage in the global marketplace."

def extract_title_and_excerpt(content):
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
                clean_title = re.sub(r'[•\-–—]', '', clean_title).strip()
                if clean_title and len(clean_title) > 10: potential_title = clean_title; break
    title = f"AI Insights for {month_year}" if not potential_title or potential_title.lower().startswith('ai insights') else potential_title
    excerpt = ""
    for line in lines:
        if line and len(line) > 100 and not line.startswith(('#', '1.', '2.', '3.', '4.', '5.', '•', '-', '*')):
            if not any(h in line.lower() for h in ['key ai development', 'canadian business impact', 'strategic recommendation', 'conclusion', 'key insights', 'major points']):
                clean_excerpt = re.sub(r'^[•\-–—:]+\s*', '', line)
                clean_excerpt = re.sub(r'\s*[•\-–—:]+$', '', clean_excerpt)
                clean_excerpt = re.sub(r'[•\-–—]', '', clean_excerpt).strip()
                if clean_excerpt:
                    excerpt = clean_excerpt[:200] + "..." if len(clean_excerpt) > 200 else clean_excerpt
                    break
    if not excerpt:
        excerpt = f"Strategic insights and practical guidance for Canadian business leaders - {month_year} analysis."
    return title, excerpt


def get_posts_for_linking(current_iso_date, max_posts=3):
    """Scan blog/posts for recent posts to link to from a new post."""
    posts_dir = "blog/posts"
    if not os.path.exists(posts_dir):
        return []
    html_files = [
        f for f in os.listdir(posts_dir)
        if f.endswith('.html') and f != 'latest.html'
        and not f.startswith('{') and '{' not in f
        and f != 'index.html' and current_iso_date not in f
    ]
    links = []
    for filename in sorted(html_files, reverse=True)[:max_posts]:
        filepath = os.path.join(posts_dir, filename)
        try:
            info = extract_post_info(filepath)
            if info and info.get('title') and info.get('date'):
                clean = re.sub(r'^[#\*\s]+', '', info['title']).strip()
                links.append({'title': clean, 'date': info['date'], 'url': f"/blog/posts/{filename}"})
        except Exception:
            continue
    return links[:max_posts]


def build_internal_links_html(links):
    """Renders the Earlier Insights section for internal linking."""
    if not links:
        return ''
    items_html = '\n'.join([
        f'''        <a href="{link['url']}" class="earlier-post-link">
            <div class="earlier-post-title">{link['title']}</div>
            <div class="earlier-post-date">{link['date']}</div>
        </a>'''
        for link in links
    ])
    return f'''
            <div class="section earlier-insights">
                <div class="section-title">Earlier Insights</div>
                <div class="earlier-posts-grid">
{items_html}
                </div>
            </div>'''


# ============================================================
# ENHANCED create_html_blog_post WITH FULL SEO + GEO SUPPORT
# ============================================================
def create_html_blog_post(content, title, excerpt):
    """Create complete HTML blog post with SEO, GEO, and structured data"""
    current_date = datetime.now()
    formatted_date = current_date.strftime("%B %d, %Y")
    iso_date = current_date.strftime("%Y-%m-%d")
    month_year = current_date.strftime("%B %Y")

    # Clean title - strip any accidental markdown artifacts
    clean_title = re.sub(r'^[#\*\s]+', '', title).strip()
    if not clean_title or len(clean_title) < 5:
        clean_title = f"AI Insights for {month_year}"

    # SEO-optimised page title
    seo_title = f"{clean_title} | AI News for Canadian Business | Robert Simon"

    # Build canonical URL slug
    slug = clean_filename(clean_title)
    canonical_url = f"https://www.imetrobert.com/blog/posts/{iso_date}-{slug}.html"

    # Truncate excerpt safely for meta description (155 chars max)
    meta_desc = re.sub(r'\s+', ' ', excerpt).strip()
    if len(meta_desc) > 155:
        meta_desc = meta_desc[:152].rstrip() + "..."

    # Build OG image (static brand image)
    og_image = "https://www.imetrobert.com/blog/og-blog.jpg"

    sections = parse_structured_content(content)
    content_html = []

    if sections['introduction']:
        content_html.append(f'<div class="section"><p>{sections["introduction"]}</p></div>')

    if sections['developments']:
        content_html.append(
            '<div class="section">'
            '<div class="section-title">Key AI Developments This Month</div>'
            '<ul class="bullet-list numbered">'
            + ''.join(f'<li>{item}</li>' for item in sections['developments'])
            + '</ul></div>'
        )

    if sections['canadian_impact']:
        content_html.append(
            f'<div class="section"><div class="section-title">Impact on Canadian Businesses</div>'
            f'<p>{sections["canadian_impact"]}</p></div>'
        )

    if sections['recommendations']:
        content_html.append(
            '<div class="section"><div class="section-title">Strategic Recommendations for Canadian Leaders</div>'
            '<ul class="bullet-list">'
            + ''.join(f'<li>{item}</li>' for item in sections['recommendations'])
            + '</ul></div>'
        )

    if sections['adoption_metrics']:
        content_html.append(
            '<div class="section"><div class="section-title">Canadian Business AI Adoption Metrics</div>'
            '<ul class="bullet-list">'
            + ''.join(f'<li>{item}</li>' for item in sections['adoption_metrics'])
            + '</ul></div>'
        )

    conclusion_text = sections['conclusion'] if sections['conclusion'] else generate_dynamic_conclusion(sections)
    conclusion_text = re.sub(r'[-•*]\s*[-•*]\s*', '', conclusion_text)
    conclusion_text = re.sub(r'^\s*[-•*]\s*', '', conclusion_text)

    all_content = '\n'.join(content_html)

    # ── Build FAQ schema from recs (GEO: helps AI answer engines cite this page) ──
    faq_items = []
    faq_questions = [
        f"How does {month_year} AI news affect Canadian businesses?",
        "What are the key AI strategic recommendations for Canadian leaders?",
        f"What is Canada's AI adoption rate in {month_year}?",
        "How should Canadian companies prepare for AI regulation?",
        "What AI tools should Canadian businesses prioritize?"
    ]
    for i, rec in enumerate(sections['recommendations'][:5]):
        if i < len(faq_questions):
            faq_items.append({
                "question": faq_questions[i],
                "answer": rec[:500]
            })

    faq_schema_items = ',\n'.join([
        f'{{"@type":"Question","name":{json.dumps(f["question"])},"acceptedAnswer":{{"@type":"Answer","text":{json.dumps(f["answer"])}}}}}'
        for f in faq_items
    ]) if faq_items else ''

    faq_schema = f'''
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {faq_schema_items}
  ]
}}
</script>''' if faq_schema_items else ''

    # ── Article / BlogPosting schema ──
    article_schema = f'''
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "BlogPosting",
  "headline": {json.dumps(clean_title)},
  "description": {json.dumps(meta_desc)},
  "datePublished": "{iso_date}",
  "dateModified": "{iso_date}",
  "author": {{
    "@type": "Person",
    "name": "Robert Simon",
    "url": "https://www.imetrobert.com",
    "jobTitle": "AI Evangelist & Digital Sales Leader",
    "worksFor": {{"@type": "Organization", "name": "Bell Canada"}},
    "address": {{"@type": "PostalAddress", "addressLocality": "Montreal", "addressRegion": "QC", "addressCountry": "CA"}}
  }},
  "publisher": {{
    "@type": "Person",
    "name": "Robert Simon",
    "url": "https://www.imetrobert.com"
  }},
  "mainEntityOfPage": {{
    "@type": "WebPage",
    "@id": {json.dumps(canonical_url)}
  }},
  "url": {json.dumps(canonical_url)},
  "image": {json.dumps(og_image)},
  "inLanguage": "en-CA",
  "about": [
    {{"@type": "Thing", "name": "Artificial Intelligence"}},
    {{"@type": "Thing", "name": "Canadian Business"}},
    {{"@type": "Place", "name": "Canada"}}
  ],
  "keywords": "AI Canada, artificial intelligence Canada, Canadian business AI, AI news Montreal, AI strategy Canada, digital transformation Canada, AI adoption Canada"
}}
</script>'''

    # ── BreadcrumbList schema ──
    breadcrumb_schema = f'''
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {{"@type": "ListItem", "position": 1, "name": "Home", "item": "https://www.imetrobert.com"}},
    {{"@type": "ListItem", "position": 2, "name": "AI Insights Blog", "item": "https://www.imetrobert.com/blog/"}},
    {{"@type": "ListItem", "position": 3, "name": {json.dumps(clean_title)}, "item": {json.dumps(canonical_url)}}}
  ]
}}
</script>'''

    html_template = f'''<!DOCTYPE html>
<html lang="en-CA">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <!-- ═══ SEO: Primary meta ═══ -->
    <title>{seo_title}</title>
    <meta name="description" content="{meta_desc}">
    <meta name="keywords" content="AI Canada {month_year}, Canadian AI news, artificial intelligence Canada, AI business strategy Canada, AI adoption Canada, Montreal AI, Bell Canada AI, Canadian digital transformation, AI news for Canadians, AI insights {month_year}">
    <meta name="author" content="Robert Simon">
    <meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1">
    <meta name="language" content="en-CA">

    <!-- ═══ GEO: Canadian location signals ═══ -->
    <meta name="geo.region" content="CA-QC">
    <meta name="geo.placename" content="Montreal, Quebec, Canada">
    <meta name="geo.position" content="45.5017;-73.5673">
    <meta name="ICBM" content="45.5017, -73.5673">
    <meta name="DC.coverage" content="Canada">

    <!-- ═══ Canonical ═══ -->
    <link rel="canonical" href="{canonical_url}">

    <!-- ═══ Open Graph ═══ -->
    <meta property="og:type" content="article">
    <meta property="og:url" content="{canonical_url}">
    <meta property="og:title" content="{clean_title} | AI Insights for Canadian Business">
    <meta property="og:description" content="{meta_desc}">
    <meta property="og:image" content="{og_image}">
    <meta property="og:site_name" content="Robert Simon - AI Innovation">
    <meta property="og:locale" content="en_CA">
    <meta property="article:published_time" content="{iso_date}T00:00:00+00:00">
    <meta property="article:modified_time" content="{iso_date}T00:00:00+00:00">
    <meta property="article:author" content="Robert Simon">
    <meta property="article:section" content="AI Strategy">
    <meta property="article:tag" content="AI Canada">
    <meta property="article:tag" content="Canadian Business">
    <meta property="article:tag" content="Artificial Intelligence">
    <meta property="article:tag" content="Digital Transformation">
    <meta property="article:tag" content="Montreal">

    <!-- ═══ Twitter / X card ═══ -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{clean_title} | AI News for Canadian Business">
    <meta name="twitter:description" content="{meta_desc}">
    <meta name="twitter:image" content="{og_image}">
    <meta name="twitter:creator" content="@thedigitalrobert">
    <meta name="twitter:site" content="@thedigitalrobert">

    <!-- ═══ Structured data: Article, FAQ, Breadcrumb ═══ -->
{article_schema}
{faq_schema}
{breadcrumb_schema}

    <!-- ═══ Google Analytics ═══ -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-Y0FZTVVLBS"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('js', new Date());
      gtag('config', 'G-Y0FZTVVLBS');
    </script>

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
        /* ── Author byline ── */
        .author-byline {{ display: flex; align-items: center; gap: 1rem; padding: 1.5rem 3rem; border-bottom: 1px solid #f1f5f9; background: #fafbfc; }}
        .author-byline img {{ width: 48px; height: 48px; border-radius: 50%; object-fit: cover; }}
        .author-byline .author-name {{ font-weight: 600; color: var(--dark-navy); font-size: 0.95rem; }}
        .author-byline .author-role {{ font-size: 0.85rem; color: var(--medium-gray); }}
        /* ── Breadcrumb ── */
        .breadcrumb {{ font-size: 0.82rem; color: var(--medium-gray); padding: 0.75rem 3rem; background: #fafbfc; border-bottom: 1px solid #f1f5f9; }}
        .breadcrumb a {{ color: var(--primary-blue); text-decoration: none; }}
        .breadcrumb a:hover {{ text-decoration: underline; }}
        /* Earlier insights internal links */
        .earlier-insights {{ margin-top: 3rem; padding-top: 2rem; border-top: 1px solid #f1f5f9; }}
        .earlier-posts-grid {{ display: grid; gap: 1rem; margin-top: 1.5rem; }}
        .earlier-post-link {{ display: block; padding: 1.25rem 1.5rem; border: 1px solid #e2e8f0; border-radius: 12px; text-decoration: none; color: inherit; transition: all 0.25s ease; background: #fafbfc; }}
        .earlier-post-link:hover {{ border-color: var(--primary-blue); box-shadow: 0 4px 12px rgb(37 99 235 / 0.08); background: white; transform: translateY(-2px); }}
        .earlier-post-title {{ font-size: 1.05rem; font-weight: 600; color: var(--primary-blue); margin-bottom: 0.35rem; }}
        .earlier-post-date {{ font-size: 0.85rem; color: var(--medium-gray); }}
                @media (max-width: 768px) {{
            .header h1 {{ font-size: 2.2rem; }}
            .container {{ padding: 2rem 1rem 3rem; }}
            .article-content {{ padding: 2rem 1.5rem; }}
            .nav-content {{ flex-direction: column; gap: 1rem; align-items: flex-start; }}
            .blog-meta {{ width: 100%; }}
            .author-byline {{ padding: 1rem 1.5rem; }}
            .breadcrumb {{ padding: 0.75rem 1.5rem; }}
        }}
    </style>
</head>
<body>
    <nav class="nav-bar">
        <div class="nav-content">
            <a href="https://www.imetrobert.com/blog/" class="nav-link">
                &#8592; Back to Blog
            </a>
            <div class="blog-meta">
                <span>AI Insights for Canadian Business</span>
                <span>&#8226;</span>
                <span>{formatted_date}</span>
            </div>
        </div>
    </nav>

    <header class="header">
        <div class="header-content">
            <h1>{clean_title}</h1>
            <div class="subtitle">Key AI Developments &amp; Canadian Business Impact</div>
            <div class="intro">{excerpt}</div>
        </div>
    </header>

    <div class="container">
        <article class="article-container" itemscope itemtype="https://schema.org/BlogPosting">
            <meta itemprop="headline" content="{clean_title}">
            <meta itemprop="datePublished" content="{iso_date}">
            <meta itemprop="dateModified" content="{iso_date}">
            <meta itemprop="author" content="Robert Simon">
            <meta itemprop="publisher" content="Robert Simon">
            <meta itemprop="description" content="{meta_desc}">

            <!-- Breadcrumb visible -->
            <nav class="breadcrumb" aria-label="Breadcrumb">
                <a href="https://www.imetrobert.com">Home</a> &rsaquo;
                <a href="https://www.imetrobert.com/blog/">AI Insights Blog</a> &rsaquo;
                <span>{clean_title}</span>
            </nav>

            <!-- Author byline (E-E-A-T signal) -->
            <div class="author-byline">
                <img src="https://imetrobert.github.io/profile.jpg" alt="Robert Simon - AI Evangelist, Montreal" loading="lazy">
                <div>
                    <div class="author-name">Robert Simon</div>
                    <div class="author-role">AI Evangelist &amp; Digital Sales Leader, Bell Canada &mdash; Montreal, QC</div>
                </div>
            </div>

            <div class="article-content" itemprop="articleBody">
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

# ── All remaining functions unchanged ──
def extract_post_info(html_file):
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
    intro_div = soup.find("div", class_="intro")
    if intro_div:
        excerpt = re.sub(r'\s+', ' ', intro_div.get_text()).strip()
        excerpt = re.sub(r'\.\.\.f$', '...', excerpt)
        excerpt = re.sub(r'f\.\.\.$', '...', excerpt)
        excerpt = re.sub(r'\.\.\.$', '', excerpt).strip()
    if not excerpt:
        article_content = soup.find("div", class_="article-content")
        if article_content:
            first_section = article_content.find("div", class_="section")
            if first_section:
                p_tag = first_section.find("p")
                if p_tag:
                    excerpt = re.sub(r'\s+', ' ', p_tag.get_text()).strip()
    if not excerpt:
        excerpt = "Read the latest AI insights and business applications."
    if len(excerpt) > 200:
        excerpt = excerpt[:200].rstrip() + "..."
    elif not excerpt.endswith('...') and len(excerpt) < 200:
        if not excerpt.endswith('.'):
            excerpt = excerpt + "..."
    return {"title": title, "date": date_text, "excerpt": excerpt, "filename": os.path.basename(html_file)}

def create_blog_index_html(posts):
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

    # Build blog post list for ItemList schema
    itemlist_elements = []
    for i, post in enumerate(validated_posts[:10], 1):
        post_url = f"https://www.imetrobert.com/blog/posts/{post['filename']}"
        itemlist_elements.append(f'{{"@type":"ListItem","position":{i},"url":"{post_url}","name":{json.dumps(post["title"])}}}')
    itemlist_schema = ',\n    '.join(itemlist_elements)

    blog_index_html = f'''<!DOCTYPE html>
<html lang="en-CA">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <!-- ═══ SEO: Primary meta ═══ -->
    <title>AI News for Canadians | Monthly AI Insights Blog | Robert Simon</title>
    <meta name="description" content="Monthly AI insights for Canadian business leaders. Stay ahead with expert analysis of AI breakthroughs, Canadian AI adoption data, and practical implementation strategies from Montreal-based AI Evangelist Robert Simon.">
    <meta name="keywords" content="AI blog Canada, Canadian AI insights, AI news for Canadians, artificial intelligence Canada, AI strategy Canada, Montreal AI expert, Canadian business AI, AI adoption Canada, Bell Canada AI, digital transformation Canada">
    <meta name="author" content="Robert Simon">
    <meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large">
    <meta name="language" content="en-CA">

    <!-- ═══ GEO: Canadian location signals ═══ -->
    <meta name="geo.region" content="CA-QC">
    <meta name="geo.placename" content="Montreal, Quebec, Canada">
    <meta name="geo.position" content="45.5017;-73.5673">
    <meta name="ICBM" content="45.5017, -73.5673">
    <meta name="DC.coverage" content="Canada">

    <!-- ═══ Canonical ═══ -->
    <link rel="canonical" href="https://www.imetrobert.com/blog/">

    <!-- ═══ Open Graph ═══ -->
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://www.imetrobert.com/blog/">
    <meta property="og:title" content="AI News for Canadians | Monthly AI Insights Blog | Robert Simon">
    <meta property="og:description" content="Monthly AI insights for Canadian business leaders from Montreal-based AI Evangelist Robert Simon. Expert analysis of AI breakthroughs and Canadian business impact.">
    <meta property="og:image" content="https://www.imetrobert.com/blog/og-blog.jpg">
    <meta property="og:site_name" content="Robert Simon - AI Innovation">
    <meta property="og:locale" content="en_CA">

    <!-- ═══ Twitter / X card ═══ -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="AI News for Canadians | Monthly AI Insights | Robert Simon">
    <meta name="twitter:description" content="Monthly AI insights for Canadian business leaders from Montreal-based AI Evangelist Robert Simon.">
    <meta name="twitter:image" content="https://www.imetrobert.com/blog/og-blog.jpg">
    <meta name="twitter:creator" content="@thedigitalrobert">

    <!-- ═══ Structured data: Blog + ItemList ═══ -->
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "Blog",
      "name": "AI Insights for Canadian Business",
      "description": "Monthly AI innovation analysis for Canadian business leaders by Robert Simon, AI Evangelist at Bell Canada.",
      "url": "https://www.imetrobert.com/blog/",
      "inLanguage": "en-CA",
      "author": {{
        "@type": "Person",
        "name": "Robert Simon",
        "url": "https://www.imetrobert.com",
        "jobTitle": "AI Evangelist & Digital Sales Leader",
        "worksFor": {{"@type": "Organization", "name": "Bell Canada"}},
        "address": {{"@type": "PostalAddress", "addressLocality": "Montreal", "addressRegion": "QC", "addressCountry": "CA"}}
      }},
      "about": [
        {{"@type": "Thing", "name": "Artificial Intelligence"}},
        {{"@type": "Thing", "name": "Canadian Business"}},
        {{"@type": "Place", "name": "Canada"}}
      ]
    }}
    </script>
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "ItemList",
      "name": "AI Insights Blog Posts",
      "url": "https://www.imetrobert.com/blog/",
      "numberOfItems": {len(validated_posts)},
      "itemListElement": [
        {itemlist_schema}
      ]
    }}
    </script>
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      "itemListElement": [
        {{"@type": "ListItem", "position": 1, "name": "Home", "item": "https://www.imetrobert.com"}},
        {{"@type": "ListItem", "position": 2, "name": "AI Insights Blog", "item": "https://www.imetrobert.com/blog/"}}
      ]
    }}
    </script>

    <!-- ═══ Google Analytics ═══ -->
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-Y0FZTVVLBS"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('js', new Date());
      gtag('config', 'G-Y0FZTVVLBS');
    </script>

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
        .blog-tagline {{ font-size: 1.1rem; opacity: 0.9; margin-top: 0.5rem; }}
    </style>
</head>
<body>
    <nav class="nav-bar">
        <div class="nav-content">
            <a href="https://www.imetrobert.com" class="nav-link">&#8592; Back to Homepage</a>
        </div>
    </nav>

    <div class="container">
        <header>
            <h1>AI Insights Blog</h1>
            <p>Strategic Intelligence for Digital Leaders</p>
            <p class="blog-tagline">Monthly AI analysis for Canadian business &mdash; by Robert Simon, Montreal</p>
        </header>

        <section class="latest-post-section">
            <div class="latest-badge">Latest</div>
            <h2 class="latest-post-title">{latest_post['title']}</h2>
            <div style="margin-bottom: 1rem; opacity: 0.9;">{latest_post['date']}</div>
            <p style="line-height: 1.6; margin-bottom: 1.5rem;">{latest_post['excerpt']}</p>
            <a href="/blog/posts/latest.html" class="read-latest-btn">Read Full Analysis &#8594;</a>
        </section>

        <section class="older-posts-section">
            <h3 class="older-posts-title">Previous Insights</h3>
            <div class="older-posts-grid">
                {older_posts_html}
            </div>
        </section>
    </div>
</body>
</html>'''

    return blog_index_html

def update_blog_index():
    posts_dir = "blog/posts"
    index_file = "blog/index.html"
    if not os.path.exists(posts_dir):
        return []
    latest_path = os.path.join(posts_dir, "latest.html")
    posts = []
    if os.path.exists(latest_path) and os.path.getsize(latest_path) > 100:
        try:
            latest_info = extract_post_info(latest_path)
            if latest_info and latest_info.get('title') and latest_info.get('excerpt'):
                latest_info['filename'] = 'latest.html'
                posts.append(latest_info)
                print(f"Loaded latest post: {latest_info['title']}")
        except Exception as e:
            print(f"Warning: Could not process latest.html: {e}")
    html_files = [f for f in os.listdir(posts_dir)
                  if f.endswith(".html") and f != "latest.html"
                  and not f.startswith("{") and '{' not in f and f != "index.html"]
    for file in sorted(html_files, reverse=True):
        file_path = os.path.join(posts_dir, file)
        try:
            if os.path.exists(file_path) and os.path.getsize(file_path) > 100:
                post_info = extract_post_info(file_path)
                if post_info and post_info.get('title') and post_info.get('filename'):
                    posts.append(post_info)
        except Exception as e:
            print(f"Warning: Could not process {file}: {e}"); continue
    if not posts:
        print("Warning: No valid posts found"); return []
    latest_post = posts[0]
    older_posts = []
    seen_months = set()
    try:
        latest_date = datetime.strptime(latest_post['date'], "%B %d, %Y")
        seen_months.add(latest_date.strftime("%Y-%m"))
    except: pass
    for post in posts[1:]:
        try:
            post_date = datetime.strptime(post['date'], "%B %d, %Y")
            post_month_year = post_date.strftime("%Y-%m")
            if post_month_year not in seen_months:
                older_posts.append(post); seen_months.add(post_month_year)
        except: older_posts.append(post)
    print(f"Found {len(posts)} total posts, showing latest and {len(older_posts)} from previous months")
    new_blog_index = create_blog_index_html([latest_post] + older_posts)
    if not new_blog_index: return []
    try:
        with open(index_file, "w", encoding="utf-8") as f:
            f.write(new_blog_index)
        print(f"Blog index recreated with latest post + {len(older_posts)} previous months")
    except Exception as e:
        print(f"Error writing blog index: {e}")
    return posts

def main():
    parser = argparse.ArgumentParser(description="Blog Generator")
    parser.add_argument("--topic", help="Custom topic")
    parser.add_argument("--output", default="posts", choices=["staging", "posts"])
    args = parser.parse_args()
    print("RUNNING BLOG GENERATOR")
    api_key = os.getenv("PERPLEXITY_API_KEY")
    if not api_key:
        print("PERPLEXITY_API_KEY not set. Check your GitHub Actions secret.")
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
        with open(path_html, "w", encoding="utf-8") as f:
            f.write(html_content); f.flush(); os.fsync(f.fileno())
        print(f"Blog post saved: {path_html}")
        latest_path = os.path.join("blog", "posts", "latest.html")
        os.makedirs(os.path.dirname(latest_path), exist_ok=True)
        with open(latest_path, "w", encoding="utf-8") as f:
            f.write(html_content); f.flush(); os.fsync(f.fileno())
        print(f"Latest post updated")
        import time; time.sleep(0.1)
        posts = update_blog_index()
        print(f"Blog index updated with {len(posts)} posts")
        print("SUCCESS!")
    except Exception as e:
        print(f"Failed: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
