"""Funnel: raw -> keyword filter -> LLM filter -> structured records.

Every stage reports source composition (counts and %) and flags any source
above CONCENTRATION_ALERT of the investor (non-staff) pool.

    python pipeline.py keywords   # stage 1, deterministic, no network
    python pipeline.py limits     # print Groq rate limits for both models
    python pipeline.py dev        # tune prompts on a dev sample (no labelled items)
    python pipeline.py freeze     # freeze prompts before any labelled item is run
    python pipeline.py corpus     # stages 2-3 on a random sample (frozen prompts only)
"""
import csv
import hashlib
import json
import math
import random
import re
import sys
import time
from collections import Counter

import config as C
import scrape

FUNNEL = C.PROCESSED_DIR / "funnel.json"
RECORDS = C.PROCESSED_DIR / "records.json"
SOURCES = ["play", "appstore", "youtube", "tradingqna"]

KEYWORD_RE = re.compile(
    r"(?<!\w)(?:"
    + "|".join(map(re.escape, sorted(C.SEED_KEYWORDS + C.ADDED_KEYWORDS, key=len, reverse=True)))
    + r")(?!\w)",
    re.I,
)


def load_items():
    """Raw items with is_staff set on every source (only TradingQ&A has staff).
    Items with no text are dropped: TradingQ&A posts that were only a quote."""
    items = [{**i, "is_staff": bool(i.get("is_staff"))} for i in scrape.load_raw()]
    kept = [i for i in items if i["raw_text"].strip()]
    if len(kept) < len(items):
        print(f"  dropped {len(items) - len(kept)} items with no text")
    return kept


def keyword_matches(text):
    return sorted({m.group(0).lower() for m in KEYWORD_RE.finditer(text)})


