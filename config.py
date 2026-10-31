"""All tunable settings in one place: sources, keywords, taxonomy, seeds, models."""
from pathlib import Path

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
LLM_CACHE = ROOT / "data" / "llm_cache.jsonl"

SEED = 42
USER_AGENT = "Mozilla/5.0 (sip-discovery-engine; academic research; non-commercial)"
REQUEST_DELAY_S = 1.0  # polite delay between HTTP calls
HTTP_MAX_RETRIES = 6  # exponential backoff on 429/503 (honours Retry-After)

# --- Sources -----------------------------------------------------------------
# Play package IDs verified with google_play_scraper.app() on 2026-10-29.
# Search's top hit returns appId=None (scraper bug); Kuvera's ID was read from
# the Play search page and then verified with app().
PLAY_APPS = {
    "groww": "com.nextbillion.groww",
    "zerodha_kite": "com.zerodha.kite3",
    "zerodha_coin": "com.zerodha.coin",
    "indmoney": "in.indwealth",
    "paytm_money": "com.paytmmoney",
    "et_money": "com.smartspends",
    "kuvera": "com.gooogle.android.kuvera.app",
}
PLAY_REVIEWS_PER_APP = {"groww": 6000}  # Groww is the focus app
PLAY_REVIEWS_DEFAULT = 2000

# App Store IDs from the iTunes Search API (country=in) on 2026-10-29.
APPSTORE_APPS = {
    "groww": 1404871703,
    "zerodha_kite": 1449453802,
    "zerodha_coin": 1392892554,
    "indmoney": 1450178837,
    "paytm_money": 1344431352,
    "et_money": 1212752482,
    "kuvera": 1329701793,
}
APPSTORE_PAGES = 10  # the RSS feed caps at 10 pages x 50 reviews

# Reddit's official API now requires manual approval for new apps, so we use
# the public .json endpoints. robots.txt disallows them; the project owner
# chose to proceed and this is disclosed in evidence_log.md.
REDDIT_SUBREDDITS = ["IndiaInvestments", "personalfinanceindia", "mutualfunds",
                     "IndianStreetBets", "india"]
REDDIT_JSON_USER_AGENT = "python:sip-discovery-engine:v1.0 (academic research project)"
REDDIT_DELAY_S = 2.0  # minimum gap between Reddit requests
REDDIT_MAX_RETRIES = 5  # exponential backoff on 429/503
REDDIT_SEARCH_LIMIT = 100
REDDIT_USER_AGENT = "python:sip-discovery-engine:v0.1 (academic research, read-only)"  # PRAW (unused)
# Mix of problem-framed and neutral queries, so continuers aren't searched out
# of the corpus. Query choice shapes the corpus; see evidence_log.md.
REDDIT_QUERIES = ["SIP", "stop SIP", "pause SIP", "SIP mandate", "SIP loss", "SIP returns",
                  "first SIP", "started SIP", "SIP advice"]
REDDIT_POSTS_PER_QUERY = 25
REDDIT_COMMENTS_PER_POST = 30

YOUTUBE_QUERIES = [
    "SIP for beginners mutual fund India",
    "should I stop my SIP",
    "SIP returns negative what to do",
    "SIP mistakes to avoid",
    "mutual fund SIP explained hindi",
    "SIP band kare ya nahi",
    "is SIP worth it",
    "SIP vs FD",
    "Groww SIP tutorial",
    "step up SIP explained",
    # neutral / continuer-framed
    "my SIP journey",
    "SIP results after years",
    "SIP for beginners",
]
YOUTUBE_VIDEOS_PER_QUERY = 4
YOUTUBE_COMMENTS_PER_VIDEO = 400

TRADINGQNA_QUERIES = [
    "sip", "stop sip", "pause sip", "cancel sip", "sip mandate", "sip failed",
    "sip not deducted", "enach", "autopay sip", "sip installment", "step up sip",
    "sip loss", "sip returns", "xirr", "redeem sip", "elss sip",
    # neutral / continuer-framed
    "first sip", "start sip", "sip advice", "continue sip",
]
TRADINGQNA_SEARCH_PAGES = 3
TRADINGQNA_MAX_TOPICS = 400  # filled round-robin across queries, so late queries aren't cut

