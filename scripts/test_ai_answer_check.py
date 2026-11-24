"""Offline test. Run: python3 scripts/test_ai_answer_check.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ai_answer_check as a
r = a.analyse("q", {"content": "Try AI with Robert in Montreal.", "grounding": {"chunks": [{"title": "seniors.aiwithrobert.com", "uri": "https://x"}]}})
assert r["named"] and r["cited"], r
r = a.analyse("q", {"content": "Try Groovy AI.", "grounding": {"chunks": [{"title": "groovy.ai", "uri": "https://y"}]}})
assert not r["named"] and not r["cited"], r
def call(q):
    if "tutor" in q: raise RuntimeError("quota")
    return {"content": "nothing", "grounding": {"chunks": []}}
res = a.run(call)
assert len(res) == len(a.QUESTIONS) and "error" in res[0] and res[1]["named"] is False
print("ALL PASSED")
