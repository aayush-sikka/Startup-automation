"""
agent.py  — Assignment 3: Automated Startup Outreach System  (Google ADK)
==========================================================================
Five tools mapping exactly to the 5 assignment tasks:

  Tool 1: discover_startups_tool        → Task 1 (Discovery, 50+ startups)
  Tool 2: classify_and_filter_tool      → Task 2 (Filter by industry)
  Tool 3: enrich_startups_tool          → Task 3 (Enrichment)
  Tool 4: generate_outreach_tool        → Task 4 (Message generation)
  Tool 5: export_to_excel_tool          → Export + Task 5 (Sending layer notes)

Setup:
  pip install google-adk google-search-results requests beautifulsoup4 lxml python-dotenv openpyxl

.env (project root):
  SERPAPI_KEY=...        # Required
  GOOGLE_API_KEY=...     # Required (Gemini)
  HUNTER_API_KEY=...     # Optional — boosts email accuracy
  CLEARBIT_API_KEY=...   # Optional — boosts company metadata

Run:
  adk run phase6_startup_discovery/agent.py
  adk web
"""

import os, sys, json
from typing import List, Optional

# ── Path setup ────────────────────────────────────────────────────────────────
_this_dir   = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_this_dir)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from google.adk.agents import Agent

from phase6_startup_discovery.startup_scrapers import (
    find_startups_complete,
    search_startups_google,
    filter_by_industry,
    calculate_accuracy_score,
)
from phase6_startup_discovery.message_generator import add_messages_to_all
from phase6_startup_discovery.excel_exporter import export_to_excel


# ── In-memory session store (shared across tool calls in one session) ─────────
_SESSION: dict = {"startups": []}


# ============================================================================
# TOOL 1 — Company Discovery  (Task 1: 50+ startups)
# ============================================================================

def discover_startups_tool(
    query: str = "new Indian startups 2025 2026",
    location: str = "India",
    target_count: int = 55,
    year: str = "2025 2026",
) -> dict:
    """
    Task 1 — Discover at least 50 newly registered Indian startups.

    Sources used (multi-source approach):
      • Google Search via SerpAPI (11 targeted query templates)
      • Accelerator signals: Y Combinator, Antler India, Sequoia Surge, 100X.VC
      • Funding signals: seed, pre-seed, Series A mentions
      • DPIIT recognition signals
      • Website scraping for enrichment

    Args:
        query:        Primary search terms (default covers 2025/2026)
        location:     Country filter (default: "India")
        target_count: Minimum startups to find (default: 55 — leaves buffer above 50)
        year:         Year filter for queries (default: "2025 2026")

    Returns:
        dict with total discovered, breakdown by industry, and startup list
    """
    result = find_startups_complete(
        query=query,
        location=location,
        max_results=target_count,
        enrich_data=True,
        year=year,
    )

    if result.get("status") == "error":
        return {"status": "error", "message": result.get("message")}

    startups = result.get("startups", [])
    _SESSION["startups"] = startups   # cache for subsequent tools

    # Industry breakdown
    from collections import Counter
    industry_counts = dict(Counter(s.get("industry", "Other") for s in startups))

    return {
        "status":           "success",
        "task":             "Task 1 — Company Discovery",
        "total_discovered": len(startups),
        "target":           target_count,
        "meets_requirement": len(startups) >= 50,
        "by_industry":      industry_counts,
        "avg_accuracy":     round(sum(s.get("accuracy_score",0) for s in startups) / max(len(startups),1), 1),
        "note":             "Data cached in session. Run classify_and_filter_tool next.",
    }


# ============================================================================
# TOOL 2 — Classification & Filter  (Task 2)
# ============================================================================

def classify_and_filter_tool(
    industry: str = "Fintech",
    min_accuracy: int = 0,
) -> dict:
    """
    Task 2 — Filter discovered startups by industry/domain.

    Supported industries: Fintech, SaaS, D2C, HealthTech, EdTech, Mobility, Other

    Classification uses keyword matching across company name, description,
    and problem statement. Industry labels are assigned automatically during
    discovery — this tool filters to a specific category.

    Args:
        industry:     Industry to filter by (default: "Fintech" per assignment)
        min_accuracy: Optional minimum accuracy score filter (default: 0 = show all)

    Returns:
        dict with filtered startup list and count
    """
    startups = _SESSION.get("startups", [])
    if not startups:
        return {"status": "error", "message": "No startups in session. Run discover_startups_tool first."}

    filtered = filter_by_industry(startups, industry)
    if min_accuracy > 0:
        filtered = [s for s in filtered if s.get("accuracy_score", 0) >= min_accuracy]

    return {
        "status":       "success",
        "task":         "Task 2 — Classification & Filter",
        "industry":     industry,
        "total_in_category": len(filtered),
        "total_all":    len(startups),
        "startups":     filtered,
        "note":         f"Showing {industry} startups. Change `industry` param to filter by other sectors.",
    }


# ============================================================================
# TOOL 3 — Enrichment Summary  (Task 3)
# ============================================================================

