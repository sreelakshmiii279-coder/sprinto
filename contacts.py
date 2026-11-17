"""Step 4: find the right person.

The case allows two sources, and by default only these are used:
  Option A - Hunter.io Domain Search API (HUNTER_API_KEY; free tier = 25 searches/month)
  Option B - Apollo.io, looked up by hand and hardcoded in data/contacts.csv

Those two are always tried first. With EXTRA_CONTACT_SOURCES=1 (the default) the step then falls back to named
leaders on the company's website and a cited web search, an extra for when Hunter has no data on a small
company or nobody has been looked up on Apollo yet. Set it to 0 to use only the brief's two sources.

Who counts as "right" depends on company size: under 50 people the founders own compliance;
above that it's security / engineering leadership. Never just the first "manager" on a list.
"""
import csv
import json
import os

import requests

import config
import llm

HERE = os.path.dirname(__file__)
CONTACTS_CSV = os.path.join(HERE, "data", "contacts.csv")
HUNTER_CACHE = os.path.join(HERE, "data", "hunter_cache.json")
APOLLO_TODO = os.path.join(HERE, "data", "apollo_todo.csv")


# Spelled-out titles -> the short forms used in config.ROLES_* ("Chief Executive Officer" -> "ceo").
TITLE_ALIASES = {"chief executive officer": "ceo", "chief technology officer": "cto",
                 "chief information security officer": "ciso", "chief security officer": "ciso",
                 "vice president of engineering": "vp engineering", "vp of engineering": "vp engineering",
                 "cofounder": "co-founder"}


def _rank(title, size):
    roles = config.ROLES_SMALL if 0 <= size < 50 else config.ROLES_MID
    t = (title or "").lower()
    for long, short in TITLE_ALIASES.items():
        t = t.replace(long, short)
    for i, role in enumerate(roles):
        if role in t:
            return i
    return None


def _from_csv(domain):
    """Option B: people you looked up on Apollo and pasted into data/contacts.csv."""
    if not os.path.exists(CONTACTS_CSV):
        return []
    with open(CONTACTS_CSV, newline="", encoding="utf-8") as f:
        return [{"name": r["name"].strip(), "title": r["title"].strip(), "email": (r.get("email") or "").strip(),
                 "source": "Apollo (looked up by hand)"}
                for r in csv.DictReader(f) if (r.get("domain") or "").strip().lower() == domain.lower()]


def _from_hunter(domain):
    """Option A: Hunter.io Domain Search. Results are cached per domain so re-runs don't spend the
    25 free monthly searches again. Only called for companies that already qualified."""
    if not config.HUNTER_API_KEY:
        return []
    cache = json.load(open(HUNTER_CACHE, encoding="utf-8")) if os.path.exists(HUNTER_CACHE) else {}
    if domain not in cache:
        r = requests.get("https://api.hunter.io/v2/domain-search", timeout=config.TIMEOUT_S, params={
            "domain": domain, "api_key": config.HUNTER_API_KEY, "seniority": "senior,executive", "limit": 10})
        if r.status_code == 429:
            raise RuntimeError("Hunter.io: monthly search limit reached (free tier = 25). Use Apollo (contacts.csv).")
        if r.status_code != 200:
            raise RuntimeError(f"Hunter.io HTTP {r.status_code}: {r.text[:150]}")
        cache[domain] = [{"name": f"{e.get('first_name') or ''} {e.get('last_name') or ''}".strip(),
                          "title": e.get("position") or "", "email": e.get("value") or "",
                          "confidence": e.get("confidence")}
                         for e in r.json().get("data", {}).get("emails", []) if e.get("first_name")]
        with open(HUNTER_CACHE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=1)
    return [{**c, "source": "Hunter.io"} for c in cache[domain]]


PEOPLE_SCHEMA = {"type": "object", "properties": {"people": {"type": "array", "items": {"type": "object",
    "properties": {"name": {"type": "string"}, "title": {"type": "string"}}, "required": ["name", "title"]}}},
    "required": ["people"]}


def _from_search(domain, company):
    """Extra (off by default): a cited web search for the company's leaders. Only used if it cites sources."""
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


def _add_apollo_todo(domain, company):
    """A qualified company with no contact: list it so the Growth Lead can look the PoC up on Apollo."""
    exists = os.path.exists(APOLLO_TODO)
    rows = list(csv.DictReader(open(APOLLO_TODO, encoding="utf-8"))) if exists else []
    if any(r["domain"] == domain for r in rows):
        return
    size = company.get("employee_estimate", -1)
    roles = config.ROLES_SMALL if 0 <= size < 50 else config.ROLES_MID
    with open(APOLLO_TODO, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["domain", "company", "look_for_roles"])
        w.writerow([domain, company.get("company_name", ""), ", ".join(roles[:4])])


def find_contact(domain, company, site_domain=None):
    """Returns (contact or None, explanation). site_domain: where the website actually lives if it redirects
    (e.g. zenduty.com -> xurrent.com after an acquisition); Hunter is searched there too if needed."""
    size = company.get("employee_estimate", -1)
    hunter_domains = [domain] + ([site_domain] if site_domain and site_domain != domain else [])
    sources = [("Apollo list", lambda: _from_csv(domain)),
               ("Hunter.io", lambda: [c for d in hunter_domains for c in _from_hunter(d)])]
    if config.EXTRA_CONTACT_SOURCES:
        sources += [("company website", lambda: [{**p, "email": "", "source": "company website"}
                                                 for p in company.get("people", [])]),
                    ("web search", lambda: _from_search(domain, company))]
    for _, get in sources:  # lazy: later sources only run if earlier ones found nobody suitable
        ranked = [c for c in get() if _rank(c["title"], size) is not None]
        if ranked:
            best = min(ranked, key=lambda c: _rank(c["title"], size))
            band = "under 50 people, so a founder owns compliance" if 0 <= size < 50 else \
                   "50+ people (or unknown), so security/engineering leadership owns compliance"
            why = f"{best['name']} ({best['title']}) from {best['source']}: {band}"
            if best["source"] not in ("Hunter.io", "Apollo (looked up by hand)"):
                why += ". Apollo/Hunter had nobody suitable, so this came from a fallback source: verify before a real send"
            return best, why

    tried = ", ".join(name for name, _ in sources if name != "Hunter.io" or config.HUNTER_API_KEY)
    _add_apollo_todo(domain, company)
    hint = "" if config.HUNTER_API_KEY else " Add HUNTER_API_KEY to .env, or"
    return None, (f"no one with a compliance-owning role found ({tried}).{hint} look them up on Apollo: "
                  "added to data/apollo_todo.csv, then put them in data/contacts.csv")
