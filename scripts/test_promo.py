#!/usr/bin/env python3
"""Offline tests for scripts/promo_kit.py, scripts/reply_helper.py and their cards (stubbed model)."""
import json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import promo_kit as pk
import reply_helper as rh
import write_nothing_pending_placeholder as ph

fails = []
def check(name, ok):
    print(("ok   " if ok else "FAIL ") + name)
    if not ok: fails.append(name)

P = "Small businesses can now get more from the plan they already pay for.\n\n" + "Here is one thing that matters for your week and your quotes. " * 12 + "\n\nWhat eats your week?\n\n#SmallBusiness #AI"
FR = "Les PME peuvent tirer plus de leur abonnement.\n\n" + "Voici ce qui compte pour votre semaine et vos soumissions. " * 14 + "\n\nQu'est-ce qui vous prend le plus de temps?\n\n#PME #IA"
hooks_fr = f"HOOKS:\n1. Your AI plan can do more than you think\n2. One change that saves an hour a week\n3. Are you paying for features you never use?\nFRENCH POST:\n{FR}\nFRENCH COMMENT:\nLe numéro complet est en anglais, je vous invite à le lire ce mois-ci."
def drip_raw(page="subs", post=P):
    out = ""
    for n in (1, 2, 3):
        out += f"POST {n}:\n{post}\nPAGE {n}:\n{page}\nCOMMENT {n}:\nI wrote more about this on the Business site.\n"
    return out

check("campaign names", pk.campaign("2026-12-03-x.html") == "issue-2026-12" and pk.campaign("2026-12-03-x.html", 2) == "issue-2026-12-d2")
link = pk.biz_link("subs", "en", "issue-2026-12-d1")
check("service link carries source and campaign", "/articles/get-more-from-your-ai-subscriptions/" in link and "utm_source=linkedin" in link and "utm_campaign=issue-2026-12-d1" in link)
check("french link uses /fr/ path", "/fr/articles/tirer-plus-de-vos-abonnements-ia/" in pk.biz_link("subs", "fr", "c"))
hooks, fr_post, fr_c = pk.parse_hooks_french(hooks_fr)
check("parses 3 hooks, French post and comment", len(hooks) == 3 and fr_post.startswith("Les PME") and fr_c)
for name, bad in (("rejects 2 hooks", hooks_fr.replace("3. Are you paying for features you never use?\n", "")),
                  ("rejects link in French post", hooks_fr.replace("Voici", "https://x.com Voici")),
                  ("rejects invented own data in French", hooks_fr.replace("Voici ce", "Mes clients disent que ce")),
                  ("rejects missing labels", "nothing useful")):
    try: pk.parse_hooks_french(bad); check(name, False)
    except ValueError: check(name, True)
d = pk.parse_drip(drip_raw(), "2026-12-03-x.html")
check("drip has 3 posts on days 8/15/22 with the program-added link", [x["day"] for x in d] == [8, 15, 22] and d[0]["comment"].endswith(d[0]["link"]) and "utm_campaign=issue-2026-12-d3" in d[2]["link"])
for name, bad in (("rejects unknown page id", drip_raw("blog")), ("rejects link in drip post", drip_raw(post=P.replace("Here", "see http://a.b Here")))):
    try: pk.parse_drip(bad, "2026-12-03-x.html"); check(name, False)
    except ValueError: check(name, True)

cwd = os.getcwd(); os.chdir(tempfile.mkdtemp())
os.makedirs("blog/posts"); os.makedirs("blog/staging")
open("blog/posts/2026-12-03-x.html", "w").write('<html><body><h1>AI Insights for December 2026</h1><div class="article-content"><p>' + "Plan prices fell. " * 40 + "</p></div></body></html>")
json.dump({"post_file": "2026-12-03-x.html", "title": "t", "post": P, "first_comment": "c", "generated_at": "2026-12-03T10:00:00+00:00", "history": []}, open("blog/staging/linkedin.json", "w"))
calls = []
def fake(prompt):
    calls.append(prompt)
    return hooks_fr if "HOOKS:" in prompt and "REPLY 1" not in prompt else drip_raw()
data = pk.generate("2026-12-03-x.html", call=fake)
check("generate writes promo.json", os.path.exists("blog/staging/promo.json") and len(data["drip"]) == 3 and data["published"] == "2026-12-03")
check("french comment gets the French feasibility link", "/fr/?utm_source=linkedin" in data["french"]["first_comment"] and "issue-2026-12-fr" in data["french"]["link"])
check("prompts carry the audience and the menu", "5 to 20 people" in calls[0] and "get-more" not in calls[1] and "subs:" in calls[1])
json.dump({"post_file": "other.html", "post": P}, open("blog/staging/linkedin.json", "w"))
try: pk.generate("2026-12-03-x.html", call=fake); check("refuses a main post from another issue", False)
except ValueError: check("refuses a main post from another issue", True)

R = "REPLY 1:\nThanks for reading, glad it helped.\nREPLY 2:\nGood point. The issue notes the plan change applies to teams too, which matters for quotes.\nREPLY 3:\nThanks. Which task eats most of your week?"
check("reply helper parses 3 options", len(rh.parse(R)) == 3)
for name, bad in (("reply rejects a link", R.replace("Thanks for", "see http://x.y Thanks for")), ("reply rejects own-data claims", R.replace("Good point.", "My clients agree.")), ("reply rejects missing option", "REPLY 1:\nok fine thanks")):
    try: rh.parse(bad); check(name, False)
    except ValueError: check(name, True)
rd = rh.generate("Great post, but is it really worth the money?", "", call=lambda p: R)
check("reply helper writes reply.json", rd["replies"][2].startswith("Thanks. Which") and os.path.exists("blog/staging/reply.json"))

li = {"post_file": "2026-12-03-x.html", "title": "t", "post": P, "first_comment": "c", "generated_at": "g"}
html_missing = ph.build_html("Dec 31", ("2026-12-03-x.html", "December 2026"), li)
check("page offers to build the promo kit when none exists", "Build the promo kit" in html_missing and "askReply(" in html_missing)
html_full = ph.build_html("Dec 31", ("2026-12-03-x.html", "December 2026"), li, data, rd)
check("page shows hooks, French, 3 follow-ups, reminders", html_full.count("pk-p") >= 3 and "pk-fr" in html_full and "pk-h3" in html_full and html_full.count("addReminder(this)") == 3 and "BEGIN:VCALENDAR" in html_full)
check("reminder dates are published date plus offset", "DTSTART:20261211T090000" in html_full and "DTSTART:20261218T090000" in html_full)
os.chdir(cwd)
print("\nALL PASSED" if not fails else f"\n{len(fails)} FAILED")
sys.exit(1 if fails else 0)
