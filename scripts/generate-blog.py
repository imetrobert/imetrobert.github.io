"""
generate-blog.py
Entry point for the monthly blog generator.
Imports from modular scripts: gemini, parser, renderer, blog_index, utils.
"""

import argparse
import os
import sys
import time
from datetime import datetime

from utils import clean_filename
from gemini import generate_blog_with_gemini
from parser import extract_title_and_excerpt
from renderer import create_html_blog_post
from blog_index import update_blog_index


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic",  help="Custom topic / focus directive (optional)")
    parser.add_argument("--output", default="posts", choices=["staging", "posts"])
    args = parser.parse_args()

    print("=== Blog Generator ===")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set.")
        sys.exit(1)

    try:
        result     = generate_blog_with_gemini(api_key, args.topic)
        month_year = datetime.now().strftime("%B %Y")
        title, excerpt = extract_title_and_excerpt(result["content"], month_year)

        print(f"Title:   {title}")
        print(f"Excerpt: {excerpt[:80]}...")

        html_content = create_html_blog_post(result["content"], title, excerpt)

        iso_date   = datetime.now().strftime("%Y-%m-%d")
        filename   = f"{iso_date}-{clean_filename(title)}.html"
        output_dir = os.path.join("blog", args.output)
        os.makedirs(output_dir, exist_ok=True)

        out_path = os.path.join(output_dir, filename)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html_content)
            f.flush()
            os.fsync(f.fileno())
        print(f"Saved: {out_path}")

        if args.output == "posts":
            latest_path = os.path.join("blog", "posts", "latest.html")
            os.makedirs(os.path.dirname(latest_path), exist_ok=True)
            with open(latest_path, "w", encoding="utf-8") as f:
                f.write(html_content)
                f.flush()
                os.fsync(f.fileno())
            print("Updated latest.html")
        else:
            print("Staging mode — latest.html NOT updated (production unchanged)")

        time.sleep(0.2)

        if args.output == "posts":
            update_blog_index()
            print("Blog index updated.")
        else:
            print("Staging mode — blog/index.html NOT updated (production unchanged)")

        print("SUCCESS.")

    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
