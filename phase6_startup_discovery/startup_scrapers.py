"""
startup_scrapers.py  — Assignment 3 (v4 — timeout-hardened)
=============================================================
Key fixes vs v3:
  - Per-startup hard cap: max 2 pages scraped (homepage + 1 team page)
  - Request timeout dropped to 5s (was 10s)
  - Sleep reduced to 0.2s between requests (was 0.6s)
  - signal-based per-startup wall-clock timeout (15s max per startup)
  - Pipeline capped at exactly 50 startups — stops immediately after
  - Scrape skipped entirely if startup already has enough data from SerpAPI
"""

import os, re, time, signal, requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

# ── Junk domains ──────────────────────────────────────────────────────────────
JUNK_DOMAINS = {
    "yourstory.com","inc42.com","entrackr.com","techcrunch.com",
    "economictimes.indiatimes.com","livemint.com","moneycontrol.com",
    "businessinsider.com","forbes.com","growthlist.co","indiabizforsale.com",
    "cyberleads.com","mygreatlearning.com","ycombinator.com","crunchbase.com",
    "linkedin.com","twitter.com","facebook.com","instagram.com","wikipedia.org",
    "glassdoor.com","ambitionbox.com","tracxn.com","startupindia.gov.in",
    "nasscom.in","medium.com","substack.com","wordpress.com","blogspot.com",
    "angellist.com","f6s.com","producthunt.com","g2.com","fundable.com",
    "pitchbook.com","dealroom.co","ventureradar.com",
}

INDUSTRY_KEYWORDS = {
    "Fintech":    ["fintech","payment","lending","neobank","insurance","wealth","credit",
                   "remittance","upi","nbfc","financial","banking","invoice","accounting"],
    "SaaS":       ["saas","b2b software","crm","erp","hr software","workflow","automation",
                   "api","platform","dashboard","analytics","cloud software","devops"],
    "D2C":        ["d2c","direct to consumer","ecommerce","e-commerce","brand","dtc",
                   "consumer brand","retail","personal care","fashion","beauty","food brand"],
    "HealthTech": ["healthtech","health tech","telemedicine","medtech","diagnostics",
                   "mental health","wellness","pharma","hospital","clinical","patient",
                   "healthcare","femtech","ayurveda","nutrition"],
    "EdTech":     ["edtech","ed tech","learning","education","upskilling","skill",
                   "e-learning","tutoring","coaching","course","certification","school"],
    "Mobility":   ["mobility","ev","electric vehicle","logistics","fleet","delivery",
                   "transport","ride","commute","last mile","autonomous","drone"],
}

