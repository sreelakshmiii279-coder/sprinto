"""Step 2: turn cleaned page text into structured company facts, each backed by a quote from the site."""
import config
import llm

STAGES = ["pre_seed", "seed", "series_a", "series_b", "series_c", "series_d_plus", "public", "bootstrapped", "unknown"]
COMPLIANCE = ["certified", "in_progress", "mentioned", "not_found"]

SCHEMA = {
    "type": "object",
    "properties": {
        "company_name": {"type": "string"},
        "is_saas": {"type": "string", "enum": ["yes", "no", "unknown"]},
        "what_they_sell": {"type": "string", "description": "one sentence"},
        "sells_to": {"type": "string", "enum": ["smb", "midmarket", "enterprise", "mixed", "unknown"]},
        "funding_stage": {"type": "string", "enum": STAGES},
        "employee_estimate": {"type": "integer", "description": "-1 if the pages don't say"},
        "soc2": {"type": "string", "enum": COMPLIANCE},
        "iso27001": {"type": "string", "enum": COMPLIANCE},
        "gdpr_mentioned": {"type": "boolean"},
        "enterprise_signals": {"type": "array", "items": {"type": "string"},
                               "description": "e.g. enterprise plan, SSO/SAML, named large customers, security questionnaire mentions"},
        "notable_customers": {"type": "array", "items": {"type": "string"}},
        "security_or_compliance_hiring": {"type": "boolean"},
        "people": {"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string"}, "title": {"type": "string"}}, "required": ["name", "title"]}},
        "evidence": {"type": "array", "items": {"type": "object", "properties": {
            "fact": {"type": "string"}, "quote": {"type": "string"}, "url": {"type": "string"}},
            "required": ["fact", "quote", "url"]}},
    },
    "required": ["company_name", "is_saas", "what_they_sell", "sells_to", "funding_stage", "employee_estimate",
                 "soc2", "iso27001", "gdpr_mentioned", "enterprise_signals", "notable_customers",
                 "security_or_compliance_hiring", "people", "evidence"],
}

PROMPT = """You are a research analyst. From the website pages below, extract facts about the company.

Rules:
- Use ONLY what the pages say. If a page doesn't state something, use "unknown", -1, false, "not_found" or [].
- is_saas: "yes" if they sell software that customers use over the internet on a subscription or usage plan,
  including open-source products with a paid hosted/cloud version. "no" only for agencies, services firms,
  marketplaces, hardware, or purely free/self-hosted tools with no paid cloud offering.
- soc2 / iso27001: "certified" only if the page says they are certified / audited / compliant;
  "in_progress" if they say they are working towards it; "mentioned" if it's only named (e.g. their customers need it).
- people: only real named people with titles that appear on the pages (founders, leadership, team). Never invent.
- evidence: one entry per important fact, with a short exact quote copied from the page and the page URL.

Pages:
{pages}"""


def extract(pages):
    """pages: list of scrape.fetch() results that succeeded."""
    joined = "\n\n".join(f"=== {p['url']} ({p['title']}) ===\n{p['text']}" for p in pages)
    return llm.ask_json(PROMPT.format(pages=joined), SCHEMA, temperature=config.EXTRACT_TEMPERATURE)
