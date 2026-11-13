#!/usr/bin/env python3
"""
plan_research.py
Research step for the "New in Your AI Subscription" section (issues from
December 2026 on).

WHY THIS EXISTS. Asked in one request for a whole issue, the model reported real
plan changes but cited them to whatever page its search happened to surface:
resellers, agencies, training companies. The source allowlist deleted them, and
three trial issues kept 0, 2 and 1 of six items. Telling it which sources to use
did not help, because the source name is text the model types.

WHAT IT DOES. One small search-grounded request PER VENDOR ("what changed in
ChatGPT plans in <month>?"). Each finding is kept only if Google's own grounding
record for that request shows the search landed on the vendor's site or on a
major outlet. The Source shown on the page then comes from that record, not from
the model. The verified findings are handed to the issue prompt as the only
plan changes it may report.

Run by generate-blog.py before the main request. Standalone, for a look at what
the search returns (prints everything, changes nothing):
    python3 scripts/plan_research.py --month October --year 2026
"""
import argparse
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# name: what the reader calls it. own: domains that are the vendor's own newsroom,
# blog or dated release notes, mapped to the Source name printed on the page.
VENDORS = [
    {"name": "OpenAI", "product": "ChatGPT",
     "plans": "ChatGPT Plus, ChatGPT Business (formerly Team), ChatGPT Go",
     "own": {"openai.com": "OpenAI", "help.openai.com": "OpenAI Release Notes",
             "chatgpt.com": "OpenAI"},
     "pages": ["https://help.openai.com/en/articles/6825453-chatgpt-release-notes"],
     "hints": ["OpenAI ChatGPT release notes {month_year}", "help.openai.com ChatGPT release notes",
               "openai.com news ChatGPT {month_year}"]},
    {"name": "Anthropic", "product": "Claude",
     "plans": "Claude Pro, Claude Max, Claude Team",
     "own": {"anthropic.com": "Anthropic", "claude.com": "Anthropic",
             "claude.ai": "Anthropic", "support.anthropic.com": "Anthropic Release Notes",
             "support.claude.com": "Anthropic Release Notes"},
     "pages": ["https://support.claude.com/en/articles/12138966-release-notes"],
     "hints": ["Claude release notes {month_year} support.claude.com", "anthropic.com news Claude {month_year}",
               "claude.com blog {month_year}"]},
    {"name": "Google", "product": "Gemini",
     "plans": "Google AI Pro, Gemini in Google Workspace (Business plans)",
     "own": {"blog.google": "Google", "googleblog.com": "Google Workspace Updates",
             "gemini.google": "Google Gemini Release Notes",
             "workspace.google.com": "Google Workspace",
             "gemini.google.com": "Google", "support.google.com": "Google Release Notes",
             "google.com": "Google"},
     "pages": ["https://gemini.google/release-notes/", "https://workspaceupdates.googleblog.com/"],
     "hints": ["Google Workspace Updates blog Gemini {month_year}", "workspaceupdates.googleblog.com Gemini weekly recap {month_year}",
               "blog.google Gemini app new features {month_year}", "Gemini Drop {month_year} blog.google"]},
    {"name": "Microsoft", "product": "Microsoft 365 Copilot",
     "plans": "Microsoft 365 Copilot for business, Copilot in Microsoft 365 Personal and Family, Copilot Pro",
     "own": {"microsoft.com": "Microsoft", "techcommunity.microsoft.com": "Microsoft Tech Community",
             "learn.microsoft.com": "Microsoft 365 Copilot Release Notes",
             "blogs.microsoft.com": "Microsoft", "support.microsoft.com": "Microsoft Release Notes"},
     "pages": ["https://learn.microsoft.com/en-us/microsoft-365/copilot/release-notes?tabs=all"],
     "hints": ["What's new in Microsoft 365 Copilot {month_year} techcommunity.microsoft.com",
               "Microsoft 365 Blog Copilot {month_year}", "Microsoft 365 Copilot release notes {month_year} learn.microsoft.com"]},
]

