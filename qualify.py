"""Step 3: does this company fit Sprinto's ICP? An evidence-map loop with a hard cap.

ICP (from the case): SaaS, typically Series A-C, either preparing for a compliance audit or under
pressure from enterprise customers to get certified.

The model only extracts facts (step 2). The yes/no decision is plain code below, so every point of
the score can be traced to a fact and a quote. Score and threshold are both 0-100.
"""
import config
import extract
import llm
import scrape


def _missing(c):
    """Evidence-map questions still unanswered -> which page would answer them (in priority order)."""
    need = []
    if c["is_saas"] == "unknown" or c["funding_stage"] == "unknown":
        need.append("about")
    if c["soc2"] == "not_found" and c["iso27001"] == "not_found":
        need.append("security")
    if not c["enterprise_signals"] and c["sells_to"] in ("unknown", "smb"):
        need.append("customers")
    if c["funding_stage"] == "unknown":
        need.append("press")
    if c["employee_estimate"] < 0 and not c["security_or_compliance_hiring"]:
        need.append("careers")
    return need


def _short_circuit(c):
    """Facts that end the assessment immediately (drop), with the reason."""
    if c["is_saas"] == "no":
        return "not a SaaS company"
    if c["soc2"] == "certified" and c["iso27001"] in ("certified", "not_found"):
        return "already SOC 2 certified, so not preparing for an audit"
    if c["funding_stage"] in ("series_d_plus", "public"):
        return f"too late-stage ({c['funding_stage']})"
    if c["employee_estimate"] > config.MAX_EMPLOYEES:
        return f"too large (~{c['employee_estimate']} people)"
    return None


def score(c):
    """0-100 with a reason for every point awarded."""
    pts, why = 0, []

    def add(n, reason):
        nonlocal pts
        pts += n
        why.append(f"+{n} {reason}")

    if c["is_saas"] == "yes":
        add(25, "SaaS product")
    elif c["is_saas"] == "unknown":
        add(10, "probably software (not confirmed as SaaS)")

    stage = c["funding_stage"]
    if stage in ("series_a", "series_b", "series_c"):
        add(25, f"{stage.replace('_', ' ').title()}: inside Sprinto's sweet spot")
    elif stage == "seed":
        add(15, "Seed stage: a little early but often chasing first enterprise deals")
    elif stage in ("unknown", "bootstrapped"):
        add(8, f"funding stage {stage}")

    if c["sells_to"] in ("enterprise", "midmarket", "mixed"):
        add(15, f"sells to {c['sells_to']} customers (they ask for SOC 2)")
    if len(c["enterprise_signals"]) >= 2:
        add(10, "enterprise signals: " + "; ".join(c["enterprise_signals"][:3]))

    if c["soc2"] == "in_progress" or c["iso27001"] == "in_progress":
        add(25, "working towards SOC 2 / ISO 27001 right now")
    elif c["soc2"] == "mentioned" or c["iso27001"] == "mentioned":
        add(15, "talks about SOC 2 / ISO 27001 but isn't certified")
    if c["gdpr_mentioned"]:
        add(5, "mentions GDPR")
    if c["security_or_compliance_hiring"]:
        add(10, "hiring for security / compliance")

    n = c["employee_estimate"]
    if 20 <= n <= 500:
        add(10, f"~{n} people: big enough to need it, small enough to lack a GRC team")

    return min(pts, 100), why


SEARCH_PROMPT = """Search the web now (do not answer from memory). For the company whose website is {domain}
({name}): what is its most recent funding round (stage, amount, date) and roughly how many employees does it
have? Answer in two or three sentences, saying which source each fact comes from."""

SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "funding_stage": {"type": "string", "enum": extract.STAGES},
        "funding_detail": {"type": "string", "description": "amount, date, investors as stated, or empty"},
        "employee_estimate": {"type": "integer", "description": "-1 if not stated"},
    },
    "required": ["funding_stage", "funding_detail", "employee_estimate"],
}


