#!/usr/bin/env python3
"""
update-post-styles.py  —  place in repo ROOT
Retrofits all existing blog posts with the current mobile-optimised CSS.
Run via GitHub Actions workflow_dispatch.
"""
import os, re, sys

CANONICAL_CSS = """<style>
        :root {
            --primary-blue: #2563eb;
            --accent-cyan: #06b6d4;
            --dark-navy: #1e293b;
            --medium-gray: #64748b;
            --white: #ffffff;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Inter', sans-serif; background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%); color: var(--dark-navy); line-height: 1.6; }
        .nav-bar { background: var(--white); padding: 1rem 0; box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05); position: sticky; top: 0; z-index: 100; }
        .nav-content { max-width: 1200px; margin: 0 auto; padding: 0 1rem; display: flex; justify-content: space-between; align-items: center; gap: 1rem; flex-wrap: wrap; }
        .nav-link { color: white; text-decoration: none; font-weight: 600; padding: 0.5rem 1.25rem; font-size: 0.9rem; border-radius: 20px; background: linear-gradient(135deg, var(--primary-blue), var(--accent-cyan)); transition: all 0.3s ease; flex-shrink: 0; }
        .nav-link:hover { transform: translateY(-2px); box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); }
        .blog-meta { font-size: 0.85rem; color: var(--medium-gray); display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
        .header { background: linear-gradient(135deg, var(--primary-blue) 0%, var(--accent-cyan) 100%); color: white; padding: 3rem 0 2.5rem; text-align: center; }
        .header-content { max-width: 1000px; margin: 0 auto; padding: 0 1.25rem; }
        .header h1 { font-size: 2rem; font-weight: 700; margin-bottom: 0.5rem; line-height: 1.2; }
        .header .subtitle { font-size: 1.05rem; font-weight: 500; opacity: 0.9; margin-bottom: 1rem; }
        .header .intro { font-size: 0.95rem; opacity: 0.85; max-width: 800px; margin: 0 auto; line-height: 1.6; }
        .container { max-width: 1000px; margin: 0 auto; padding: 2rem 1.25rem 3rem; }
        .article-container { background: white; border-radius: 16px; box-shadow: 0 10px 25px -5px rgb(0 0 0 / 0.1); overflow: hidden; }
        .article-content { padding: 1.75rem; }
        .section { margin-bottom: 2.5rem; }
        .section-title { font-size: 1.5rem; color: var(--dark-navy); margin-bottom: 1.25rem; margin-top: 1.5rem; font-weight: 700; padding-left: 1rem; position: relative; }
        .section-title::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 4px; background: var(--primary-blue); border-radius: 2px; }
        .bullet-list { margin-bottom: 1.5rem; padding-left: 0; list-style: none; }
        .bullet-list li { margin-bottom: 1.25rem; line-height: 1.75; color: var(--medium-gray); position: relative; padding-left: 2rem; font-size: 0.95rem; }
        .bullet-list li::before { content: '●'; position: absolute; left: 0; color: var(--primary-blue); font-weight: bold; top: 0.1rem; font-size: 0.8rem; }
        .bullet-list.numbered { counter-reset: list-counter; }
        .bullet-list.numbered li { counter-increment: list-counter; }
        .bullet-list.numbered li::before { content: counter(list-counter) '.'; background: var(--primary-blue); color: white; width: 1.6rem; height: 1.6rem; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 600; font-size: 0.8rem; }
        p { margin-bottom: 1rem; line-height: 1.75; color: var(--medium-gray); font-size: 0.95rem; }
        strong { color: var(--dark-navy); font-weight: 600; }
        .conclusion { background: linear-gradient(135deg, var(--primary-blue) 0%, var(--accent-cyan) 100%); color: white; padding: 2rem; border-radius: 12px; margin-top: 2rem; }
        .conclusion p { color: rgba(255, 255, 255, 0.95); font-size: 1rem; font-weight: 500; margin-bottom: 0; }
        .conclusion strong { color: white; }
        .author-byline { display: flex; align-items: center; gap: 0.875rem; padding: 1rem 1.75rem; border-bottom: 1px solid #f1f5f9; background: #fafbfc; }
        .author-byline img { width: 44px; height: 44px; border-radius: 50%; object-fit: cover; flex-shrink: 0; }
        .author-byline .author-name { font-weight: 600; color: var(--dark-navy); font-size: 0.9rem; }
        .author-byline .author-role { font-size: 0.8rem; color: var(--medium-gray); }
        .breadcrumb { font-size: 0.78rem; color: var(--medium-gray); padding: 0.625rem 1.75rem; background: #fafbfc; border-bottom: 1px solid #f1f5f9; }
        .breadcrumb a { color: var(--primary-blue); text-decoration: none; }
        .earlier-insights { margin-top: 2rem; padding-top: 1.5rem; border-top: 1px solid #f1f5f9; }
        .earlier-posts-grid { display: grid; gap: 0.875rem; margin-top: 1.25rem; }
        .earlier-post-link { display: block; padding: 1rem 1.25rem; border: 1px solid #e2e8f0; border-radius: 10px; text-decoration: none; color: inherit; transition: all 0.25s ease; background: #fafbfc; }
        .earlier-post-link:hover { border-color: var(--primary-blue); background: white; }
        .earlier-post-title { font-size: 0.95rem; font-weight: 600; color: var(--primary-blue); margin-bottom: 0.25rem; }
        .earlier-post-date { font-size: 0.8rem; color: var(--medium-gray); }
        @media (max-width: 600px) {
            .header h1 { font-size: 1.5rem; }
            .header .subtitle { font-size: 0.95rem; }
            .header .intro { font-size: 0.875rem; }
            .container { padding: 1.25rem 0.875rem 2rem; }
            .article-content { padding: 1.25rem; }
            .section-title { font-size: 1.25rem; }
            .nav-content { flex-direction: column; align-items: flex-start; gap: 0.5rem; }
            .blog-meta { flex-direction: column; gap: 0.1rem; }
            .author-byline { padding: 0.875rem 1.25rem; }
            .breadcrumb { padding: 0.5rem 1.25rem; }
        }
    </style>"""

posts_dir = 'blog/posts'

if not os.path.exists(posts_dir):
    print("ERROR: blog/posts not found. Run from repo root.")
    sys.exit(1)

eligible = [
    f for f in os.listdir(posts_dir)
    if f.endswith('.html')
    and f != 'latest.html'
    and not f.startswith('{')
    and '{' not in f
    and f != 'index.html'
]

print(f"Found {len(eligible)} posts to update")
updated = 0
skipped = 0

for filename in sorted(eligible):
    filepath = os.path.join(posts_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()

    # Replace the existing <style>...</style> block
    new_html = re.sub(r'<style>.*?</style>', CANONICAL_CSS, html, count=1, flags=re.DOTALL)

    if new_html == html:
        print(f"  SKIPPED (no style block found): {filename}")
        skipped += 1
        continue

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_html)
    print(f"  Updated: {filename}")
    updated += 1

print(f"\nDone. Updated: {updated}, Skipped: {skipped}")
