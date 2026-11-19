"""Web app for the Sprinto pipeline (Vercel serverless, Flask).

GET  /              the page: paste domains, run, see every decision
POST /api/run       {"domain": "...", "send": true}  -> one company, end to end (60-100 s)
GET  /api/runs      recent runs, newest first
GET  /api/meta      default domains, daily cap, Apollo to-do list
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from flask import Flask, jsonify, request, send_from_directory  # noqa: E402

import config  # noqa: E402
import run  # noqa: E402
import storage  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
app = Flask(__name__)
DOMAIN_RE = re.compile(r"^(?=.{4,253}$)([a-z0-9-]{1,63}\.)+[a-z]{2,24}$")


def clean_domain(raw):
    """A pasted URL or domain -> bare domain ("HTTPS://www.Acme.com:443/pricing#x" -> "acme.com"), or None."""
    if not isinstance(raw, str):  # numbers, lists, null from direct API calls
        return None
    d = raw.strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = re.split(r"[/?#]", d)[0].split(":")[0].removeprefix("www.").rstrip(".")
    return d if DOMAIN_RE.match(d) and ".." not in d else None


@app.get("/")
def page():
    return send_from_directory(os.path.join(ROOT, "web"), "index.html")


@app.get("/api/meta")
def meta():
    with open(os.path.join(ROOT, "data", "domains.txt"), encoding="utf-8") as f:
        domains = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    used = storage.runs_today()
    return jsonify(domains=domains, cap=config.DAILY_RUN_CAP, used_today=used,
                   apollo_todo=storage.apollo_todo(), to_address=config.TO_ADDRESS,
                   sender="Gmail" if config.GMAIL_APP_PASSWORD else "Resend" if config.RESEND_API_KEY else "outbox only")


@app.get("/api/runs")
def runs():
    return jsonify(storage.recent_runs(60))


@app.post("/api/run")
def run_domain():
    body = request.get_json(silent=True) or {}
    domain = clean_domain(body.get("domain"))
    if not domain:
        return jsonify(error="That doesn't look like a company domain (e.g. acme.com)."), 400
    if storage.runs_today() >= config.DAILY_RUN_CAP:
        return jsonify(error=f"Daily limit reached ({config.DAILY_RUN_CAP} companies per 24 hours). "
                             "It protects the Gemini, Hunter and Resend quotas; try again tomorrow."), 429
    return jsonify(run.run_one(domain, do_send=bool(body.get("send", True))))
