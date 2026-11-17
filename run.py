"""Run the whole pipeline on data/domains.txt.

    python run.py                 # all domains in data/domains.txt
    python run.py acme.com x.io   # just these
    python run.py --no-send       # stop after drafting (outbox only)

Every decision, with its reason, is logged (Postgres if DATABASE_URL is set, else runs/run_log.jsonl) -
that log is how you defend the system.
A failure on one domain is logged with its error and the run carries on; it never hides as a "no".
"""
import os
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

import contacts
import drafts
import qualify
import send
import storage


def process(domain, do_send=True):
    row = {"domain": domain, "at": datetime.now(timezone.utc).isoformat()}
    q = qualify.qualify(domain)
    row.update(status=q["status"], score=q["score"], qualify_reasons=q["reasons"], pages=q["pages"],
               rounds=q["rounds"], company=q["company"])
    if q["status"] != "qualified":
        return row

    # If the pages we read live on another domain (a redirect or acquisition), Hunter is searched there too.
    hosts = [urlparse(p["url"]).netloc.removeprefix("www.") for p in q["pages"] if p["ok"] and p["url"].startswith("http")]
    site = next((h for h in hosts if h != domain), None)
    contact, why = contacts.find_contact(domain, q["company"], site_domain=site)
    row.update(contact=contact, contact_reason=why)
    if not contact:
        row["status"] = "no_contact"
        return row

    d, problems = drafts.draft(q["company"], contact)
    row.update(pain_points=d["pain_points"], hook=d.get("hook"), subject=d["subject"], body=d["body"],
               draft_problems=problems)
    if problems:
        row["status"] = "draft_failed_checks"  # don't send something that failed its own checks
        return row

    row["send"] = send.send(domain, contact, d["subject"], d["body"]) if do_send else "not sent (--no-send)"
    row["status"] = "emailed" if do_send else "drafted"
    return row


def run_one(domain, do_send=True):
    """One company, end to end, logged. Used by the command line and the web app."""
    t = time.time()
    try:
        row = process(domain, do_send)
    except Exception as e:  # one company's failure must be visible, not silent, and not stop the run
        row = {"domain": domain, "status": "error", "error": f"{type(e).__name__}: {e}"}
    row["seconds"] = round(time.time() - t, 1)
    storage.log_run(row)
    return row


def main(argv):
    do_send = "--no-send" not in argv
    domains = [a for a in argv if not a.startswith("--")]
    if not domains:
        with open(os.path.join("data", "domains.txt"), encoding="utf-8") as f:
            domains = [l.strip() for l in f if l.strip() and not l.startswith("#")]

    results = []
    for domain in domains:
        row = run_one(domain, do_send)
        results.append(row)
        who = row.get("contact") or {}
        print(f"{domain:28} {row['status']:20} score={row.get('score')!s:5} "
              f"{who.get('name', ''):22} {row['seconds']}s", flush=True)

    print(f"\n{sum(r['status'] in ('emailed', 'drafted') for r in results)}/{len(results)} reached a draft. "
          "Readable report: python report.py")


if __name__ == "__main__":
    main(sys.argv[1:])
