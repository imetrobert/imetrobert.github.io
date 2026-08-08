"""
renderer.py
Builds the HTML blog post from parsed content sections.
"""

import re
import json
from datetime import datetime
from html import escape as escape_html
from urllib.parse import quote
from utils import clean_filename, estimate_reading_time, get_issue_number, get_issue_labels
from utils import (BRAND, BRAND_SHORT, BRAND_TAGLINE, AUTHOR,
                   is_government_entity, is_recognised_publication, is_newswire,
                   uses_stock_phrase)
from parser import (
    _resolve_item_date,
    parse_sections, parse_list_items, parse_developments, parse_spotlight_items,
    parse_adoption_stats, deduplicate_spotlight_against_developments,
    parse_actions, parse_predictions, parse_question,
)


def create_html_blog_post(content, title, excerpt, coverage_date=None, is_draft=False):
    current_date   = datetime.now()
    formatted_date = current_date.strftime("%B %d, %Y")
    iso_date       = current_date.strftime("%Y-%m-%d")

    # issue_month_year = the label readers see (never looks stale).
    # coverage_month_year/name = the month the actual news is from.
    # coverage_date lets a regeneration stay locked to the ORIGINAL month
    # being reported on, even if it's run days later — see
    # utils.get_issue_labels() for the full story.
    labels               = get_issue_labels(coverage_date or current_date)
    issue_month_year     = labels["issue_month_year"]
    coverage_month_year  = labels["coverage_month_year"]
    coverage_month_name  = labels["coverage_month_name"]
    issue_badge_text     = labels["issue_badge_text"]

    # Pass the ISSUE date (not real "now") so regenerating a couple days
    # after the calendar rolls over doesn't bump the issue number.
    issue_num      = get_issue_number(labels["issue_date"])
    reading_time   = estimate_reading_time(content)
    word_count     = len(re.sub(r'\s+', ' ', content).split())

    clean_title = re.sub(r'^[#\*\s]+', '', title).strip() or f"{BRAND} \u2014 {issue_month_year}"
    slug        = clean_filename(clean_title)
    canonical   = f"https://www.imetrobert.com/blog/posts/{iso_date}-{slug}.html"
    # Per-issue social card. Falls back to the static one rather than risking a
    # 404 og:image if Pillow or the fonts are unavailable in the runner.
    og_image    = "https://www.imetrobert.com/blog/og-blog.jpg"
    og_alt      = f"{BRAND} \u2014 {issue_month_year} issue by {AUTHOR}"
    try:
        import os as _os
        from og_image import build_og_image
        _root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
        _rel  = f"blog/og/{iso_date}-{slug}.jpg"
        build_og_image(_os.path.join(_root, _rel), issue_month_year)
        og_image = f"https://www.imetrobert.com/{_rel}"
    except Exception as _e:
        print(f"  OG image generation unavailable ({_e}); using the static card")
    # Drafts sitting in blog/staging/ must never be indexable — the URL
    # differs from the eventual blog/posts/ URL, so a crawler that found a
    # draft before approval would leave a stale, permanent entry in search
    # results with no path to ever clean it up. Canonical still points to
    # the eventual published URL either way (see `canonical` above).
    robots_meta = (
        "noindex, nofollow"
        if is_draft else
        "index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1"
    )

    meta_desc = re.sub(r'\s+', ' ', excerpt).strip()
    if len(meta_desc) > 155:
        truncated = meta_desc[:152]
        if ' ' in truncated:
            truncated = truncated[:truncated.rfind(' ')]
        meta_desc = truncated.rstrip('.,;:- ') + '...'

    # Raw (unescaped) versions go into JSON-LD via json.dumps, which does its
    # own string escaping. HTML-escaped versions go everywhere else — meta
    # tag attributes and text nodes — so a quote or ampersand in the
    # AI-generated excerpt/title (e.g. a quoted strategy name) can't truncate
    # or corrupt the surrounding markup.
    meta_desc_html    = escape_html(meta_desc, quote=True)
    clean_title_html  = escape_html(clean_title, quote=True)
    excerpt_html      = escape_html(re.sub(r'\s+', ' ', excerpt).strip(), quote=True)
    # Topic first: the front of the title carries the most retrieval weight, and
    # it is what survives truncation in a SERP. Month second for freshness and
    # issue identity, brand last.
    seo_title         = f"{clean_title_html} | {BRAND_SHORT}, {issue_month_year} | {AUTHOR}"

    sections = parse_sections(content)

    intro_text      = sections.get("INTRODUCTION", "")
    canadian_spot   = sections.get("CANADIAN SPOTLIGHT", "")
    roberts_raw     = sections.get("FROM ROBERTS DESK", "")
    adoption_raw    = sections.get("ADOPTION SNAPSHOT", "")

    # Coverage date resolves the year on a bare "August 12" so the parser can
    # tell a past item from a forward-dated one. See _drop_future_dated.
    developments    = parse_developments(
        sections.get("KEY AI DEVELOPMENTS", ""), coverage_date or current_date
    )
    spotlight_items = parse_spotlight_items(canadian_spot)
    spotlight_items = deduplicate_spotlight_against_developments(spotlight_items, developments)
    actions         = parse_actions(sections.get("STRATEGIC ACTIONS FOR THIS MONTH", ""))
    adoption        = parse_adoption_stats(adoption_raw)
    summary_points  = parse_list_items(sections.get("EXECUTIVE SUMMARY", ""), min_length=25)[:3]
    predictions     = parse_predictions(sections.get("LOOKING AHEAD: THREE PREDICTIONS", ""))
    closing_question = parse_question(sections.get("ONE QUESTION FOR YOUR LEADERSHIP TEAM", ""))

    # Action bodies are what the FAQ quotes; they should never
    # carry the OWNER/PRIORITY labels into prose meant to be read as a sentence.
    action_bodies   = [a["body"] for a in actions]

    print(f"  Parsed: {len(developments)} developments, {len(spotlight_items)} spotlight, "
          f"{len(actions)} actions, {len(adoption)} stats, {len(summary_points)} summary points, "
          f"{len(predictions)} predictions, "
          f"question={'yes' if closing_question else 'no'}")
    # A section the model simply did not write is invisible: the parser returns
    # "" and the renderer skips the block, so the page looks intentional. The
    # closing question went missing from a real issue this way. Name anything
    # that came back empty, so a reviewer sees it in the log before publishing.
    _expected = {
        "Executive Summary":  summary_points,
        "Key AI Developments": developments,
        "Canadian Spotlight":  spotlight_items,
        "From Robert's Desk":  roberts_raw.strip(),
        "Strategic Actions":   actions,
        "Adoption Snapshot":   adoption,
        "Looking Ahead":       predictions,
        "One Question":        closing_question,
    }
    _missing = [name for name, value in _expected.items() if not value]
    # "AI MYTH OF THE MONTH" is intentionally absent from _expected: the header
    # is still a parse boundary (see SECTION_HEADERS) but the section is retired.
    if _missing:
        print(f"  MISSING SECTIONS: {', '.join(_missing)}. These will not appear on "
              f"the page at all. Check the model's raw output for the header — a "
              f"section it never wrote, and a header it misspelled, look identical here.")

    if len(spotlight_items) < 3:
        print(f"  NOTE: only {len(spotlight_items)} Canadian Spotlight items; the issue asks for 3.")

    # The headline is written by the model from the stories it drafted, but the
    # date, source-quality and dedup filters run afterwards — so a dropped story
    # can leave the title promising something the page never delivers. That is
    # not hypothetical: one issue was titled for a $700M compute commitment that
    # appeared nowhere in it, and another led with "new consortia" after the
    # consortium story was dropped for its source. The reader sees the title
    # first, so a dangling one reads as a broken page.
    # Two haystacks, because "missing" has two meanings. The reported items are
    # what the headline is supposed to be drawn FROM; the full prose is where a
    # reader could still find the story. Checking only the reported items cried
    # wolf on a real issue — the headline read "Ottawa expands the AI Compute
    # Access Fund" and the story was in the introduction and the Desk, so it
    # was present on the page and flagged anyway.
    _reported_text = " ".join(
        [(_d.get("company", "") + " " + _d.get("body", "")) for _d in developments]
        + [(_s.get("org", "") + " " + _s.get("body", "")) for _s in spotlight_items]
    ).lower()
    _body_text = " ".join(
        [_reported_text]
        + [_a.get("body", "") for _a in actions]
        + [_st.get("body", "") for _st in adoption]
        + [sections.get("INTRODUCTION", ""), roberts_raw]
        + summary_points
        + [_p.get("body", "") if isinstance(_p, dict) else str(_p) for _p in predictions]
        + [closing_question or ""]
    ).lower()
    # Only distinctive terms: capitalised words the title leans on, minus the
    # vocabulary every issue uses. A generic word missing from the body means
    # nothing; "Manulife" missing means the story it named is gone.
    _title_stop = {
        "ai", "the", "and", "for", "with", "new", "canada", "canadian", "canadas",
        "business", "businesses", "leaders", "month", "this", "how", "what", "why",
        "amid", "into", "from", "as", "at", "on", "in", "of", "to", "a",
    }
    _title_terms = {
        w.strip(",.:;'’\"").lower()
        for w in re.findall(r"\b[A-Z][A-Za-z0-9&.\-]{2,}\b", clean_title)
    }
    _terms = [t for t in _title_terms if t and t not in _title_stop]
    # Warn only when NOTHING in the headline is anchored — not when one term is
    # phrased differently. Requiring every term to appear cried wolf on a real
    # issue: the headline said "…$700M for SMEs", the intro said "small and
    # medium businesses", and a correct headline was flagged over a synonym.
    # One match is enough to prove the headline belongs to this issue.
    _anywhere  = [t for t in _terms if t in _body_text]
    _reported  = [t for t in _terms if t in _reported_text]
    if _terms and developments and not _anywhere:
        print(f"  TITLE MISMATCH: the headline names {', '.join(sorted(_terms))}, none of "
              f"which appears anywhere in the issue. A story the headline was written for "
              f"was most likely dropped by the date or source-quality filters above — "
              f"retitle or regenerate rather than publish a title the page does not deliver.")
    elif _terms and developments and not _reported:
        # Weaker, and a different problem: the story is on the page, but only in
        # commentary. The headline promises reporting the issue never actually does.
        print(f"  TITLE NOT REPORTED: the headline names {', '.join(sorted(_terms))}, which "
              f"appears only in the introduction or commentary — no development or spotlight "
              f"item covers it. Usually means the story it was written for was dropped above, "
              f"leaving the headline on something the issue only mentions in passing.")

    # Spotlight items sometimes carry a date. The future-date filter only looks
    # forward, so an item from a PRIOR month — which the prompt forbids — passes
    # silently. Not dropped: with three items, removing one guts the section,
    # and only a human can judge whether a late-breaking item is worth keeping.
    _cov = (coverage_date or current_date)
    for _item in spotlight_items:
        _d = _item.get("date", "")
        _resolved = _resolve_item_date(_d, _cov) if _d else None
        if _resolved and (_resolved.year, _resolved.month) != (_cov.year, _cov.month):
            print(f"  PRIOR-MONTH SPOTLIGHT: '{_item.get('org') or _d}' is dated {_d}, but this "
                  f"issue covers {_cov:%B %Y}. The prompt bans prior-month items — check it.")

    # Every citation in one place, so a source that should not be here is a
    # single line to scan instead of a scroll through the page. Anything not a
    # known outlet, not the subject's own newsroom, and not a government body
    # is called out separately — that is the shape "Signal49 Research" and
    # "CanadianAI" took, and no blocklist pattern could have caught either.
    _sources, _unverified = [], []
    for _group in (developments, spotlight_items, adoption):
        for _i in _group:
            _n = (_i.get("source_name") or "").strip()
            if not _n or _n in _sources:
                continue
            _sources.append(_n)
            _subject = (_i.get("company") or _i.get("org") or "").lower()
            _first_party = bool(_subject) and (
                _n.lower() in _subject or _subject.split()[0] in _n.lower()
            )
            if not (is_recognised_publication(_n) or _first_party
                    or is_government_entity(_n) or is_newswire(_n)):
                _unverified.append(_n)
    if _sources:
        print(f"  SOURCES CITED ({len(_sources)}): {', '.join(_sources)}")

    # Concentration, not just presence. One run cited the same unrecognised site
    # for three of five stories and its own subject for a fourth, so no story
    # rested on independent reporting — a fact the per-source list stated only
    # by implication.
    _independent = _firstparty = _unknown = _wire = 0
    for _d in developments:
        _n = (_d.get("source_name") or "").strip()
        _subj = (_d.get("company") or "").lower()
        if not _n:
            _unknown += 1
        elif _subj and (_n.lower() in _subj or _subj.split()[0] in _n.lower()):
            _firstparty += 1
        # Before the publication check: a wire release is the company's own
        # announcement carried for a fee, so counting it as independent would
        # let a month of pure corporate PR report itself as independently
        # sourced — exactly what this tally exists to expose.
        elif is_newswire(_n):
            _firstparty += 1
            _wire += 1
        elif is_recognised_publication(_n) or is_government_entity(_n):
            _independent += 1
        else:
            _unknown += 1
    if developments:
        _wire_note = f" ({_wire} via a press-release wire)" if _wire else ""
        print(f"  SOURCING: {len(developments)} developments — {_independent} independent, "
              f"{_firstparty} first-party{_wire_note}, {_unknown} unverified.")
        if _independent < 2:
            print(f"  WEAK SOURCING: only {_independent} development(s) rest on an independent "
                  f"publication. The month's reporting is effectively unsourced — regenerate "
                  f"rather than publish.")
    if _unverified:
        print(f"  UNRECOGNISED SOURCES ({len(_unverified)}): {', '.join(_unverified)}. "
              f"Not a known outlet, not the subject's own newsroom, not a government body. "
              f"Verify each is a real publication before publishing.")

    # The Desk is the one section sold as Robert's own voice, so a phrase the
    # prompt handed it is the last thing that should survive into print.
    _stock = uses_stock_phrase(roberts_raw)
    if _stock:
        print(f"  STOCK PHRASING IN THE DESK: {'; '.join(repr(p) for p in _stock)}. "
              f"These came from the prompt and have appeared in past issues — "
              f"rewrite the opening in the preview page.")

    if len(developments) < 4:
        print(f"  WARNING: only {len(developments)} developments survived parsing. "
              f"The issue asks for 5-6, so this one will read thin. Check the log "
              f"above for future-dated items removed on a mid-month run.")
    desk_words = len(roberts_raw.split())
    if desk_words < 200:
        print(f"  NOTE: From Robert's Desk is only {desk_words} words — the signature "
              f"section is meant to run 300-450. Consider rewriting it in the preview page.")

    article_parts = []

    if intro_text:
        article_parts.append(
            f'<div class="section intro-section">'
            f'<p class="intro-lead">{intro_text}</p>'
            f'</div>'
        )

    if summary_points:
        article_parts.append(_build_summary_section(summary_points))

    if developments:
        # Two tiers. A development the model rated is a major story and gets the
        # full treatment; the rest are the log. The split is driven by whether
        # the ratings are actually present, so a month where the model rates
        # nothing degrades to the old flat list instead of rendering empty
        # badge rows.
        major   = [d for d in developments if d.get("strategic_read") or d.get("importance")]
        minor   = [d for d in developments if d not in major]
        dev_cards = ""

        for d in major:
            date_html    = f'<span class="dev-date">{d["date"]}</span>' if d["date"] else ""
            company_html = f'<div class="dev-company">{d["company"]}</div>' if d["company"] else ""
            dev_cards += (
                f'<div class="dev-card dev-card-major">'
                f'  <div class="dev-header">{date_html}{company_html}'
                f'<span class="dev-tier">Major story</span></div>'
                f'  <p class="dev-body">{d["body"]}</p>'
                f'  {_build_strategic_read(d)}'
                f'  {_build_rating_row(d)}'
                f'  {_build_dev_source(d)}'
                f'</div>\n'
            )

        if minor:
            # "Also worth knowing" only means something when there is something
            # above it. If the model rated nothing this month, every item is in
            # this list, and the subordinate framing plus the de-emphasised card
            # style would present the entire section as a footnote.
            demote = bool(major)
            minor_rows = ""
            for d in minor:
                date_html = f'<span class="dev-date">{d["date"]}</span>' if d["date"] else ""
                company_html = f'<span class="dev-company">{d["company"]}</span>' if d["company"] else ""
                minor_rows += (
                    f'<div class="dev-card{" dev-card-minor" if demote else ""}">'
                    f'  <div class="dev-header">{date_html}{company_html}</div>'
                    f'  <p class="dev-body">{d["body"]}</p>'
                    f'  {_build_dev_source(d)}'
                    f'</div>\n'
                )
            dev_cards += (
                f'<div class="dev-log">'
                f'<div class="dev-log-label">Also worth knowing</div>'
                f'{minor_rows}'
                f'</div>'
            ) if demote else minor_rows

        article_parts.append(
            f'<div class="section">'
            f'<h2 class="section-title">Key AI Developments This Month</h2>'
            f'<div class="dev-grid">{dev_cards}</div>'
            f'</div>'
        )

    if spotlight_items:
        spot_cards = ""
        for item in spotlight_items:
            org_html = f'<div class="spot-org">{item["org"]}</div>' if item["org"] else ""
            source_html = ""
            if item.get("source_url"):
                src_label = item.get("source_name") or "Source"
                source_html = (
                    f'<div class="spot-source">'
                    f'<a href="{item["source_url"]}" target="_blank" rel="noopener noreferrer" '
                    f'title="Search Google for this article">'
                    f'<svg class="icon" aria-hidden="true"><use href="#i-search"/></svg> {src_label}'
                    f'</a></div>'
                )
            spot_cards += (
                f'<li>'
                f'<span class="spot-bullet"><svg class="icon icon-solid" aria-hidden="true"><use href="#i-diamond"/></svg></span>'
                f'<div class="spot-content">'
                f'{org_html}'
                f'<div class="spot-body">{item["body"]}</div>'
                f'{source_html}'
                f'</div>'
                f'</li>\n'
            )
        article_parts.append(
            f'<div class="section canada-section">'
            f'<div class="canada-header"><span class="canada-label">Canadian Spotlight</span></div>'
            f'<h2 class="section-title canada-title">What\'s Happening in Canada</h2>'
            f'<ul class="spot-list">{spot_cards}</ul>'
            f'</div>'
        )
    elif canadian_spot and len(canadian_spot) > 60:
        article_parts.append(
            f'<div class="section canada-section">'
            f'<div class="canada-header"><span class="canada-label">Canadian Spotlight</span></div>'
            f'<h2 class="section-title canada-title">What\'s Happening in Canada</h2>'
            f'<p>{canadian_spot}</p>'
            f'</div>'
        )

    # The signature section sits here on purpose — immediately after the facts
    # and before the analysis that leans on them, at the point in the page where
    # attention is still high. It used to close the issue, which is exactly
    # where a reader who skims stops reading.
    article_parts.append(_build_roberts_desk(roberts_raw))

    if actions:
        action_cards = ""
        for i, a in enumerate(actions[:5]):
            owner_html = ""
            if a.get("owner"):
                rationale = (
                    f'<div class="action-owner-why">{a["owner_rationale"]}</div>'
                    if a.get("owner_rationale") else ""
                )
                owner_html = (
                    f'<div class="action-owner">'
                    f'<span class="action-owner-label">Owner</span>'
                    f'<span class="action-owner-role">{a["owner"]}</span>'
                    f'{rationale}'
                    f'</div>'
                )
            action_cards += (
                f'<div class="action-card">'
                f'  <div class="action-num">{i+1}</div>'
                f'  <div class="action-main">'
                f'    <div class="action-body">{a["body"]}</div>'
                f'    {owner_html}'
                f'    {_build_action_meta(a)}'
                f'  </div>'
                f'</div>\n'
            )
        article_parts.append(
            f'<div class="section actions-section">'
            f'<h2 class="section-title">Strategic Actions for This Month</h2>'
            f'<div class="actions-grid">{action_cards}</div>'
            f'</div>'
        )

    if adoption:
        stat_items_html = ""
        for item in adoption:
            if item["stat_number"] and item["stat_text"] and item["stat_number"] in item["stat_text"]:
                highlighted = item["stat_text"].replace(
                    item["stat_number"],
                    f'<span class="stat-highlight">{item["stat_number"]}</span>',
                    1
                )
                stat_content = f'<p class="stat-text">{highlighted}</p>'
            elif item["stat_number"]:
                stat_content = f'<p class="stat-text"><span class="stat-highlight">{item["stat_number"]}</span> {item["stat_text"]}</p>'
            else:
                stat_content = f'<p class="stat-text">{item["stat_text"]}</p>'

            src_html = ""
            if item.get("source_url"):
                src_html = (
                    f'<div class="stat-source">'
                    f'<a href="{item["source_url"]}" target="_blank" rel="noopener noreferrer" '
                    f'title="Search Google for this statistic">'
                    f'<svg class="icon" aria-hidden="true"><use href="#i-search"/></svg> {item["source_name"]}'
                    f'</a></div>'
                )
            elif item.get("source_name"):
                src_html = f'<div class="stat-source-plain">{item["source_name"]}</div>'

            stat_items_html += (
                f'<div class="stat-item">'
                f'  {stat_content}'
                f'  {src_html}'
                f'</div>\n'
            )
        # Built from the sources actually cited, not a fixed list. The hardcoded
        # version named six organisations regardless of what the section
        # contained — an issue sourced to Statistics Canada, RSM and Deloitte
        # still credited BDC, ISED, Vector Institute, Conference Board and Mila.
        # A footer naming who the numbers came from has to be true, or it is
        # worse than no footer.
        seen, cited = set(), []
        for item in adoption:
            name = (item.get("source_name") or "").strip().rstrip('.,')
            if name and name.lower() not in seen:
                seen.add(name.lower())
                cited.append(name)
        note_html = (
            f'<p class="stat-note">Sources: {", ".join(cited)}.</p>' if cited else ""
        )
        article_parts.append(
            f'<div class="section adoption-section">'
            f'<h2 class="section-title">Canadian AI Adoption Snapshot</h2>'
            f'<div class="stat-grid">{stat_items_html}</div>'
            f'{note_html}'
            f'</div>'
        )

    if predictions:
        article_parts.append(_build_predictions_section(predictions))

    # Each question is answered from the section that actually addresses it.
    # Pairing questions against whatever happened to be in `actions` produced
    # confident non-sequiturs — fine while the FAQ was schema-only, actively
    # misleading now that it is on the page and quotable by answer engines.
    _plain = faq_plain
    _join  = faq_join


    faq_candidates = [
        (
            f"What AI developments matter most for Canadian businesses in {coverage_month_year}?",
            _join([f'{d["company"]}: {d["body"]}' if d.get("company") else d["body"]
                   for d in developments[:3]]),
        ),
        (
            "What should Canadian executives do about AI right now?",
            _join(action_bodies[:3]),
        ),
        (
            "How is AI adoption tracking across Canada?",
            _join([f'{i.get("stat_number", "")} {i.get("stat_text", "")}'.strip()
                   for i in adoption[:3]]),
        ),
        (
            "What Canadian AI companies or initiatives should I know about?",
            _join([f'{i["org"]}: {i["body"]}' if i.get("org") else i["body"]
                   for i in spotlight_items[:3]]),
        ),
        (
            f"What should Canadian executives expect from AI over the next year?",
            _join([f'{p["horizon"]}: {p["body"]}' for p in predictions]),
        ),
    ]
    # Only publish a Q&A when the post genuinely contains the answer.
    faq_items = [{"question": q, "answer": a} for q, a in faq_candidates if len(a) > 60]

    # The FAQ must be VISIBLE, not schema-only. Google requires FAQPage content
    # to appear on the page, and an answer engine can only quote what it can
    # read — schema alone gets ignored and risks a structured-data penalty.
    if faq_items:
        faq_html = "".join(
            f'<div class="faq-item">'
            f'<h3 class="faq-q">{f["question"]}</h3>'
            f'<p class="faq-a">{f["answer"]}</p>'
            f'</div>'
            for f in faq_items
        )
        article_parts.append(
            f'<div class="section faq-section">'
            f'<h2 class="section-title">Questions Canadian Leaders Are Asking</h2>'
            f'<div class="faq-list">{faq_html}</div>'
            f'</div>'
        )

    if closing_question:
        article_parts.append(_build_question_section(closing_question))

    article_parts.append(_build_survey_cta())

    article_html = "\n".join(article_parts)

    faq_schema = ""
    if faq_items:
        faq_schema_items = ',\n'.join([
            f'{{"@type":"Question","name":{json.dumps(f["question"])},'
            f'"acceptedAnswer":{{"@type":"Answer","text":{json.dumps(f["answer"])}}}}}'
            for f in faq_items
        ])
        faq_schema = f"""    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "FAQPage",
      "mainEntity": [{faq_schema_items}]
    }}
    </script>"""

    html = f'''<!DOCTYPE html>
<html lang="en-CA">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="icon" type="image/svg+xml" href="/favicon.svg">
    <link rel="apple-touch-icon" href="/apple-touch-icon.png">
    <title>{seo_title}</title>
    <meta name="description" content="{meta_desc_html}">
    <meta name="keywords" content="AI Canada {issue_month_year}, Canadian AI news, artificial intelligence Canada, AI business strategy Canada, AI adoption Canada, Montreal AI, Canadian digital transformation, AI news for Canadians, AI insights {issue_month_year}, {coverage_month_year} AI recap">
    <meta name="author" content="Robert Simon">
    <meta name="robots" content="{robots_meta}">
    <meta name="language" content="en-CA">
    <meta name="geo.region" content="CA-QC">
    <meta name="geo.placename" content="Montreal, Quebec, Canada">
    <meta name="geo.position" content="45.5017;-73.5673">
    <meta name="ICBM" content="45.5017, -73.5673">
    <meta name="DC.coverage" content="Canada">
    <link rel="canonical" href="{canonical}">
    <meta property="og:type" content="article">
    <meta property="og:url" content="{canonical}">
    <meta property="og:title" content="{clean_title_html} | {BRAND}">
    <meta property="og:description" content="{meta_desc_html}">
    <meta property="og:image" content="{og_image}">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta property="og:image:alt" content="{og_alt}">
    <meta property="og:site_name" content="{BRAND}">
    <meta property="og:locale" content="en_CA">
    <meta property="article:published_time" content="{iso_date}T00:00:00+00:00">
    <meta property="article:modified_time" content="{iso_date}T00:00:00+00:00">
    <meta property="article:author" content="Robert Simon">
    <meta property="article:section" content="AI Strategy">
    <meta property="article:tag" content="AI Canada">
    <meta property="article:tag" content="Canadian Business">
    <meta property="article:tag" content="Artificial Intelligence">
    <meta property="article:tag" content="Digital Transformation">
    <meta property="article:tag" content="Montreal">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{clean_title_html} | AI News for Canadian Business">
    <meta name="twitter:description" content="{meta_desc_html}">
    <meta name="twitter:image" content="{og_image}">
    <meta name="twitter:image:alt" content="{og_alt}">
    <meta name="twitter:creator" content="@thedigitalrobert">
    <meta name="twitter:site" content="@thedigitalrobert">
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "BlogPosting",
      "headline": {json.dumps(clean_title)},
      "description": {json.dumps(meta_desc)},
      "datePublished": "{iso_date}",
      "dateModified": "{iso_date}",
      "author": {{
        "@type": "Person",
        "name": "Robert Simon",
        "url": "https://www.imetrobert.com",
        "image": "https://www.imetrobert.com/profile.jpg",
        "jobTitle": "AI Thought Leader & Digital Transformation Expert",
        "knowsAbout": ["Artificial Intelligence", "Digital Transformation", "AI Adoption in Canada", "AI Strategy"],
        "sameAs": ["https://linkedin.com/in/thedigitalrobert"],
        "address": {{"@type": "PostalAddress", "addressLocality": "Montreal", "addressRegion": "QC", "addressCountry": "CA"}}
      }},
      "publisher": {{
        "@type": "Person",
        "name": "Robert Simon",
        "url": "https://www.imetrobert.com",
        "logo": {{"@type": "ImageObject", "url": "https://www.imetrobert.com/blog/logo-512.png", "width": 512, "height": 512}}
      }},
      "mainEntityOfPage": {{"@type": "WebPage", "@id": {json.dumps(canonical)}}},
      "url": {json.dumps(canonical)},
      "image": {json.dumps(og_image)},
      "inLanguage": "en-CA",
      "about": [
        {{"@type": "Thing", "name": "Artificial Intelligence"}},
        {{"@type": "Thing", "name": "Canadian Business"}},
        {{"@type": "Place", "name": "Canada"}}
      ],
      "keywords": "AI Canada, artificial intelligence Canada, Canadian business AI, AI news Montreal, AI strategy Canada, digital transformation Canada",
      "articleSection": "AI Strategy",
      "wordCount": {word_count},
      "timeRequired": "PT{reading_time}M",
      "isAccessibleForFree": true,
      "speakable": {{
        "@type": "SpeakableSpecification",
        "cssSelector": [".intro-lead", ".summary-list li", ".faq-q", ".faq-a"]
      }}
    }}
    </script>
{faq_schema}
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      "itemListElement": [
        {{"@type": "ListItem", "position": 1, "name": "Home", "item": "https://www.imetrobert.com"}},
        {{"@type": "ListItem", "position": 2, "name": "{BRAND}", "item": "https://www.imetrobert.com/blog/"}},
        {{"@type": "ListItem", "position": 3, "name": {json.dumps(clean_title)}, "item": {json.dumps(canonical)}}}
      ]
    }}
    </script>
    <script async src="https://www.googletagmanager.com/gtag/js?id=G-Y0FZTVVLBS"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('js', new Date());
      gtag('config', 'G-Y0FZTVVLBS');
    </script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --blue:        #2563eb;
            --blue-dark:   #1d4ed8;
            --cyan:        #06b6d4;
            --navy:        #0f172a;
            --gray-dark:   #1e293b;
            --gray:        #475569;
            --gray-light:  #94a3b8;
            --surface:     #f8fafc;
            --border:      #e2e8f0;
            --white:       #ffffff;
            --canada-red:  #dc2626;
            --green:       #16a34a;
            --amber:       #d97706;
            --shadow-sm:   0 1px 3px rgb(0 0 0 / 0.08);
            --shadow-md:   0 4px 16px rgb(0 0 0 / 0.08);
            --shadow-lg:   0 8px 32px rgb(0 0 0 / 0.10);
        }}
        *, *::before, *::after {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; background: linear-gradient(160deg, #f0f4ff 0%, #e8eef8 100%); color: var(--navy); line-height: 1.6; -webkit-font-smoothing: antialiased; }}
        .nav-bar {{ background: var(--white); padding: 0.875rem 0; box-shadow: var(--shadow-sm); position: sticky; top: 0; z-index: 100; border-bottom: 1px solid var(--border); }}
        .nav-content {{ max-width: 900px; margin: 0 auto; padding: 0 1.5rem; display: flex; justify-content: space-between; align-items: center; gap: 1rem; flex-wrap: wrap; }}
        .nav-link {{ color: var(--white); text-decoration: none; font-weight: 600; padding: 0.4rem 1rem; font-size: 0.8rem; border-radius: 20px; background: linear-gradient(135deg, var(--blue), var(--cyan)); transition: all 0.2s; letter-spacing: 0.01em; flex-shrink: 0; }}
        .nav-link:hover {{ transform: translateY(-1px); box-shadow: 0 4px 12px rgb(37 99 235 / 0.3); }}
        .nav-meta {{ font-size: 0.78rem; color: var(--gray-light); display: flex; align-items: center; gap: 0.5rem; }}
        .nav-meta .brand-icon {{ width: 22px; height: 22px; border-radius: 7px; flex-shrink: 0; }}
        .brand-logo {{ width: 76px; height: 76px; display: block; margin: 0 auto 1.5rem; padding: 7px; box-sizing: content-box; background: rgba(255,255,255,0.96); border-radius: 23px; box-shadow: 0 10px 26px rgba(15,23,42,0.25); }}
        .header {{ background: linear-gradient(135deg, var(--blue) 0%, #1a7fb5 50%, var(--cyan) 100%); color: var(--white); padding: 4rem 0 3.5rem; text-align: center; position: relative; overflow: hidden; }}
        .header::before {{ content: ''; position: absolute; inset: 0; background: radial-gradient(circle at 15% 85%, rgba(255,255,255,0.07) 0%, transparent 45%), radial-gradient(circle at 85% 15%, rgba(255,255,255,0.05) 0%, transparent 45%); pointer-events: none; }}
        .header-content {{ max-width: 780px; margin: 0 auto; padding: 0 1.5rem; position: relative; z-index: 1; }}
        .issue-badge {{ display: inline-flex; align-items: center; gap: 0.4rem; background: rgba(255,255,255,0.15); border: 1px solid rgba(255,255,255,0.25); padding: 0.3rem 0.9rem; border-radius: 20px; font-size: 0.7rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 1.25rem; }}
        .issue-badge-coverage {{ font-weight: 500; opacity: 0.75; letter-spacing: 0.04em; }}
        .header h1 {{ font-size: clamp(1.75rem, 4.5vw, 2.6rem); font-weight: 800; line-height: 1.15; margin-bottom: 0.6rem; letter-spacing: -0.02em; }}
        .header .subtitle {{ font-size: 0.95rem; font-weight: 500; opacity: 0.85; margin-bottom: 1rem; }}
        .header .intro-text {{ font-size: 0.925rem; opacity: 0.8; max-width: 640px; margin: 0 auto 1.25rem; line-height: 1.65; }}
        .reading-badge {{ display: inline-flex; align-items: center; gap: 0.3rem; background: rgba(255,255,255,0.12); padding: 0.25rem 0.75rem; border-radius: 12px; font-size: 0.72rem; font-weight: 500; opacity: 0.85; }}
        .container {{ max-width: 900px; margin: 0 auto; padding: 2.5rem 1.5rem 5rem; }}
        .article-card {{ background: var(--white); border-radius: 20px; box-shadow: var(--shadow-lg); overflow: hidden; border: 1px solid rgba(226,232,240,0.6); }}
        .breadcrumb {{ font-size: 0.72rem; color: var(--gray-light); padding: 0.65rem 2rem; background: var(--surface); border-bottom: 1px solid var(--border); }}
        .breadcrumb a {{ color: var(--blue); text-decoration: none; }}
        .author-byline {{ display: flex; align-items: center; gap: 0.875rem; padding: 1rem 2rem; border-bottom: 1px solid var(--border); background: var(--surface); }}
        .author-byline img {{ width: 42px; height: 42px; border-radius: 50%; object-fit: cover; flex-shrink: 0; border: 2px solid var(--border); }}
        .author-name  {{ font-weight: 700; color: var(--navy); font-size: 0.875rem; }}
        .author-role  {{ font-size: 0.75rem; color: var(--gray-light); margin-top: 0.1rem; }}
        .article-content {{ padding: 2.25rem 2rem; }}
        .section {{ margin-bottom: 3rem; }}
        .section-title {{ font-size: 1.2rem; font-weight: 700; color: var(--navy); margin-bottom: 1.25rem; padding-left: 0.875rem; position: relative; letter-spacing: -0.01em; }}
        .section-title::before {{ content: ''; position: absolute; left: 0; top: 0.1rem; bottom: 0.1rem; width: 3px; background: linear-gradient(to bottom, var(--blue), var(--cyan)); border-radius: 2px; }}
        .intro-section {{ border-left: 3px solid var(--cyan); padding-left: 1.25rem; }}
        .intro-lead {{ font-size: 1.05rem; line-height: 1.75; color: var(--gray-dark); font-weight: 400; }}
        .dev-grid {{ display: grid; gap: 0.75rem; }}
        .dev-card {{ padding: 1rem 1.25rem; border: 1px solid var(--border); border-radius: 12px; transition: border-color 0.2s, box-shadow 0.2s; border-left: 3px solid var(--blue); background: #fafbff; }}
        .dev-card:hover {{ border-color: var(--blue); box-shadow: var(--shadow-md); background: var(--white); }}
        .dev-header {{ display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.4rem; flex-wrap: wrap; }}
        .dev-date {{ display: inline-block; background: linear-gradient(135deg, var(--blue), var(--cyan)); color: var(--white); font-size: 0.65rem; font-weight: 700; padding: 0.15rem 0.55rem; border-radius: 10px; white-space: nowrap; letter-spacing: 0.03em; }}
        .dev-company {{ font-weight: 700; color: var(--navy); font-size: 0.85rem; }}
        .dev-body {{ font-size: 0.875rem; color: var(--gray); line-height: 1.65; }}
        .dev-source {{ margin-top: 0.5rem; }}
        .dev-source a {{ font-size: 0.72rem; color: var(--blue); text-decoration: none; font-weight: 600; opacity: 0.8; transition: opacity 0.2s; }}
        .dev-source a:hover {{ opacity: 1; text-decoration: underline; }}
        .canada-section {{ background: linear-gradient(135deg, #fff5f5 0%, #fffbfb 100%); border: 1px solid #fecaca; border-radius: 16px; padding: 1.75rem; }}
        .canada-header {{ margin-bottom: 0.75rem; }}
        .canada-label {{ display: inline-flex; align-items: center; gap: 0.35rem; background: var(--canada-red); color: var(--white); font-size: 0.65rem; font-weight: 700; padding: 0.2rem 0.7rem; border-radius: 12px; letter-spacing: 0.06em; text-transform: uppercase; }}
        /* Inline SVG icons, sprite defined at the top of <body>. Stroked in
           currentColor and sized in em so each icon matches its adjacent text. */
        .icon {{ width: 1.05em; height: 1.05em; flex-shrink: 0; fill: none; stroke: currentColor; stroke-width: 1.75; stroke-linecap: round; stroke-linejoin: round; vertical-align: -0.14em; }}
        .icon-solid {{ fill: currentColor; stroke: none; }}
        .canada-title::before {{ background: var(--canada-red) !important; }}
        .spot-list {{ list-style: none; padding: 0; display: grid; gap: 0.875rem; }}
        .spot-list li {{ display: flex; gap: 0.6rem; align-items: flex-start; font-size: 0.875rem; color: var(--gray); line-height: 1.65; padding: 0.875rem 1rem; background: var(--white); border-radius: 10px; border: 1px solid #fde8e8; }}
        .spot-bullet {{ flex-shrink: 0; margin-top: 0.35rem; font-size: 0.55rem; color: var(--canada-red); display: flex; }}
        .spot-content {{ flex: 1; }}
        .spot-org {{ font-weight: 700; color: var(--navy); font-size: 0.85rem; margin-bottom: 0.2rem; }}
        .spot-body {{ font-size: 0.875rem; color: var(--gray); line-height: 1.6; }}
        .spot-source {{ margin-top: 0.4rem; }}
        .spot-source a {{ font-size: 0.72rem; color: var(--canada-red); text-decoration: none; font-weight: 600; opacity: 0.8; transition: opacity 0.2s; }}
        .spot-source a:hover {{ opacity: 1; text-decoration: underline; }}
        .actions-grid {{ display: grid; gap: 0.875rem; }}
        .action-card {{ display: flex; gap: 1rem; align-items: flex-start; padding: 1.1rem 1.25rem; background: #f8faff; border: 1px solid #dbeafe; border-radius: 12px; border-left: 3px solid var(--blue); transition: box-shadow 0.2s; }}
        .action-card:hover {{ box-shadow: var(--shadow-md); background: var(--white); }}
        .action-num {{ display: flex; align-items: center; justify-content: center; width: 1.75rem; height: 1.75rem; min-width: 1.75rem; background: linear-gradient(135deg, var(--blue), var(--cyan)); color: var(--white); font-size: 0.72rem; font-weight: 800; border-radius: 50%; margin-top: 0.1rem; }}
        .action-body {{ font-size: 0.875rem; color: var(--gray-dark); line-height: 1.7; flex: 1; }}
        .stat-grid {{ display: grid; gap: 0.75rem; }}
        .stat-item {{ padding: 1rem 1.25rem; background: #f0fdf4; border-left: 3px solid var(--green); border-radius: 0 10px 10px 0; }}
        .stat-text {{ font-size: 0.875rem; color: var(--gray-dark); line-height: 1.65; }}
        .stat-highlight {{ font-weight: 800; color: var(--green); font-size: 1rem; }}
        .stat-source {{ margin-top: 0.35rem; }}
        .stat-source a {{ font-size: 0.7rem; color: var(--green); text-decoration: none; font-weight: 600; opacity: 0.75; transition: opacity 0.2s; }}
        .stat-source a:hover {{ opacity: 1; text-decoration: underline; }}
        .stat-source-plain {{ font-size: 0.7rem; color: var(--gray-light); margin-top: 0.35rem; }}
        .stat-note {{ font-size: 0.72rem; color: var(--gray-light); margin-top: 0.875rem; font-style: italic; }}
        .roberts-take {{ background: linear-gradient(135deg, #1e3a6e 0%, #1a5276 100%); border-radius: 16px; padding: 1.75rem; color: var(--white); }}
        .roberts-header {{ display: flex; align-items: center; gap: 0.875rem; margin-bottom: 1.1rem; padding-bottom: 1rem; border-bottom: 1px solid rgba(255,255,255,0.12); }}
        .roberts-header img {{ width: 38px; height: 38px; border-radius: 50%; object-fit: cover; border: 2px solid rgba(255,255,255,0.25); flex-shrink: 0; }}
        .roberts-label {{ font-size: 0.62rem; text-transform: uppercase; letter-spacing: 0.1em; opacity: 0.6; margin-bottom: 0.1rem; }}
        .roberts-name {{ margin: 0; font-weight: 700; font-size: 0.9rem; }}
        .roberts-body {{ font-size: 0.925rem; line-height: 1.85; color: #ffffff; font-style: normal; font-weight: 400; }}
        .roberts-placeholder {{ font-size: 0.825rem; line-height: 1.7; opacity: 0.65; border: 1px dashed rgba(255,255,255,0.25); padding: 1rem 1.25rem; border-radius: 10px; }}
        .roberts-placeholder strong {{ color: var(--white); opacity: 1; font-style: normal; }}
        .roberts-body + .roberts-body {{ margin-top: 0.9rem; }}
        /* Executive summary — the three things, above the fold. */
        .summary-section {{ background: var(--surface); border: 1px solid var(--border); border-left: 3px solid var(--navy); border-radius: 12px; padding: 1.4rem 1.6rem; }}
        .summary-label {{ margin: 0 0 0.85rem; font-size: 0.62rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.11em; color: var(--navy); opacity: 0.75; }}
        .summary-list {{ list-style: none; padding: 0; display: grid; gap: 0.7rem; counter-reset: summary; }}
        .summary-list li {{ position: relative; padding-left: 1.9rem; font-size: 0.9rem; line-height: 1.6; color: var(--gray-dark); font-weight: 500; counter-increment: summary; }}
        .summary-list li::before {{ content: counter(summary); position: absolute; left: 0; top: 0.05rem; width: 1.3rem; height: 1.3rem; display: flex; align-items: center; justify-content: center; background: var(--navy); color: var(--white); border-radius: 50%; font-size: 0.65rem; font-weight: 800; }}
        /* Major stories carry judgment and ratings; the log below does not. */
        .dev-card-major {{ padding: 1.25rem 1.4rem; }}
        .dev-tier {{ margin-left: auto; font-size: 0.58rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.09em; color: var(--blue); opacity: 0.7; }}
        .dev-read {{ margin-top: 0.85rem; padding: 0.9rem 1.1rem; background: var(--white); border: 1px solid #dbeafe; border-left: 3px solid var(--cyan); border-radius: 0 10px 10px 0; }}
        .dev-read-label {{ display: block; font-size: 0.58rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.1em; color: var(--cyan); margin-bottom: 0.35rem; }}
        .dev-read p {{ font-size: 0.86rem; line-height: 1.7; color: var(--gray-dark); margin: 0; }}
        .dev-log {{ margin-top: 1.25rem; padding-top: 1.1rem; border-top: 1px dashed var(--border); display: grid; gap: 0.6rem; }}
        .dev-log-label {{ font-size: 0.6rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.1em; color: var(--gray-light); }}
        .dev-card-minor {{ padding: 0.8rem 1rem; background: var(--white); border-left-color: var(--border); }}
        .dev-card-minor .dev-body {{ font-size: 0.83rem; }}
        .dev-card-minor .dev-company {{ font-size: 0.8rem; }}
        /* Rating badges. Label above value so a badge reads without a legend. */
        .badge-row {{ display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.9rem; }}
        .badge {{ display: inline-flex; flex-direction: column; gap: 0.1rem; padding: 0.35rem 0.7rem; border-radius: 8px; border: 1px solid var(--border); background: var(--white); min-width: 5.5rem; }}
        .badge-label {{ font-size: 0.55rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em; color: var(--gray-light); }}
        .badge-value {{ font-size: 0.8rem; font-weight: 800; color: var(--navy); line-height: 1.2; }}
        .badge.tone-high {{ background: #fff7ed; border-color: #fed7aa; }}
        .badge.tone-high .badge-value {{ color: #c2410c; }}
        .badge.tone-mid {{ background: #eff6ff; border-color: #bfdbfe; }}
        .badge.tone-mid .badge-value {{ color: #1d4ed8; }}
        .badge.tone-low {{ background: var(--surface); border-color: var(--border); }}
        .badge.tone-low .badge-value {{ color: var(--gray); }}
        .badge.tone-neutral .badge-value {{ color: var(--gray-dark); }}
        .badge-row-action {{ margin-top: 0.75rem; }}
        /* Actions: body, then who owns it and why, then the triage badges. */
        .action-main {{ flex: 1; }}
        .action-owner {{ margin-top: 0.75rem; padding: 0.6rem 0.85rem; background: var(--white); border: 1px solid #dbeafe; border-radius: 8px; }}
        .action-owner-label {{ font-size: 0.55rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.09em; color: var(--gray-light); margin-right: 0.45rem; }}
        .action-owner-role {{ font-size: 0.8rem; font-weight: 800; color: var(--navy); }}
        .action-owner-why {{ font-size: 0.78rem; line-height: 1.6; color: var(--gray); margin-top: 0.3rem; }}
        /* Looking ahead — three predictions, explicitly labelled as such. */
        .pred-note {{ font-size: 0.78rem; color: var(--gray-light); line-height: 1.6; margin-bottom: 1.1rem; font-style: italic; }}
        .pred-grid {{ display: grid; gap: 0.75rem; }}
        .pred-card {{ padding: 1rem 1.25rem; background: var(--surface); border: 1px solid var(--border); border-left: 3px solid var(--navy); border-radius: 0 10px 10px 0; }}
        .pred-horizon {{ font-size: 0.6rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.1em; color: var(--navy); opacity: 0.7; margin-bottom: 0.35rem; }}
        .pred-body {{ font-size: 0.875rem; line-height: 1.7; color: var(--gray-dark); margin: 0; }}
        /* The closing question. Deliberately the largest type in the article. */
        .question-section {{ border: 2px solid var(--navy); border-radius: 16px; padding: 1.75rem 2rem; background: var(--white); }}
        .question-label {{ margin: 0 0 0.7rem; font-size: 0.62rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.11em; color: var(--navy); opacity: 0.7; }}
        .question-body {{ font-size: 1.15rem; line-height: 1.6; font-weight: 600; color: var(--navy); margin: 0; letter-spacing: -0.01em; }}
        .faq-section {{ background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 1.75rem; }}
        .faq-list {{ display: grid; gap: 1rem; }}
        .faq-item {{ padding: 1rem 1.25rem; background: var(--white); border: 1px solid var(--border); border-radius: 12px; border-left: 3px solid var(--blue); }}
        .faq-q {{ font-size: 0.925rem; font-weight: 700; color: var(--navy); margin-bottom: 0.4rem; line-height: 1.45; }}
        .faq-a {{ font-size: 0.875rem; color: var(--gray); line-height: 1.7; margin: 0; }}
        .survey-cta {{ background: linear-gradient(135deg, var(--blue) 0%, var(--cyan) 100%); color: var(--white); border-radius: 16px; padding: 1.75rem; }}
        .survey-cta .section-title {{ color: var(--white); }}
        .survey-cta .section-title::before {{ background: rgba(255,255,255,0.85); }}
        .survey-body {{ font-size: 0.9rem; line-height: 1.75; color: rgba(255,255,255,0.94); margin-bottom: 1.25rem; }}
        .survey-body strong {{ color: var(--white); }}
        .survey-actions {{ display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; }}
        .survey-btn {{ display: inline-block; background: var(--white); color: var(--blue); font-weight: 700; font-size: 0.85rem; padding: 0.6rem 1.4rem; border-radius: 25px; text-decoration: none; transition: transform 0.15s; }}
        .survey-btn:hover {{ transform: translateY(-1px); }}
        .survey-results {{ color: rgba(255,255,255,0.92); font-size: 0.8rem; font-weight: 600; text-decoration: underline; }}
        /* Share row. Sits at the end of the issue — the point at which a reader
           who found the issue useful decides to pass it on. */
        .share-row {{ margin-top: 1.75rem; padding-top: 1.5rem; border-top: 1px solid var(--border); }}
        .share-label {{ font-size: 0.62rem; font-weight: 800; text-transform: uppercase; letter-spacing: 0.11em; color: var(--gray-light); margin-bottom: 0.8rem; }}
        .share-actions {{ display: flex; flex-wrap: wrap; gap: 0.5rem; }}
        .share-btn {{ display: inline-flex; align-items: center; gap: 0.45rem; font: inherit; font-size: 0.8rem; font-weight: 600; color: var(--navy); background: var(--white); border: 1px solid var(--border); border-radius: 22px; padding: 0.5rem 1rem; text-decoration: none; cursor: pointer; transition: border-color 0.2s, box-shadow 0.2s, transform 0.15s; }}
        .share-btn:hover {{ border-color: var(--blue); color: var(--blue); box-shadow: var(--shadow-md); transform: translateY(-1px); }}
        .share-btn .icon {{ width: 1.1em; height: 1.1em; }}
        .share-btn.copied {{ background: var(--green); border-color: var(--green); color: var(--white); }}
        .share-btn[hidden] {{ display: none; }}
        p {{ margin-bottom: 1rem; line-height: 1.75; color: var(--gray); font-size: 0.9rem; }}
        strong {{ color: var(--navy); font-weight: 600; }}
        @media (max-width: 640px) {{
            .header {{ padding: 2.5rem 0 2.25rem; }}
            .header h1 {{ font-size: 1.6rem; }}
            .brand-logo {{ width: 58px; height: 58px; padding: 6px; border-radius: 18px; margin-bottom: 1.1rem; }}
            .container {{ padding: 1.5rem 1rem 3rem; }}
            .article-content {{ padding: 1.5rem 1.25rem; }}
            .nav-content {{ flex-direction: column; align-items: flex-start; gap: 0.35rem; }}
            .author-byline {{ padding: 0.875rem 1.25rem; }}
            .breadcrumb {{ padding: 0.5rem 1.25rem; }}
            .canada-section {{ padding: 1.25rem; }}
            .action-card {{ flex-direction: column; gap: 0.6rem; }}
            .action-num {{ width: 1.5rem; height: 1.5rem; min-width: 1.5rem; }}
            .summary-section {{ padding: 1.1rem 1.2rem; }}
            .question-section {{ padding: 1.25rem 1.35rem; }}
            .question-body {{ font-size: 1rem; }}
            .dev-tier {{ margin-left: 0; flex-basis: 100%; }}
            /* Badges go full width rather than wrapping into ragged rows. */
            .badge {{ flex: 1 1 auto; min-width: 6.5rem; }}
        }}
    </style>
</head>
<body>
    <!-- Icon sprite. Reference a symbol by id from an svg.icon element.
         Markers here are geometric on purpose: the brand's maple leaf is
         illegible below ~32px, so it stays in the logo and does not get
         shrunk down into list bullets. -->
    <svg xmlns="http://www.w3.org/2000/svg" style="display:none" aria-hidden="true">
        <symbol id="i-search" viewBox="0 0 24 24">
            <circle cx="10.5" cy="10.5" r="6.5"/>
            <path d="m15.5 15.5 4.5 4.5"/>
        </symbol>
        <symbol id="i-clock" viewBox="0 0 24 24">
            <circle cx="12" cy="12" r="8.5"/>
            <path d="M12 7v5.2l3.2 2"/>
        </symbol>
        <symbol id="i-copy" viewBox="0 0 24 24">
            <rect x="9" y="9" width="11" height="11" rx="2.5"/>
            <path d="M6.5 15H5.5A2.5 2.5 0 0 1 3 12.5v-7A2.5 2.5 0 0 1 5.5 3h7A2.5 2.5 0 0 1 15 5.5v1"/>
        </symbol>
        <symbol id="i-linkedin" viewBox="0 0 24 24">
            <path fill="currentColor" stroke="none" d="M4.98 3.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5zM3 9.5h4v11H3zm7 0h3.8v1.5a4.2 4.2 0 0 1 3.7-1.9c3 0 4.5 1.9 4.5 5.3v6.1h-4v-5.4c0-1.6-.6-2.6-2-2.6s-2.2 1-2.2 2.6v5.4h-3.8z"/>
        </symbol>
        <symbol id="i-mail" viewBox="0 0 24 24">
            <rect x="3" y="5" width="18" height="14" rx="2.5"/>
            <path d="m3.5 7 8.5 6 8.5-6"/>
        </symbol>
        <symbol id="i-share" viewBox="0 0 24 24">
            <circle cx="18" cy="5" r="2.5"/><circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="19" r="2.5"/>
            <path d="m8.2 10.8 7.6-4.4M8.2 13.2l7.6 4.4"/>
        </symbol>
        <symbol id="i-pencil" viewBox="0 0 24 24">
            <path d="M4 20h4l10.5-10.5a2.1 2.1 0 0 0-3-3L5 17z"/>
            <path d="m14.5 6 3 3"/>
        </symbol>
        <symbol id="i-diamond" viewBox="0 0 24 24">
            <path d="M12 4.5 19.5 12 12 19.5 4.5 12Z"/>
        </symbol>
    </svg>
    <nav class="nav-bar">
        <div class="nav-content">
            <a href="https://www.imetrobert.com/blog/" class="nav-link">&#8592; Back to Blog</a>
            <div class="nav-meta">
                <img src="/blog/logo.svg" class="brand-icon" alt="" width="22" height="22">
                <span>{BRAND}</span>
                <span>&#8226;</span>
                <span>{formatted_date}</span>
            </div>
        </div>
    </nav>
    <header class="header">
        <div class="header-content">
            <img src="/blog/logo.svg" class="brand-logo" alt="{BRAND}" width="76" height="76">
            <div class="issue-badge">Issue #{issue_num} &nbsp;&#8226;&nbsp; {issue_month_year} <span class="issue-badge-coverage">&mdash; Covering {coverage_month_name}</span></div>
            <h1>{clean_title_html}</h1>
            <div class="subtitle">{BRAND_TAGLINE}</div>
            <div class="intro-text">{excerpt_html}</div>
            <div class="reading-badge"><svg class="icon" aria-hidden="true"><use href="#i-clock"/></svg> {reading_time} min read</div>
        </div>
    </header>
    <div class="container">
        <article class="article-card" itemscope itemtype="https://schema.org/BlogPosting">
            <meta itemprop="headline"      content="{clean_title_html}">
            <meta itemprop="datePublished" content="{iso_date}">
            <meta itemprop="dateModified"  content="{iso_date}">
            <meta itemprop="author"        content="Robert Simon">
            <meta itemprop="description"   content="{meta_desc_html}">
            <nav class="breadcrumb" aria-label="Breadcrumb">
                <a href="https://www.imetrobert.com">Home</a> &#8250;
                <a href="https://www.imetrobert.com/blog/">{BRAND}</a> &#8250;
                <span>{clean_title_html}</span>
            </nav>
            <div class="author-byline">
                <img src="https://imetrobert.github.io/profile.jpg" alt="Robert Simon" loading="lazy">
                <div>
                    <div class="author-name">Robert Simon</div>
                    <div class="author-role">AI Thought Leader &amp; Digital Transformation Expert &mdash; Montreal, QC</div>
                </div>
            </div>
            <div class="article-content" itemprop="articleBody">
                {article_html}
                {_build_share_row(canonical, clean_title, issue_month_year)}
            </div>
        </article>
    </div>
    <script>
      // Share behaviour: copy-to-clipboard and the OS share sheet. Delegated,
      // so it costs one listener no matter how many share controls a post has.
      (function () {{
        function fallbackCopy(text) {{
          var ta = document.createElement('textarea');
          ta.value = text;
          ta.setAttribute('readonly', '');
          ta.style.position = 'fixed';
          ta.style.opacity = '0';
          document.body.appendChild(ta);
          ta.select();
          try {{ document.execCommand('copy'); }} catch (e) {{}}
          document.body.removeChild(ta);
        }}

        function flash(btn) {{
          var label = btn.querySelector('.share-btn-text');
          if (!label) return;
          var original = label.textContent;
          label.textContent = 'Copied';
          btn.classList.add('copied');
          setTimeout(function () {{
            label.textContent = original;
            btn.classList.remove('copied');
          }}, 1800);
        }}

        document.addEventListener('click', function (e) {{
          var btn = e.target.closest ? e.target.closest('.share-copy') : null;
          if (!btn) return;

          // The canonical permalink, baked in at build time. Never
          // location.href — this same article is also served at latest.html,
          // which points at a different issue next month.
          var text = btn.dataset.shareUrl || '';
          if (!text) return;

          if (navigator.clipboard && navigator.clipboard.writeText) {{
            navigator.clipboard.writeText(text).then(function () {{ flash(btn); }},
                                                     function () {{ fallbackCopy(text); flash(btn); }});
          }} else {{
            fallbackCopy(text);
            flash(btn);
          }}

          if (typeof gtag === 'function') {{
            gtag('event', 'share', {{ method: 'copy_link' }});
          }}
        }});

        // The OS share sheet, where the browser has one. Revealed rather than
        // rendered, so a desktop visitor never sees a button that would do
        // nothing — LinkedIn, email and copy already cover that case.
        if (navigator.share) {{
          document.querySelectorAll('.share-native').forEach(function (b) {{
            b.hidden = false;
          }});
        }}

        document.addEventListener('click', function (e) {{
          var btn = e.target.closest ? e.target.closest('.share-native') : null;
          if (!btn || !navigator.share) return;
          navigator.share({{
            title: btn.dataset.shareTitle || document.title,
            url: btn.dataset.shareUrl
          }}).then(function () {{
            if (typeof gtag === 'function') {{
              gtag('event', 'share', {{ method: 'web_share' }});
            }}
          }}).catch(function () {{
            // The user dismissed the sheet. Not an error, and not worth a message.
          }});
        }});
      }})();
    </script>
</body>
</html>'''

    return html


