"""Offline end-to-end tests for the blog's section redraft path. Run: python3 scripts/test_pipeline.py
No network, no API key: Gemini is replaced by a stub. The fixture is the newest real published issue, so the
tests exercise the real renderer blocks, FAQ sync and JSON-LD. What is proven:

  * a good redraft changes only its own block (and the FAQ for Looking Ahead), keeps the page well formed;
  * junk, too-short, copied, malformed and exception outputs leave the file BYTE-IDENTICAL and are logged
    with a plain error code and next step;
  * a rejected first attempt is retried once with the reason, and a good second attempt is applied;
  * a write that fails the post-write check is rolled back;
  * the run log records every outcome and stays capped.
"""
import glob
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

os.environ["GEMINI_API_KEY"] = "test-key"
os.chdir(ROOT)
import runlog                      # noqa: E402
import redraft_section as rs       # noqa: E402

FIXTURE = sorted(p for p in glob.glob(os.path.join(ROOT, "blog", "posts", "2026-*.html"))
                 if "latest" not in p and "stub" not in open(p, encoding="utf-8").read(2000).lower())[-1]

DESK = ("Most small business owners I talk to are not asking whether AI works. They are asking whether it is worth "
        "the next hour of their week. " * 1 + "That question deserves a straighter answer than the industry usually gives. "
        "Here is how I think about it. Pick one task that repeats every week, such as quoting, scheduling or "
        "follow-ups. Time how long it takes today. Then try the plan you already pay for and time it again. "
        "If the saving is under twenty percent, leave it alone and move on. If it is over half, write the steps "
        "down so a colleague can repeat them. That is the whole method and it is deliberately boring. "
        "The excitement belongs to the vendors; the value belongs to the owners who keep a stopwatch. "
        "Over the past year the tools have improved quickly, yet the gap between a good result and a mediocre one "
        "still comes from how clearly the work is described, not from which logo is on the screen. "
        "A clear brief, a sample of what good looks like, and a short list of things to avoid will beat a clever "
        "prompt almost every time. Owners who treat the assistant like a new hire, with context and feedback, "
        "get better results than those who treat it like a vending machine. "
        "Privacy deserves the same discipline: decide in advance which client details never go into a chat, "
        "and write that rule where everyone can see it. Start small, measure honestly, and keep what works. "
        "That is how a good habit becomes an advantage, and it costs nothing but attention. "
        "If you do only one thing this month, make it the stopwatch test on a single repeating task.")
SUMMARY = ("1. Low-cost plans now handle recurring drafting work reliably enough to test on one real task this month.\n"
           "2. Scheduled tasks and saved instructions moved from experiments to everyday features in several plans.\n"
           "3. The deciding factor for most owners is privacy handling, not raw model quality, so write your rules first.")
PRED = ("One month: expect more plan bundles that include scheduling and file handling at the same monthly price.\n"
        "Six months: expect the cheapest plans to match today's premium tools for writing and summarising documents.\n"
        "One year: expect owners who documented their workflows to switch tools in an afternoon while others start over.")
QUESTION = "Which single weekly task in your business would you be happy never to do by hand again, and what would it take to test that this month?"

GOOD = {
    "FROM ROBERTS DESK": DESK,
    "EXECUTIVE SUMMARY": SUMMARY,
    "LOOKING AHEAD: THREE PREDICTIONS": PRED,
    "ONE QUESTION FOR YOUR LEADERSHIP TEAM": QUESTION,
}


class Stub:
    """Replaces generate_section_redraft. `script` is a list of str (returned) or Exception (raised), one per call."""
    def __init__(self, script):
        self.script, self.calls, self.notes = list(script), 0, []

    def __call__(self, api_key, section, issue_text, guidance="", month_year=None, retry_note=""):
        self.calls += 1
        self.notes.append(retry_note)
        item = self.script.pop(0) if self.script else self.script_last
        self.script_last = item
        if isinstance(item, Exception):
            raise item
        return item, "stub-model"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "issue.html")
        shutil.copy(FIXTURE, self.path)
        self.before = open(self.path, "rb").read()
        runlog.LOG_PATH = os.path.join(self.tmp, "run-log.json")
        self._orig = rs.generate_section_redraft

    def tearDown(self):
        rs.generate_section_redraft = self._orig
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_redraft(self, section, script, guidance=""):
        stub = Stub(script)
        rs.generate_section_redraft = stub
        ok = rs.redraft(self.path, section, guidance, "October 2026")
        return ok, stub

    def unchanged(self):
        return open(self.path, "rb").read() == self.before

    def last_log(self):
        return runlog._load()[-1]


