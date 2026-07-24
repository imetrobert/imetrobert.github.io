#!/usr/bin/env python3
"""
generate-preview-page.py
Generates blog/staging/preview.html — the approval UI Robert visits to review,
regenerate with a prompt, or approve and publish his monthly blog post.
"""

import argparse
import os
import sys
import json
from datetime import datetime

# Ensure scripts/ is on the path so `from utils import ...` resolves whether
# this runs via `python3 scripts/generate-preview-page.py` (repo root) or
# `cd scripts && python3 generate-preview-page.py` (as regenerate-blog.yml does).
_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)
sys.path.insert(0, os.path.join(os.getcwd(), 'scripts'))

from utils import get_issue_labels


def build_preview_html(staging_filename: str, month_year: str, run_id: str, regenerated: bool = False) -> str:
    repo = os.environ.get("GITHUB_REPOSITORY", "imetrobert/imetrobert.github.io")

    # `month_year` arrives from the workflow as the COVERAGE month (the real
    # calendar month at generation time, e.g. "June 2026" for a post
    # generated June 30 covering June's news). Derive the reader-facing
    # ISSUE month from it here so this review screen always matches what
    # will actually appear on the published post — see utils.get_issue_labels().
    try:
        coverage_date = datetime.strptime(month_year, "%B %Y")
        issue_labels  = get_issue_labels(coverage_date)
        issue_month_year     = issue_labels["issue_month_year"]
        coverage_month_year  = issue_labels["coverage_month_year"]
        coverage_month_name  = issue_labels["coverage_month_name"]
    except (ValueError, TypeError):
        # Unexpected format — fall back to showing the raw value as-is
        # rather than failing the whole preview page generation.
        issue_month_year    = month_year
        coverage_month_year = month_year
        coverage_month_name = month_year

    regen_badge = ""
    if regenerated:
        regen_badge = '<div class="regen-badge">🔄 Regenerated with custom prompt</div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Review: {issue_month_year} Issue (covers {coverage_month_name}) — Robert Simon</title>
  <style>
    :root {{
      --blue:    #2563eb;
      --cyan:    #06b6d4;
      --navy:    #0f172a;
      --gray:    #475569;
      --light:   #f8fafc;
      --border:  #e2e8f0;
      --green:   #16a34a;
      --red:     #dc2626;
      --amber:   #d97706;
      --white:   #ffffff;
      --shadow:  0 4px 24px rgb(0 0 0 / 0.10);
    }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: 'Inter', -apple-system, sans-serif;
      background: linear-gradient(160deg, #f0f4ff 0%, #e8eef8 100%);
      min-height: 100vh;
      color: var(--navy);
    }}
    .topbar {{
      background: var(--white);
      border-bottom: 1px solid var(--border);
      padding: 1rem 2rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      position: sticky;
      top: 0;
      z-index: 100;
      box-shadow: 0 1px 4px rgb(0 0 0 / 0.06);
    }}
    .topbar-left {{ display: flex; align-items: center; gap: 1rem; }}
    .logo {{ font-weight: 800; font-size: 1.1rem; color: var(--blue); }}
    .issue-label {{
      background: linear-gradient(135deg, var(--blue), var(--cyan));
      color: white;
      font-size: 0.7rem;
      font-weight: 700;
      padding: 0.2rem 0.7rem;
      border-radius: 12px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }}
    .topbar-right {{ display: flex; gap: 0.75rem; align-items: center; }}
    .btn {{
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      padding: 0.6rem 1.25rem;
      border-radius: 10px;
      font-size: 0.875rem;
      font-weight: 600;
      cursor: pointer;
      border: none;
      transition: all 0.2s;
      text-decoration: none;
    }}
    .btn:disabled {{ opacity: 0.5; cursor: not-allowed; }}
    .btn-primary {{
      background: linear-gradient(135deg, var(--green), #15803d);
      color: white;
      box-shadow: 0 2px 8px rgb(22 163 74 / 0.3);
    }}
    .btn-primary:hover:not(:disabled) {{ transform: translateY(-1px); box-shadow: 0 4px 16px rgb(22 163 74 / 0.4); }}
    .btn-secondary {{
      background: linear-gradient(135deg, var(--blue), var(--cyan));
      color: white;
      box-shadow: 0 2px 8px rgb(37 99 235 / 0.2);
    }}
    .btn-secondary:hover:not(:disabled) {{ transform: translateY(-1px); box-shadow: 0 4px 16px rgb(37 99 235 / 0.3); }}
    .btn-outline {{
      background: white;
      color: var(--gray);
      border: 1px solid var(--border);
    }}
    .btn-outline:hover {{ border-color: var(--blue); color: var(--blue); }}
    .btn-force-refresh {{
      background: linear-gradient(135deg, #7c3aed, #6d28d9);
      color: white;
      box-shadow: 0 2px 8px rgb(124 58 237 / 0.3);
    }}
    .btn-force-refresh:hover {{ transform: translateY(-1px); box-shadow: 0 4px 16px rgb(124 58 237 / 0.4); }}
    .btn-force-refresh.spinning svg {{
      animation: spin 0.7s linear infinite;
    }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    .layout {{
      display: grid;
      grid-template-columns: 340px 1fr;
      gap: 0;
      min-height: calc(100vh - 65px);
    }}
    .sidebar {{
      background: var(--white);
      border-right: 1px solid var(--border);
      padding: 1.75rem 1.5rem;
      overflow-y: auto;
      position: sticky;
      top: 65px;
      height: calc(100vh - 65px);
    }}
    .sidebar-section {{ margin-bottom: 2rem; }}
    .sidebar-section h3 {{
      font-size: 0.7rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: #94a3b8;
      margin-bottom: 1rem;
      padding-bottom: 0.5rem;
      border-bottom: 1px solid var(--border);
    }}
    .status-card {{
      background: var(--light);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 1rem;
      margin-bottom: 1rem;
    }}
    .status-row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.8rem;
      margin-bottom: 0.5rem;
    }}
    .status-row:last-child {{ margin-bottom: 0; }}
    .status-label {{ color: var(--gray); }}
    .status-value {{ font-weight: 600; color: var(--navy); font-size: 0.78rem; }}
    .badge-pending {{
      background: #fef3c7;
      color: var(--amber);
      padding: 0.15rem 0.5rem;
      border-radius: 8px;
      font-size: 0.68rem;
      font-weight: 700;
    }}
    .pat-section input {{
      width: 100%;
      padding: 0.6rem 0.875rem;
      border: 1.5px solid var(--border);
      border-radius: 8px;
      font-size: 0.8rem;
      font-family: monospace;
      margin-bottom: 0.5rem;
      transition: border-color 0.2s;
      background: var(--light);
    }}
    .pat-section input:focus {{ outline: none; border-color: var(--blue); background: white; }}
    .pat-hint {{
      font-size: 0.72rem;
      color: #94a3b8;
      line-height: 1.5;
      margin-top: 0.25rem;
    }}
    .pat-hint a {{ color: var(--blue); }}
    .pat-saved {{ display: none; font-size: 0.75rem; color: var(--green); margin-top: 0.25rem; font-weight: 600; }}
    .pat-missing-banner {{
      background: #fef2f2;
      border: 1px solid #fecaca;
      border-radius: 10px;
      padding: 0.875rem 1rem;
      margin-bottom: 0.75rem;
      font-size: 0.78rem;
      color: #991b1b;
      line-height: 1.55;
    }}
    .pat-missing-banner strong {{ display: block; margin-bottom: 0.3rem; color: #7f1d1d; }}
    .pat-missing-banner a.btn {{
      margin-top: 0.6rem;
      width: 100%;
      justify-content: center;
      background: linear-gradient(135deg, var(--red), #b91c1c);
      color: white;
      box-shadow: 0 2px 8px rgb(220 38 38 / 0.25);
    }}
    .pat-missing-banner.attention {{ animation: patPulse 0.9s ease-in-out 2; }}
    @keyframes patPulse {{
      0%, 100% {{ box-shadow: none; }}
      50% {{ box-shadow: 0 0 0 4px rgb(220 38 38 / 0.25); }}
    }}
    .prompt-area {{
      width: 100%;
      min-height: 120px;
      padding: 0.75rem;
      border: 1.5px solid var(--border);
      border-radius: 8px;
      font-size: 0.825rem;
      font-family: inherit;
      line-height: 1.6;
      resize: vertical;
      margin-bottom: 0.75rem;
      transition: border-color 0.2s;
      background: var(--light);
    }}
    .prompt-area:focus {{ outline: none; border-color: var(--blue); background: white; }}
    .prompt-hint {{
      font-size: 0.72rem;
      color: #94a3b8;
      margin-bottom: 0.75rem;
      line-height: 1.5;
    }}
    .prompt-examples {{ margin-bottom: 0.875rem; }}
    .prompt-examples p {{
      font-size: 0.72rem;
      font-weight: 600;
      color: var(--gray);
      margin-bottom: 0.4rem;
    }}
    .prompt-chip {{
      display: inline-block;
      background: #eff6ff;
      color: var(--blue);
      border: 1px solid #bfdbfe;
      padding: 0.2rem 0.6rem;
      border-radius: 8px;
      font-size: 0.7rem;
      cursor: pointer;
      margin: 0.2rem 0.2rem 0.2rem 0;
      transition: all 0.15s;
    }}
    .prompt-chip:hover {{ background: #dbeafe; border-color: var(--blue); }}
    .approve-confirm {{
      font-size: 0.78rem;
      color: var(--gray);
      line-height: 1.6;
      margin-bottom: 0.875rem;
    }}
    .approve-confirm ul {{ padding-left: 1.2rem; margin-top: 0.5rem; }}
    .approve-confirm li {{ margin-bottom: 0.3rem; }}
    .preview-area {{
      padding: 2rem;
      overflow-y: auto;
    }}
    .preview-toolbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 1.25rem;
      flex-wrap: wrap;
      gap: 0.75rem;
    }}
    .preview-toolbar h2 {{
      font-size: 1rem;
      font-weight: 700;
      color: var(--navy);
    }}
    .preview-meta {{ font-size: 0.78rem; color: #94a3b8; }}
    .preview-frame {{
      border: 1px solid var(--border);
      border-radius: 16px;
      overflow: hidden;
      box-shadow: var(--shadow);
      background: white;
      position: relative;
    }}
    .preview-frame iframe {{
      width: 100%;
      height: calc(100vh - 220px);
      border: none;
      display: block;
    }}
    .iframe-loading {{
      display: none;
      position: absolute;
      inset: 0;
      background: rgba(248,250,252,0.85);
      border-radius: 16px;
      align-items: center;
      justify-content: center;
      flex-direction: column;
      gap: 0.75rem;
      z-index: 10;
    }}
    .iframe-loading.show {{ display: flex; }}
    .iframe-loading-spinner {{
      width: 36px; height: 36px;
      border: 3px solid #e2e8f0;
      border-top-color: #7c3aed;
      border-radius: 50%;
      animation: spin 0.7s linear infinite;
    }}
    .iframe-loading-text {{
      font-size: 0.8rem;
      color: var(--gray);
      font-weight: 600;
    }}
    #toast {{
      position: fixed;
      bottom: 2rem;
      left: 50%;
      transform: translateX(-50%) translateY(100px);
      background: var(--navy);
      color: white;
      padding: 0.875rem 1.5rem;
      border-radius: 12px;
      font-size: 0.875rem;
      font-weight: 500;
      z-index: 1000;
      transition: transform 0.3s ease;
      max-width: 480px;
      text-align: center;
      box-shadow: 0 8px 32px rgb(0 0 0 / 0.2);
    }}
    #toast.show {{ transform: translateX(-50%) translateY(0); }}
    #toast.success {{ background: var(--green); }}
    #toast.error   {{ background: var(--red); }}
    #toast.info    {{ background: var(--blue); }}
    #toast.purple  {{ background: #7c3aed; }}
    #overlay {{
      display: none;
      position: fixed;
      inset: 0;
      background: rgba(15,23,42,0.6);
      backdrop-filter: blur(4px);
      z-index: 200;
      align-items: center;
      justify-content: center;
    }}
    #overlay.show {{ display: flex; }}
    .overlay-card {{
      background: white;
      border-radius: 20px;
      padding: 2.5rem;
      max-width: 440px;
      width: 90%;
      text-align: center;
      box-shadow: 0 20px 60px rgb(0 0 0 / 0.2);
    }}
    .overlay-icon {{ font-size: 3rem; margin-bottom: 1rem; }}
    .overlay-title {{ font-size: 1.3rem; font-weight: 700; margin-bottom: 0.5rem; }}
    .overlay-body  {{ font-size: 0.9rem; color: var(--gray); line-height: 1.65; margin-bottom: 1.5rem; }}
    .spinner {{
      width: 40px; height: 40px;
      border: 3px solid #e2e8f0;
      border-top-color: var(--blue);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
      margin: 0 auto 1rem;
    }}
    .regen-badge {{
      background: #fef3c7;
      color: var(--amber);
      border: 1px solid #fde68a;
      padding: 0.4rem 1rem;
      border-radius: 8px;
      font-size: 0.78rem;
      font-weight: 600;
      display: inline-block;
      margin-bottom: 0.75rem;
    }}
    .lock-banner {{
      background: #fffbeb;
      border: 1px solid #fde68a;
      border-radius: 10px;
      padding: 0.875rem 1rem;
      margin-top: 0.75rem;
      font-size: 0.78rem;
      color: #92400e;
      line-height: 1.55;
    }}
    .lock-banner strong {{ display: block; margin-bottom: 0.2rem; color: #78350f; }}
    .lock-banner button {{
      display: block;
      margin-top: 0.6rem;
      background: none;
      border: none;
      color: #92400e;
      font-weight: 700;
      font-size: 0.75rem;
      text-decoration: underline;
      cursor: pointer;
      padding: 0;
    }}
    @media (max-width: 900px) {{
      .layout {{ grid-template-columns: 1fr; }}
      .sidebar {{ position: static; height: auto; border-right: none; border-bottom: 1px solid var(--border); }}
      .preview-frame iframe {{ height: 60vh; }}
    }}
  </style>
</head>
<body>

<div class="topbar">
  <div class="topbar-left">
    <span class="logo">imetrobert.com</span>
    <span class="issue-label">📝 Review: {issue_month_year} &mdash; covers {coverage_month_name}</span>
  </div>
  <div class="topbar-right">
    <a href="https://www.imetrobert.com/blog/" class="btn btn-outline" target="_blank">
      🌐 Live Blog
    </a>
    <button class="btn btn-outline" onclick="openStagingPost()">
      ↗ Open Full Post
    </button>
  </div>
</div>

<div class="layout">

  <div class="sidebar">

    <div class="sidebar-section">
      <h3>Status</h3>
      <div class="status-card">
        <div class="status-row">
          <span class="status-label">Issue</span>
          <span class="status-value">{issue_month_year}</span>
        </div>
        <div class="status-row">
          <span class="status-label">Covers</span>
          <span class="status-value">{coverage_month_name}</span>
        </div>
        <div class="status-row">
          <span class="status-label">File</span>
          <span class="status-value" style="font-family:monospace;font-size:0.7rem;">{staging_filename}</span>
        </div>
        <div class="status-row">
          <span class="status-label">Status</span>
          <span class="badge-pending">⏳ Awaiting approval</span>
        </div>
        <div class="status-row" id="gen-info" style="display:none;">
          <span class="status-label">Generated</span>
          <span class="status-value" id="gen-run">—</span>
        </div>
        <div class="status-row">
          <span class="status-label">Page loaded</span>
          <span class="status-value" id="page-loaded-time">—</span>
        </div>
      </div>
      {regen_badge}
      <div id="lock-banner" style="display:none;">
        <div class="lock-banner">
          <strong>⏳ Regenerating…</strong>
          <span id="lock-banner-text">This page will reload automatically when the new version is ready. Approve and Regenerate are locked until then — the file this page knows about will be replaced.</span>
          <button onclick="location.reload()">🔄 Reload page now</button>
        </div>
      </div>
    </div>

    <div class="sidebar-section pat-section" id="pat-section">
      <h3>GitHub Access Token</h3>
      <div id="pat-missing-banner" style="display:none;">
        <div class="pat-missing-banner">
          <strong>🔑 No token found on this browser</strong>
          <span>Needed to trigger GitHub Actions from this page. This happens after clearing your cache, or on a new browser or device — nothing's wrong, you just need to add one again.</span>
          <a href="https://github.com/settings/tokens/new?scopes=workflow&description=Blog+Preview+Approval" target="_blank" class="btn">
            🔗 Create a token on GitHub
          </a>
        </div>
      </div>
      <input
        type="password"
        id="pat-input"
        placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
        autocomplete="off"
      >
      <div id="pat-saved" class="pat-saved">✓ Token saved in this browser</div>
      <p class="pat-hint">
        Needs <strong>workflow</strong> scope. Saved only in this browser's localStorage — you'll need to re-add it after clearing your cache or on a new browser/device.
        <a href="https://github.com/settings/tokens/new?scopes=workflow&description=Blog+Preview+Approval" target="_blank">Create a token</a>
        if you don't have one handy.
      </p>
      <button class="btn btn-outline" style="width:100%;margin-top:0.5rem;" onclick="savePAT()">
        Save Token
      </button>
    </div>

    <div class="sidebar-section">
      <h3>Regenerate with Prompt</h3>
      <div class="prompt-examples">
        <p>Quick prompts:</p>
        <span class="prompt-chip" onclick="setPrompt('Make the Canadian business impact section more specific to financial services and banking')">More FinServ focus</span>
        <span class="prompt-chip" onclick="setPrompt('Rewrite with a more direct, less corporate tone. Cut all filler phrases.')">Sharper tone</span>
        <span class="prompt-chip" onclick="setPrompt('Add more specific Canadian company examples — Shopify, RBC, Bell, Cohere — throughout the analysis')">More Cdn examples</span>
        <span class="prompt-chip" onclick="setPrompt('Focus this month on agentic AI and autonomous workflows for enterprise. Make it the central theme.')">Agentic AI focus</span>
        <span class="prompt-chip" onclick="setPrompt('Completely rewrite — different angle, fresher insights, less repetitive structure')">Fresh rewrite</span>
      </div>
      <textarea
        id="prompt-input"
        class="prompt-area"
        placeholder="e.g. Make the strategic recommendations more specific to manufacturing. Add more detail on Quebec AI regulation. Cut the intro and get to the insights faster."
      ></textarea>
      <div id="last-prompt-box" style="display:none;background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:0.75rem;margin-bottom:0.75rem;">
        <div style="font-size:0.65rem;font-weight:700;text-transform:uppercase;letter-spacing:0.07em;color:#16a34a;margin-bottom:0.3rem;">Last prompt used</div>
        <div id="last-prompt-text" style="font-size:0.78rem;color:#1e293b;line-height:1.5;"></div>
        <button onclick="reuseLastPrompt()" style="margin-top:0.5rem;font-size:0.7rem;color:#16a34a;background:none;border:none;cursor:pointer;padding:0;font-weight:600;text-decoration:underline;">↩ Reuse this prompt</button>
      </div>
      <p class="prompt-hint">
        Your prompt is passed to Gemini as a refinement topic. The full monthly newsletter format is preserved. Allow ~5 min for generation + GitHub Pages rebuild.
      </p>
      <button class="btn btn-secondary" id="regenerate-btn" style="width:100%;" onclick="triggerRegenerate()">
        🔄 Regenerate Post
      </button>
    </div>

    <div class="sidebar-section">
      <h3>Approve &amp; Publish</h3>
      <p class="approve-confirm">
        Publishing will:
        <ul>
          <li>Move post to <code>blog/posts/</code></li>
          <li>Update <code>latest.html</code></li>
          <li>Regenerate <code>sitemap.xml</code></li>
          <li>Update the blog index page</li>
          <li>Ping Google to recrawl</li>
        </ul>
      </p>
      <button class="btn btn-primary" id="approve-btn" style="width:100%;padding:0.875rem;" onclick="triggerApprove()">
        ✅ Approve &amp; Publish
      </button>
    </div>

  </div>

  <div class="preview-area">
    <div class="preview-toolbar">
      <div>
        <h2>Post Preview — {issue_month_year} <span style="font-weight:400;opacity:0.6;">(covers {coverage_month_name})</span></h2>
        <div class="preview-meta">Staging file: {staging_filename}</div>
      </div>
      <div style="display:flex;gap:0.5rem;align-items:center;">
        <span id="cache-hint" style="font-size:0.72rem;color:#94a3b8;display:none;">Seeing an old version?</span>
        <button class="btn btn-force-refresh" id="force-refresh-btn" onclick="forceRefresh()" title="Bypass cache and reload the latest version">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/>
            <path d="M21 3v5h-5"/>
            <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/>
            <path d="M3 21v-5h5"/>
          </svg>
          Force Refresh
        </button>
      </div>
    </div>
    <div class="preview-frame" id="preview-frame-wrapper">
      <div class="iframe-loading show" id="iframe-loading">
        <div class="iframe-loading-spinner"></div>
        <div class="iframe-loading-text">Loading latest version…</div>
      </div>
      <iframe id="preview-iframe" src="" title="Blog post preview" onload="onIframeLoad()"></iframe>
    </div>
  </div>

</div>

<div id="toast"></div>
<div id="overlay">
  <div class="overlay-card" id="overlay-card"></div>
</div>

<script>
  const REPO          = "{repo}";
  const STAGING_FILE  = "{staging_filename}";
  const ISSUE_MONTH_YEAR    = "{issue_month_year}";
  const COVERAGE_MONTH_YEAR = "{coverage_month_year}";
  const APPROVE_WF    = "approve-blog.yml";
  const REGENERATE_WF = "regenerate-blog.yml";
  const GITHUB_API    = "https://api.github.com";

  // ── Set iframe src with cache-busting timestamp on load ────────
  function setIframeSrc(extraBust) {{
    const iframe = document.getElementById("preview-iframe");
    const ts = extraBust || Date.now();
    iframe.src = `/blog/staging/${{STAGING_FILE}}?v=${{ts}}`;
  }}

  document.addEventListener("DOMContentLoaded", () => {{
    loadPAT();
    loadLastPrompt();
    const runId = "{run_id}";
    if (runId && runId !== "0") {{
      const row = document.getElementById("gen-info");
      const val = document.getElementById("gen-run");
      if (row && val) {{
        row.style.display = "flex";
        val.innerHTML = `<a href="https://github.com/${{REPO}}/actions/runs/${{runId}}" target="_blank" style="color:var(--blue);">Run #${{runId}}</a>`;
      }}
    }}
    // Set iframe src with cache-busting timestamp — fixes blank iframe on slow JS
    setIframeSrc();
    // Show cache hint after 3 seconds in case content looks stale
    setTimeout(() => {{
      document.getElementById("cache-hint").style.display = "inline";
    }}, 3000);
    // Every full page load reflects the true current staging_filename (baked
    // in server-side at generation time) — this timestamp is how you can
    // tell whether THIS page still matches what's actually on GitHub.
    document.getElementById("page-loaded-time").textContent = new Date().toLocaleTimeString();
  }});

  function onIframeLoad() {{
    document.getElementById("iframe-loading").classList.remove("show");
    const btn = document.getElementById("force-refresh-btn");
    btn.classList.remove("spinning");
    btn.disabled = false;
  }}

  // ── Force Refresh — bypasses all browser and CDN cache ─────────
  function forceRefresh() {{
    const btn = document.getElementById("force-refresh-btn");
    btn.classList.add("spinning");
    btn.disabled = true;
    document.getElementById("iframe-loading").classList.add("show");
    showToast("Fetching latest version, bypassing cache…", "purple");

    const bust = Date.now() + "_" + Math.random().toString(36).slice(2);
    setIframeSrc(bust);

    // Safety timeout — re-enable button after 10s in case onload never fires
    setTimeout(() => {{
      btn.classList.remove("spinning");
      btn.disabled = false;
      document.getElementById("iframe-loading").classList.remove("show");
    }}, 10000);
  }}

  // ── PAT management ─────────────────────────────────────────────
  // Shows the loud "no token" banner (with a direct link to GitHub's token
  // creation page) whenever there's nothing saved, and the quiet green
  // checkmark otherwise. Called on load and every time the saved value
  // changes, so clearing your cache / a new browser / a rejected token all
  // land you back at the same clear "here's what to do" state.
  function updatePatUI(saved) {{
    document.getElementById("pat-saved").style.display = saved ? "block" : "none";
    document.getElementById("pat-missing-banner").style.display = saved ? "none" : "block";
    if (saved) document.getElementById("pat-input").value = saved;
  }}

  function flashPatAttention() {{
    document.getElementById("pat-section").scrollIntoView({{ behavior: "smooth", block: "start" }});
    const banner = document.getElementById("pat-missing-banner");
    banner.classList.remove("attention");
    void banner.offsetWidth; // restart the animation if it's already mid-flash
    banner.classList.add("attention");
  }}

  function loadPAT() {{
    const saved = localStorage.getItem("blog_preview_pat");
    updatePatUI(saved);
    return saved || "";
  }}

  // ── Last prompt persistence ─────────────────────────────────────
  const LAST_PROMPT_KEY = "blog_preview_last_prompt";

  function saveLastPrompt(prompt) {{
    localStorage.setItem(LAST_PROMPT_KEY, prompt);
  }}

  function loadLastPrompt() {{
    const saved = localStorage.getItem(LAST_PROMPT_KEY);
    const box = document.getElementById("last-prompt-box");
    const text = document.getElementById("last-prompt-text");
    if (saved && saved.trim()) {{
      text.textContent = saved;
      box.style.display = "block";
    }} else {{
      box.style.display = "none";
    }}
  }}

  function reuseLastPrompt() {{
    const saved = localStorage.getItem(LAST_PROMPT_KEY);
    if (saved) {{
      document.getElementById("prompt-input").value = saved;
      document.getElementById("prompt-input").focus();
      document.getElementById("prompt-input").scrollIntoView({{ behavior: "smooth", block: "center" }});
    }}
  }}

  function savePAT() {{
    const val = document.getElementById("pat-input").value.trim();
    if (!val.startsWith("ghp_") && !val.startsWith("github_pat_")) {{
      showToast("Token should start with ghp_ or github_pat_", "error");
      return;
    }}
    localStorage.setItem("blog_preview_pat", val);
    updatePatUI(val);
    showToast("Token saved in this browser ✓", "success");
  }}

  // ── GitHub Actions trigger ──────────────────────────────────────
  async function triggerWorkflow(workflow, inputs) {{
    const pat = loadPAT();
    if (!pat) {{
      showToast("Please add your GitHub token below first.", "error");
      document.getElementById("pat-input").focus();
      flashPatAttention();
      return null;
    }}
    const url = `${{GITHUB_API}}/repos/${{REPO}}/actions/workflows/${{workflow}}/dispatches`;
    try {{
      const res = await fetch(url, {{
        method: "POST",
        headers: {{
          "Authorization": `Bearer ${{pat}}`,
          "Accept": "application/vnd.github+json",
          "Content-Type": "application/json",
          "X-GitHub-Api-Version": "2022-11-28"
        }},
        body: JSON.stringify({{ ref: "main", inputs }})
      }});
      if (res.status === 401) {{
        // Confirmed dead — don't leave the misleading green "✓ Token saved"
        // checkmark up for a token GitHub just rejected.
        localStorage.removeItem("blog_preview_pat");
        updatePatUI(null);
        flashPatAttention();
      }}
      return res;
    }} catch (err) {{
      // Network drop, DNS failure, offline, blocked request — fetch throws
      // rather than resolving, so without this the loading overlay would
      // spin forever with no explanation.
      hideOverlay();
      showToast("Network error contacting GitHub — check your connection and try again.", "error");
      return null;
    }}
  }}

  function apiErrorMessage(res, body) {{
    if (res.status === 401) return "GitHub rejected the token (401) — it's invalid or expired, so it's been cleared from this browser. See the banner in the sidebar to get a new one.";
    if (res.status === 403) return `GitHub returned 403 — the token likely lacks 'workflow' scope. ${{body.message || ""}}`;
    if (res.status === 404) return "GitHub returned 404 — check the token has 'workflow' scope and that all three workflow files are committed to the main branch.";
    return `GitHub API returned ${{res.status}}: ${{body.message || "Unknown error"}}.`;
  }}

  // ── Lock/unlock Approve + Regenerate while a workflow run is in
  // flight, or while this page's known staging_filename may be stale
  // (a regenerate can rename the file — see startPolling). Only a full
  // page reload can safely re-establish which filename is current, so
  // unlocking happens via reload, not a timer.
  let published = false;
  function lockButtons(message) {{
    document.getElementById("regenerate-btn").disabled = true;
    document.getElementById("approve-btn").disabled = true;
    const banner = document.getElementById("lock-banner");
    if (message) document.getElementById("lock-banner-text").innerHTML = message;
    banner.style.display = "block";
  }}
  function unlockButtons() {{
    if (published) return;
    document.getElementById("regenerate-btn").disabled = false;
    document.getElementById("approve-btn").disabled = false;
    document.getElementById("lock-banner").style.display = "none";
  }}

  // ── Approve ─────────────────────────────────────────────────────
  async function triggerApprove() {{
    showOverlay("confirming");
  }}

  async function confirmApprove() {{
    hideOverlay();
    lockButtons("Publishing… Approve and Regenerate are locked while this runs.");
    showOverlay("loading", "Publishing...", "Triggering the publish workflow on GitHub Actions.");
    const res = await triggerWorkflow(APPROVE_WF, {{
      staging_filename: STAGING_FILE,
      month_year: ISSUE_MONTH_YEAR
    }});
    if (!res) {{ unlockButtons(); return; }}
    if (res.status === 204) {{
      published = true;
      document.getElementById("lock-banner-text").innerHTML = "✅ Published. This staging file no longer exists, so Approve and Regenerate stay locked on this page — visit the live blog to see the post, or generate a new draft next month.";
      showOverlay("success",
        "🎉 Post queued for publishing!",
        "The approve-blog workflow is now running. Your post will be live in ~2 minutes.",
        `https://github.com/${{REPO}}/actions/workflows/${{APPROVE_WF}}`
      );
    }} else {{
      const body = await res.json().catch(() => ({{}}));
      unlockButtons();
      showOverlay("error", "Publish failed", apiErrorMessage(res, body));
    }}
  }}

  // ── Regenerate ──────────────────────────────────────────────────
  async function triggerRegenerate() {{
    const prompt = document.getElementById("prompt-input").value.trim();
    if (!prompt) {{
      showToast("Please enter a prompt describing what to change.", "error");
      document.getElementById("prompt-input").focus();
      return;
    }}
    saveLastPrompt(prompt);
    // Locked immediately, before the network round-trip: regeneration almost
    // always produces a NEW staging filename (it's stamped with today's
    // date), which orphans the filename this page currently knows about.
    // Approving or re-triggering against that stale value fails or, worse,
    // targets the wrong file — so both actions stay locked until a full
    // page reload picks up the real current state.
    lockButtons();
    showOverlay("loading", "🔄 Triggering regeneration...",
      "GitHub Actions will regenerate the post with your prompt. This takes ~5 minutes. This page will reload itself automatically once the new version is live."
    );
    const res = await triggerWorkflow(REGENERATE_WF, {{
      prompt: prompt,
      staging_filename: STAGING_FILE,
      coverage_month: COVERAGE_MONTH_YEAR
    }});
    if (!res) {{ hideOverlay(); unlockButtons(); return; }}
    if (res.status === 204) {{
      startPolling();
      showOverlay("regen-queued", "⏳ Regeneration queued!",
        "This page checks every 15s for up to 10 min and reloads itself the moment the new version is live — you can close this dialog and it'll keep watching.",
        `https://github.com/${{REPO}}/actions/workflows/${{REGENERATE_WF}}`
      );
    }} else {{
      const body = await res.json().catch(() => ({{}}));
      hideOverlay();
      unlockButtons();
      showToast(apiErrorMessage(res, body), "error");
    }}
  }}

  // ── Prompt chips ────────────────────────────────────────────────
  function setPrompt(text) {{
    document.getElementById("prompt-input").value = text;
    document.getElementById("prompt-input").focus();
  }}

  function openStagingPost() {{
    const bust = Date.now() + "_" + Math.random().toString(36).slice(2);
    window.open(`/blog/staging/${{STAGING_FILE}}?v=${{bust}}`, "_blank");
  }}

  // ── Toast ────────────────────────────────────────────────────────
  let toastTimer;
  function showToast(msg, type = "info") {{
    const el = document.getElementById("toast");
    el.textContent = msg;
    el.className = `show ${{type}}`;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {{ el.className = ""; }}, 4000);
  }}

  // ── Overlay ──────────────────────────────────────────────────────
  function showOverlay(type, title = "", body = "", actionUrl = "") {{
    const card = document.getElementById("overlay-card");
    const overlay = document.getElementById("overlay");
    let html = "";
    if (type === "confirming") {{
      html = `
        <div class="overlay-icon">📤</div>
        <div class="overlay-title">Ready to publish?</div>
        <div class="overlay-body">This will publish <code>${{STAGING_FILE}}</code> — promote it to production, update <code>latest.html</code>, regenerate the sitemap, and ping Google. Double-check that filename matches what you've been reviewing in the frame on the right — if you regenerated recently and haven't reloaded this page, it may not.</div>
        <div style="display:flex;gap:0.75rem;justify-content:center;">
          <button class="btn btn-outline" onclick="hideOverlay()">Cancel</button>
          <button class="btn btn-primary" onclick="confirmApprove()">Yes, Publish Now</button>
        </div>`;
    }} else if (type === "loading") {{
      html = `<div class="spinner"></div><div class="overlay-title">${{title}}</div><div class="overlay-body">${{body}}</div>`;
    }} else if (type === "success") {{
      html = `
        <div class="overlay-icon">✅</div>
        <div class="overlay-title">${{title}}</div>
        <div class="overlay-body">${{body}}</div>
        <div style="display:flex;gap:0.75rem;justify-content:center;flex-wrap:wrap;">
          ${{actionUrl ? `<a href="${{actionUrl}}" target="_blank" class="btn btn-secondary">View Workflow Run</a>` : ""}}
          <a href="https://www.imetrobert.com/blog/" target="_blank" class="btn btn-primary">View Live Blog</a>
          <button class="btn btn-outline" onclick="hideOverlay()">Close</button>
        </div>`;
    }} else if (type === "regen-queued") {{
      html = `
        <div class="overlay-icon">⏳</div>
        <div class="overlay-title">${{title}}</div>
        <div class="overlay-body">${{body}}</div>
        <div style="display:flex;gap:0.75rem;justify-content:center;flex-wrap:wrap;">
          ${{actionUrl ? `<a href="${{actionUrl}}" target="_blank" class="btn btn-secondary">Watch Workflow</a>` : ""}}
          <button class="btn btn-outline" onclick="hideOverlay()">Dismiss (still watching)</button>
        </div>`;
    }} else if (type === "error") {{
      html = `
        <div class="overlay-icon">❌</div>
        <div class="overlay-title">${{title}}</div>
        <div class="overlay-body">${{body}}</div>
        <button class="btn btn-outline" onclick="hideOverlay()">Close</button>`;
    }}
    card.innerHTML = html;
    overlay.classList.add("show");
  }}

  function hideOverlay() {{
    document.getElementById("overlay").classList.remove("show");
  }}

  // ── Auto-refresh polling after regeneration ─────────────────────
  // Polls the freshly-pushed preview.html itself (not the iframe) and, once
  // it sees the regen badge, does a FULL page reload — not just an iframe
  // refresh. Regeneration renames the staging file (new date-stamped
  // filename) essentially every time, so only a real reload of this parent
  // page picks up the new STAGING_FILE constant baked in server-side.
  // Refreshing just the iframe would leave Approve pointed at a filename
  // that's already been deleted.
  let pollInterval;
  function startPolling() {{
    if (pollInterval) return; // already watching — don't stack intervals
    let checks = 0;
    pollInterval = setInterval(async () => {{
      checks++;
      if (checks > 40) {{
        clearInterval(pollInterval);
        pollInterval = null;
        lockButtons(
          `Regeneration is taking longer than 10 minutes or may have failed. ` +
          `<a href="https://github.com/${{REPO}}/actions/workflows/${{REGENERATE_WF}}" target="_blank">Check the Actions tab</a>, ` +
          `then reload once you've confirmed it finished.`
        );
        showToast("Stopped auto-checking — see the sidebar for what to do next.", "error");
        return;
      }}
      try {{
        const r = await fetch(`/blog/staging/preview.html?nocache=${{Date.now()}}`, {{ cache: "no-store" }});
        const text = await r.text();
        if (text.includes("🔄 Regenerated with custom prompt")) {{
          clearInterval(pollInterval);
          pollInterval = null;
          showToast("✅ New version ready! Reloading page…", "success");
          setTimeout(() => location.reload(), 1200);
        }}
      }} catch (e) {{}}
    }}, 15000);
  }}
</script>

</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--filename",    required=True, help="Staging HTML filename")
    parser.add_argument("--month",       required=True, help="Month year label, e.g. May 2026")
    parser.add_argument("--run-id",      default="0",   help="GitHub Actions run ID")
    parser.add_argument("--regenerated", action="store_true", help="Flag post as regenerated")
    args = parser.parse_args()

    html = build_preview_html(
        staging_filename=args.filename,
        month_year=args.month,
        run_id=args.run_id,
        regenerated=args.regenerated
    )

    os.makedirs("blog/staging", exist_ok=True)
    output_path = "blog/staging/preview.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Preview page written to: {output_path}")


if __name__ == "__main__":
    main()
