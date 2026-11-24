"""Offline test. Run: python3 scripts/test_content_gap_report.py"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import content_gap_report as c
pages = c.existing_pages()
assert "consulting" in pages and pages["consulting"]["kind"] == "services"
good = {"title": "T", "question": "q?", "why": "w", "outline": ["a", "b", "c"], "link_to": "consulting", "faq": ["x?", "y?"]}
assert c.parse("```json\n" + json.dumps(good) + "\n```", pages)["title"] == "T"
for bad in ({**good, "link_to": "nope"}, {**good, "outline": ["a"]}, {**good, "why": "saves 40% of time"}, {k: v for k, v in good.items() if k != "faq"}):
    try:
        c.parse(json.dumps(bad), pages); raise SystemExit(f"accepted bad reply {bad}")
    except ValueError:
        pass
print("ALL PASSED")
