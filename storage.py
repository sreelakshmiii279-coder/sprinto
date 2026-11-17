"""Where results live: Postgres (Neon) when DATABASE_URL is set - required on Vercel, where files don't
persist - otherwise local files (runs/run_log.jsonl, data/hunter_cache.json, data/apollo_todo.csv)."""
import csv
import json
import os

import config

HERE = os.path.dirname(os.path.abspath(__file__))
# Vercel's filesystem is read-only except /tmp.
WRITABLE = "/tmp" if os.environ.get("VERCEL") else HERE

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id serial PRIMARY KEY, domain text NOT NULL, status text NOT NULL, score int,
  row jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS hunter_cache (domain text PRIMARY KEY, people jsonb NOT NULL,
  fetched_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS apollo_todo (domain text PRIMARY KEY, company text, roles text,
  added_at timestamptz NOT NULL DEFAULT now());
"""

_ready = False


def _db():
    global _ready
    import psycopg
    conn = psycopg.connect(config.DATABASE_URL, autocommit=True)
    if not _ready:
        conn.execute(SCHEMA)
        _ready = True
    return conn


def _path(*parts):
    p = os.path.join(WRITABLE, *parts)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


# ---- run log ----

def log_run(row):
    if config.DATABASE_URL:
        with _db() as c:
            c.execute("INSERT INTO runs (domain, status, score, row) VALUES (%s, %s, %s, %s)",
                      (row["domain"], row["status"], row.get("score"), json.dumps(row, ensure_ascii=False)))
        return
    with open(_path("runs", "run_log.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def recent_runs(limit=50):
    """Newest first."""
    if config.DATABASE_URL:
        with _db() as c:
            return [r[0] for r in c.execute("SELECT row FROM runs ORDER BY id DESC LIMIT %s", (limit,))]
    path = _path("runs", "run_log.jsonl")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f][::-1][:limit]


def runs_today():
    if config.DATABASE_URL:
        with _db() as c:
            return c.execute("SELECT count(*) FROM runs WHERE created_at > now() - interval '24 hours'").fetchone()[0]
    return 0


# ---- Hunter.io cache (protects the free monthly searches) ----

def hunter_get(domain):
    if config.DATABASE_URL:
        with _db() as c:
            r = c.execute("SELECT people FROM hunter_cache WHERE domain = %s", (domain,)).fetchone()
            return r[0] if r else None
    path = _path("data", "hunter_cache.json")
    return json.load(open(path, encoding="utf-8")).get(domain) if os.path.exists(path) else None


def hunter_put(domain, people):
    if config.DATABASE_URL:
        with _db() as c:
            c.execute("INSERT INTO hunter_cache (domain, people) VALUES (%s, %s) ON CONFLICT (domain) "
                      "DO UPDATE SET people = EXCLUDED.people, fetched_at = now()", (domain, json.dumps(people)))
        return
    path = _path("data", "hunter_cache.json")
    cache = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    cache[domain] = people
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=1)


# ---- Apollo to-do list (qualified companies nobody has been found for) ----

def apollo_todo_add(domain, company, roles):
    if config.DATABASE_URL:
        with _db() as c:
            c.execute("INSERT INTO apollo_todo (domain, company, roles) VALUES (%s, %s, %s) "
                      "ON CONFLICT (domain) DO NOTHING", (domain, company, roles))
        return
    path = _path("data", "apollo_todo.csv")
    exists = os.path.exists(path)
    rows = list(csv.DictReader(open(path, encoding="utf-8"))) if exists else []
    if any(r["domain"] == domain for r in rows):
        return
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow(["domain", "company", "look_for_roles"])
        w.writerow([domain, company, roles])


def apollo_todo():
    if config.DATABASE_URL:
        with _db() as c:
            return [{"domain": d, "company": co, "look_for_roles": r}
                    for d, co, r in c.execute("SELECT domain, company, roles FROM apollo_todo ORDER BY added_at")]
    path = _path("data", "apollo_todo.csv")
    return list(csv.DictReader(open(path, encoding="utf-8"))) if os.path.exists(path) else []