class GoodRedrafts(Base):
    def test_each_section_applies_cleanly(self):
        for section, text in GOOD.items():
            with self.subTest(section=section):
                shutil.copy(FIXTURE, self.path)
                ok, stub = self.run_redraft(section, [text])
                self.assertTrue(ok, runlog._load()[-1:])
                html = open(self.path, encoding="utf-8").read()
                self.assertEqual(html.lower().count("<div"), html.lower().count("</div"))
                self.assertIsNotNone(rs.find_block(html, rs.SECTION_BLOCKS[section]["block_class"]))
                self.assertEqual(stub.calls, 1)
                self.assertEqual(self.last_log()["status"], "ok")
                self.assertEqual(self.last_log()["section"], section)

    def test_only_the_target_block_changes(self):
        ok, _ = self.run_redraft("ONE QUESTION FOR YOUR LEADERSHIP TEAM", [QUESTION])
        self.assertTrue(ok)
        before = open(FIXTURE, encoding="utf-8").read()
        after = open(self.path, encoding="utf-8").read()
        for other in ("FROM ROBERTS DESK", "EXECUTIVE SUMMARY", "LOOKING AHEAD: THREE PREDICTIONS"):
            c = rs.SECTION_BLOCKS[other]["block_class"]
            a, b = rs.find_block(before, c), rs.find_block(after, c)
            self.assertEqual(before[a[0]:a[1]], after[b[0]:b[1]], other)
        self.assertEqual(before.count("application/ld+json"), after.count("application/ld+json"))

    def test_predictions_refresh_the_faq_copy(self):
        ok, _ = self.run_redraft("LOOKING AHEAD: THREE PREDICTIONS", [PRED])
        self.assertTrue(ok)
        html = open(self.path, encoding="utf-8").read()
        self.assertIn("same monthly price", html)          # visible FAQ answer or schema carries the new text


class BadOutputLeavesFileAlone(Base):
    def check(self, section, bad, code):
        ok, stub = self.run_redraft(section, [bad])      # the stub repeats `bad` on the retry too
        self.assertFalse(ok)
        self.assertTrue(self.unchanged(), "file must be byte-identical after a rejected redraft")
        self.assertEqual(self.last_log()["code"], code)
        self.assertTrue(self.last_log()["next"])
        self.assertEqual(stub.calls, rs.MAX_ATTEMPTS)

    def test_checklist_notes_instead_of_desk(self):
        self.check("FROM ROBERTS DESK", "Constraint checklist: no invented specifics. " + DESK, "JUNK_OUTPUT")

    def test_chat_opener(self):
        self.check("EXECUTIVE SUMMARY", "Sure, here are three points:\n" + SUMMARY, "JUNK_OUTPUT")

    def test_markdown_and_links(self):
        self.check("ONE QUESTION FOR YOUR LEADERSHIP TEAM", "**" + QUESTION + "** (source: https://example.com)", "JUNK_OUTPUT")

    def test_too_short_desk(self):
        self.check("FROM ROBERTS DESK", "I think AI is useful for small business owners.", "TOO_SHORT")

    def test_copy_of_current_text(self):
        html = open(self.path, encoding="utf-8").read()
        c = rs.SECTION_BLOCKS["ONE QUESTION FOR YOUR LEADERSHIP TEAM"]["block_class"]
        span = rs.find_block(html, c)
        old = rs.block_text(html[span[0]:span[1]])
        ok, stub = self.run_redraft("FROM ROBERTS DESK",
                                    [rs.block_text(html[rs.find_block(html, "desk-section")[0]:rs.find_block(html, "desk-section")[1]])])
        self.assertFalse(ok)
        self.assertTrue(self.unchanged())
        self.assertIn(self.last_log()["code"], ("TOO_SIMILAR", "JUNK_OUTPUT", "TOO_SHORT"))

    def test_predictions_missing_a_horizon(self):
        two = ("One month: expect more plan bundles that include scheduling and file handling at the same price point this year.\n"
               "Six months: expect the cheapest plans to match today's premium tools for drafting and summarising long documents.")
        self.check("LOOKING AHEAD: THREE PREDICTIONS", two, "FORMAT_MISMATCH")

    def test_summary_with_only_two_items(self):
        two = ("1. Low-cost plans now handle recurring drafting work reliably enough to test on one real task this month.\n"
               "2. Scheduled tasks and saved instructions moved from experiments to everyday features in several plans.")
        self.check("EXECUTIVE SUMMARY", two, "FORMAT_MISMATCH")

    def test_model_exception_is_classified(self):
        for exc, code in ((Exception("API key rejected (403). Check your GEMINI_API_KEY secret."), "API_KEY_REJECTED"),
                          (Exception("All Gemini models failed to produce a search-grounded answer."), "UNGROUNDED_REJECTED"),
                          (Exception("All Gemini models failed."), "ALL_MODELS_FAILED")):
            with self.subTest(code=code):
                ok, _ = self.run_redraft("EXECUTIVE SUMMARY", [exc])
                self.assertFalse(ok)
                self.assertTrue(self.unchanged())
                self.assertEqual(self.last_log()["code"], code)

    def test_unknown_section_and_missing_key(self):
        ok = rs.redraft(self.path, "SOMETHING ELSE", "", None)
        self.assertFalse(ok)
        self.assertEqual(self.last_log()["code"], "SECTION_NOT_REDRAFTABLE")
        key = os.environ.pop("GEMINI_API_KEY")
        try:
            self.assertFalse(rs.redraft(self.path, "FROM ROBERTS DESK", "", None))
            self.assertEqual(self.last_log()["code"], "NO_API_KEY")
        finally:
            os.environ["GEMINI_API_KEY"] = key
        self.assertTrue(self.unchanged())


