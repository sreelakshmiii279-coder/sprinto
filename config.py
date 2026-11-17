"""Every setting in one place. Business rules are marked; change those with the Growth Lead, not alone."""
import os
from dotenv import load_dotenv

# Always this project's .env, whatever folder the program is started from. On Vercel there is no .env file;
# settings come from the project's environment variables.
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), override=True)

# --- Model (technical) ---
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
EXTRACT_TEMPERATURE = 0.0   # pulling facts: no creativity
DRAFT_TEMPERATURE = 0.4     # writing: a little variety, still grounded

# --- Scraping (technical) ---
USER_AGENT = "SprintoOutreachResearch/1.0 (MESA student project; contact via TO_ADDRESS)"
TIMEOUT_S = 15
MAX_PAGE_CHARS = 6000       # cleaned text sent to the model per page (cost control)

# --- Qualification (BUSINESS RULES) ---
# Score is 0-100 and the threshold is on the SAME 0-100 scale (the S1 bug was 0-100 vs 0.7).
QUALIFY_THRESHOLD = 60
MAX_ROUNDS = 2              # extra pages read + re-extracted per company before deciding (loop cap)
MAX_FETCH_ATTEMPTS = 4      # hard cap on page fetches, including failed ones
MAX_EMPLOYEES = 1000        # bigger than this: past Sprinto's sweet spot
TARGET_STAGES = {"seed", "series_a", "series_b", "series_c"}  # seed allowed but scores lower

# --- Contacts (BUSINESS RULE): who owns compliance, by company size ---
ROLES_SMALL = ["founder", "co-founder", "ceo", "cto"]                                   # < 50 people
ROLES_MID = ["ciso", "head of security", "security", "compliance", "grc", "cto",
             "vp engineering", "head of engineering", "founder", "co-founder", "ceo"]    # 50+ people

# --- Sending (SAFETY RULE) ---
TO_ADDRESS = os.environ.get("TO_ADDRESS", "").strip()   # every email goes here and nowhere else
# Step 7 senders: Resend first (no app password needed), then Gmail, else outbox/.
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
RESEND_FROM = os.environ.get("RESEND_FROM", "").strip() or "Sprinto Outreach <onboarding@resend.dev>"
GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS", "").strip() or TO_ADDRESS
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "").strip()

HUNTER_API_KEY = os.environ.get("HUNTER_API_KEY", "").strip()
# Step 4 always tries the brief's sources first (Apollo list, then Hunter.io). "1" (default) then falls back to
# named leaders on the company website and a cited web search; "0" = brief's sources only.
EXTRA_CONTACT_SOURCES = os.environ.get("EXTRA_CONTACT_SOURCES", "1").strip() == "1"

# Run history, Hunter cache, Apollo to-do list. Postgres when set (needed on Vercel), else local files.
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
# Web app: most companies it will process per 24 hours (protects Gemini / Hunter / Resend quotas).
DAILY_RUN_CAP = int(os.environ.get("DAILY_RUN_CAP", "30"))
