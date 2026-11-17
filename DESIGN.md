# Sprinto cold outreach: design decisions

MESA PGP C4 · Term 2 AI · Case 02 "Cold Outreach, at Scale" (3 Nov 2026). Everything here was decided before
or while building, and every rule below lives in `config.py` or the step file named next to it.

## 1. The 9 checks: does this deserve to be built?

| # | Check | Answer |
|---|---|---|
| 1 | Problem real? | Yes. 15–20 min per company by hand; quality drops by the end of the week. |
| 2 | Workflow repeated? | Yes. Same research → contact → email steps for every prospect, every week. |
| 3 | Input available? | Yes. Company websites are public; funding/headcount via cited web search; contacts via Apollo/Hunter or public sources. |
| 4 | Output valuable? | Yes. A qualified lead + named contact + drafted email is directly usable. |
| 5 | Impact measurable? | Yes. Time per company, % of drafts the Growth Lead rewrites, reply rate. |
| 6 | ROI worth it? | Yes. ~35 s and a few cents of model calls per company vs 15–20 min of a Growth Lead's time. |
| 7 | Failure risk OK? | Only with a boundary: emails go to our own inbox, never to a prospect, until a human approves. |
| 8 | Judgement protected? | Yes. The model extracts facts; the qualify decision is transparent code a human can read and change. |
| 9 | Owner clear? | The Growth Lead owns the ICP rules (`config.py`) and approves every send. |

## 2. The 5 pre-build decisions

1. **Outcome:** Sprinto's Growth Lead goes from 15–20 min to under 2 min of her time per company, without email quality dropping; ultimately more qualified meetings per week (pipeline ₹, not just time).
2. **Baseline:** 8–15 companies/week, 15–20 min each (2–5 hours/week), quality falls toward the end of the list.
3. **Workflow change:** she stops researching and writing; she supplies the domain list and reviews/approves drafts (the human gate). The system never sends to a prospect on its own.
4. **Measurement plan:** per run: seconds per company (`runs/run_log.jsonl`); weekly: % of drafts she rewrites, PoC accuracy (is it the right person?), reply rate vs her manual emails.
5. **Kill criterion:** shut it down if she rewrites more than 50% of emails, if the right person is found less than 60% of the time, or if running + reviewing takes longer than doing it by hand.

**Capability ceiling:** she can review ~15 drafts a week, so feed the system ~30–50 domains a week (roughly a third qualify), not hundreds.

## 3. ICP: "right companies", arrived at through research

From the case: SaaS, typically Series A–C, either preparing for a compliance audit or under pressure from enterprise customers. What that means in code (`qualify.py`):

- **Drop immediately (short circuits):** not SaaS · already SOC 2 certified (they're past the audit) · Series D+ or public · more than 1,000 people.
- **Score 0–100** (threshold **60, on the same 0–100 scale**):

| Signal | Points | Why it matters to Sprinto |
|---|---|---|
| SaaS product (10 if unconfirmed) | 25 | Sprinto only sells to SaaS |
| Series A–C (seed 15, unknown/bootstrapped 8) | 25 | the stage where enterprise deals start demanding certification |
| Sells to enterprise / mid-market | 15 | those buyers send security questionnaires and ask for SOC 2 |
| 2+ enterprise signals (SSO, enterprise plan, big logos) | 10 | the same pressure, seen on the site |
| Working towards SOC 2 / ISO 27001 (mentioned only: 15) | 25 | literally preparing for an audit |
| Mentions GDPR | 5 | another framework Sprinto covers |
| Hiring for security / compliance | 10 | building the function Sprinto replaces |
| 20–500 people | 10 | big enough to need it, small enough to lack a GRC team |
| Trust/security page we couldn't read | −15 | might already be certified: check before sending |

## 4. Evidence map (the qualify loop)

| Question | Fact that answers it | Where it lives | Sufficient when | Limit | If unanswered | Short circuit |
|---|---|---|---|---|---|---|
| Is it SaaS? | Subscription software sold online (incl. paid cloud of open source) | Homepage, pricing | Clear yes/no | 2 extra pages | scored as "probably" (10) | "no" → drop |
| Funding stage? | Latest round | About, press, then web search | A named round | 1 cited search | scored as unknown (8) | Series D+/public → drop |
| Compliance status? | SOC 2 / ISO 27001 certified, in progress, mentioned | Security / trust page, footer | Any statement | 2 extra pages | not_found | SOC 2 certified → drop |
| Enterprise pressure? | Enterprise plan, SSO, named big customers | Customers, pricing | 2+ signals | 2 extra pages | no points | n/a |
| Size? | Employee count | About, careers, then web search | A number | 1 cited search | no points | >1,000 → drop |

Loop rules: a "round" is an extra page that was read and re-extracted (max 2). Failed fetches don't use a round but are capped at 4 attempts, so the loop always ends. A search answer is only used if it cites sources.

## 5. Components map

```
domains.txt → 1 scrape (code) → 2 extract (LLM, facts + quotes) → 3 qualify (code + capped loop + 1 search)
                                                                        ├─ drop / below threshold / unreadable → log
                                                                        ↓ qualified
   contacts.csv (Apollo) / Hunter.io / website / cited search → 4 find contact (code, role by size)
                                                                        ↓
                                     5–6 pain points + draft (LLM, checked in code) → human review → 7 send (own inbox) → run log
```

## 6. Decisions you can defend

- **Why the model doesn't decide "qualified":** a model score is hard to audit and drifts. The model only reads pages and returns facts with exact quotes; the yes/no is plain rules a founder can read in one screen (the S1 lesson: the threshold and the score must be on the same scale, and you must be able to point at the line).
- **Why "unreadable" isn't a score of 0:** a site we can't read is not a bad fit (the S1 bare-except bug). It's flagged for a human.
- **Why the scraper announces itself and respects robots.txt:** scraping is a last resort (S4: hiQ vs LinkedIn). Sites that block us are logged, not worked around.
- **Why clean HTML before the model:** raw HTML is mostly menus and scripts; cleaning cuts tokens (and cost) by an order of magnitude or more.
- **Why the contact depends on size:** under 50 people a founder owns compliance; above that, security/engineering leadership. Never "the first person with manager in their title".
- **Why emails go to our own inbox:** the brief says so, and the human gate is the workflow change. `send.py` has no code path that uses the prospect's address.
- **Why drafts are checked in code:** first-name greeting, no placeholders, no hype words, under 140 words, and every hook/pain must point at a real evidence item. A draft that fails twice is not sent.

## 7. Known limits (be ready for these questions)

- **JavaScript-only sites** (e.g. Hoppscotch) can't be read without a headless browser (10–15× the cost); they're flagged "unreadable" for a human instead.
- **Acquisitions:** Zenduty now redirects to Xurrent; the funding found (2021 seed) may describe Zenduty before the acquisition. A human should sanity-check stage for redirected domains.
- **Run-to-run variation:** the model can read the same page slightly differently (Twenty scored 45–60 across runs). Borderline scores near 60 deserve a human look.
- **Contacts** come only from the brief's two sources by default: Apollo (looked up by hand, `contacts.csv`) and Hunter.io (25 free searches/month, so it only searches qualified companies and caches results). Website / web-search contacts are an opt-in extra (`EXTRA_CONTACT_SOURCES=1`) because they can be out of date.
- **Next (post-Diwali build):** the S5 feedback loop (store the Growth Lead's edits with persona/stage tags, track a disagreement score) and the S6 reply agent (tools with 4-rule descriptions, a state object, a retry table).
