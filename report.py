"""Turn the latest run of each domain in runs/run_log.jsonl into a readable report (runs/report.md):
why each company qualified or not, why this person, and what the email's hook is based on."""
import json
import os

LABEL = {"emailed": "Emailed", "drafted": "Drafted", "qualified": "Qualified", "below_threshold": "Below threshold",
         "dropped": "Dropped", "unreadable": "Couldn't read site (needs a human)", "no_contact": "No contact found",
         "draft_failed_checks": "Draft failed checks", "error": "Error"}


def main():
    latest = {}
    with open(os.path.join("runs", "run_log.jsonl"), encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            latest[row["domain"]] = row
    out = ["# Sprinto outreach: decision report\n"]
    for r in latest.values():
        c = r.get("company") or {}
        out.append(f"## {c.get('company_name') or r['domain']} ({r['domain']}): {LABEL.get(r['status'], r['status'])}")
        if r.get("error"):
            out.append(f"- Error: `{r['error']}`")
        if c:
            out.append(f"- **What they do:** {c['what_they_sell']}")
            out.append(f"- **Facts:** SaaS {c['is_saas']} · stage {c['funding_stage']} · sells to {c['sells_to']} · "
                       f"~{c['employee_estimate'] if c['employee_estimate'] >= 0 else '?'} people · "
                       f"SOC 2 {c['soc2']} · ISO 27001 {c['iso27001']}")
        if r.get("qualify_reasons"):
            out.append("- **Why this decision:**")
            out += [f"  - {x}" for x in r["qualify_reasons"]]
        if r.get("pages"):
            out.append("- **Pages read:** " + ", ".join(f"{p['url']}{'' if p['ok'] else ' (failed: ' + p['reason'] + ')'}"
                                                        for p in r["pages"]) + f" · extra rounds: {r.get('rounds', 0)}")
        if r.get("contact_reason"):
            out.append(f"- **Why this person:** {r['contact_reason']}")
        for i, p in enumerate(r.get("pain_points") or [], 1):
            out.append(f"- **Pain {i}:** {p['pain']}  \n  _Evidence:_ \"{p['evidence']['quote']}\" ({p['evidence']['url']})")
        if r.get("hook"):
            out.append(f"- **Hook based on:** \"{r['hook']['quote']}\" ({r['hook']['url']})")
        if r.get("body"):
            out.append(f"\n**Subject:** {r['subject']}\n\n```\n{r['body']}\n```")
        if r.get("draft_problems"):
            out.append(f"- Draft problems: {', '.join(r['draft_problems'])}")
        if r.get("send"):
            out.append(f"- **Send:** {r['send']}")
        out.append(f"- Took {r.get('seconds')}s\n")
    with open(os.path.join("runs", "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print("Wrote runs/report.md")


if __name__ == "__main__":
    main()
