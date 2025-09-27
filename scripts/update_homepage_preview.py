def update_homepage_blog_section(posts):
    """Update the main portfolio homepage with latest blog post - matching design"""
    homepage_file = "index.html"
    
    if not os.path.exists(homepage_file):
        print("Homepage file not found")
        return
    
    if not posts:
        print("No posts to update homepage with")
        return
        
    try:
        with open(homepage_file, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading homepage: {e}")
        return
    
    latest_post = posts[0]
    other_posts = posts[1:3] if len(posts) > 1 else []  # Show max 3 previous posts
    
    # Update latest post content
    latest_post_update = f'''
                <div class="latest-post-content">
                    <h3 class="latest-post-title">{latest_post['title']}</h3>
                    <div class="latest-post-meta">
                        <span class="post-date">{latest_post['date']}</span>
                        <span class="post-category">Strategic Intelligence</span>
                    </div>
                    <p class="latest-post-excerpt">{latest_post['excerpt']}</p>
                    
                    <div class="latest-post-actions">
                        <a href="/blog/posts/{latest_post['filename']}" class="btn btn-primary">
                            <span>Read Full Analysis</span>
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M5 12h14M12 5l7 7-7 7"/>
                            </svg>
                        </a>
                    </div>
                </div>'''
    
    # Replace the latest post content
    latest_content_pattern = r'<div class="latest-post-content">.*?</div>\s*</div>'
    if re.search(latest_content_pattern, content, re.DOTALL):
        content = re.sub(latest_content_pattern, latest_post_update + '\n                </div>', content, flags=re.DOTALL)
        print("Updated existing latest post content")
    else:
        # If pattern not found, look for placeholder content
        placeholder_pattern = r'<h3 class="latest-post-title">AI Insights Coming Soon</h3>.*?</div>\s*</div>'
        if re.search(placeholder_pattern, content, re.DOTALL):
            # Extract just the content part
            content_only = latest_post_update.split('<div class="latest-post-content">')[1].split('</div>')[0]
            replacement = f'<h3 class="latest-post-title">{latest_post["title"]}</h3>{content_only}</div>'
            content = re.sub(placeholder_pattern, replacement, content, flags=re.DOTALL)
            print("Updated placeholder content with latest post")
    
    # Update previous posts section if there are other posts
    if other_posts:
        previous_posts_html = ''
        for post in other_posts:
            previous_posts_html += f'''
                        <div class="previous-post-item">
                            <h5><a href="/blog/posts/{post['filename']}">{post['title']}</a></h5>
                            <div class="previous-post-date">{post['date']}</div>
                        </div>'''
        
        # Show the previous posts section
        content = re.sub(
            r'<div class="previous-posts-section"[^>]*style="display: none;"[^>]*>',
            '<div class="previous-posts-section">',
            content
        )
        
        # Replace the grid content
        grid_pattern = r'(<div class="previous-posts-grid">).*?(</div>)'
        if re.search(grid_pattern, content, re.DOTALL):
            content = re.sub(
                grid_pattern, 
                r'\1' + previous_posts_html + '\n                ' + r'\2', 
                content, 
                flags=re.DOTALL
            )
            print(f"Updated previous posts with {len(other_posts)} posts")
    
    try:
        with open(homepage_file, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Homepage updated with latest blog post: {latest_post['title']}")
        
        # Also update the badge text to "Latest"
        content = content.replace(
            '<span class="badge-text">Latest Post</span>',
            '<span class="badge-text">Latest</span>'
        )
        
        with open(homepage_file, "w", encoding="utf-8") as f:
            f.write(content)
            
    except Exception as e:
        print(f"Error writing homepage: {e}")
