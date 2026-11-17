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
| 4 Contact | `contacts.py` | Apollo list → Hunter.io → website → cited search; picks by role and company size |
| 5–6 Draft | `drafts.py` | Two evidence-backed pain points, then a short email with a specific hook; checked in code |
| 7 Send | `send.py` | Gmail to `TO_ADDRESS` only, or saves to `outbox/` if no Gmail app password |
| Run all | `run.py` | Runs every domain, logs to `runs/run_log.jsonl`, never hides a failure |
| Report | `report.py` | Writes `runs/report.md`: why each company, why each person, what each hook is based on |

Settings and business rules: `config.py`. Model calls: `llm.py`.

## Run it

```bash
python -m venv .venv
.venv\Scripts\activate          # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # then fill it in (see below)
python run.py                   # every domain in data/domains.txt
python run.py acme.com          # just one
python run.py --no-send         # stop after drafting
python report.py                # readable report in runs/report.md
```

## Settings (.env, never committed)

- `GEMINI_API_KEY`, `GEMINI_MODEL`: Google AI Studio key and model.
- `TO_ADDRESS`: your own email. Every email goes here and nowhere else.
- `GMAIL_ADDRESS` + `GMAIL_APP_PASSWORD`: to actually send through Gmail. Create an app password at
  myaccount.google.com → Security → 2-Step Verification → App passwords. Without it, emails are saved to `outbox/`.
- `HUNTER_API_KEY` (optional): Hunter.io Domain Search, 25 free searches/month (case option A).
- Case option B (Apollo): add people you looked up by hand to `data/contacts.csv` as `domain,name,title,email`.

## Last run (17 Nov 2026, 9 domains, ~35 s each)

| Company | Result | Why |
|---|---|---|
| Zenduty / Xurrent IMR | Emailed (75) | SaaS, seed, ~47 people, enterprise customers; email to co-founder & CEO opens with their Bajaj Finserv Health case study |
| Twenty | Held back (45–60) | Fits on paper, but has a trust page we couldn't read: may already be certified, check first |
| SpotDraft, Rocketlane, Hevo, Airmeet, Formbricks | Dropped | Already SOC 2 certified (found on their security/trust pages) |
| Postman | Dropped | Too late-stage |
| Hoppscotch | Needs a human | JavaScript-only site, couldn't be read |
