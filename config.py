"""Every setting in one place. Business rules are marked; change those with the Growth Lead, not alone."""
import os
from dotenv import load_dotenv

load_dotenv()

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
GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS", "").strip() or TO_ADDRESS
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "").strip()

HUNTER_API_KEY = os.environ.get("HUNTER_API_KEY", "").strip()
