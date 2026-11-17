"""Checks everything the pipeline needs before a run. Sends nothing; spends no Hunter searches.

    python check_setup.py
"""
import csv
import os
import smtplib
import subprocess

import requests

import config

OK, MISSING, FAIL = "OK     ", "MISSING", "FAILED "


def gemini():
    try:
        import llm
        llm.ask_json('Reply with {"ok": true}', {"type": "object", "properties": {"ok": {"type": "boolean"}},
                                                  "required": ["ok"]})
        return OK, f"Gemini answers ({config.MODEL})"
    except KeyError:
        return MISSING, "GEMINI_API_KEY is not in .env"
    except Exception as e:  # noqa: BLE001
        return FAIL, f"Gemini call failed: {str(e)[:120]}"


def gmail():
    if not config.TO_ADDRESS:
        return MISSING, "TO_ADDRESS (your own email) is not in .env"
    if config.RESEND_API_KEY and not config.GMAIL_APP_PASSWORD:
        r = requests.get("https://api.resend.com/domains", timeout=15,
                         headers={"Authorization": f"Bearer {config.RESEND_API_KEY}"})
        # A send-only key is refused here with "restricted_api_key" - that still means the key is valid.
        if r.status_code >= 400 and "restricted_api_key" not in r.text:
            return FAIL, f"Resend rejected the key (HTTP {r.status_code})"
        return OK, (f"Resend key works; emails go from {config.RESEND_FROM} to {config.TO_ADDRESS} "
                    "(onboarding@resend.dev can only reach your Resend account's email)")
    if not config.GMAIL_APP_PASSWORD:
        return MISSING, ("GMAIL_APP_PASSWORD is empty, so emails go to outbox/ instead of your inbox. Create one at "
                         "myaccount.google.com/apppasswords (needs 2-Step Verification) and set GMAIL_ADDRESS to "
                         "the Gmail account it belongs to.")
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as s:
            s.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
        return OK, f"Gmail login works for {config.GMAIL_ADDRESS}; emails will go to {config.TO_ADDRESS}"
    except smtplib.SMTPAuthenticationError:
        return FAIL, ("Gmail rejected the login. Check GMAIL_ADDRESS matches the account the app password belongs "
                      "to (school/work accounts often block app passwords; a personal Gmail works).")
    except Exception as e:  # noqa: BLE001
        return FAIL, f"Gmail connection failed: {str(e)[:120]}"


def hunter():
    if not config.HUNTER_API_KEY:
        return MISSING, "HUNTER_API_KEY is empty (option A). Fine if you use Apollo (option B) instead."
    r = requests.get("https://api.hunter.io/v2/account", params={"api_key": config.HUNTER_API_KEY}, timeout=15)
    if r.status_code != 200:
        return FAIL, f"Hunter.io rejected the key (HTTP {r.status_code})"
    s = r.json()["data"]["requests"]["searches"]
    return OK, f"Hunter.io key works: {s['used']} of {s['available']} searches used this month"


def apollo():
    path = os.path.join("data", "contacts.csv")
    rows = [r for r in csv.DictReader(open(path, encoding="utf-8")) if r.get("domain") and
            not r["domain"].startswith("#")] if os.path.exists(path) else []
    todo = os.path.join("data", "apollo_todo.csv")
    pending = max(0, sum(1 for _ in open(todo, encoding="utf-8")) - 1) if os.path.exists(todo) else 0
    if rows:
        return OK, f"{len(rows)} hand-picked contact(s) in data/contacts.csv" + \
               (f"; {pending} more companies waiting in data/apollo_todo.csv" if pending else "")
    return MISSING, "no contacts in data/contacts.csv yet (option B)" + \
           (f"; {pending} qualified companies listed in data/apollo_todo.csv to look up" if pending else "")


def secrets():
    try:
        out = subprocess.run(["git", "check-ignore", ".env"], capture_output=True, text=True).stdout.strip()
        return (OK, ".env is ignored by git") if out else (FAIL, ".env is NOT ignored by git: fix .gitignore")
    except FileNotFoundError:
        return OK, "git not installed (nothing to leak)"


if __name__ == "__main__":
    results = [("Gemini", gemini()), ("Send (step 7)", gmail()), ("Hunter.io (4A)", hunter()),
               ("Apollo (4B)", apollo()), ("Secrets", secrets())]
    for name, (state, msg) in results:
        print(f"[{state}] {name:15} {msg}")
    a, b = results[2][1][0], results[3][1][0]
    print("\nStep 4 ready:", "yes" if OK in (a, b) else "no - add a Hunter.io key or Apollo contacts")
    print("Step 7 ready:", "yes" if results[1][1][0] == OK else "no - emails will be saved to outbox/")
