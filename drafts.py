"""Steps 5-6: the two most likely pain points for this person, then a short personal email.

Every pain point must point at a piece of evidence from the site, and the hook must be a real fact
from that evidence. The draft is checked in code before it's accepted.
"""
import json
import re

import config
import llm

SCHEMA = {
    "type": "object",
    "properties": {
        "pain_points": {"type": "array", "minItems": 2, "maxItems": 2, "items": {"type": "object", "properties": {
            "pain": {"type": "string"}, "evidence_index": {"type": "integer"}}, "required": ["pain", "evidence_index"]}},
        "hook_evidence_index": {"type": "integer"},
        "subject": {"type": "string"},
        "body": {"type": "string"},
    },
    "required": ["pain_points", "hook_evidence_index", "subject", "body"],
}

PROMPT = """You write first-touch cold emails for Sprinto's Growth Lead.

About Sprinto (use only these claims): Sprinto automates compliance certifications - SOC 2, ISO 27001,
GDPR - for SaaS companies. It connects to the tools a company already uses, runs the evidence collection
and control monitoring continuously, and gets teams audit-ready without a dedicated compliance team.

Recipient: {name}, {title} at {company}.
What we know about {company} (numbered evidence from their own website):
{evidence}
Other facts: {facts}

Do this:
1. Pick the TWO most likely compliance-related pain points for this person in this role, each tied to one
   evidence item (give its number).
2. Write the email:
   - Open with a specific hook from ONE evidence item (give its number) - something only true of this company.
     The hook must NOT be their homepage tagline or a description of what they sell. Prefer, in order:
     a recent funding round, a named enterprise customer, an enterprise plan / SSO / security page,
     GDPR or data-processor duties, a security or compliance hire.
   - Connect it to their likely pain in one sentence, then one sentence on how Sprinto helps.
   - One low-effort ask (a 15-minute call). Sign off as "Sprinto team".
   - Address them by first name. Under 120 words. Plain, human, no made-up numbers, no placeholders like [Name].
   - No hype words: effortless(ly), seamless(ly), revolutionary, game-changing, unlock, supercharge.
   - Short paragraphs separated by blank lines (greeting, hook, how Sprinto helps, ask, sign-off).
   - Subject under 8 words, specific to them."""


def _check(d, contact, n_evidence):
    first = contact["name"].split()[0]
    problems = []
    if first.lower() not in d["body"].lower():
        problems.append(f"doesn't address {first} by name")
    if re.search(r"\[[^\]]+\]|\{[^}]+\}", d["body"] + d["subject"]):
        problems.append("contains a placeholder")
    if len(d["body"].split()) > 140:
        problems.append("too long")
    hype = [w for w in ("effortless", "seamless", "revolutionary", "game-changing", "supercharge", "unlock")
            if w in d["body"].lower()]
    if hype:
        problems.append(f"hype words: {', '.join(hype)}")
    idx = [d["hook_evidence_index"]] + [p["evidence_index"] for p in d["pain_points"]]
    if any(not (1 <= i <= n_evidence) for i in idx):
        problems.append("points at evidence that doesn't exist")
    return problems


def draft(company, contact):
    evidence = company.get("evidence", [])
    numbered = "\n".join(f"{i}. {e['fact']} - \"{e['quote']}\" ({e['url']})" for i, e in enumerate(evidence, 1))
    facts = json.dumps({k: company[k] for k in ("what_they_sell", "sells_to", "funding_stage", "soc2", "iso27001",
                                                 "enterprise_signals", "notable_customers")})
    prompt = PROMPT.format(name=contact["name"], title=contact["title"], company=company["company_name"],
                           evidence=numbered or "(none)", facts=facts)
    for _ in range(2):  # one rewrite if the checks fail
        d = llm.ask_json(prompt, SCHEMA, temperature=config.DRAFT_TEMPERATURE)
        problems = _check(d, contact, len(evidence))
        if not problems:
            d["hook"] = evidence[d["hook_evidence_index"] - 1]
            d["pain_points"] = [{**p, "evidence": evidence[p["evidence_index"] - 1]} for p in d["pain_points"]]
            return d, []
        prompt += f"\n\nYour previous draft had problems: {'; '.join(problems)}. Fix them."
    return d, problems
