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
    """Extract title, date, and excerpt from an HTML blog post"""
    with open(html_file, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    # Title: from <h1> or <title>
    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else "Untitled"

    # Date: look for <p> containing date or fallback to filename
    date_tag = soup.find(text=re.compile(r'\b\d{4}-\d{2}-\d{2}\b'))
    if date_tag:
        date_text = date_tag.strip()
    else:
        # fallback: extract date from filename like 2025-09-26-ai-insights.html
        basename = os.path.basename(html_file)
        match = re.match(r"(\d{4}-\d{2}-\d{2})-", basename)
        date_text = match.group(1) if match else "Unknown Date"

    # Excerpt: first paragraph inside <p>
    p_tag = soup.find("p")
    excerpt = clean_html_text(p_tag.get_text()) if p_tag else "Read the full post."

    return {
        "title": title,
        "date": date_text,
        "excerpt": excerpt,
        "filename": os.path.basename(html_file)
    }

def build_blog_card(post):
    """Return HTML snippet for a blog card"""
    return f"""
    <div class="blog-card">
        <h4>{post['title']}</h4>
        <div class="blog-date">{post['date']}</div>
        <p class="blog-excerpt">{post['excerpt']}</p>
        <a class="read-more" href="blog/posts/{post['filename']}">Read More →</a>
    </div>
    """

def update_homepage_preview():
    """Main function to update blog-preview div in homepage"""
    # Gather posts
    posts = []
    for file in sorted(os.listdir(POSTS_DIR), reverse=True):
        if file.endswith(".html"):
            posts.append(extract_post_info(os.path.join(POSTS_DIR, file)))

    # Build blog cards HTML
    cards_html = "\n".join([build_blog_card(p) for p in posts])

    # Read homepage
    with open(HOMEPAGE_FILE, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")

    # Find blog-preview div
    preview_div = soup.find("div", {"id": "blog-preview"})
    if preview_div:
        preview_div.clear()
        preview_div.append(BeautifulSoup(cards_html, "html.parser"))
    else:
        print("⚠️ Could not find <div id='blog-preview'> in homepage.")

    # Save updated homepage
    with open(HOMEPAGE_FILE, "w", encoding="utf-8") as f:
        f.write(str(soup.prettify(formatter="html")))

    print(f"✅ Homepage preview updated with {len(posts)} posts.")

if __name__ == "__main__":
    update_homepage_preview()
