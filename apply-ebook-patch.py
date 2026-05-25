#!/usr/bin/env python3
"""
apply-ebook-patch.py
====================
Run this from the root of your imetrobert GitHub repo:
  python3 apply-ebook-patch.py

It replaces the single-edition ebook section in index.html
with the new dual-edition layout (2027 Edition primary, 2023 First Edition
as a credibility/backstory secondary).
"""

OLD = """     <section class="content-section ebook-section fade-in">
      <div class="ebook-content">
       <img alt="AI Business Guide Cover" class="ebook-cover" src="https://public-files.gumroad.com/5ex95xj692a4vdvx4ccl1tdnq70l"/>
       <div class="ebook-text">
        <h3>
         AI Business Guide
        </h3>
        <p>
         Get my comprehensive guide on implementing AI in Canadian businesses at an affordable price. Learn practical strategies, real-world case studies, and actionable insights from 25+ years in digital innovation.
        </p>
        <a class="ebook-link" href="https://robertino65.gumroad.com/l/ai-marketing-canada" target="_blank">
         💰 Get Your Copy Now
        </a>
       </div>
      </div>
      <div class="ai-circuit">
      </div>
     </section>"""

NEW = """     <!-- ═══ EBOOK: 2nd Edition primary, 1st Edition credibility ═══ -->
     <style>
       .edition-new-badge {
         display: inline-flex; align-items: center;
         background: rgba(255,255,255,0.2); border: 1px solid rgba(255,255,255,0.3);
         padding: 0.25rem 0.8rem; border-radius: 20px;
         font-size: 0.68rem; font-weight: 700; letter-spacing: 0.08em;
         text-transform: uppercase; color: white; margin-bottom: 1.1rem;
       }
       .edition-main {
         display: grid; grid-template-columns: 120px 1fr;
         gap: 1.5rem; align-items: flex-start;
         position: relative; z-index: 2;
       }
       .edition-cover-wrap { position: relative; flex-shrink: 0; }
       .edition-cover {
         width: 120px; height: 160px; border-radius: 8px;
         box-shadow: 0 12px 35px rgba(0,0,0,0.4), 0 0 0 2px rgba(255,255,255,0.12);
         object-fit: cover; display: block; transition: transform 0.3s ease;
       }
       .edition-cover:hover { transform: scale(1.04) rotateY(4deg); }
       .edition-2-badge {
         position: absolute; top: -8px; right: -8px;
         background: #fbbf24; color: #1e293b;
         font-size: 0.58rem; font-weight: 800;
         padding: 0.2rem 0.5rem; border-radius: 6px; letter-spacing: 0.04em;
         box-shadow: 0 2px 8px rgba(0,0,0,0.2);
       }
       .edition-title { font-size: 1.25rem; font-weight: 700; color: white; margin-bottom: 0.2rem; }
       .edition-label { font-size: 0.72rem; opacity: 0.75; margin-bottom: 0.7rem; font-style: italic; }
       .edition-features { list-style: none; padding: 0; margin: 0 0 1.1rem; }
       .edition-features li {
         font-size: 0.8rem; opacity: 0.92; display: flex;
         align-items: flex-start; gap: 0.4rem; margin-bottom: 0.3rem; line-height: 1.35;
       }
       .edition-features li::before { content: "¹3"; color: #6ee7b7; font-weight: 700; flex-shrink: 0; margin-top: 0.05rem; }
       .edition-cta {
         background: white; color: var(--primary-blue);
         padding: 0.6rem 1.35rem; border-radius: 25px;
         text-decoration: none; font-weight: 700; font-size: 0.875rem;
         display: inline-flex; align-items: center; gap: 0.4rem;
         transition: all 0.3s ease; box-shadow: 0 4px 15px rgba(0,0,0,0.2);
       }
       .edition-cta:hover { transform: translateY(-2px); box-shadow: 0 8px 25px rgba(0,0,0,0.3); }
       .edition-price {
         display: inline-block; background: rgba(37,99,235,0.12);
         border-radius: 10px; padding: 0.1rem 0.5rem;
         font-size: 0.78rem; font-weight: 700; margin-left: 0.3rem; vertical-align: middle;
       }
       .edition-divider {
         border: none; border-top: 1px solid rgba(255,255,255,0.15); margin: 1.25rem 0;
         position: relative; z-index: 2;
       }
       .edition-prev {
         display: grid; grid-template-columns: 52px 1fr;
         gap: 0.875rem; align-items: center;
         background: rgba(0,0,0,0.18); border-radius: 12px;
         padding: 0.875rem 1rem; position: relative; z-index: 2;
       }
       .edition-prev-cover {
         width: 52px; height: 69px; border-radius: 5px; object-fit: cover;
         opacity: 0.65; filter: grayscale(25%);
         box-shadow: 0 4px 12px rgba(0,0,0,0.3); display: block;
       }
       .edition-prev .prev-label {
         font-size: 0.6rem; font-weight: 700; letter-spacing: 0.08em;
         text-transform: uppercase; opacity: 0.5; margin-bottom: 0.15rem;
       }
       .edition-prev h4 { font-size: 0.85rem; font-weight: 600; margin-bottom: 0.15rem; opacity: 0.8; color: white; }
       .edition-prev p { font-size: 0.7rem; opacity: 0.5; margin-bottom: 0.45rem; line-height: 1.35; color: white; }
       .edition-prev-link {
         color: rgba(255,255,255,0.55); font-size: 0.72rem; font-weight: 600;
         text-decoration: none; border-bottom: 1px solid rgba(255,255,255,0.2);
         transition: all 0.2s;
       }
       .edition-prev-link:hover { color: white; }
       @media (max-width: 480px) {
         .edition-main { grid-template-columns: 90px 1fr; gap: 1rem; }
         .edition-cover { width: 90px; height: 120px; }
       }
     </style>

     <section class="content-section ebook-section fade-in">

       <!-- NEW RELEASE BADGE -->
       <div class="edition-new-badge">&#11088; New Release &nbsp;&middot;&nbsp; 2027 Edition</div>

       <!-- 2ND EDITION — PRIMARY -->
       <div class="edition-main">
         <div class="edition-cover-wrap">
           <img
             class="edition-cover"
             src="https://imetrobert.github.io/cover-2027.png"
             alt="AI Marketing Launch Kit 2027 Edition"
             onerror="this.src='https://public-files.gumroad.com/5ex95xj692a4vdvx4ccl1tdnq70l'"
           />
           <span class="edition-2-badge">2ND ED.</span>
         </div>
         <div>
           <div class="edition-title">AI Marketing Launch Kit</div>
           <div class="edition-label">Canada Edition &nbsp;&middot;&nbsp; 2027 &nbsp;&middot;&nbsp; 34 pages</div>
           <ul class="edition-features">
             <li><strong>New:</strong> Agentic AI &mdash; full chapter</li>
             <li><strong>New:</strong> AI ROI Measurement Framework</li>
             <li>20 Canadian use cases across 10 sectors</li>
             <li>AIDA, Bill C-27 &amp; Bill 96 updated</li>
             <li>Tools &amp; pricing in CAD</li>
           </ul>
           <a
             class="edition-cta"
             href="https://robertino65.gumroad.com/l/AIkit2027"
             target="_blank"
             rel="noopener"
           >
             &#x1F4B0; Get the 2027 Edition
             <span class="edition-price">$24.97 CAD</span>
           </a>
           <p style="margin-top:0.6rem; font-size:0.68rem; opacity:0.65; line-height:1.4;">
             &#128214; Available in English only &nbsp;&middot;&nbsp; Ce livre est disponible en anglais seulement
           </p>
         </div>
       </div>

       <hr class="edition-divider">

       <!-- 1ST EDITION — SECONDARY / CREDIBILITY -->
       <div class="edition-prev">
         <img
           class="edition-prev-cover"
           src="https://public-files.gumroad.com/5ex95xj692a4vdvx4ccl1tdnq70l"
           alt="AI Marketing Launch Kit First Edition"
         />
         <div>
           <div class="prev-label">Where it started &nbsp;&middot;&nbsp; First Edition 2023</div>
           <h4>AI Marketing Launch Kit</h4>
           <p>The original guide that introduced the framework. Still available for readers starting their AI journey.</p>
           <a
             class="edition-prev-link"
             href="https://robertino65.gumroad.com/l/ai-marketing-canada"
             target="_blank"
             rel="noopener"
           >
             Also available &mdash; First Edition $9.98 CAD &rarr;
           </a>
         </div>
       </div>

       <div class="ai-circuit"></div>
     </section>"""

import sys

with open("index.html", "r", encoding="utf-8") as f:
    src = f.read()

if OLD not in src:
    print("ERROR: could not find the old ebook section in index.html.")
    print("The section may have already been updated, or whitespace differs.")
    sys.exit(1)

updated = src.replace(OLD, NEW, 1)

with open("index.html", "w", encoding="utf-8") as f:
    f.write(updated)

print("SUCCESS: index.html updated with 2027 Edition as primary ebook.")
print("Next steps:")
print("  git add index.html")
print('  git commit -m "Homepage: 2027 Edition primary, 1st edition as credibility item"')
print("  git push")