def stratified_sample(pool, n, seed):
    """n items spread evenly across sources; the remainder goes to the largest pools."""
    by_source = {s: sorted((i for i in pool if i["source"] == s), key=lambda i: i["id"])
                 for s in SOURCES}
    order = sorted(by_source, key=lambda s: -len(by_source[s]))
    quota = {s: n // len(order) + (k < n % len(order)) for k, s in enumerate(order)}
    rng = random.Random(seed)
    picked = []
    for s in SOURCES:  # fixed order keeps the RNG sequence reproducible
        picked += rng.sample(by_source[s], quota[s])
    return picked


# --- Composition ----------------------------------------------------------------
def composition(items):
    investor = [i for i in items if not i["is_staff"]]
    c, n = Counter(i["source"] for i in investor), len(investor)
    return {"total": len(items), "staff_excluded": len(items) - n, "investor_total": n,
            "by_source": {s: {"n": c[s], "pct": round(c[s] / n, 4) if n else 0} for s in SOURCES}}


def record_stage(stage, items, quiet=False):
    """Save this stage's composition to funnel.json, print it, flag concentration."""
    funnel = json.loads(FUNNEL.read_text()) if FUNNEL.exists() else {}
    funnel[stage] = comp = composition(items)
    C.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    FUNNEL.write_text(json.dumps(funnel, indent=1))
    if quiet:
        return comp

    print(f"\n[{stage}] {comp['total']} items, {comp['staff_excluded']} staff excluded "
          f"-> {comp['investor_total']} investor items")
    for s, v in comp["by_source"].items():
        flag = "  <-- OVER CONCENTRATION LIMIT" if v["pct"] > C.CONCENTRATION_ALERT else ""
        print(f"  {s:12} {v['n']:6d}  {v['pct']:6.1%}{flag}")
    over = [s for s, v in comp["by_source"].items() if v["pct"] > C.CONCENTRATION_ALERT]
    if over:
        print(f"  !! {over} above {C.CONCENTRATION_ALERT:.0%} of the investor pool: stop and review")
    return comp


# --- Stage 1: keyword filter ------------------------------------------------------
def split_by_keywords(items):
    """(kept, rejected): deterministic, no network."""
    kept, rejected = [], []
    for i in items:
        m = keyword_matches(i["raw_text"])
        (kept if m else rejected).append({**i, "keywords": m})
    return kept, rejected


def run_keywords():
    items = load_items()
    record_stage("raw", items)
    kept, rejected = split_by_keywords(items)
    (C.PROCESSED_DIR / "keyword_kept.json").write_text(
        json.dumps(kept, ensure_ascii=False, indent=1))
    record_stage("keyword_kept", kept)
    return kept, rejected


# --- Prompts ----------------------------------------------------------------------
FILTER_SYSTEM = """You screen public posts for a study of how Indian investors start, continue, pause and stop SIPs (Systematic Investment Plans in mutual funds).

For each item, decide keep = true or false.

keep = true only when the text describes the writer's own SIP experience, problem or decision, or comments directly on continuing or stopping SIPs. This includes:
- trouble starting a SIP: a mandate, e-mandate or payment that would not set up, a SIP that would not create or execute
- SIP instalments, mandates, e-NACH, autopay, UPI payments, debits, failed or missed instalments, units not allotted
- the returns of a SIP they hold, compared with what they expected
- changing a SIP they hold (amount, date, step-up, top-up), pausing, stopping, cancelling or redeeming one
- confusion or unanswered questions about a SIP they hold
- deciding whether to continue, or commentary about whether people should continue their SIPs

keep = false for:
- pre-start items where no SIP is held and no problem is described: beginner questions about what a SIP is or how to start one, statements of intent or enthusiasm about starting, asking which SIP or fund to choose
- fund or scheme recommendations and comparisons
- portfolio display features or bugs (holdings, NAV display, XIRR display, sync, tracking) that do not involve a SIP
- general app bugs, login, KYC, UI or support complaints that do not involve a SIP
- stock, F&O or intraday trading, IPOs, US stocks, gold, FDs, loans or insurance
- tax questions not about continuing or stopping a SIP
- company or support-team auto-replies, greetings, praise, thanks, jokes, spam, or text too vague to tell
A passing mention of the word "SIP" is not enough; the text must say something about a SIP itself.

The "context" line is the video or forum topic the item appeared under; use it to understand short replies.
Return only JSON: {"results": [{"id": "<id>", "keep": true or false, "reason": "<max 12 words>"}]} with exactly one entry per item, using the ids given."""

EXTRACT_SYSTEM = """You extract structured evidence from one public post about SIPs (Systematic Investment Plans in Indian mutual funds). Do not summarise. Every judgement must rest on words in the text.

Return only a JSON object with exactly these keys:

is_sip_related: true only if the text describes the writer's own SIP experience, problem or decision, or comments directly on continuing or stopping SIPs. false for pre-start items where no SIP is held and no problem is described (beginner questions, intent or enthusiasm about starting, asking which fund to choose), for portfolio display features or bugs that do not involve a SIP, for tax questions not about continuing a SIP, and for company auto-replies.

primary_category: exactly one of
- mandate_payment_failure: instalment bounced, insufficient balance, e-NACH/autopay/UPI mandate broke, debited but no units allotted
- affordability_cashflow: money needed elsewhere, income dropped, stopped or reduced for financial reasons
- expectation_returns_mismatch: returns disappointing against what they expected, "too slow", "FD is better", confused that value < amount invested
- no_answer_available: confused, couldn't find out whether something was normal, no guidance
- app_mechanics: can't pause/cancel/modify, can't find something, broken flow
- fees_trust: charges, hidden fees, distrust of the platform
- not_relevant: not about a SIP experience (use this if and only if is_sip_related is false)
Label by cause, not symptom. When the text says why a SIP went wrong, choose the category of that cause: if an app fault, platform rule or platform behaviour is what stopped or distorted the payment, the category follows that cause (app_mechanics or fees_trust), not mandate_payment_failure. Use mandate_payment_failure when the failure lies in the payment or mandate itself (bounce, insufficient balance, mandate rejected, expired or not registered) and no other cause is given. An e-mandate is the SIP mandate. A request for a missing SIP feature is app_mechanics.
Never invent a category. If none of the first six fits a SIP-related post exactly, choose the closest one and lower confidence.

secondary_categories: other categories from the same list that also clearly apply; may be empty; never includes primary_category or not_relevant.

lifecycle_stage: starting (considering or just started), first_months (roughly the first year), ongoing (established SIP, continuing), stopping (considering or in the middle of pausing / stopping / reducing), stopped (already paused, stopped, cancelled or redeemed), or unclear.

stoppage_type: involuntary (the SIP stopped or missed an instalment without their choice: failed debit, broken mandate, platform or bank issue), voluntary (they chose to pause / stop / reduce), passive (it lapsed through inaction: forgot, didn't renew, didn't notice), not_applicable (no pause, stop or miss discussed), or unclear.

went_outside_app: yes if the text says they looked for information or help somewhere other than the investing app (YouTube, Google, friends or family, an advisor, a forum, the AMC or registrar, their bank, a regulator complaint). Writing this post does not count by itself. no if they say they only used the app. Otherwise unclear.

what_they_tried: a short phrase (max 12 words) for what they did about it, e.g. "raised support ticket", "re-registered the mandate", "switched to another app"; null if nothing is said.

evidence_quote: a span copied character-for-character from the post text: no edits, no ellipses, no translation, no added punctuation, no words dropped or added. Never quote the context line, and never include the <<< or >>> markers (they only show where the text starts and ends). Choose the shortest span (max about 300 characters) that supports primary_category, extended to include the signal words of any segment field you fill. For not_relevant items, quote the span that shows what the text is about.

confidence: 0.0 to 1.0, your confidence in primary_category.

start_motivation: why they started or want to start a SIP, if stated: wealth_building, specific_goal, tax_saving, beat_fd_or_inflation, someone_recommended, habit_or_discipline, other, or unknown.

checking_behaviour: a short phrase (max 12 words) for what they check and how often, if stated, e.g. "checks portfolio value daily"; null if not stated.

Segment fields: segment_age_stated, segment_income_stated, money_source, influenced_by.
Populate these only when the person explicitly says it in the text, never inferred from tone, vocabulary or context. “I’m a student” counts. “Sounds young” does not.
- segment_age_stated: student, under_25, 25_to_40, over_40, or unknown
- segment_income_stated: salaried, self_employed, irregular, no_income, or unknown
- money_source (where the SIP money comes from): salary, business_income, irregular_income, savings, family_or_pocket_money, other, or unknown
- influenced_by (who got them to start): family, friend, finfluencer, app_or_platform, advisor, other, or unknown
For each segment field you fill (anything other than unknown), segment_signals must give the exact words from the text that state it, and those words must be inside evidence_quote. If you cannot point at the words, the field stays unknown.

segment_signals: object mapping each filled segment field to its verbatim signal words, e.g. {"segment_age_stated": "I am a college student"}; {} if none.

The "context" line is the video or forum topic the item appeared under. Use it to understand the text, but never quote it."""


def prompt_fingerprint():
    """Hash of everything that determines model output; frozen before labelled runs."""
    spec = {"filter": [C.FILTER_MODEL, C.FILTER_EFFORT, C.FILTER_BATCH, FILTER_SYSTEM],
            "extract": [C.EXTRACT_MODEL, C.EXTRACT_EFFORT, EXTRACT_SYSTEM],
            "render": [C.LLM_MAX_CHARS, _render({"id": "x", "source": "y", "raw_text": "z"})],
            "seed": C.SEED}
    return hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()


def require_frozen():
    if not C.FREEZE_FILE.exists():
        sys.exit("Prompts are not frozen. Run `python pipeline.py freeze` first.")
    frozen = json.loads(C.FREEZE_FILE.read_text())["fingerprint"]
    if frozen != prompt_fingerprint():
        sys.exit("Prompts/models changed since the freeze; labelled results would not be blind.")


def freeze():
    from datetime import datetime, timezone
    C.FREEZE_FILE.write_text(json.dumps({
        "fingerprint": prompt_fingerprint(),
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "filter_model": C.FILTER_MODEL, "extract_model": C.EXTRACT_MODEL,
        "filter_prompt_sha": hashlib.sha256(FILTER_SYSTEM.encode()).hexdigest(),
        "extract_prompt_sha": hashlib.sha256(EXTRACT_SYSTEM.encode()).hexdigest(),
    }, indent=1))
    print("frozen:", prompt_fingerprint())


# --- Groq calls + cache -------------------------------------------------------------
TOKENS = Counter()
_client_obj = None
_cache = None


def _client():
    global _client_obj
    if _client_obj is None:
        from dotenv import load_dotenv
        from groq import Groq

        load_dotenv(C.ROOT / ".env")
        _client_obj = Groq(max_retries=2)  # longer waits (daily token cap) handled in _chat
    return _client_obj


def _render(item):
    context = item.get("topic_title") or item.get("video_title") or item.get("post_title") or ""
    return (f"id: {item['id']}\nsource: {item['source']}\ncontext (not quotable): {context}\n"
            f"text:\n<<<\n{item['raw_text'][:C.LLM_MAX_CHARS]}\n>>>")


def _key(*parts):
    return hashlib.sha256(json.dumps([*parts, C.SEED]).encode()).hexdigest()


def _cache_get(key):
    global _cache
    if _cache is None:
        _cache = {}
        if C.LLM_CACHE.exists():
            for line in C.LLM_CACHE.open(encoding="utf-8"):
                r = json.loads(line)
                _cache[r["key"]] = r["result"]
    return _cache.get(key)


def _cache_put(key, model, result):
    _cache[key] = result
    with C.LLM_CACHE.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"key": key, "model": model, "result": result}, ensure_ascii=False) + "\n")


