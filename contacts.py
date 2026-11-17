"""Step 4: find the right person. Sources, in order of trust:

1. data/contacts.csv  - people you looked up by hand on Apollo (case option B)
2. Hunter.io Domain Search API - if HUNTER_API_KEY is set (case option A, 25 free searches/month)
3. Named leaders on the company's own website (found in step 2)

Who counts as "right" depends on company size: under 50 people the founders own compliance;
above that it's security / engineering leadership. Never just the first "manager" on a list.
"""
import csv
import os

import requests

import config
import llm


def _rank(title, size):
    roles = config.ROLES_SMALL if 0 <= size < 50 else config.ROLES_MID
    t = (title or "").lower()
    for i, role in enumerate(roles):
        if role in t:
            return i
    return None


def _from_csv(domain):
    path = os.path.join(os.path.dirname(__file__), "data", "contacts.csv")
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return [{"name": r["name"], "title": r["title"], "email": r.get("email", ""), "source": "apollo (manual)"}
                for r in csv.DictReader(f) if r["domain"].strip().lower() == domain.lower()]


def _from_hunter(domain):
    if not config.HUNTER_API_KEY:
        return []
    r = requests.get("https://api.hunter.io/v2/domain-search", timeout=config.TIMEOUT_S, params={
        "domain": domain, "api_key": config.HUNTER_API_KEY, "seniority": "senior,executive", "limit": 10})
    if r.status_code != 200:
        raise RuntimeError(f"Hunter.io HTTP {r.status_code}: {r.text[:150]}")
    return [{"name": f"{e.get('first_name') or ''} {e.get('last_name') or ''}".strip(),
             "title": e.get("position") or "", "email": e.get("value") or "", "source": "hunter.io"}
            for e in r.json().get("data", {}).get("emails", []) if e.get("first_name")]


PEOPLE_SCHEMA = {"type": "object", "properties": {"people": {"type": "array", "items": {"type": "object",
    "properties": {"name": {"type": "string"}, "title": {"type": "string"}}, "required": ["name", "title"]}}},
    "required": ["people"]}


def _from_search(domain, company):
    """Last resort: a cited web search for the company's leaders. Only used if the search cites sources."""
    answer, sources = llm.ask_search(
        f"Search the web now (do not answer from memory). Who are the founders, CEO, CTO, and head of security "
        f"or compliance at {company['company_name']} (website {domain}) today? Give each person's name and current "
        f"title, and say which source says so.")
    if not sources:
        return []
    found = llm.ask_json("List the people and titles this note names for the company. Use only what it says.\n\n"
                         + answer, PEOPLE_SCHEMA)
    titles = ", ".join(dict.fromkeys(s["title"] for s in sources if s["title"]))
    return [{**p, "email": "", "source": f"web search ({titles})"} for p in found["people"]]


def find_contact(domain, company):
    """Returns (contact or None, explanation)."""
    size = company.get("employee_estimate", -1)
    website_people = [{**p, "email": "", "source": "company website"} for p in company.get("people", [])]
    sources = [lambda: _from_csv(domain), lambda: _from_hunter(domain), lambda: website_people,
               lambda: _from_search(domain, company)]
    for get in sources:  # lazy: the search only runs if nothing earlier found someone
        source = get()
        ranked = [c for c in source if _rank(c["title"], size) is not None]
        if ranked:
            best = min(ranked, key=lambda c: _rank(c["title"], size))
            band = "under 50 people, so a founder owns compliance" if 0 <= size < 50 else \
                   "50+ people (or unknown), so security/engineering leadership owns compliance"
            return best, f"{best['name']} ({best['title']}) from {best['source']}: {band}"
    tried = "contacts.csv, " + ("Hunter.io, " if config.HUNTER_API_KEY else "") + "company website, web search"
    return None, f"no one with a compliance-owning role found ({tried})"