def enrich_startups_tool(
    min_accuracy: int = 30,
) -> dict:
    """
    Task 3 — Show enriched startup data with all required fields.

    Enrichment fields per startup:
      • Founder name(s)
      • Official website
      • Contact email (from Hunter.io, website scraping, or SerpAPI)
      • Industry and sub-sector
      • Product description / problem being solved
      • Target customers (inferred)
      • Location
      • Startup stage (Pre-Seed / Seed / Post-Seed / Growth)

    This tool shows enrichment quality stats and lists startups that
    meet the minimum requirement (founder + email + 2-3 context fields).

    Args:
        min_accuracy: Minimum accuracy score to include (default: 30)

    Returns:
        Enrichment statistics and startup list with all fields populated
    """
    startups = _SESSION.get("startups", [])
    if not startups:
        return {"status": "error", "message": "No startups in session. Run discover_startups_tool first."}

    filtered = [s for s in startups if s.get("accuracy_score", 0) >= min_accuracy]

    # Check minimum requirement: founder + email + 2 context fields
    meets_min = []
    for s in filtered:
        has_founder = bool(s.get("founders"))
        has_email   = bool(s.get("founder_emails") or s.get("contact_emails"))
        context_fields = sum(1 for f in ["description","industry","stage","location","founded_year","problem_statement"]
                             if s.get(f) and s.get(f) not in ("N/A","Unknown",""))
        if has_founder and has_email and context_fields >= 2:
            meets_min.append(s)

    return {
        "status":              "success",
        "task":                "Task 3 — Company Enrichment",
        "total_enriched":      len(filtered),
        "meets_min_requirement": len(meets_min),
        "min_requirement":     "Founder name + contact email + 2 context fields",
        "with_founders":       sum(1 for s in filtered if s.get("founders")),
        "with_email":          sum(1 for s in filtered if s.get("founder_emails") or s.get("contact_emails")),
        "with_description":    sum(1 for s in filtered if s.get("description","") not in ("N/A","")),
        "with_problem_stmt":   sum(1 for s in filtered if s.get("problem_statement")),
        "with_stage":          sum(1 for s in filtered if s.get("stage")),
        "startups":            filtered,
    }


# ============================================================================
# TOOL 4 — Message Generation  (Task 4)
# ============================================================================

def generate_outreach_tool(
    industry_filter: Optional[str] = None,
    max_messages: int = 55,
) -> dict:
    """
    Task 4 — Generate personalized outreach messages for each startup.

    For each startup generates:
      A) Email outreach: 80-120 words
         - Industry-aware opening (Fintech → compliance/onboarding pain points)
         - Personalized with founder name, company name, accelerator if known
         - References problem statement from website if available
         - Value-driven (not templated spam)

      B) WhatsApp short pitch: 25-40 words
         - Punchy and conversational
         - Mentions specific industry pain point

    Personalization signals:
      • Startup domain (industry-specific pain points)
      • Founder name (first name basis)
      • Accelerator / funding (Y Combinator, Antler, Surge, etc.)
      • Problem statement scraped from website

    Args:
        industry_filter: Optional — only generate for one industry (e.g. "Fintech")
        max_messages:    Max number of messages to generate (default: 55)

    Returns:
        Startups with outreach_email and outreach_whatsapp fields added
    """
    startups = _SESSION.get("startups", [])
    if not startups:
        return {"status": "error", "message": "No startups in session. Run discover_startups_tool first."}

    to_process = startups
    if industry_filter:
        to_process = filter_by_industry(startups, industry_filter)

    to_process = to_process[:max_messages]
    to_process = add_messages_to_all(to_process)

    # Update session
    updated_ids = {id(s) for s in to_process}
    for s in _SESSION["startups"]:
        if id(s) in updated_ids:
            pass   # already mutated in place by add_messages_to_all

    # Sample preview (first 3)
    preview = []
    for s in to_process[:3]:
        preview.append({
            "company":   s.get("name"),
            "industry":  s.get("industry"),
            "founder":   (s.get("founders") or ["Unknown"])[0],
            "email_preview":    " ".join(s.get("outreach_email","").split()[:20]) + "…",
            "whatsapp_preview": s.get("outreach_whatsapp",""),
        })

    return {
        "status":            "success",
        "task":              "Task 4 — Message Generation",
        "messages_generated": len(to_process),
        "email_word_range":  "80-120 words",
        "whatsapp_word_range": "25-40 words",
        "personalization_signals": [
            "Founder first name", "Company name", "Industry pain points",
            "Accelerator mention (if known)", "Problem statement (if scraped)",
        ],
        "sample_preview":    preview,
        "note":              "Run export_to_excel_tool to download the full dataset.",
    }


# ============================================================================
# TOOL 5 — Export + Sending Layer  (Task 5 + download)
# ============================================================================