def _build_survey_cta():
    """Invitation to the reader survey, rendered only once a form URL is set.

    This is the collection end of the one thing on the site that makes Robert a
    primary source rather than a reporter of other people's numbers. It stays
    invisible until data/survey.json has a form_url, so the section can be built
    and reviewed without ever shipping a dead link.
    """
    import json as _json, os as _os
    root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    try:
        with open(_os.path.join(root, "data", "survey.json"), encoding="utf-8") as f:
            cfg = _json.load(f)
    except Exception:
        return ""

    form_url = (cfg.get("form_url") or "").strip()
    if not form_url:
        return ""

    name = escape_html(cfg.get("survey_name", "reader survey"))
    results_exists = _os.path.exists(_os.path.join(root, "blog", "canadian-ai-pulse.html"))
    results_link = ('<a class="survey-results" href="/blog/canadian-ai-pulse.html">'
                    'See the current results</a>') if results_exists else ""

    return (
        f'<div class="section survey-cta">'
        f'<h2 class="section-title">Add your data point</h2>'
        f'<p class="survey-body">Most of the adoption numbers in this issue come from '
        f'somebody else\'s survey. <strong>{name}</strong> is ours: five questions, under a '
        f'minute, no email required. Results are published openly with the sample size, so '
        f'you get to compare your position against the rest of this readership rather than '
        f'against a national average that may not look anything like you.</p>'
        f'<div class="survey-actions">'
        f'<a class="survey-btn" href="{form_url}" target="_blank" rel="noopener noreferrer">'
        f'Take the {name} survey</a>{results_link}'
        f'</div></div>'
    )