def _search_gaps(domain, company):
    """One grounded search for funding stage / headcount. Only used if the search actually cited sources."""
    try:
        answer, sources = llm.ask_search(SEARCH_PROMPT.format(domain=domain, name=company["company_name"]))
        if not sources:
            return company, {"ok": False, "reason": "search cited no sources, so the answer wasn't used"}
        found = llm.ask_json("Turn this research note into the fields. Use only what it says.\n\n" + answer,
                             SEARCH_SCHEMA)
    except Exception as e:  # noqa: BLE001 - search is a bonus; failing it must be visible but not fatal
        return company, {"ok": False, "reason": f"search failed: {type(e).__name__}: {e}"}
    company = dict(company)
    titles = ", ".join(dict.fromkeys(s["title"] for s in sources if s["title"]))
    if company["funding_stage"] == "unknown" and found["funding_stage"] != "unknown":
        company["funding_stage"] = found["funding_stage"]
        company["evidence"] = company["evidence"] + [{
            "fact": f"Funding: {found['funding_stage'].replace('_', ' ')}", "quote": found["funding_detail"],
            "url": f"web search ({titles})"}]
    if company["employee_estimate"] < 0 and found["employee_estimate"] > 0:
        company["employee_estimate"] = found["employee_estimate"]
    return company, {"ok": True, "reason": f"search sources: {titles}"}


def qualify(domain):
    """Returns a decision dict. status: qualified | below_threshold | dropped | unreadable."""
    home = scrape.fetch(domain)
    pages_tried = [{"url": home["url"], "ok": home["ok"], "reason": home["reason"]}]
    if not home["ok"]:
        # Not a poor fit: we simply couldn't read it. Flag for a human instead of scoring 0.
        return {"domain": domain, "status": "unreadable", "score": None,
                "reasons": [f"homepage unreadable: {home['reason']}"], "company": None,
                "pages": pages_tried, "rounds": 0}

    pages = [home]
    company = extract.extract(pages)
    rounds = 0
    # Loop: fetch the page most likely to answer what's still unknown. A round = one extra page that was
    # read and re-extracted (costs a model call). Failed fetches are cheap and don't use a round, but total
    # attempts are capped too, so the loop always ends.
    attempts = 0
    while rounds < config.MAX_ROUNDS and attempts < config.MAX_FETCH_ATTEMPTS and not _short_circuit(company):
        # Both the link we asked for and where it redirected to count as tried.
        tried = {p["url"] for p in pages_tried} | {p.get("requested", "") for p in pages_tried} | {domain}
        url = next((u for kind in _missing(company)
                    for u in [scrape.find_link(home, kind, exclude=tried)] if u), None)
        if not url:
            break
        more = scrape.fetch(url)
        attempts += 1
        pages_tried.append({"url": more["url"], "requested": url, "ok": more["ok"], "reason": more["reason"]})
        if more["ok"]:
            rounds += 1
            pages.append(more)
            company = extract.extract(pages)

    # Funding and headcount are rarely on the website: one grounded web search, sources kept as evidence.
    if not _short_circuit(company) and (company["funding_stage"] == "unknown" or company["employee_estimate"] < 0):
        company, searched = _search_gaps(domain, company)
        pages_tried.append({"url": "google search (via Gemini)", "ok": searched["ok"], "reason": searched["reason"]})

    stop = _short_circuit(company)
    if stop:
        return {"domain": domain, "status": "dropped", "score": 0, "reasons": [f"dropped: {stop}"],
                "company": company, "pages": pages_tried, "rounds": rounds}

    pts, why = score(company)
    # A security/trust page we couldn't read often means they're already certified: lower confidence, say so.
    blind = [p["url"] for p in pages_tried
             if not p["ok"] and any(k in p["url"].lower() for k in ("trust", "security", "compliance"))]
    if blind and company["soc2"] == "not_found":
        pts -= 15
        why.append(f"-15 has a trust/security page we couldn't read ({blind[0]}); they may already be certified, "
                   "check it before sending")
    status = "qualified" if pts >= config.QUALIFY_THRESHOLD else "below_threshold"
    return {"domain": domain, "status": status, "score": pts,
            "reasons": why + [f"score {pts}/100 vs threshold {config.QUALIFY_THRESHOLD}/100"],
            "company": company, "pages": pages_tried, "rounds": rounds}