class RetryAndRollback(Base):
    def test_rejected_first_attempt_is_retried_with_the_reason(self):
        ok, stub = self.run_redraft("EXECUTIVE SUMMARY", ["Sure, here you go:\n" + SUMMARY, SUMMARY])
        self.assertTrue(ok)
        self.assertEqual(stub.calls, 2)
        self.assertEqual(stub.notes[0], "")
        self.assertIn("chat reply", stub.notes[1])            # the second prompt carried the rejection reason

    def test_transient_failure_then_success(self):
        ok, stub = self.run_redraft("ONE QUESTION FOR YOUR LEADERSHIP TEAM", [Exception("All Gemini models failed."), QUESTION])
        self.assertTrue(ok)
        self.assertEqual(stub.calls, 2)

    def test_failed_verification_rolls_back(self):
        orig = rs.verify_written
        rs.verify_written = lambda *a, **k: ["div tags are no longer balanced"]
        try:
            ok, _ = self.run_redraft("ONE QUESTION FOR YOUR LEADERSHIP TEAM", [QUESTION])
        finally:
            rs.verify_written = orig
        self.assertFalse(ok)
        self.assertTrue(self.unchanged())
        self.assertEqual(self.last_log()["code"], "VERIFY_FAILED")


class RunLog(Base):
    def test_log_is_capped_and_explains_every_code(self):
        for i in range(runlog.MAX_ENTRIES + 20):
            runlog.record("test", "ok", "OK", f"entry {i}")
        self.assertEqual(len(runlog._load()), runlog.MAX_ENTRIES)
        for code in runlog.CATALOGUE:
            what, _ = runlog.explain(code)
            self.assertTrue(what)

    def test_official_body_items_must_cite_the_body(self):
        import parser as P
        mk = lambda org, src: {"org": org, "body": "x" * 40, "source_name": src, "source_url": ""}
        items = [mk("Quebec's Commission d'acces a l'information", "PolicyFirst AI"),
                 mk("Quebec's Commission d'acces a l'information", "Commission d'acces a l'information du Quebec"),
                 mk("Office of the Privacy Commissioner of Canada", "Office of the Privacy Commissioner of Canada"),
                 mk("Shopify", "The Globe and Mail")]
        kept = P._drop_low_quality_sourced(items, "org")
        self.assertEqual([i["source_name"] for i in kept],
                         ["Commission d'acces a l'information du Quebec",
                          "Office of the Privacy Commissioner of Canada", "The Globe and Mail"])

    def test_classify(self):
        self.assertEqual(runlog.classify(Exception("HTTP 429 resource_exhausted")), "QUOTA_EXHAUSTED")
        self.assertEqual(runlog.classify("model gemini-x is not found for API version"), "MODEL_UNAVAILABLE")
        self.assertEqual(runlog.classify("boom"), "UNEXPECTED")


class WorkflowWiring(unittest.TestCase):
    def test_redraft_choices_match_the_registry(self):
        import gemini
        wf = open(os.path.join(ROOT, ".github", "workflows", "redraft-section.yml"), encoding="utf-8").read()
        for key in gemini.REDRAFTABLE_SECTIONS:
            self.assertIn(key, wf, f"redraft-section.yml has no choice for {key}")
        self.assertEqual(set(gemini.REDRAFTABLE_SECTIONS), set(rs.SECTION_BLOCKS))


if __name__ == "__main__":
    unittest.main(verbosity=1)