# Outlets that report product news. Domain -> the name the allowlist knows.
OUTLETS = {
    "theverge.com": "The Verge", "techcrunch.com": "TechCrunch", "arstechnica.com": "Ars Technica",
    "wired.com": "Wired", "cnbc.com": "CNBC", "reuters.com": "Reuters", "bloomberg.com": "Bloomberg",
    "axios.com": "Axios", "theregister.com": "The Register", "businessinsider.com": "Business Insider",
    "betakit.com": "BetaKit", "thelogic.co": "The Logic", "theglobeandmail.com": "Globe and Mail",
    "financialpost.com": "Financial Post", "cbc.ca": "CBC", "zdnet.com": "ZDNet",
    "engadget.com": "Engadget", "venturebeat.com": "VentureBeat", "9to5google.com": "9to5Google",
    "9to5mac.com": "9to5Mac", "macrumors.com": "MacRumors", "pcmag.com": "PCMag",
    "cnet.com": "CNET", "theinformation.com": "The Information", "forbes.com": "Forbes",
    "wsj.com": "Wall Street Journal", "nytimes.com": "New York Times", "ft.com": "Financial Times",
    "bbc.com": "BBC", "bbc.co.uk": "BBC", "apnews.com": "AP", "computerworld.com": "Computerworld",
    "tomsguide.com": "Tom's Guide", "androidauthority.com": "Android Authority",
    "windowscentral.com": "Windows Central", "itworldcanada.com": "IT World Canada",
}

MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]


def _domain(title_or_uri):
    """Grounding chunks carry the site as their title ("openai.com"); the uri is
    a Google redirect. Fall back to the uri host only when the title is not a host."""
    t = (title_or_uri or "").strip().lower()
    t = re.sub(r"^https?://", "", t).split("/")[0]
    t = re.sub(r"^www\.", "", t)
    return t if re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", t) else ""


def _lookup(domain, table):
    """Longest suffix match, so help.openai.com beats openai.com."""
    best = None
    for d, name in table.items():
        if domain == d or domain.endswith("." + d):
            if best is None or len(d) > len(best[0]):
                best = (d, name)
    return best[1] if best else None


def classify(domain, vendor):
    """('own'|'outlet'|None, Source name)."""
    name = _lookup(domain, vendor["own"])
    if name:
        return "own", name
    name = _lookup(domain, OUTLETS)
    if name:
        return "outlet", name
    return None, None


def build_prompt(vendor, month_year, today_str, pages=False):
    hints = "\n".join(f'  - "{h.format(month_year=month_year)}"' for h in vendor.get("hints", []))
    if pages:
        urls = "\n".join(f"  - {u}" for u in vendor.get("pages", []))
        lead = f"""Read these pages first. They are {vendor['name']}'s own dated release notes:
{urls}
Take the entries dated in {month_year} from them. Then use Google Search only to fill gaps, on {vendor['name']}'s own sites or major technology outlets.
"""
    else:
        lead = f"""Run these searches (and others like them) so that you are reading {vendor['name']}'s own pages:
{hints}
"""
    return f"""Use Google Search. Today is {today_str}.

{lead}
List the changes {vendor['name']} announced in {month_year} to {vendor['product']} on its low-cost paid plans ({vendor['plans']}): new features, new connections to other tools (email, calendar, files, spreadsheets, accounting, e-commerce), changes to usage limits or price, and availability in Canada.

Search {vendor['name']}'s own site first (its news or blog, and its dated release notes), then major technology outlets (The Verge, TechCrunch, Ars Technica, CNBC, Reuters). Ignore resellers, agencies, consultancies, training companies and personal blogs.

Rules:
- Only changes announced in {month_year}. Nothing earlier, nothing after {today_str}. If you are not sure of the day, leave the item out.
- Only things a non-technical owner of a small business could use. No API-only, developer-only or enterprise-only changes, no research papers, no funding news.
- State the plan or tier ONLY if the page you found states it; otherwise write "not stated".
- If you find nothing that qualifies, reply with the single line: NONE

Reply with one line per change, most useful to a small business first, at most 5 lines, in EXACTLY this form and nothing else:
CHANGE | [Month Day] | [product and plan, or "not stated"] | [what changed, one plain sentence] | [name of the site you read it on] | [exact title of that page]"""


def _tokens(s):
    return set(re.findall(r"[a-z0-9]{4,}", (s or "").lower()))


def _supporting_domains(line, grounding):
    """Domains of the pages Google says support this line of the answer."""
    lt = _tokens(line)
    out = []
    for sp in grounding.get("supports") or []:
        st = _tokens(sp.get("text"))
        if not st or not lt:
            continue
        if len(st & lt) / max(1, min(len(st), len(lt))) >= 0.6:
            for i in sp.get("chunks") or []:
                ch = (grounding.get("chunks") or [])
                if 0 <= i < len(ch):
                    d = _domain(ch[i].get("title")) or _domain(ch[i].get("uri"))
                    if d and d not in out:
                        out.append(d)
    return out


