import os
import json
from datetime import datetime
from bs4 import BeautifulSoup

def update_blog_index():
    """Update the blog index page with current posts"""
    posts_dir = "blog/posts"
    index_file = "blog/index.html"  # or wherever your blog main page is
    
    # Get all blog posts
    posts = []
    for file in sorted(os.listdir(posts_dir), reverse=True):
        if file.endswith(".html") and file != "index.html":
            posts.append(extract_post_info(os.path.join(posts_dir, file)))
    
    # Read the blog index template
    with open(index_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Generate JavaScript data
    posts_js = generate_posts_javascript(posts)
    
    # Replace the fetchBlogPosts function
    content = replace_fetch_function(content, posts_js)
    
    # Write updated file
    with open(index_file, "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"✅ Blog index updated with {len(posts)} posts")

def generate_posts_javascript(posts):
    """Generate JavaScript array of posts"""
    js_posts = []
    for post in posts:
        js_posts.append({
            "title": post["title"],
            "date": post["date"], 
            "excerpt": post["excerpt"],
            "filename": post["filename"]
        })
    
    return json.dumps(js_posts, indent=8)

def replace_fetch_function(content, posts_data):
    """Replace the fetchBlogPosts function with real data"""
    new_function = f'''async function fetchBlogPosts() {{
            return {posts_data};
        }}'''
    
    # Find and replace the fetchBlogPosts function
    import re
    pattern = r'async function fetchBlogPosts\(\) \{[^}]+\}[^}]+\}'
    content = re.sub(pattern, new_function, content, flags=re.DOTALL)
    
    return content
