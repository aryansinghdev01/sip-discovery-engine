"""Hand-label sets, sampled with a fixed seed and stratified by source.

    python golden.py export   # blank golden_30 + recall_10 (never overwrites)
    python golden.py extra    # blank recall_20_extra (rejected pool, minus recall_10)
    python golden.py run      # model on the labelled items, blind (frozen prompts only)
    python golden.py score    # model vs human agreement report

golden_30.csv        30 items from the keyword-KEPT pool: tests the LLM's judgement
recall_10.csv        10 items from the keyword-REJECTED pool: tests what the filter drops
recall_20_extra.csv  20 more rejected items, so 30 in total bound the leak rate

Staff/moderator posts are excluded from all of them: the labels are about
investor voice. Files must be labelled before the model is run on them.
"""
import csv
import json
import sys
from collections import Counter

import config as C
import pipeline

GOLDEN_CSV = C.PROCESSED_DIR / "golden_30.csv"
RECALL_CSV = C.PROCESSED_DIR / "recall_10.csv"
RECALL_EXTRA_CSV = C.PROCESSED_DIR / "recall_20_extra.csv"
RETEST_CSV = C.PROCESSED_DIR / "blind_retest_20.csv"
MODEL_CSV = C.PROCESSED_DIR / "golden_model.csv"
REPORT = C.PROCESSED_DIR / "validation.json"
OPTIONAL_FIELDS = ["start_motivation", "checking_behaviour", "influenced_by", "money_source",
                   "segment_age_stated", "segment_income_stated"]


def _pools():
    kept, rejected = pipeline.split_by_keywords(pipeline.load_items())
    return ([i for i in kept if not i["is_staff"]], [i for i in rejected if not i["is_staff"]])


def _write(path, items, label_cols):
    if path.exists():
        sys.exit(f"{path.name} exists (it may hold labels); refusing to overwrite.")
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "source", "url", "raw_text", *label_cols, "notes"])
        for i in items:
            w.writerow([i["id"], i["source"], i["url"], i["raw_text"], *[""] * len(label_cols), ""])
    print(path.name, {s: sum(i["source"] == s for i in items) for s in pipeline.SOURCES})


def _read(path):
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def export():
    kept, rejected = _pools()
    _write(GOLDEN_CSV, pipeline.stratified_sample(kept, C.GOLDEN_SIZE, C.SEED),
           ["is_sip_related", "primary_category"])
    _write(RECALL_CSV, pipeline.stratified_sample(rejected, C.RECALL_SIZE, C.SEED), ["is_sip_related"])


def extra():
    """20 more rejected-pool items, same seed and stratification, none from recall_10."""
    _, rejected = _pools()
    taken = {r["id"] for r in _read(RECALL_CSV)}
    pool = [i for i in rejected if i["id"] not in taken]
    _write(RECALL_EXTRA_CSV, pipeline.stratified_sample(pool, 20, C.SEED), ["is_sip_related"])


def retest():
    """20 fresh kept-pool items for the blind post-revision score: seed 44, stratified,
    excluding every labelled item and the 40 dev items the prompt was tuned on."""
    kept, _ = _pools()
    exclude = pipeline.labelled_ids() | {i["id"] for i in pipeline.dev_sample()}
    pool = [i for i in kept if i["id"] not in exclude]
    _write(RETEST_CSV, pipeline.stratified_sample(pool, 20, C.SEED + 2),
           ["is_sip_related", "primary_category"])


def run():
    """Model labels for golden_30 + recall_10, using the frozen prompts. Reads only
    the id column of the label files."""
    pipeline.require_frozen()
    ids = [r["id"] for p in (GOLDEN_CSV, RECALL_CSV) for r in _read(p)]
    by_id = {i["id"]: i for i in pipeline.load_items()}
    records = pipeline.run_items([by_id[i] for i in ids])
    missing = [i for i in ids if i not in records]
    if missing:
        sys.exit(f"no model result yet for {len(missing)} items (rate limit?); rerun to resume")
    cols = ["id", "stage", "is_sip_related", "primary_category", "secondary_categories",
            "lifecycle_stage", "stoppage_type", "went_outside_app", "confidence", "quote_match",
            "evidence_quote", "filter_reason", "flags", *OPTIONAL_FIELDS]
    with MODEL_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for i in ids:
            r = records[i]
            w.writerow({**r, "secondary_categories": ";".join(r.get("secondary_categories", [])),
                        "flags": ";".join(r["flags"])})
    (C.PROCESSED_DIR / "golden_model_records.json").write_text(
        json.dumps([records[i] for i in ids], ensure_ascii=False, indent=1))
    print(f"model labels written for {len(ids)} items; tokens: {dict(pipeline.TOKENS)}")