def faq_plain(text, limit=480):
    text = re.sub(r"<[^>]+>", " ", str(text))
    # Answers get quoted verbatim by answer engines, so scrub anything that
    # betrays the source format: bare URLs, the pipe-delimited field syntax
    # the generator emits, markdown headings, and leading list bullets.
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"#{1,6}\s*[A-Z][A-Z '\u2019]*$", "", text)
    text = re.sub(r"^[\s\-\*\u2022]+", "", text)
    text = text.replace(" | ", " \u2014 ")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"(?:\s*\u2014){2,}", " \u2014", text)          # URL removal can leave a dangling dash
    text = re.sub(r"\s*\u2014\s*$", "", text)
    text = text.strip(" \u2014-#*\u2022 ")
    if len(text) > limit:
        text = text[: limit - 3].rsplit(" ", 1)[0] + "..."
    return text


def faq_join(parts, limit=480):
    out = ""
    for part in parts:
        part = faq_plain(part, limit)
        if not part:
            continue
        candidate = f"{out} {part}".strip() if out else part
        if len(candidate) > limit:
            break
        out = candidate
    return out


def _build_summary_section(summary_points):
    points_html = "".join(f'<li>{p}</li>' for p in summary_points)
    return (
        f'<div class="section summary-section">'
        f'<h2 class="summary-label">Executive Summary</h2>'
        f'<ul class="summary-list">{points_html}</ul>'
        f'</div>'
    )



