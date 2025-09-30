import os
import re

# Google Analytics tag to add
GA_TAG = '''<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-Y0FZTVVLBS"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-Y0FZTVVLBS');
</script>'''

def add_analytics_to_file(filepath):
    """Add Google Analytics tag to an HTML file if not already present"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if GA tag already exists
        if 'G-Y0FZTVVLBS' in content or 'gtag' in content:
            print(f"✓ {filepath} already has analytics")
            return False
        
        # Find the </head> tag and insert GA tag before it
        if '</head>' in content:
            content = content.replace('</head>', f'{GA_TAG}\n</head>')
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Added analytics to {filepath}")
            return True
        else:
            print(f"⚠️  No </head> tag found in {filepath}")
            return False
            
    except Exception as e:
        print(f"❌ Error processing {filepath}: {e}")
        return False

def process_all_html_files():
    """Process all HTML files in the project"""
    files_updated = 0
    
    # Process root index.html
    if os.path.exists('index.html'):
        if add_analytics_to_file('index.html'):
            files_updated += 1
    
    # Process blog/index.html
    if os.path.exists('blog/index.html'):
        if add_analytics_to_file('blog/index.html'):
            files_updated += 1
    
    # Process all files in blog/posts/
    posts_dir = 'blog/posts'
    if os.path.exists(posts_dir):
        for filename in os.listdir(posts_dir):
            if filename.endswith('.html'):
                filepath = os.path.join(posts_dir, filename)
                if add_analytics_to_file(filepath):
                    files_updated += 1
    
    print(f"\n🎉 Updated {files_updated} files with Google Analytics")

if __name__ == "__main__":
    print("Adding Google Analytics to all HTML pages...\n")
    process_all_html_files()