# --- Keyword filter ----------------------------------------------------------
SEED_KEYWORDS = [
    "sip", "systematic investment", "monthly investment", "mandate", "enach",
    "e-nach", "nach", "autopay", "auto debit", "auto-pay", "instalment",
    "installment", "emi date", "bounced", "failed", "insufficient balance",
    "stopped my sip", "paused", "cancel sip", "discontinue", "skipped",
    "step up", "elss", "lock-in", "redeem", "exit load", "xirr", "nav",
    "returns", "folio",
]
# Added after measuring hits on items the seeds missed (see evidence_log.md).
# Tested and NOT added: mutual fund(s)/mf (1,600 hits, mostly general app
# talk), stp/swp (transfer/withdrawal plans), lumpsum, deducted/debited
# (mostly tax and wallet), monthly (too broad).
ADDED_KEYWORDS = [
    "sips",                                   # plural; whole-word "sip" misses it
    "mandates", "emandate", "e-mandate",
    "installments", "instalments",
    "step-up", "stepup", "top up", "top-up",  # SIP modification
    "every month", "har mahine", "invest monthly",
    "pause", "stop investing", "stopped investing",
    "एसआईपी",                                 # SIP in Devanagari
]

CONCENTRATION_ALERT = 0.60  # stop and flag if one source passes this share

# --- Taxonomy (closed set; LLM output is validated against it) ---------------
CATEGORIES = [
    "mandate_payment_failure",
    "affordability_cashflow",
    "expectation_returns_mismatch",
    "no_answer_available",
    "app_mechanics",
    "fees_trust",
    "not_relevant",
]
LIFECYCLE_STAGES = ["starting", "first_months", "ongoing", "stopping", "stopped", "unclear"]
STOPPAGE_TYPES = ["involuntary", "voluntary", "passive", "not_applicable", "unclear"]
YES_NO_UNCLEAR = ["yes", "no", "unclear"]

# Extra fields (Q1, Q4, Q8). Segment fields must be explicitly stated, and
# their signal words must sit inside evidence_quote, or they reset to unknown.
START_MOTIVATIONS = ["wealth_building", "specific_goal", "tax_saving", "beat_fd_or_inflation",
                     "someone_recommended", "habit_or_discipline", "other", "unknown"]
INFLUENCED_BY = ["family", "friend", "finfluencer", "app_or_platform", "advisor", "other", "unknown"]
MONEY_SOURCES = ["salary", "business_income", "irregular_income", "savings",
                 "family_or_pocket_money", "other", "unknown"]
AGE_STATED = ["student", "under_25", "25_to_40", "over_40", "unknown"]
INCOME_STATED = ["salaried", "self_employed", "irregular", "no_income", "unknown"]
SEGMENT_FIELDS = ["segment_age_stated", "segment_income_stated", "money_source", "influenced_by"]

# --- LLM ---------------------------------------------------------------------
FILTER_MODEL = "openai/gpt-oss-20b"
EXTRACT_MODEL = "openai/gpt-oss-120b"
FILTER_EFFORT = "medium"   # gpt-oss reasoning effort; "low" wrongly rejected SIP reviews in dev
EXTRACT_EFFORT = "medium"
FILTER_BATCH = 10          # items per filter call (results cached per item)
EXTRACT_BATCH = 1          # items per extraction call
LLM_MAX_CHARS = 4000       # text sent per item; quotes still verified against full raw_text
DEV_SIZE = 40              # prompt-tuning sample; excludes all hand-labelled items
CORPUS_MAX = 1000          # proportional sample of the kept pool, in seeded random order
CORPUS_TARGET_RECORDS = 300  # stop once this many final records exist
CORPUS_CHUNK = 40          # items per filter+extract round; progress saved after each
FREEZE_FILE = PROCESSED_DIR / "prompt_freeze.json"
GOLDEN_SIZE = 30  # from the keyword-KEPT pool
RECALL_SIZE = 10  # from the keyword-REJECTED pool (filter recall)
