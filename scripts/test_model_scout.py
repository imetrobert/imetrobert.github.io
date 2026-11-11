"""Offline tests for the model scout. Run: python3 scripts/test_model_scout.py
No network and no API key: every Gemini call is replaced."""
import os, sys, unittest
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model_scout as ms
import utils

ms.record_gemini_request = lambda *a, **k: None   # tests must not touch the real usage ledger
NOW = datetime(2026, 11, 11, tzinfo=timezone.utc)

def cfg(**kw):
    c = utils.load_model_config("/nonexistent")
    c.update(kw)
    return c

class Resp:
    def __init__(self, status, data=None): self.status_code, self._d = status, data or {}
    def json(self): return self._d

def ok_resp(grounded=True, text="Canada funds a thing for AI this week, says the ministry."):
    cand = {"content": {"parts": [{"text": text}]}}
    if grounded: cand["groundingMetadata"] = {"webSearchQueries": ["q"]}
    return Resp(200, {"candidates": [cand]})

class Candidates(unittest.TestCase):
    def test_filters(self):
        found = ["gemini-3.7-flash", "gemini-3.5-flash-lite", "gemini-3.6-pro", "gemini-3.5-transcribe",
                 "gemini-3.8-flash-image", "gemini-2.0-flash", "gemini-3.9-flash"]
        got = ms.pick_candidates(found, cfg(), NOW)
        self.assertEqual(got, ["gemini-3.9-flash", "gemini-3.7-flash"])
    def test_version_order_uses_tuples(self):
        got = ms.pick_candidates(["gemini-3.9-flash", "gemini-3.10-flash"], cfg(), NOW)
        self.assertEqual(got[0], "gemini-3.10-flash")
    def test_skips_recent_rejection_but_retries_after_cooldown(self):
        rej = {"gemini-3.7-flash": {"retry_after": (NOW + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")}}
        self.assertEqual(ms.pick_candidates(["gemini-3.7-flash"], cfg(rejected=rej), NOW), [])
        later = NOW + timedelta(days=5)
        self.assertEqual(ms.pick_candidates(["gemini-3.7-flash"], cfg(rejected=rej), later), ["gemini-3.7-flash"])
    def test_dismissed_and_tiny_limit_never_lead(self):
        c = cfg(dismissed=["gemini-3.7-flash"]); c["limits"]["gemini-3.8-flash"] = 20
        self.assertEqual(ms.pick_candidates(["gemini-3.7-flash", "gemini-3.8-flash"], c, NOW), [])
    def test_not_newer_than_leader_skipped(self):
        c = cfg(qualified={"gemini-3.7-flash": {}})
        self.assertEqual(ms.pick_candidates(["gemini-3.6-flash"], c, NOW), [])

class Probe(unittest.TestCase):
    def run_probe(self, *resps):
        it = iter(resps)
        return ms.probe("k", "m", post=lambda *a, **k: next(it), sleep=lambda s: None)
    def test_ok(self): self.assertTrue(self.run_probe(ok_resp())["ok"])
    def test_ungrounded(self):
        r = self.run_probe(ok_resp(grounded=False)); self.assertFalse(r["ok"]); self.assertIn("without", r["reason"])
    def test_429_after_retry(self):
        r = self.run_probe(Resp(429), Resp(429)); self.assertFalse(r["ok"]); self.assertIn("429", r["reason"])
    def test_transient_then_ok(self): self.assertTrue(self.run_probe(Resp(503), ok_resp())["ok"])
    def test_404(self): self.assertIn("404", self.run_probe(Resp(404))["reason"])
    def test_network_error(self):
        def boom(*a, **k): raise OSError("x")
        self.assertFalse(ms.probe("k", "m", post=boom, sleep=lambda s: None)["ok"])

class Scout(unittest.TestCase):
    def passing_trial(self, k, m): return {"ok": True, "reason": "ok", "checks": {"desk_words": 400}}
    def test_qualifies_and_leads(self):
        c = cfg()
        changed = ms.run_scout("k", c, ["gemini-3.7-flash", "gemini-3.5-flash"],
                               probe_fn=lambda k, m: {"ok": True, "reason": "ok"},
                               trial_fn=self.passing_trial, now=NOW)
        self.assertTrue(changed)
        self.assertEqual(utils.resolve_model_order(c)[0], "gemini-3.7-flash")
        self.assertEqual(c["order"][-1], "gemini-2.0-flash")       # baseline stays as the safety net
        self.assertNotIn("gemini-3.5-flash", c["qualified"])         # older than the winner: not tested after it
        self.assertEqual(c["available"], [])
    def test_probe_failure_rejects_and_next_candidate_tried(self):
        c = cfg()
        seen = []
        def probe_fn(k, m):
            seen.append(m); return {"ok": m != "gemini-3.8-flash", "reason": "429: no free-tier quota"}
        ms.run_scout("k", c, ["gemini-3.8-flash", "gemini-3.7-flash"], probe_fn=probe_fn,
                     trial_fn=self.passing_trial, now=NOW)
        self.assertIn("gemini-3.8-flash", c["rejected"])
        self.assertEqual(utils.resolve_model_order(c)[0], "gemini-3.7-flash")
    def test_quality_failure_rejects_with_long_cooldown(self):
        c = cfg()
        ms.run_scout("k", c, ["gemini-3.7-flash"], probe_fn=lambda k, m: {"ok": True, "reason": "ok"},
                     trial_fn=lambda k, m: {"ok": False, "reason": "quality: desk_words 90 < 250", "checks": {}}, now=NOW)
        self.assertEqual(utils.resolve_model_order(c)[0], "gemini-2.5-flash")
        self.assertIn("quality", c["rejected"]["gemini-3.7-flash"]["reason"])
        self.assertEqual(c["rejected"]["gemini-3.7-flash"]["retry_after"], "2026-12-11T00:00:00Z")
    def test_leader_demoted_when_it_stops_working(self):
        c = cfg(qualified={"gemini-3.7-flash": {"at": "x"}})
        ms.run_scout("k", c, [], probe_fn=lambda k, m: {"ok": False, "reason": "429"}, trial_fn=self.passing_trial, now=NOW)
        self.assertEqual(utils.resolve_model_order(c)[0], "gemini-2.5-flash")
        self.assertIn("gemini-3.7-flash", c["rejected"])
    def test_no_candidates_no_calls(self):
        c = cfg(); calls = []
        ms.run_scout("k", c, ["gemini-2.5-flash"], probe_fn=lambda k, m: calls.append(m), trial_fn=self.passing_trial, now=NOW)
        self.assertEqual(calls, [])
    def test_pinned_overrides_but_only_proven(self):
        c = cfg(qualified={"gemini-3.7-flash": {}}, mode="pinned", pinned="gemini-2.5-flash-lite")
        self.assertEqual(utils.resolve_model_order(c)[0], "gemini-2.5-flash-lite")
        c["pinned"] = "gemini-9-unproven"
        self.assertEqual(utils.resolve_model_order(c)[0], "gemini-3.7-flash")


DESK = " ".join(["Most executives will read this as a procurement question, and that is the first mistake."] * 4 +
                ["The people who should be in the room are legal counsel and the chief risk officer, because the exposure is contractual."] * 8 +
                ["A practical test for this month is to ask who signs off when a vendor changes its model under you."] * 6)
GOOD_ISSUE = f"""HEADLINE
Canadian Firms Face New AI Contract Questions This Month

INTRODUCTION
Three things happened in October that change how Canadian leaders buy AI. Vendors moved faster than procurement. Regulators started asking harder questions.

EXECUTIVE SUMMARY
1. Vendor model changes now carry contract risk for Canadian firms.
2. Ottawa money is flowing to domestic compute, with strings attached.
3. Adoption is rising faster in mid-market firms than in large banks.

KEY AI DEVELOPMENTS
October 3: Google — Released a new enterprise model tier for Workspace customers. Canadian financial firms can deploy it inside existing contracts. STRATEGIC READ: Most firms route this to IT, yet it is a data residency question for Legal and Risk to own. The firms that act first get leverage in renewals. IMPORTANCE: High. HORIZON: Now. ATTENTION: Yes. Source: Reuters | Google adds enterprise model tier for Workspace
October 9: Microsoft — Announced agent controls inside its copilot admin console. Canadian retailers gain audit logs for agent actions. STRATEGIC READ: Governance teams finally get a lever, but only if someone is told it exists. Expect most firms to miss it for a quarter. IMPORTANCE: Medium. HORIZON: 3 Months. ATTENTION: Yes. Source: The Verge | Microsoft ships agent controls for copilot
October 14: OpenAI — Cut API pricing for its mid-tier model by thirty percent. Canadian startups see lower inference costs immediately. STRATEGIC READ: Cheaper calls tempt teams to scale pilots without governance. The cost saving is real; the control gap is the risk. IMPORTANCE: Medium. HORIZON: Now. ATTENTION: Monitor. Source: Bloomberg | OpenAI lowers API prices again
October 18: Anthropic — Opened a Toronto office for enterprise support teams.
October 22: Cohere — Released a private deployment option for regulated industries.
October 27: Mistral — Published an open-weight model aimed at European banks.

CANADIAN SPOTLIGHT
Government of Canada: Announced a new fund for sovereign compute access for small firms. Mid-market manufacturers can apply from January. Source: ISED | Sovereign compute access fund opens
Royal Bank of Canada: Expanded its internal assistant to all branch staff. Frontline advisers get faster answers on policy questions. Source: Globe and Mail | RBC expands AI assistant to branches
Shopify: Released new merchant tools built on agent workflows. Canadian retailers can automate returns handling. Source: Shopify | Shopify launches agent workflow tools

FROM ROBERTS DESK
{DESK}

STRATEGIC ACTIONS FOR THIS MONTH
1. Audit every vendor contract for model change clauses before renewal. OWNER: General Counsel — because the risk is contractual, not technical, and the CIO will not read the fine print. PRIORITY: High. EFFORT: Medium. IMPACT: High.
2. Ask procurement for a list of AI features switched on by default across all suites. OWNER: Chief Risk Officer — because exposure sits in risk registers, not in IT tickets. PRIORITY: High. EFFORT: Small. IMPACT: Medium.
3. Brief the board audit committee on the sovereign compute fund deadline. OWNER: CFO — because the money has an application window and a matching cost. PRIORITY: Medium. EFFORT: Small. IMPACT: Medium.
4. Pilot agent audit logs with one governed workflow before expanding. OWNER: Head of Data Governance — because logging only matters if someone reads it. PRIORITY: Medium. EFFORT: Medium. IMPACT: Medium.
5. Set a price review trigger for the OpenAI pricing change. OWNER: VP Operations — because the saving lands in operating budgets. PRIORITY: Low. EFFORT: Small. IMPACT: Low.

ADOPTION SNAPSHOT
30% of Canadian businesses have adopted AI in at least one function. Source: BDC, 2025.
46% of employed Canadians say AI has impacted their career trajectory. Source: Borderless AI, 2026.
Global: 70% of organizations have an AI strategy in place. Source: McKinsey, 2025.
12% of small firms report a formal AI policy. Source: CIRA, 2025.
21% of Canadian firms plan to raise AI spending next year. Source: Deloitte Canada, 2025.

LOOKING AHEAD: THREE PREDICTIONS
One month: Expect at least one large vendor to announce a contract term change tied to model updates.
Six months: Mid-market firms will outpace banks in agent deployments because their approval paths are shorter.
One year: A Canadian regulator will publish expectations for vendor model change notices.

ONE QUESTION FOR YOUR LEADERSHIP TEAM
Who in your organization is told, in writing, when a vendor changes the model behind a tool you rely on?
"""

class Quality(unittest.TestCase):
    def test_well_formed_issue_passes(self):
        passed, checks, failures = ms.score_issue(GOOD_ISSUE)
        self.assertTrue(passed, (checks, failures))
    def test_thin_desk_and_truncation_fail(self):
        thin = GOOD_ISSUE.replace(DESK, 'Too short.')
        passed, checks, failures = ms.score_issue(thin)
        self.assertFalse(passed); self.assertTrue(any('desk_words' in f for f in failures))
        truncated = GOOD_ISSUE.split('STRATEGIC ACTIONS FOR THIS MONTH')[0]
        self.assertFalse(ms.score_issue(truncated)[0])

    def test_empty_issue_fails(self):
        passed, checks, failures = ms.score_issue("just some text without sections")
        self.assertFalse(passed); self.assertTrue(failures)

if __name__ == "__main__":
    unittest.main(verbosity=1)