def _build_predictions_section(predictions):
    pred_html = "".join(
        f'<div class="pred-card">'
        f'<div class="pred-horizon">{p["horizon"]}</div>'
        f'<p class="pred-body">{p["body"]}</p>'
        f'</div>'
        for p in predictions
    )
    return (
        f'<div class="section pred-section">'
        f'<h2 class="section-title">Looking Ahead</h2>'
        f'<p class="pred-note">These are predictions, not reported facts \u2014 '
        f'Robert\u2019s assessment of where this goes next, offered so you can '
        f'judge it against your own.</p>'
        f'<div class="pred-grid">{pred_html}</div>'
        f'</div>'
    )


def _build_question_section(closing_question):
    return (
        f'<div class="section question-section">'
        f'<h2 class="question-label">One question for your leadership team</h2>'
        f'<p class="question-body">{closing_question}</p>'
        f'</div>'
    )


def _build_share_row(canonical, title, issue_month_year):
    """Share controls for a published issue.

    Every link is built from `canonical`, never from the page's own address.
    A post is served at BOTH its dated permalink and at latest.html, and
    latest.html is a rotating alias — same URL, a different article every
    month. Sharing the address the reader happens to be at means a link that
    silently points at next month's issue, and social platforms cache Open
    Graph data per URL essentially forever, so the preview stays wrong too.

    LinkedIn and email are plain hrefs resolved at build time, so they work
    with JavaScript disabled. Only copy-to-clipboard and the OS share sheet
    need scripting, and the share sheet button stays hidden until the browser
    says it supports it.
    """
    url_q = quote(canonical, safe='')
    # A topical headline gets the publication name appended for context; a
    # fallback title already carries the brand and would otherwise read
    # "Practical AI for Canadian Business — Practical AI Canada, September 2026".
    # "ai insights" stays in the guard for issues written before the rename.
    already_branded = any(
        s in title.lower() for s in (BRAND.lower(), BRAND_SHORT.lower(), "ai insights")
    )
    subject = (
        title if already_branded
        else f"{title} — {BRAND_SHORT}, {issue_month_year}"
    )
    subject_q = quote(subject, safe='')
    body_q    = quote(
        f"Thought this was worth your time — Robert Simon's monthly AI briefing "
        f"for Canadian business leaders.\n\n{title}\n{canonical}\n",
        safe=''
    )

    linkedin = f"https://www.linkedin.com/sharing/share-offsite/?url={url_q}"
    mailto   = f"mailto:?subject={subject_q}&body={body_q}"
    url_attr = escape_html(canonical, quote=True)

    return (
        f'<div class="share-row">'
        f'  <div class="share-label">Forward this issue</div>'
        f'  <div class="share-actions">'
        f'    <a class="share-btn" href="{escape_html(linkedin, quote=True)}" '
        f'target="_blank" rel="noopener noreferrer">'
        f'<svg class="icon" aria-hidden="true"><use href="#i-linkedin"/></svg>'
        f'<span>LinkedIn</span></a>'
        f'    <a class="share-btn" href="{escape_html(mailto, quote=True)}">'
        f'<svg class="icon" aria-hidden="true"><use href="#i-mail"/></svg>'
        f'<span>Email</span></a>'
        f'    <button type="button" class="share-btn share-copy" '
        f'data-share-url="{url_attr}">'
        f'<svg class="icon" aria-hidden="true"><use href="#i-copy"/></svg>'
        f'<span class="share-btn-text">Copy link</span></button>'
        f'    <button type="button" class="share-btn share-native" hidden '
        f'data-share-url="{url_attr}" data-share-title="{escape_html(title, quote=True)}">'
        f'<svg class="icon" aria-hidden="true"><use href="#i-share"/></svg>'
        f'<span>Share</span></button>'
        f'  </div>'
        f'</div>'
    )


