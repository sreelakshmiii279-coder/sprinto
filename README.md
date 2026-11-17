# Sprinto cold outreach pipeline

MESA Term 2 · AI Case 02. Give it a list of company domains; for each one it decides whether the company fits
Sprinto's ICP, finds the right person, writes a personal cold email, and sends it **to your own inbox only**.
Every decision and its reason is logged so you can defend it. Design and reasoning: [DESIGN.md](DESIGN.md).

## The 7 steps, one file each

| Step | File | What it does |
|---|---|---|
| 1 Scrape | `scrape.py` | Fetches pages politely (robots.txt, honest user agent), strips menus/scripts, reports failures |
| 2 Extract | `extract.py` | Model turns page text into company facts, each with a quote from the site |
| 3 Qualify | `qualify.py` | Evidence-map loop (≤2 extra pages, 1 cited search), short circuits, 0–100 score vs 60 |
| 4 Contact | `contacts.py` | Apollo list (option B) and Hunter.io (option A) first, as the brief asks; then website / cited web search as a labelled fallback; picks by role and company size |
| 5–6 Draft | `drafts.py` | Two evidence-backed pain points, then a short email with a specific hook; checked in code |
| 7 Send | `send.py` | Gmail (the brief's sender), else Resend, to `TO_ADDRESS` only; saves to `outbox/` if neither is set up |
| Run all | `run.py` | Runs every domain, logs to `runs/run_log.jsonl`, never hides a failure |
| Report | `report.py` | Writes `runs/report.md`: why each company, why each person, what each hook is based on |

Settings and business rules: `config.py`. Model calls: `llm.py`. Setup doctor: `check_setup.py`.

## Run it

```bash
python -m venv .venv
.venv\Scripts\activate          # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # then fill it in (see below)
python check_setup.py           # checks Gemini, Gmail, Hunter/Apollo; sends nothing
python run.py                   # every domain in data/domains.txt
python run.py acme.com          # just one
python run.py --no-send         # stop after drafting
python report.py                # readable report in runs/report.md
```

## Settings (.env, never committed)

- `GEMINI_API_KEY`, `GEMINI_MODEL`: Google AI Studio key and model.
- `TO_ADDRESS`: your own email. Every email goes here and nowhere else.
- Step 7 sender (Gmail is used first when set, as the brief asks; Resend otherwise):
  - **Resend:** `RESEND_API_KEY` from resend.com (a send-only key is enough). With the default sender
    `onboarding@resend.dev`, Resend only delivers to the email your Resend account is registered with, so
    `TO_ADDRESS` must be that address (or verify a domain on Resend and set `RESEND_FROM`).
  - **Gmail:** `GMAIL_ADDRESS` + `GMAIL_APP_PASSWORD` (myaccount.google.com/apppasswords, needs 2-Step Verification).
  - Neither: emails are saved to `outbox/`.
- Step 4 needs **one** of these (the brief's two options):
  - **Option A, Hunter.io:** `HUNTER_API_KEY` from hunter.io (free tier: 25 searches/month). Only qualified companies
    are searched, and results are cached in `data/hunter_cache.json`, so re-runs don't use up searches.
  - **Option B, Apollo:** look the person up on apollo.io and add a row to `data/contacts.csv`
    (`domain,name,title,email`). Qualified companies with no contact are listed in `data/apollo_todo.csv`,
    with the roles to look for.
- `EXTRA_CONTACT_SOURCES=1` (default; an extra beyond the brief): after Apollo and Hunter, fall back to named leaders
  on the company's website and a cited web search. Set `0` to use only the brief's two sources.

Every line of the case brief, mapped to the file that does it: [DESIGN.md, section 0](DESIGN.md).

## Last run (17 Nov 2026, 9 domains, ~35 s each)

Step 7 verified: the Zenduty email was delivered to my inbox through Resend.

| Company | Result | Why |
|---|---|---|
| Zenduty / Xurrent IMR | Emailed (75) | SaaS, seed, ~47 people, enterprise customers; email to co-founder & CEO opens with their Bajaj Finserv Health case study (contact found with the extra web-search source; with the brief's sources only, it waits in `apollo_todo.csv`) |
| Twenty | Held back (45–60) | Fits on paper, but has a trust page we couldn't read: may already be certified, check first |
| SpotDraft, Rocketlane, Hevo, Airmeet, Formbricks | Dropped | Already SOC 2 certified (found on their security/trust pages) |
| Postman | Dropped | Too late-stage |
| Hoppscotch | Needs a human | JavaScript-only site, couldn't be read |