def _chat(model, system, user, effort):
    """One JSON-mode call; returns parsed JSON or None. Rate limits (including the
    daily token cap) and transient server errors are waited out, so a multi-day
    run keeps going."""
    import groq

    while True:
        try:
            resp = _client().chat.completions.create(
                model=model, temperature=0, seed=C.SEED, reasoning_effort=effort,
                include_reasoning=False, max_completion_tokens=6000,
                response_format={"type": "json_object"},
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
            break
        except groq.RateLimitError as e:
            ra = e.response.headers.get("retry-after", "")
            wait = max(float(ra) if ra.replace(".", "", 1).isdigit() else 60.0, 10.0)
            print(f"    {model} rate-limited; waiting {wait / 60:.1f} min ({str(e)[:120]})", flush=True)
            time.sleep(wait + 2)
        except (groq.APIConnectionError, groq.InternalServerError) as e:
            print(f"    {model} {type(e).__name__}; retrying in 60s", flush=True)
            time.sleep(60)
        except groq.BadRequestError as e:  # e.g. json_validate_failed
            print(f"    bad request: {str(e)[:160]}")
            return None
    TOKENS[model] += resp.usage.total_tokens
    TOKENS[model + ":calls"] += 1
    details = getattr(resp.usage, "prompt_tokens_details", None)
    TOKENS[model + ":cached"] += getattr(details, "cached_tokens", 0) or 0  # free per Groq docs
    try:
        return json.loads(resp.choices[0].message.content)
    except (json.JSONDecodeError, TypeError):
        return None


def _filter_batch(items):
    ids = {i["id"] for i in items}
    data = _chat(C.FILTER_MODEL, FILTER_SYSTEM, "\n\n".join(map(_render, items)), C.FILTER_EFFORT)
    got = {}
    for r in (data or {}).get("results", []) if isinstance(data, dict) else []:
        if isinstance(r, dict) and r.get("id") in ids and isinstance(r.get("keep"), bool):
            got[r["id"]] = {"keep": r["keep"], "reason": str(r.get("reason", ""))}
    missing = [i for i in items if i["id"] not in got]
    if missing and len(items) > 1:  # retry stragglers one at a time
        for i in missing:
            got.update(_filter_batch([i]))
    return got


def llm_filter(items):
    """{id: {"keep", "reason"}}; cached per item, so reruns cost nothing."""
    out, todo = {}, []
    for i in items:
        k = _key(C.FILTER_MODEL, C.FILTER_EFFORT, FILTER_SYSTEM, _render(i))
        hit = _cache_get(k)
        if hit is not None:
            out[i["id"]] = hit
        else:
            todo.append((i, k))
    for b in range(0, len(todo), C.FILTER_BATCH):
        batch = todo[b:b + C.FILTER_BATCH]
        got = _filter_batch([i for i, _ in batch])
        for i, k in batch:
            if i["id"] in got:  # failures stay uncached and are retried next run
                _cache_put(k, C.FILTER_MODEL, got[i["id"]])
                out[i["id"]] = got[i["id"]]
        print(f"  filter {min(b + C.FILTER_BATCH, len(todo))}/{len(todo)} new "
              f"({len(items) - len(todo)} cached), tokens so far {TOKENS[C.FILTER_MODEL]}")
    return out


def llm_extract(items):
    """{id: raw model JSON}; cached per item. Validation happens afterwards, in
    build_record, so it can change without paying for new calls."""
    out = {}
    for n, i in enumerate(items, 1):
        k = _key(C.EXTRACT_MODEL, C.EXTRACT_EFFORT, EXTRACT_SYSTEM, _render(i))
        r = _cache_get(k)
        if r is None:
            for _ in range(2):
                r = _chat(C.EXTRACT_MODEL, EXTRACT_SYSTEM, _render(i), C.EXTRACT_EFFORT)
                if isinstance(r, dict):
                    break
            if not isinstance(r, dict):
                print(f"    extract failed for {i['id']} (not cached; retried next run)")
                continue
            _cache_put(k, C.EXTRACT_MODEL, r)
            if n % 25 == 0:
                print(f"  extract {n}/{len(items)}, tokens so far {TOKENS[C.EXTRACT_MODEL]}")
        out[i["id"]] = r
    return out


# --- Validation -------------------------------------------------------------------
ENUM_FIELDS = {
    "lifecycle_stage": (C.LIFECYCLE_STAGES, "unclear"),
    "stoppage_type": (C.STOPPAGE_TYPES, "unclear"),
    "went_outside_app": (C.YES_NO_UNCLEAR, "unclear"),
    "start_motivation": (C.START_MOTIVATIONS, "unknown"),
    "segment_age_stated": (C.AGE_STATED, "unknown"),
    "segment_income_stated": (C.INCOME_STATED, "unknown"),
    "money_source": (C.MONEY_SOURCES, "unknown"),
    "influenced_by": (C.INFLUENCED_BY, "unknown"),
}
BASE_FIELDS = ("id", "source", "url", "date", "raw_text", "is_staff", "app", "keywords")


def _norm(s):
    return " ".join(s.split())


def quote_match(quote, text):
    """exact | whitespace (matches once runs of whitespace are collapsed) | failed | missing"""
    if not quote:
        return "missing"
    if quote in text:
        return "exact"
    return "whitespace" if _norm(quote) in _norm(text) else "failed"


def build_record(item, raw):
    """Validate one extraction against the schema. Invalid values are replaced
    and listed in `flags`; nothing is silently accepted."""
    rec, flags = {k: item.get(k) for k in BASE_FIELDS}, []

    cat = raw.get("primary_category")
    if cat not in C.CATEGORIES:
        flags.append(f"invalid_category:{cat}")
        cat = None
    rec["primary_category"] = cat
    # The category is authoritative: is_sip_related follows from it.
    rec["is_sip_related"] = cat is not None and cat != "not_relevant"
    if cat is not None and raw.get("is_sip_related") is not rec["is_sip_related"]:
        flags.append("is_sip_related_mismatch")

    sec = raw.get("secondary_categories") if isinstance(raw.get("secondary_categories"), list) else []
    if any(c not in C.CATEGORIES for c in sec):
        flags.append("invalid_secondary")
    rec["secondary_categories"] = [c for c in dict.fromkeys(sec)
                                   if c in C.CATEGORIES and c not in (cat, "not_relevant")]

    for f, (allowed, default) in ENUM_FIELDS.items():
        v = raw.get(f, default)
        if v not in allowed:
            flags.append(f"invalid_{f}:{v}")
            v = default
        rec[f] = v
    for f in ("what_they_tried", "checking_behaviour"):
        v = raw.get(f)
        rec[f] = v.strip() if isinstance(v, str) and v.strip().lower() not in ("", "null", "none") else None

    quote = raw.get("evidence_quote") if isinstance(raw.get("evidence_quote"), str) else ""
    rec["evidence_quote"] = quote
    rec["quote_match"] = quote_match(quote, item["raw_text"])
    rec["quote_verified"] = rec["quote_match"] in ("exact", "whitespace")
    if not rec["quote_verified"]:
        flags.append("quote_not_verbatim")

    # Segment fields need their stated signal inside a verified evidence_quote.
    signals = raw.get("segment_signals") if isinstance(raw.get("segment_signals"), dict) else {}
    for f in C.SEGMENT_FIELDS:
        if rec[f] == "unknown":
            continue
        sig = signals.get(f)
        if not (rec["quote_verified"] and isinstance(sig, str) and sig.strip()
                and _norm(sig).lower() in _norm(quote).lower()):
            flags.append(f"segment_reset:{f}")
            rec[f] = "unknown"
    rec["segment_signals"] = {f: signals[f] for f in C.SEGMENT_FIELDS if rec[f] != "unknown"}

    try:
        rec["confidence"] = min(max(float(raw.get("confidence")), 0.0), 1.0)
    except (TypeError, ValueError):
        rec["confidence"] = None
        flags.append("invalid_confidence")
    rec["flags"] = flags
    return rec


def run_items(items):
    """Filter, then extract what passes. Every item that got a verdict gets a
    record, so filter-rejected items can be scored too."""
    verdicts = llm_filter(items)
    extractions = llm_extract([i for i in items if verdicts.get(i["id"], {}).get("keep")])
    records = {}
    for i in items:
        v = verdicts.get(i["id"])
        if v is None:
            continue
        if not v["keep"]:
            records[i["id"]] = {**{k: i.get(k) for k in BASE_FIELDS}, "stage": "llm_rejected",
                                "is_sip_related": False, "primary_category": "not_relevant",
                                "filter_reason": v["reason"], "flags": []}
        elif i["id"] in extractions:
            records[i["id"]] = {**build_record(i, extractions[i["id"]]), "stage": "extracted",
                                "filter_reason": v["reason"]}
    return records


# --- Commands -----------------------------------------------------------------------
LABEL_FILES = ["golden_30.csv", "recall_10.csv", "recall_20_extra.csv", "retest_20.csv"]


def labelled_ids(files=LABEL_FILES):
    """IDs in the hand-label files (id column only; labels are never read here)."""
    ids = set()
    for name in files:
        path = C.PROCESSED_DIR / name
        if path.exists():
            with path.open(encoding="utf-8") as f:
                ids |= {row["id"] for row in csv.DictReader(f)}
    return ids


def investor_kept():
    kept, _ = split_by_keywords(load_items())
    return [i for i in kept if not i["is_staff"]]


def dev_sample():
    """Prompt-tuning sample: fixed by its original definition (excludes the first
    40 labelled items), so adding label files later doesn't change it."""
    exclude = labelled_ids(["golden_30.csv", "recall_10.csv"])
    pool = [i for i in investor_kept() if i["id"] not in exclude]
    return stratified_sample(pool, C.DEV_SIZE, C.SEED + 1)


def limits():
    for model in (C.FILTER_MODEL, C.EXTRACT_MODEL):
        raw = _client().chat.completions.with_raw_response.create(
            model=model, max_completion_tokens=8, messages=[{"role": "user", "content": "hi"}])
        print(model, {k: v for k, v in raw.headers.items() if k.startswith("x-ratelimit")})


def dev():
    """Run the current prompts on the dev sample (no labelled item is in it)."""
    records = run_items(dev_sample())
    (C.PROCESSED_DIR / "dev_records.json").write_text(
        json.dumps(list(records.values()), ensure_ascii=False, indent=1))
    for r in records.values():
        print(f"\n{r['id']}  [{r['stage']}] {r['primary_category']}  "
              f"stage={r.get('lifecycle_stage')} stop={r.get('stoppage_type')} "
              f"outside={r.get('went_outside_app')} conf={r.get('confidence')} "
              f"quote={r.get('quote_match')} flags={r['flags']}")
        print(f"   filter: {r['filter_reason']}")
        print(f"   text:  {_norm(r['raw_text'])[:220]}")
        if r.get("evidence_quote"):
            print(f"   quote: {_norm(r['evidence_quote'])[:220]}")
    print("\ntokens:", dict(TOKENS))


SAMPLE_IDS = C.PROCESSED_DIR / "corpus_sample_ids.json"
PROGRESS = C.PROCESSED_DIR / "corpus_progress.json"


def proportional_sample(pool, n, seed):
    """n items allocated to sources in proportion to the pool (largest remainder),
    then shuffled into one seeded processing order."""
    by_source = {s: sorted((i for i in pool if i["source"] == s), key=lambda i: i["id"])
                 for s in SOURCES}
    exact = {s: n * len(v) / len(pool) for s, v in by_source.items()}
    quota = {s: int(x) for s, x in exact.items()}
    for s in sorted(exact, key=lambda s: exact[s] - quota[s], reverse=True)[:n - sum(quota.values())]:
        quota[s] += 1
    rng = random.Random(seed)
    order = [i for s in SOURCES for i in rng.sample(by_source[s], quota[s])]
    rng.shuffle(order)
    return order


def final_records(records):
    return [r for r in records if r["stage"] == "extracted" and r["is_sip_related"]]


def category_table(final):
    """Count, share and 95% margin of error (normal approximation) per category."""
    n = len(final)
    c = Counter(r["primary_category"] for r in final)
    return {cat: {"n": c[cat], "pct": c[cat] / n if n else 0,
                  "moe": 1.96 * math.sqrt((c[cat] / n) * (1 - c[cat] / n) / n) if n else 0}
            for cat in C.CATEGORIES if cat != "not_relevant"}


def run_corpus():
    """Stages 2-3 on a proportional sample of the investor kept pool, using the
    frozen prompts. Items are processed in a seeded random order until
    CORPUS_TARGET_RECORDS final records exist, so whatever has been processed
    is itself a random sample. Resumable: cached items cost nothing on rerun."""
    require_frozen()
    held_out = labelled_ids(["retest_20.csv"])  # held out for the retest
    pool = [i for i in investor_kept() if i["id"] not in held_out]
    order = proportional_sample(pool, C.CORPUS_MAX, C.SEED)
    SAMPLE_IDS.write_text(json.dumps([i["id"] for i in order]))
    print(f"sample order: {len(order)} items, {len(held_out)} retest items held out")

    records, done = {}, 0
    while done < len(order):
        chunk = order[done:done + C.CORPUS_CHUNK]
        records.update(run_items(chunk))
        done += len(chunk)
        processed = order[:done]
        by_id = {i["id"]: i for i in processed}
        final = final_records(records.values())
        RECORDS.write_text(json.dumps(list(records.values()), ensure_ascii=False, indent=1))
        record_stage("sampled", processed, quiet=True)
        record_stage("llm_kept", [by_id[r["id"]] for r in records.values()
                                  if r["stage"] == "extracted"], quiet=True)
        record_stage("final_records", [by_id[r["id"]] for r in final], quiet=True)
        PROGRESS.write_text(json.dumps({"processed": done, "final_records": len(final),
                                        "target": C.CORPUS_TARGET_RECORDS, "tokens": dict(TOKENS),
                                        "updated": time.strftime("%Y-%m-%d %H:%M")}, indent=1))
        print(f"[{time.strftime('%m-%d %H:%M')}] processed {done}/{len(order)}, "
              f"final records {len(final)}/{C.CORPUS_TARGET_RECORDS}, tokens {dict(TOKENS)}", flush=True)
        if len(final) >= C.CORPUS_TARGET_RECORDS:
            break

    for stage in ("sampled", "llm_kept", "final_records"):
        print(stage, json.loads(FUNNEL.read_text())[stage])
    for cat, v in category_table(final).items():
        print(f"  {cat:30} {v['n']:4d}  {v['pct']:6.1%}  ±{v['moe']:.1%}")


if __name__ == "__main__":
    {"keywords": run_keywords, "limits": limits, "dev": dev, "freeze": freeze,
     "corpus": run_corpus}[sys.argv[1] if len(sys.argv) > 1 else "keywords"]()