def _build_dev_source(d):
    if not d.get("source_url"):
        return ""
    src_label = d.get("source_name") or "Source"
    return (
        f'<div class="dev-source">'
        f'<a href="{d["source_url"]}" target="_blank" rel="noopener noreferrer" '
        f'title="Search Google for this article">'
        f'<svg class="icon" aria-hidden="true"><use href="#i-search"/></svg> {src_label}'
        f'</a></div>'
    )


def _build_strategic_read(d):
    """Robert's interpretation of a major story. Visually distinct from the
    reported sentences above it — a reader must be able to tell at a glance
    which half of this card is fact and which half is judgment."""
    text = (d.get("strategic_read") or "").strip()
    if len(text) < 40:
        return ""
    return (
        f'<div class="dev-read">'
        f'<span class="dev-read-label">Strategic read</span>'
        f'<p>{escape_html(text, quote=False)}</p>'
        f'</div>'
    )


# Rating value -> modifier class. Anything unrecognised renders neutral rather
# than unstyled, so an off-script value from the model still looks deliberate.
_RATING_TONE = {
    "high": "tone-high", "medium": "tone-mid", "low": "tone-low",
    "yes": "tone-high", "monitor": "tone-mid", "ignore": "tone-low",
    "now": "tone-high", "3 months": "tone-mid",
    "6 months": "tone-low", "12 months": "tone-low",
    "small": "tone-low", "large": "tone-high",
}