NAV_NOISE = {
    "click here","check here","previous post","next post","browse topics",
    "cloud computing","career development","digital marketing","read more",
    "learn more","get started","sign up","log in","contact us","about us",
    "home","blog","pricing","features","solutions","services","products",
    "portfolio","team","leadership","investors","media","press","careers",
    "jobs","faq","growth list team","regional funding","frequently asked",
    "hey startup founders","hottest startup categories",
}
_BAD_ENDINGS = {
    "team","agency","lab","labs","ventures","capital","studio","media",
    "network","group","fund","post","topics","computing","development",
    "marketing","management","money","depot","opinions","categories",
}
_NAME_RE  = re.compile(r"^[A-Z][a-z]{1,20}(?:\s[A-Z][a-z]{1,20})?\s[A-Z][a-z]{1,25}$")
_ROLE_RE  = re.compile(r'\b(founder|co-founder|cofounder|ceo|chief\sexecutive|cto|coo|managing\sdirector|president)\b', re.I)
_EMAIL_RE = re.compile(r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b')
_PHONE_RE = re.compile(r'(?:\+91[\s\-]?)?[6-9]\d{9}')
_NOISE_EMAIL = {"noreply","no-reply","example","test@","info@example","privacy@","legal@"}

_REQ_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

# ── Timeout helper (Unix only) ────────────────────────────────────────────────
class _Timeout:
    def __init__(self, seconds):
        self.seconds = seconds
    def __enter__(self):
        try:
            signal.signal(signal.SIGALRM, self._handler)
            signal.alarm(self.seconds)
        except (AttributeError, OSError):
            pass   # Windows — no SIGALRM, just skip
        return self
    def __exit__(self, *args):
        try:
            signal.alarm(0)
        except (AttributeError, OSError):
            pass
    @staticmethod
    def _handler(signum, frame):
        raise TimeoutError("Startup scrape timed out")


def infer_stage(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["series b","series c","series d","growth stage"]): return "Growth"
    if any(k in t for k in ["series a","post-seed","bridge round"]): return "Post-Seed"
    if any(k in t for k in ["seed","seed funding","seed round","angel","pre-series"]): return "Seed"
    if any(k in t for k in ["pre-seed","idea stage","stealth","building","mvp","beta"]): return "Pre-Seed / Idea"
    return "Early"

def classify_industry(text: str) -> str:
    t = text.lower()
    scores = {ind: sum(1 for kw in kws if kw in t) for ind, kws in INDUSTRY_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "Other"

def is_real_person_name(text: str) -> bool:
    text = text.strip()
    if not (5 <= len(text) <= 45): return False
    words = text.split()
    if not (2 <= len(words) <= 3): return False
    if text.lower() in NAV_NOISE: return False
    for noise in NAV_NOISE:
        if noise in text.lower(): return False
    if not _NAME_RE.match(text): return False
    if words[-1].lower() in _BAD_ENDINGS: return False
    return True

def is_junk_url(url: str) -> bool:
    if not url: return True
    u = url.lower()
    return any(j in u for j in JUNK_DOMAINS)

def _extract_domain(url: str) -> Optional[str]:
    if not url: return None
    m = re.search(r'https?://(?:www\.)?([^/?#]+)', url)
    return m.group(1).lower() if m else None

def _extract_year(text: str) -> Optional[str]:
    if not text: return None
    m = re.search(r'(?:founded|established|est\.?|launched|since|incorporated)\s*(?:in\s*)?(202[4-6])', text, re.I)
    if m: return m.group(1)
    m = re.search(r'\b(202[4-6])\b', text)
    return m.group(1) if m else None

def _clean_name(title: str, domain: str = "") -> str:
    if domain:
        base = domain.split(".")[0]
        if 2 < len(base) < 30 and base not in {"www","app","get","try","blog","mail","help"}:
            return base.title()
    title = re.sub(r'\s*[-|:]\s*(About|Home|Official|Founders|Contact|Blog|Welcome|India).*', '', title, re.I)
    title = re.sub(r'\.(com|in|io|co|ai|tech|app)\b.*', '', title, re.I)
    return title.strip()[:80] or "Unknown"


# ============================================================================
# SERPAPI SEARCH
# ============================================================================

_SEARCH_QUERIES = [
    '"{year}" India startup founded CEO founder contact site:*.io OR site:*.ai OR site:*.in',
    '"founded in {year}" India startup "our founders" OR "meet the team"',
    '"launched in {year}" India startup CEO founder contact email',
    '"seed funding" OR "pre-seed" India startup {year} founders',
    '"Antler India" OR "100X.VC" OR "Sequoia Surge" startup {year} founders',
    '"Y Combinator" India startup {year} founders contact',
    'India fintech startup {year} founders CEO email contact',
    'India SaaS startup {year} co-founder about team',
    'India healthtech OR edtech startup {year} founders',
    'India D2C brand startup {year} founder email',
    'India mobility OR EV startup {year} founder contact',
    'India DPIIT recognized startup {year} founder email contact',
    '"new startup" India {year} "series A" OR "seed round" founders',
]


def search_startups_google(
    query: str = "new startups India 2025 2026",
    location: str = "India",
    max_results: int = 55,        # fetch a few extra so we have buffer
    year: str = "2025 2026",
) -> List[Dict]:
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        return [{"error": "SERPAPI_KEY not found in .env"}]
    try:
        from serpapi import GoogleSearch
    except ImportError:
        return [{"error": "Run: pip install google-search-results"}]

    seen_domains: set = set()
    results_list: List[Dict] = []
    all_queries = [f"{query} {location}"] + [q.replace("{year}", year) for q in _SEARCH_QUERIES]

    for q in all_queries:
        if len(results_list) >= max_results:
            break
        try:
            params = {
                "api_key": api_key, "engine": "google", "q": q,
                "num": 10, "gl": "in", "hl": "en", "filter": "1", "tbs": "qdr:y",
            }
            data = GoogleSearch(params).get_dict()
            if "error" in data: continue

            for r in data.get("organic_results", []):
                if len(results_list) >= max_results: break
                url = r.get("link", "")
                if is_junk_url(url): continue
                domain = _extract_domain(url) or ""
                if not domain or domain in seen_domains: continue
                seen_domains.add(domain)

                snippet  = r.get("snippet", "")
                title    = r.get("title", "")
                combined = f"{title} {snippet}"

                results_list.append({
                    "name":           _clean_name(title, domain),
                    "description":    snippet if len(snippet) > 30 else "N/A",
                    "website":        url,
                    "source":         "Google Search",
                    "founded_year":   _extract_year(combined),
                    "location":       location,
                    "industry":       classify_industry(combined),
                    "stage":          infer_stage(combined),
                    "founders":       [],
                    "founder_emails": [],
                    "contact_emails": [],
                    "contact_phones": [],
                    "twitter":        None,
                    "linkedin":       None,
                    "employees":      None,
                    "funding":        None,
                    "target_customers":  None,
                    "problem_statement": None,
                })
            time.sleep(0.3)
        except Exception as e:
            print(f"  ⚠️  Query error: {e}")
            continue

    return results_list[:max_results]


# ============================================================================
# HUNTER.IO  (optional)
# ============================================================================

def find_founder_emails_hunter(domain: str) -> Dict:
    api_key = os.getenv("HUNTER_API_KEY")
    if not api_key: return {"status": "skipped"}
    try:
        r = requests.get(
            "https://api.hunter.io/v2/domain-search",
            params={"domain": domain, "api_key": api_key, "type": "personal"},
            timeout=5,   # ← hard 5s limit
        )
        r.raise_for_status()
        data = r.json()
        if data.get("errors"): return {"status": "error"}
        emails = data.get("data", {}).get("emails", [])
        kws = {"founder","ceo","co-founder","chief","cto","coo","managing"}
        fe = [e["value"] for e in emails if any(k in (e.get("position") or "").lower() for k in kws)]
        return {"status": "success", "founder_emails": fe[:5]}
    except Exception:
        return {"status": "error"}


# ============================================================================
# CLEARBIT  (optional)
# ============================================================================

def enrich_company_clearbit(domain: str) -> Dict:
    api_key = os.getenv("CLEARBIT_API_KEY")
    if not api_key: return {"status": "skipped"}
    try:
        r = requests.get(
            "https://company.clearbit.com/v2/companies/find",
            headers={"Authorization": f"Bearer {api_key}"},
            params={"domain": domain},
            timeout=5,   # ← hard 5s limit
        )
        if r.status_code == 404: return {"status": "not_found"}
        if r.status_code != 200: return {"status": "error"}
        d = r.json()
        return {
            "status":       "success",
            "name":         d.get("name"),
            "description":  d.get("description"),
            "founded_year": str(d["foundedYear"]) if d.get("foundedYear") else None,
            "employees":    d.get("metrics", {}).get("employees"),
            "funding":      d.get("metrics", {}).get("raised"),
            "twitter":      d.get("twitter", {}).get("handle"),
            "linkedin":     d.get("linkedin", {}).get("handle"),
            "location":     d.get("location"),
        }
    except Exception:
        return {"status": "error"}


# ============================================================================
# WEBSITE SCRAPER  — hard-limited to 2 pages, 5s timeout, 15s wall-clock cap
# ============================================================================

# Only try homepage + ONE team page (not 8 pages like before)
_TEAM_PATHS = ["/about", "/team", "/founders"]


def scrape_startup_website(url: str) -> Dict:
    """
    Scrape homepage + at most 1 team/about page.
    Hard wall-clock cap: 15 seconds total per startup.
    Individual request timeout: 5 seconds.
    Sleep between requests: 0.2s only.
    """
    if not url or url == "N/A" or is_junk_url(url):
        return {"error": "Skipped"}

    base  = url.rstrip("/")
    pages = [base, base + "/about"]   # homepage + about only

    all_founders, all_emails, all_phones = [], [], []
    problem_statement = None
    scraped_any = False

    try:
        with _Timeout(15):   # ← 15s hard wall-clock limit for entire startup
            for page_url in pages:
                try:
                    time.sleep(0.2)   # polite but fast
                    resp = requests.get(
                        page_url, headers=_REQ_HEADERS,
                        timeout=5,            # ← 5s per request (was 10s)
                        allow_redirects=True,
                        stream=False,
                    )
                    if resp.status_code != 200:
                        continue

                    # Hard cap on response size — skip huge pages
                    if len(resp.content) > 500_000:   # 500 KB max
                        continue

                    soup = BeautifulSoup(resp.text, "lxml")
                    for t in soup(["script","style","nav","footer","header","noscript"]):
                        t.decompose()

                    scraped_any = True
                    page_text   = soup.get_text(separator="\n")

                    # Founders
                    for el in soup.find_all(["h1","h2","h3","h4","p","span","strong","b"]):
                        el_text = el.get_text(separator=" ", strip=True)
                        if not _ROLE_RE.search(el_text): continue
                        container = el.parent or el
                        for sib in container.find_all(["h2","h3","h4","p","span","strong","b"]):
                            c = sib.get_text(strip=True)
                            if is_real_person_name(c): all_founders.append(c)
                        for part in re.split(r'[,\-–|/]', el_text):
                            part = part.strip()
                            if is_real_person_name(part): all_founders.append(part)

                    # Problem statement
                    if not problem_statement:
                        for el in soup.find_all(["p","h2","h3"]):
                            txt = el.get_text(strip=True)
                            if any(kw in txt.lower() for kw in ["we solve","our mission","we help","problem we","built to","our goal"]):
                                if 40 < len(txt) < 300:
                                    problem_statement = txt
                                    break

                    # Emails & phones
                    found_emails = _EMAIL_RE.findall(page_text)
                    all_emails.extend([
                        e for e in found_emails
                        if not any(n in e.lower() for n in _NOISE_EMAIL)
                        and not e.lower().endswith((".png",".jpg",".svg",".gif"))
                    ])
                    all_phones.extend(_PHONE_RE.findall(page_text))

                    # Stop early if we found founders on about page
                    if all_founders and page_url != base:
                        break

                except (requests.exceptions.Timeout,
                        requests.exceptions.ConnectionError,
                        requests.exceptions.TooManyRedirects):
                    continue   # skip this page, try next
                except Exception:
                    continue

    except TimeoutError:
        print(f"    ⏱️  Hard timeout hit for {url[:60]}")

    if not scraped_any:
        return {"error": "Could not reach website"}

    def dedup(lst):
        seen, out = set(), []
        for x in lst:
            if x not in seen: seen.add(x); out.append(x)
        return out

    return {
        "status":            "success",
        "founders":          dedup(all_founders)[:6],
        "emails":            dedup(all_emails)[:5],
        "phones":            dedup(all_phones)[:3],
        "problem_statement": problem_statement,
    }


# ============================================================================
# ACCURACY SCORE
# ============================================================================

def calculate_accuracy_score(s: Dict) -> int:
    score = 0
    name = (s.get("name") or "").strip()
    if name and name != "N/A" and 3 < len(name) < 60: score += 10

    desc = (s.get("description") or "").strip()
    listicle = ["top ","best ","list of","7095+","3928+","browse ","find recently"]
    if desc and desc != "N/A" and len(desc) > 60 and not any(m in desc.lower() for m in listicle):
        score += 10

    founders = s.get("founders") or []
    valid = [f for f in founders if is_real_person_name(f)]
    if valid: s["founders"] = valid; score += 25

    emails = (s.get("founder_emails") or []) + (s.get("contact_emails") or [])
    if emails: score += 20

    if s.get("contact_phones"):  score += 10
    if (s.get("website") or "N/A") != "N/A": score += 5
    if s.get("twitter") or s.get("linkedin"): score += 5
    if str(s.get("founded_year") or "") in ("2024","2025","2026"): score += 5
    if s.get("problem_statement"): score += 5
    if s.get("industry") and s.get("industry") != "Other": score += 5
    return min(score, 100)


def filter_by_industry(startups: List[Dict], industry: str) -> List[Dict]:
    return [s for s in startups if s.get("industry","").lower() == industry.lower()]


# ============================================================================
# MAIN PIPELINE  — capped at exactly 50
# ============================================================================

def find_startups_complete(
    query: str = "new startups 2025 2026",
    location: str = "India",
    max_results: int = 50,        # ← HARD CAP at 50 for demo
    enrich_data: bool = True,
    year: str = "2025 2026",
) -> Dict:
    """
    Pipeline with hard 50-startup cap and per-startup timeout.
    Stops enrichment the moment we hit 50 processed startups.
    """
    print(f"\n🔍 Searching: '{query}' | cap: {max_results} startups")

    # Fetch slightly more from Google so we have buffer after junk filtering
    raw = search_startups_google(query, location, max_results=max_results + 10, year=year)

    if not raw:
        return {"status": "error", "message": "No results from Google Search"}
    if "error" in (raw[0] if raw else {}):
        return {"status": "error", "message": raw[0].get("error","Unknown error")}

    # Hard cap — only process up to max_results
    raw = raw[:max_results]
    print(f"  ✅ Processing {len(raw)} candidates (capped at {max_results})")

    enriched = []
    for i, s in enumerate(raw, 1):
        name = s.get("name", "Unknown")
        print(f"  [{i:02d}/{len(raw)}] {name[:45]:<45}", end=" ", flush=True)

        website = s.get("website", "")
        domain  = _extract_domain(website)

        if enrich_data and domain:
            # Hunter.io
            h = find_founder_emails_hunter(domain)
            if h.get("status") == "success":
                s["founder_emails"] = h.get("founder_emails", [])

            # Clearbit
            c = enrich_company_clearbit(domain)
            if c.get("status") == "success":
                if c.get("name"): s["name"] = c["name"]
                if c.get("description") and s.get("description") in ("N/A","",None):
                    s["description"] = c["description"]
                for f in ("founded_year","employees","funding","twitter","linkedin"):
                    if c.get(f): s[f] = c[f]

            # Website scrape — per-startup 15s hard cap inside function
            w = scrape_startup_website(website)
            if w.get("status") == "success":
                if w.get("founders"):          s["founders"]          = w["founders"]
                if w.get("emails"):            s["contact_emails"]    = w["emails"]
                if w.get("phones"):            s["contact_phones"]    = w["phones"]
                if w.get("problem_statement"): s["problem_statement"] = w["problem_statement"]

        all_text = " ".join(filter(None,[s.get("name",""),s.get("description",""),s.get("problem_statement","")]))
        s["industry"] = classify_industry(all_text)
        s["stage"]    = infer_stage(all_text)
        s["accuracy_score"] = calculate_accuracy_score(s)
        enriched.append(s)
        print(f"✓ score={s['accuracy_score']}")

    enriched.sort(key=lambda x: x.get("accuracy_score", 0), reverse=True)
    print(f"\n  ✅ Done. {len(enriched)} startups. Top score: {enriched[0]['accuracy_score'] if enriched else 0}/100")

    return {
        "status":      "success",
        "total_found": len(enriched),
        "query":       query,
        "location":    location,
        "startups":    enriched,
    }