def parse_findings(text, vendor, grounding, month_year, today=None, log=print):
    month = month_year.split()[0]
    call_domains = []
    for u in grounding.get("urls") or []:  # pages the model really fetched
        d = _domain(u.get("url")) if u.get("ok") else ""
        if d and d not in call_domains:
            call_domains.append(d)
    for ch in grounding.get("chunks") or []:
        d = _domain(ch.get("title")) or _domain(ch.get("uri"))
        if d and d not in call_domains:
            call_domains.append(d)
    kept = []
    seen_any = False
    for raw in (text or "").splitlines():
        # Tolerate markdown, numbering and [brackets] copied from the template.
        line = re.sub(r"^[\s\-\*\d\.\)\u2022`>#]+", "", raw).replace("**", "").strip()
        if not line.upper().startswith("CHANGE"):
            continue
        seen_any = True
        parts = [p.strip().strip("[]").strip() for p in line.split("|")]
        if len(parts) < 4 or not parts[3]:
            log(f"    skipped (wrong shape, {len(parts)} fields): {line[:160]}")
            continue
        # The site and page title are optional: neither is trusted anyway, the
        # source comes from the search record below.
        parts += ["", ""]
        _, date, plan, what, stated_site, title = parts[:6]
        if "what changed" in what.lower() and "sentence" in what.lower():
            continue  # the model echoed the template line
        m = re.match(r"(%s)\s+(\d{1,2})\b" % "|".join(MONTHS), date)
        if not m or m.group(1) != month:
            log(f"    skipped (date '{date}' is not a day in {month}): {what[:70]}")
            continue
        if today is not None:
            try:
                if datetime(int(month_year.split()[1]), MONTHS.index(month) + 1, int(m.group(2))) > today:
                    log(f"    skipped (dated after today): {what[:70]}")
                    continue
            except ValueError:
                log(f"    skipped (impossible date '{date}'): {what[:70]}")
                continue
        # Where did the search really land for THIS line? Vendor's own site wins.
        doms = _supporting_domains(line, grounding)
        how = "line"
        if not doms:
            doms, how = call_domains, "call"
        source = None
        for want in ("own", "outlet"):
            for d in doms:
                kind, name = classify(d, vendor)
                if kind == want:
                    source = (name, d, kind)
                    break
            if source:
                break
        if not source:
            log(f"    REJECTED (search landed on {', '.join(doms) or 'nothing'}; model said '{stated_site}'): {what[:70]}")
            continue
        # The page title the model typed belongs to whatever page it was reading,
        # which is often not the one the search record points to. Keep it only
        # when the site it named is the source being credited; otherwise use a
        # plain description, which is what the "search for this article" link needs.
        same_site = _tokens(stated_site) & _tokens(source[0] + " " + source[1])
        if not same_site or not title:
            title = f"{vendor['product']}: {what.rstrip('.')}"[:110]
        kept.append({"vendor": vendor["name"], "product": vendor["product"], "date": f"{m.group(1)} {int(m.group(2))}",
                     "plan": plan, "what": what, "source": source[0], "domain": source[1],
                     "source_kind": source[2], "matched": how, "title": title})
        log(f"    KEPT [{source[0]} via {source[1]}, {how}-level]: {date}: {what[:80]}")
    if not seen_any:
        log(f"    no CHANGE lines in the reply. It began: {(text or '').strip()[:300]!r}")
    return kept


