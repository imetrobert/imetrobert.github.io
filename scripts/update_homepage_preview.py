import os
import re
from datetime import datetime
from bs4 import BeautifulSoup

# Paths
POSTS_DIR = "blog/posts"
HOMEPAGE_FILE = "index.html"  # adjust if your homepage file is elsewhere

def clean_html_text(html_content):
    """Remove extra whitespace and newlines"""
    return re.sub(r'\s+', ' ', html_content).strip()

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
        excerpt = clean_html_text(intro_div.get_text())
    
    # Try first paragraph in article content
    if not excerpt:
        article_content = soup.find("div", class_="article-content")
        if article_content:
            p_tag = article_content.find("p")
            if p_tag:
                excerpt = clean_html_text(p_tag.get_text())
    
    # Generic fallback to any paragraph
    if not excerpt:
        p_tag = soup.find("p")
        if p_tag:
            excerpt = clean_html_text(p_tag.get_text())
    
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

def build_blog_card(post):
    """Return HTML snippet for a blog card matching your homepage style"""
    return f'''<div class="blog-card">
    <h4>{post['title']}</h4>
    <div class="blog-date">{post['date']}</div>
    <p class="blog-excerpt">{post['excerpt']}</p>
    <a href="/blog/posts/{post['filename']}" class="blog-read-more">
        Read Full Post →
    </a>
</div>'''

def update_homepage_preview():
    """Main function to update blog-preview div in homepage"""
    # Check if posts directory exists
    if not os.path.exists(POSTS_DIR):
        print(f"Posts directory {POSTS_DIR} does not exist. Creating it...")
        os.makedirs(POSTS_DIR, exist_ok=True)
        print("No posts found to display.")
        return

    # Check if homepage exists
    if not os.path.exists(HOMEPAGE_FILE):
        print(f"Homepage file {HOMEPAGE_FILE} not found.")
        return

    # Gather posts
    posts = []
    html_files = [f for f in os.listdir(POSTS_DIR) if f.endswith(".html")]
    
    if not html_files:
        print("No HTML files found in posts directory.")
        return

    print(f"Found {len(html_files)} HTML files in posts directory.")

    # Sort by filename (which should include date) in reverse order for newest first
    for file in sorted(html_files, reverse=True):
        file_path = os.path.join(POSTS_DIR, file)
        try:
            post_info = extract_post_info(file_path)
            posts.append(post_info)
            print(f"Processed: {file} -> {post_info['title']}")
        except Exception as e:
            print(f"Error processing {file}: {e}")
            continue

    if not posts:
        print("No valid posts could be processed.")
        return

    # Build blog cards HTML
    cards_html = "\n".join([build_blog_card(p) for p in posts])

    # Read homepage
    try:
        with open(HOMEPAGE_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            soup = BeautifulSoup(content, "html.parser")
    except Exception as e:
        print(f"Error reading homepage: {e}")
        return

    # Find blog-preview div
    preview_div = soup.find("div", {"id": "blog-preview"})
    if preview_div:
        # Clear existing content and add new cards
        preview_div.clear()
        preview_div.append(BeautifulSoup(cards_html, "html.parser"))
        
        # Save updated homepage
        try:
            with open(HOMEPAGE_FILE, "w", encoding="utf-8") as f:
                # Use prettify with minimal formatter to maintain structure
                f.write(str(soup.prettify(formatter="html")))
            print(f"Homepage preview updated with {len(posts)} posts.")
        except Exception as e:
            print(f"Error writing homepage: {e}")
    else:
        print("Could not find <div id='blog-preview'> in homepage.")
        print("Available divs with IDs:")
        divs_with_ids = soup.find_all("div", id=True)
        for div in divs_with_ids[:10]:  # Show first 10
            print(f"  - {div.get('id')}")

def main():
    """Main function for command line usage"""
    print("Updating homepage blog preview...")
    print("=" * 50)
    update_homepage_preview()
    print("Done!")

if __name__ == "__main__":
    main()