def export_to_excel_tool(
    filename: str = "startup_outreach_india.xlsx",
) -> dict:
    """
    Export full enriched dataset to a professional Excel workbook.

    Sheets produced:
      1. All Startups       — complete dataset (50+ rows, all fields)
      2. Fintech Startups   — Task 2 mandatory filtered category
      3. Outreach Messages  — email + WhatsApp per startup
      4. Summary Dashboard  — counts by industry, stage, accuracy + Task 5 sending layer

    Task 5 — Sending Layer (documented in dashboard sheet):
      • Email:     SendGrid / Mailgun API — loop startups, send outreach_email field
      • WhatsApp:  Meta Cloud API (WhatsApp Business) — send outreach_whatsapp field
      • Rate limits: 50 emails/hr, 20 WhatsApp/hr
      • Tracking:  Log open/reply rates back to spreadsheet
      • Follow-up: Auto-schedule via n8n / Zapier after 3 days

    Args:
        filename: Output Excel filename (default: "startup_outreach_india.xlsx")

    Returns:
        dict with filepath and summary stats
    """
    startups = _SESSION.get("startups", [])
    if not startups:
        return {"status": "error", "message": "No startups in session. Run discover_startups_tool first."}

    # Ensure messages are generated
    if not startups[0].get("outreach_email"):
        startups = add_messages_to_all(startups)

    filepath = os.path.join(_parent_dir, filename)
    export_to_excel(startups, filepath)

    fintech_count = sum(1 for s in startups if s.get("industry","").lower() == "fintech")

    return {
        "status":     "success",
        "task":       "Export + Task 5 — Sending Layer",
        "filepath":   filepath,
        "filename":   filename,
        "sheets": {
            "All Startups":      f"{len(startups)} rows — full dataset",
            "Fintech Startups":  f"{fintech_count} rows — Task 2 filtered category",
            "Outreach Messages": f"{len(startups)} personalized email + WhatsApp messages",
            "Summary Dashboard": "Industry / stage / accuracy breakdown + sending layer workflow",
        },
        "download_instruction": f"File saved to: {filepath}",
    }


# ============================================================================
# AGENT
# ============================================================================

root_agent = Agent(
    model="gemini-2.5-flash",
    name="startup_outreach_agent",
    description=(
        "Assignment 3: Automated Startup Outreach System — "
        "Discovers 50+ Indian startups (2025/2026), classifies by industry, "
        "enriches with founder/contact data, generates personalized outreach, "
        "and exports to Excel."
    ),
    instruction="""
You are the Assignment 3 Automated Startup Outreach Agent for the Indian market.

You cover all 5 assignment tasks using 5 tools:

━━━ TASK → TOOL MAPPING ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Task 1 — Company Discovery (50+ startups)   → discover_startups_tool
Task 2 — Filter / Classification             → classify_and_filter_tool
Task 3 — Company Enrichment                  → enrich_startups_tool
Task 4 — Message Generation                  → generate_outreach_tool
Task 5 — Sending Layer + Export              → export_to_excel_tool

━━━ DEFAULT WORKFLOW (run in order) ━━━━━━━━━━━━━━━━━━━━━━━━━
1. discover_startups_tool(target_count=55)
2. classify_and_filter_tool(industry="Fintech")
3. enrich_startups_tool(min_accuracy=30)
4. generate_outreach_tool()
5. export_to_excel_tool()

━━━ TOOL DETAILS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
discover_startups_tool:
  • Runs 13 targeted Google queries (SerpAPI)
  • Covers Y Combinator, Antler, Sequoia Surge, 100X.VC, DPIIT signals
  • Filters junk domains automatically
  • Scrapes each website for founders, emails, problem statement
  • Industry classification: Fintech, SaaS, D2C, HealthTech, EdTech, Mobility

classify_and_filter_tool:
  • Filter to any industry (Fintech is the assignment default)
  • Returns subset with accuracy scores

enrich_startups_tool:
  • Shows enrichment stats: founders found, emails, descriptions, stage
  • Verifies minimum requirement: founder + email + 2 context fields

generate_outreach_tool:
  • Email (80-120 words): industry pain points + founder name + company + accelerator
  • WhatsApp (25-40 words): punchy, industry-specific, value-driven
  • Uses problem statement from website when available

export_to_excel_tool:
  • 4-sheet Excel workbook
  • Task 5 sending layer documented in dashboard tab
  • Ready for submission

━━━ ACCURACY SCORE (0-100) ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🟢 70-100  Excellent  — founders, emails, full info
🟡 50-69   Good       — partial contact info
🟠 30-49   Moderate   — basic company info
🔴  0-29   Poor       — discard

━━━ DISPLAY FORMAT ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
When showing startups, always display:
⭐ Score | 🏢 Company | 👤 Founders | 📧 Email | 🏭 Industry
📝 Description | 🌱 Stage | 📅 Founded | 🌐 Website

━━━ QUALITY RULES ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✔ Only show REAL startup homepages (not news/directories)
✔ Founder names must be genuine human names (2-3 words, Title Case)
✔ Nav-bar text / button labels are NEVER founder names
✔ Aim for 50+ results — if short, re-run with broader query
✔ Always remind user to verify contact info before outreach
""",
    tools=[
        discover_startups_tool,
        classify_and_filter_tool,
        enrich_startups_tool,
        generate_outreach_tool,
        export_to_excel_tool,
    ],
)