def _badge(label, value, extra=""):
    if not value:
        return ""
    tone = _RATING_TONE.get(value.strip().lower(), "tone-neutral")
    return (
        f'<span class="badge {tone} {extra}">'
        f'<span class="badge-label">{label}</span>'
        f'<span class="badge-value">{escape_html(value, quote=False)}</span>'
        f'</span>'
    )


def _build_rating_row(d):
    badges = (
        _badge("Strategic importance", d.get("importance", ""))
        + _badge("Time horizon", d.get("horizon", ""))
        + _badge("Executive attention", d.get("attention", ""))
    )
    if not badges:
        return ""
    return f'<div class="badge-row">{badges}</div>'


def _build_action_meta(a):
    badges = (
        _badge("Priority", a.get("priority", ""))
        + _badge("Effort", a.get("effort", ""))
        + _badge("Impact", a.get("impact", ""))
    )
    if not badges:
        return ""
    return f'<div class="badge-row badge-row-action">{badges}</div>'


def _build_roberts_desk(raw_text):
    """The signature section.

    Rendered as ordinary paragraphs, not a pull quote. The old two-sentence
    take was wrapped in curly quotes, which reads as an aside; at 300-450 words
    that framing would undercut the one section the publication is sold on.

    The class names (.roberts-take / .roberts-header / .roberts-body) are load
    bearing — inject_take.py finds and replaces the body through them when the
    reviewer types their own version in the preview page. Renaming them here
    silently breaks that path, and the failure mode is the model's draft
    shipping under Robert's byline.
    """
    cleaned = (raw_text or "").strip()
    cleaned = re.sub(r'^\[.*?\]\s*', '', cleaned, flags=re.DOTALL).strip()
    cleaned = re.sub(r'\*\*(.*?)\*\*', r'\1', cleaned)
    cleaned = re.sub(r'\*(.*?)\*', r'\1', cleaned)

    is_placeholder = (
        not cleaned
        or 'PLACEHOLDER' in cleaned.upper()
        or len(cleaned) < 120
    )

    header = (
        '<div class="roberts-header">'
        '<img src="https://imetrobert.github.io/profile.jpg" alt="Robert Simon">'
        '<div>'
        '<div class="roberts-label">Executive Perspective</div>'
        '<h2 class="roberts-name">From Robert&#39;s Desk</h2>'
        '</div>'
        '</div>'
    )

    if is_placeholder:
        body = (
            '<div class="roberts-placeholder">'
            '<strong><svg class="icon" aria-hidden="true"><use href="#i-pencil"/></svg> '
            'Write this section before publishing.</strong><br><br>'
            'What surprised you this month? What do executives keep getting wrong about it? '
            'What is overhyped, what can wait, and what will matter six months from now? '
            '300-450 words in your own voice. This is the section people subscribe for — '
            'it is also the E-E-A-T signal that separates this from an aggregator.'
            '</div>'
        )
    else:
        paras = [p.strip() for p in re.split(r'\n\s*\n', cleaned) if len(p.strip()) > 25]
        if len(paras) < 2:
            # Single-newline paragraphing, or one long block. Splitting a wall of
            # text on sentence boundaries is worse than leaving it whole, so only
            # the line-break case is recovered.
            paras = [p.strip() for p in cleaned.split('\n') if len(p.strip()) > 25] or [cleaned]
        body = "".join(
            f'<p class="roberts-body">{escape_html(" ".join(p.split()), quote=False)}</p>'
            for p in paras
        )

    return f'<div class="section desk-section"><div class="roberts-take">{header}{body}</div></div>'