def research_plan_changes(api_key, month_year, today=None, log=print, call=None):
    """Returns a list of verified findings (possibly empty). Never raises for a
    single vendor failing: the issue can still be written from the others."""
    if call is None:
        from gemini import _call_gemini as call
    today = today or datetime.now()
    today_str = today.strftime("%B %d, %Y")
    findings = []
    for v in VENDORS:
        log(f"PLAN RESEARCH: {v['name']} ({v['product']})")
        got = []
        # First the vendor's own release-notes pages (the model fetches them and
        # the response records that it did); if that yields nothing, a plain
        # search of the vendor's sites and the outlets.
        for label, use_pages in (("release-notes pages", True), ("search only", False)):
            if use_pages and not v.get("pages"):
                continue
            try:
                res = call(api_key, build_prompt(v, month_year, today_str, pages=use_pages), max_output_tokens=4096,
                           temperature=0.2, use_search=True, min_chars=4, require_grounding=True,
                           read_urls=use_pages)
            except Exception as e:  # one vendor or one method down must not stop the issue
                log(f"    {label}: request failed: {str(e)[:160]}")
                continue
            g = res.get("grounding") or {}
            doms = []
            for ch in g.get("chunks") or []:
                d = _domain(ch.get("title")) or _domain(ch.get("uri"))
                if d and d not in doms:
                    doms.append(d)
            read = [u["url"] for u in (g.get("urls") or []) if u.get("ok")]
            log(f"    {label}: search landed on {', '.join(doms) or '(nothing)'}; "
                f"pages read: {', '.join(read) or '(none)'}; {len(g.get('supports') or [])} supported passage(s)")
            got = parse_findings(res.get("content") or "", v, g, month_year, today, log)
            if got:
                break
            log(f"    {label}: nothing verified for {v['name']}")
        findings += got
    findings = tidy(findings)
    by = {}
    for f in findings:
        by.setdefault(f["vendor"], 0)
        by[f["vendor"]] += 1
    log(f"PLAN RESEARCH RESULT: {len(findings)} verified change(s) "
        f"({', '.join(f'{k} {n}' for k, n in by.items()) or 'none'}).")
    return findings


def tidy(findings, per_vendor=3):
    """Drop citation markers, fragments and repeats; keep the best-evidenced
    three per vendor (a line Google tied to the vendor's page outranks one that
    only shares the request with it)."""
    out, seen, count = [], set(), {}
    order = sorted(findings, key=lambda f: (0 if f["matched"] == "line" else 1, 0 if f["source_kind"] == "own" else 1))
    for f in order:
        what = re.sub(r"\[cite[^\]]*\]?", "", f["what"]).strip()
        what = re.sub(r"\s+", " ", what).strip(" |")
        if len(what.split()) < 6:
            continue
        key = (f["vendor"], re.sub(r"[^a-z0-9]", "", what.lower())[:50])
        if key in seen or count.get(f["vendor"], 0) >= per_vendor:
            continue
        seen.add(key)
        count[f["vendor"]] = count.get(f["vendor"], 0) + 1
        g = dict(f, what=what, title=re.sub(r"\[cite[^\]]*\]?", "", f["title"]).strip(" |") or f["product"])
        out.append(g)
    # Back in vendor order so no vendor crowds the top of the list.
    out.sort(key=lambda f: [v["name"] for v in VENDORS].index(f["vendor"]))
    return out


def prompt_block(findings, month_year):
    """Text added to the issue prompt. Empty string when nothing was verified,
    which leaves the prompt exactly as it was."""
    if not findings:
        return ""
    lines = [f"{i+1}. {f['date']} | {f['vendor']} | {f['product']} ({f['plan']}) | {f['what']} | Source: {f['source']} | {f['title']}"
             for i, f in enumerate(findings)]
    return f"""
VERIFIED PLAN CHANGES FOR {month_year.upper()} — researched separately, one vendor at a time, and
each one checked against the page the search actually landed on. For KEY AI DEVELOPMENTS:
- Every item about ChatGPT, Claude, Gemini or Microsoft 365 Copilot MUST be one of these. Do not
  add any other change to those four products, however sure you are of it: it will be deleted.
- Use between 4 and 6 of them when that many are listed (all of them when fewer), choosing the
  most useful to a small business, and keep the three most useful first.
- Copy the date, the company and the text after "Source:" EXACTLY as written here, as the item's
  date, [Company] and Source line (Source: [name] | [title]).
- Rewrite the description in your own words to fit the format; add nothing the line does not say
  about plan, price or Canadian availability.
- If fewer than 4 are listed, fill the remaining slots (up to 5 in total) with other AI company
  news that meets the source rules below.
- Build the HEADLINE from one of these.

""" + "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", required=True)
    ap.add_argument("--year", required=True)
    a = ap.parse_args()
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        print("GEMINI_API_KEY is not set."); return 1
    my = f"{a.month} {a.year}"
    f = research_plan_changes(key, my)
    print("\n----- block that would be added to the issue prompt -----")
    print(prompt_block(f, my) or "(nothing verified: the prompt would be unchanged)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
