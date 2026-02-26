"""
message_generator.py  — Task 4: Personalized Outreach Message Generation
=========================================================================
Generates:
  A) Email outreach (80-120 words) — industry-aware, personalized
  B) WhatsApp short pitch (25-40 words) — punchy and value-driven

Personalization signals used:
  - Startup domain / industry
  - Founder name
  - Funding / accelerator details
  - Problem statement from website
  - Stage
"""

import os
import re
from typing import Dict, Optional


# ── Industry-specific value propositions ─────────────────────────────────────
INDUSTRY_VALUE_PROPS = {
    "Fintech": {
        "pain_points": ["compliance automation", "KYC/AML workflows", "payment reconciliation"],
        "value":       "helping fintech startups automate compliance and accelerate onboarding",
        "opener":      "The regulatory complexity in Indian fintech is real — and growing.",
    },
    "SaaS": {
        "pain_points": ["customer onboarding", "churn reduction", "sales pipeline visibility"],
        "value":       "helping SaaS teams cut churn and accelerate GTM in the Indian B2B market",
        "opener":      "Scaling a B2B SaaS in India comes with unique GTM challenges.",
    },
    "D2C": {
        "pain_points": ["customer acquisition cost", "repeat purchase rates", "supply chain"],
        "value":       "helping D2C brands reduce CAC and build loyal repeat customer bases",
        "opener":      "Standing out in India's crowded D2C space requires more than a great product.",
    },
    "HealthTech": {
        "pain_points": ["patient engagement", "data interoperability", "regulatory approvals"],
        "value":       "helping healthtech teams navigate regulation and improve patient outcomes",
        "opener":      "Healthcare in India is undergoing a digital revolution — and the bar for trust is high.",
    },
    "EdTech": {
        "pain_points": ["learner retention", "content personalisation", "B2B institutional sales"],
        "value":       "helping edtech platforms improve learner retention and institutional sales",
        "opener":      "Learner engagement remains the #1 challenge for edtech platforms in India.",
    },
    "Mobility": {
        "pain_points": ["fleet operations", "EV charging infrastructure", "last-mile logistics"],
        "value":       "helping mobility startups optimise fleet ops and reduce operational costs",
        "opener":      "India's mobility sector is at an inflection point — efficiency is everything.",
    },
    "Other": {
        "pain_points": ["operational efficiency", "customer growth", "product-market fit"],
        "value":       "helping early-stage startups scale faster with the right tooling",
        "opener":      "Building a startup in India is hard — the right infrastructure makes all the difference.",
    },
}

# ── Accelerator / funding shoutouts ──────────────────────────────────────────
ACCELERATOR_MENTIONS = {
    "y combinator": "Being a YC company, you understand the value of moving fast",
    "antler":       "Antler-backed teams know what it means to build with conviction",
    "sequoia surge":"With Surge's backing, you're already thinking at scale",
    "100x.vc":      "100X.VC portfolio companies are known for ambitious execution",
    "elevation":    "Elevation Capital's portfolio speaks to your growth ambitions",
    "lightspeed":   "With Lightspeed's support, scaling is clearly on your roadmap",
}


def _get_accelerator_line(text: str) -> Optional[str]:
    t = text.lower()
    for key, line in ACCELERATOR_MENTIONS.items():
        if key in t:
            return line
    return None


def _safe_founder(startup: Dict) -> str:
    founders = startup.get("founders") or []
    if founders:
        # Take first name only (friendlier)
        full = founders[0]
        first = full.split()[0]
        return first
    return "Founder"


def _safe_company(startup: Dict) -> str:
    name = (startup.get("name") or "").strip()
    return name if name and name != "Unknown" else "your startup"


def generate_email(startup: Dict) -> str:
    """
    Generate a personalized email outreach (80-120 words).
    """
    industry  = startup.get("industry", "Other")
    props     = INDUSTRY_VALUE_PROPS.get(industry, INDUSTRY_VALUE_PROPS["Other"])
    founder   = _safe_founder(startup)
    company   = _safe_company(startup)
    stage     = startup.get("stage", "early-stage")
    problem   = startup.get("problem_statement", "")
    all_text  = f"{startup.get('description','')} {startup.get('funding','')} {problem}"
    accel_line = _get_accelerator_line(all_text)

    # Build problem-aware opening if we have a problem statement
    if problem and len(problem) > 40:
        problem_ref = f"I came across {company} and your focus on solving {problem[:80].rstrip()}."
    else:
        problem_ref = f"I came across {company} while researching {industry.lower()} startups in India."

    accel_sentence = f" {accel_line}." if accel_line else ""

    email = (
        f"Hi {founder},\n\n"
        f"{problem_ref}{accel_sentence}\n\n"
        f"{props['opener']}\n\n"
        f"We specialize in {props['value']} — specifically around "
        f"{props['pain_points'][0]} and {props['pain_points'][1]}.\n\n"
        f"Given where {company} is at ({stage} stage), I believe there's a strong fit. "
        f"Would you be open to a quick 20-minute call this week?\n\n"
        f"Best,\n[Your Name]\n[Your Company]"
    )

    # Trim to ~120 words
    words = email.split()
    if len(words) > 130:
        # Keep full structure but shorten the middle
        email = (
            f"Hi {founder},\n\n"
            f"{problem_ref}\n\n"
            f"We help {industry} startups with {props['pain_points'][0]} and {props['pain_points'][1]}. "
            f"{accel_line + '.' if accel_line else ''}\n\n"
            f"Given {company}'s {stage} stage trajectory, I think there's a real fit. "
            f"Open to a quick 20-minute call this week?\n\n"
            f"Best,\n[Your Name]\n[Your Company]"
        )

    return email.strip()


def generate_whatsapp(startup: Dict) -> str:
    """
    Generate a WhatsApp short pitch (25-40 words).
    """
    industry = startup.get("industry", "Other")
    props    = INDUSTRY_VALUE_PROPS.get(industry, INDUSTRY_VALUE_PROPS["Other"])
    founder  = _safe_founder(startup)
    company  = _safe_company(startup)

    msg = (
        f"Hi {founder}! 👋 We help {industry} startups like {company} tackle "
        f"{props['pain_points'][0]} and {props['pain_points'][1]}. "
        f"Worth a quick chat? 🚀"
    )

    # Ensure 25-40 words
    words = msg.split()
    if len(words) > 42:
        msg = (
            f"Hi {founder}! We help {industry} startups with {props['pain_points'][0]}. "
            f"Think {company} could benefit — open to a quick call? 🚀"
        )
    elif len(words) < 23:
        msg = (
            f"Hi {founder}! We work with early-stage {industry} startups in India to solve "
            f"{props['pain_points'][0]} challenges. Would love to connect with the {company} team! 🚀"
        )

    return msg.strip()


def generate_messages_for_startup(startup: Dict) -> Dict:
    """Generate both email and WhatsApp for a single startup."""
    return {
        "email":     generate_email(startup),
        "whatsapp":  generate_whatsapp(startup),
        "word_count_email":    len(generate_email(startup).split()),
        "word_count_whatsapp": len(generate_whatsapp(startup).split()),
    }


def add_messages_to_all(startups: list) -> list:
    """Add outreach messages to every startup in the list."""
    for s in startups:
        msgs = generate_messages_for_startup(s)
        s["outreach_email"]     = msgs["email"]
        s["outreach_whatsapp"]  = msgs["whatsapp"]
    return startups