# --- Scoring ------------------------------------------------------------------------
def _yes(v):
    v = (v or "").strip().lower()
    return True if v in ("yes", "y", "true", "1") else False if v in ("no", "n", "false", "0") else None


def _upper_bound_zero(n, alpha=0.05):
    """One-sided 95% upper bound on a rate when 0 of n are positive (exact binomial)."""
    return 1 - alpha ** (1 / n)


def _upper_bound(k, n, alpha=0.05):
    """One-sided exact (Clopper-Pearson) upper bound for k of n, by bisection."""
    from math import comb
    if k == n:
        return 1.0
    lo, hi = k / n, 1.0
    for _ in range(60):
        p = (lo + hi) / 2
        cdf = sum(comb(n, j) * p ** j * (1 - p) ** (n - j) for j in range(k + 1))
        lo, hi = (p, hi) if cdf > alpha else (lo, p)
    return hi


def score():
    model = {r["id"]: r for r in json.loads((C.PROCESSED_DIR / "golden_model_records.json").read_text())}
    report = {}

    for name, path in [("golden_30", GOLDEN_CSV), ("recall_10", RECALL_CSV)]:
        rows, dis, agree, n = _read(path), [], 0, 0
        for h in rows:
            hy, m = _yes(h["is_sip_related"]), model[h["id"]]
            if hy is None:
                dis.append({"id": h["id"], "problem": f"unreadable human label {h['is_sip_related']!r}"})
                continue
            n += 1
            if hy == m["is_sip_related"]:
                agree += 1
            else:
                dis.append({"id": h["id"], "source": h["source"], "human": hy, "model": m["is_sip_related"],
                            "model_category": m["primary_category"], "model_stage": m["stage"],
                            "filter_reason": m.get("filter_reason"), "human_note": h.get("notes", ""),
                            "text": pipeline._norm(h["raw_text"])[:200]})
        report[name] = {"is_sip_related": {"agree": agree, "n": n, "rate": agree / n if n else None,
                                           "disagreements": dis}}

    # Category agreement on golden_30 items both sides marked SIP-related.
    rows = _read(GOLDEN_CSV)
    both = [h for h in rows if _yes(h["is_sip_related"]) and model[h["id"]]["is_sip_related"]]
    cat_dis = [{"id": h["id"], "source": h["source"], "human": h["primary_category"].strip(),
                "model": model[h["id"]]["primary_category"],
                "model_secondary": model[h["id"]].get("secondary_categories"),
                "model_confidence": model[h["id"]].get("confidence"),
                "human_note": h.get("notes", ""), "text": pipeline._norm(h["raw_text"])[:200]}
               for h in both if h["primary_category"].strip() != model[h["id"]]["primary_category"]]
    human_bad = sorted({h["primary_category"].strip() for h in rows
                        if h["primary_category"].strip() and h["primary_category"].strip() not in C.CATEGORIES})
    report["golden_30"]["primary_category"] = {
        "agree": len(both) - len(cat_dis), "n": len(both),
        "rate": (len(both) - len(cat_dis)) / len(both) if both else None,
        "disagreements": cat_dis, "human_labels_outside_taxonomy": human_bad}

    # Keyword-filter leak: human-relevant items in the rejected pool.
    rec = _read(RECALL_CSV) + (_read(RECALL_EXTRA_CSV) if RECALL_EXTRA_CSV.exists() else [])
    labelled = [r for r in rec if _yes(r["is_sip_related"]) is not None]
    k = sum(_yes(r["is_sip_related"]) for r in labelled)
    report["filter_leak"] = {"relevant": k, "n": len(labelled),
                             "upper_bound_95": _upper_bound(k, len(labelled)) if labelled else None}

    # Model-output checks over every extracted labelled item.
    ext = [m for m in model.values() if m["stage"] == "extracted"]
    report["quotes"] = dict(Counter(m["quote_match"] for m in ext))
    report["invalid_categories"] = sum(any(f.startswith("invalid_category") for f in m["flags"]) for m in ext)
    report["other_flags"] = dict(Counter(f.split(":")[0] for m in ext for f in m["flags"]))
    rel = [m for m in ext if m["is_sip_related"]]
    report["fill_rates"] = {"n": len(rel), **{
        f: sum(m.get(f) not in (None, "unknown") for m in rel) for f in OPTIONAL_FIELDS}}
    report["human_notes"] = {r["id"]: r["notes"] for r in _read(GOLDEN_CSV) + _read(RECALL_CSV)
                             if r.get("notes", "").strip()}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1))
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    {"export": export, "extra": extra, "retest": retest, "run": run, "score": score}[
        sys.argv[1] if len(sys.argv) > 1 else "export"]()
