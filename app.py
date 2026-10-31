"""SIP Discovery Engine: Streamlit app. Reads data/processed/ only; never scrapes.

    streamlit run app.py

The one live LLM call is "Ask the corpus" (Groq, key from st.secrets or .env).
"""
import json
import os

import altair as alt
import pandas as pd
import streamlit as st

import config as C
import pipeline

REPO = "https://github.com/aryansinghdev01/sip-discovery-engine"
LOG = f"{REPO}/blob/build/evidence_log.md"
DIVERGENCE_URL = f"{LOG}#known-divergence-from-primary-research-why-sips-stop"
ASK_MODEL = "openai/gpt-oss-20b"

CATEGORY_LABELS = {
    "mandate_payment_failure": "Mandate / payment failure",
    "affordability_cashflow": "Affordability / cash flow",
    "expectation_returns_mismatch": "Returns below expectation",
    "no_answer_available": "No answer available",
    "app_mechanics": "App mechanics",
    "fees_trust": "Fees / trust",
}
SOURCE_LABELS = {"play": "Google Play", "appstore": "App Store", "youtube": "YouTube",
                 "tradingqna": "TradingQ&A"}
STAGE_LABELS = {"raw": "Raw (scraped)", "keyword_kept": "Kept by keyword filter",
                "sampled": "Random sample sent to LLM", "llm_kept": "Kept by LLM filter",
                "final_records": "Final structured records"}

# Reference data-viz palette, slots 1-4 in fixed order (validated light + dark).
SERIES = {"light": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"],
          "dark": ["#3987e5", "#d95926", "#199e70", "#c98500"]}
WHISKER = "#8a8985"
SURFACE = {"light": "#ffffff", "dark": "#0e1117"}  # Streamlit backgrounds; 2px gaps between stacked fills

st.set_page_config(page_title="SIP Discovery Engine", page_icon="📉", layout="wide")


# --- Data -------------------------------------------------------------------------
@st.cache_data
def load():
    p = C.PROCESSED_DIR
    records = json.loads((p / "records.json").read_text())
    funnel = json.loads((p / "funnel.json").read_text())
    validation = json.loads((p / "validation.json").read_text()) if (p / "validation.json").exists() else {}
    progress = json.loads((p / "corpus_progress.json").read_text()) if (p / "corpus_progress.json").exists() else {}
    return records, funnel, validation, progress


records, funnel, validation, progress = load()
final = [r for r in pipeline.final_records(records) if not r.get("is_staff")]
cats = pipeline.category_table(final)
theme = "dark" if getattr(getattr(st.context, "theme", None), "type", None) == "dark" else "light"


def pct(x, d=1):
    return f"{x * 100:.{d}f}%"


# --- Header -----------------------------------------------------------------------
st.title("SIP Discovery Engine")
st.markdown(
    "Where does SIP continuation break down for first-time mutual fund investors? "
    "Structured evidence from public feedback (Google Play, App Store, YouTube, TradingQ&A), "
    "every record tied to a verbatim quote."
)
b1, b2, _ = st.columns([2, 1, 3])
b1.link_button("📄 Evidence log: sources, validation, limitations", LOG, type="primary", width="stretch")
b2.link_button("Code on GitHub", REPO, width="stretch")
if progress and progress.get("final_records", 0) < progress.get("target", 0) and \
        progress.get("processed", 0) < C.CORPUS_MAX:
    st.warning(f"Interim data: the corpus run is still in progress "
               f"({progress['processed']} of {C.CORPUS_MAX} sampled items processed).")
st.caption(
    f"**{len(final)} final records** from a seeded random sample of the keyword-filtered pool. "
    "Shares describe Indian SIP investors who post publicly. They are **not** comparisons between apps "
    "(the apps' review samples span very different periods). Staff and moderator posts are excluded from "
    f"all counts. [Evidence log]({LOG})"
)

# --- Hero: category distribution ------------------------------------------------------
st.header("Where SIP continuation breaks down")
cat_df = pd.DataFrame([
    {"category": CATEGORY_LABELS[c], "key": c, "records": v["n"], "share": v["pct"], "moe": v["moe"],
     "lo": max(v["pct"] - v["moe"], 0.0), "hi": min(v["pct"] + v["moe"], 1.0),
     "label": f"{pct(v['pct'])} ±{v['moe'] * 100:.1f}",
     "range": f"{pct(max(v['pct'] - v['moe'], 0))} to {pct(min(v['pct'] + v['moe'], 1))}"}
    for c, v in cats.items()
]).sort_values("share", ascending=False)

base = alt.Chart(cat_df).encode(
    y=alt.Y("category:N", sort=list(cat_df["category"]), title=None,
            axis=alt.Axis(labelLimit=240, ticks=False, domain=False, labelPadding=8)))
tooltip = [alt.Tooltip("category:N", title="Category"), alt.Tooltip("records:Q", title="Records"),
           alt.Tooltip("share:Q", title="Share", format=".1%"),
           alt.Tooltip("range:N", title="95% interval")]
bars = base.mark_bar(color=SERIES[theme][0], cornerRadiusEnd=4, height=20).encode(
    x=alt.X("share:Q", title="Share of final records (95% margin of error shown)",
            scale=alt.Scale(domain=[0, min(cat_df["hi"].max() * 1.25, 1)]),
            axis=alt.Axis(format="%", gridOpacity=0.25, domain=False, tickCount=5)),
    tooltip=tooltip)
whiskers = base.mark_rule(color=WHISKER, strokeWidth=2).encode(x="lo:Q", x2="hi:Q", tooltip=tooltip)
labels = base.mark_text(align="left", dx=8, fontSize=13).encode(x="hi:Q", text="label:N")
st.altair_chart((bars + whiskers + labels).properties(height=46 * len(cat_df)).configure_view(stroke=None),
                width="stretch")

aff = cats["affordability_cashflow"]
st.info(
    f"**The corpus and primary research disagree on cause.** Here, affordability / cash flow is "
    f"**{pct(aff['pct'])}** (±{aff['moe'] * 100:.1f}) of records. In a survey of 21 investors, money "
    f"reasons were behind **5 of 6** stopped SIPs. Public review channels capture app failures, not private "
    f"financial circumstances, so read these shares as *what goes wrong in the product and payment chain*, "
    f"not as the full set of reasons people stop. [Why this happens →]({DIVERGENCE_URL})",
    icon="⚠️")
with st.expander("Table view"):
    st.dataframe(cat_df[["category", "records", "share", "moe"]].rename(
        columns={"category": "Category", "records": "Records", "share": "Share", "moe": "± margin (95%)"}),
        hide_index=True, width="stretch",
        column_config={"Share": st.column_config.NumberColumn(format="percent"),
                       "± margin (95%)": st.column_config.NumberColumn(format="percent")})

# --- Funnel ------------------------------------------------------------------------
st.header("Funnel and source composition")
st.caption("Investor items only (staff excluded). Any source above "
           f"{C.CONCENTRATION_ALERT:.0%} of a stage would be flagged.")
stages = [s for s in STAGE_LABELS if s in funnel]
rows = []
for s in stages:
    f = funnel[s]
    row = {"Stage": STAGE_LABELS[s], "Total": f["investor_total"]}
    for src, lab in SOURCE_LABELS.items():
        v = f["by_source"][src]
        row[lab] = f"{v['n']:,} ({pct(v['pct'])})"
    row["Staff excluded"] = f["staff_excluded"]
    rows.append(row)
st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

comp = pd.DataFrame([{"stage": STAGE_LABELS[s], "source": SOURCE_LABELS[src], "order": k,
                      "share": funnel[s]["by_source"][src]["pct"], "n": funnel[s]["by_source"][src]["n"]}
                     for s in stages for k, src in enumerate(SOURCE_LABELS)])
st.altair_chart(alt.Chart(comp).mark_bar(height=18, stroke=SURFACE[theme], strokeWidth=2).encode(
    y=alt.Y("stage:N", sort=[STAGE_LABELS[s] for s in stages], title=None,
            axis=alt.Axis(labelLimit=240, ticks=False, domain=False)),
    x=alt.X("share:Q", stack="normalize", title="Source share of stage",
            axis=alt.Axis(format="%", gridOpacity=0.25, domain=False)),
    color=alt.Color("source:N", sort=list(SOURCE_LABELS.values()),
                    scale=alt.Scale(domain=list(SOURCE_LABELS.values()), range=SERIES[theme]),
                    legend=alt.Legend(title=None, orient="top")),
    order="order:Q",
    tooltip=[alt.Tooltip("stage:N", title="Stage"), alt.Tooltip("source:N", title="Source"),
             alt.Tooltip("n:Q", title="Items", format=","), alt.Tooltip("share:Q", title="Share", format=".1%")],
).properties(height=40 * len(stages)).configure_view(stroke=None), width="stretch")

# --- Cross-tabs ----------------------------------------------------------------------
st.header("Cross-tabs")
fdf = pd.DataFrame(final)
fdf["Category"] = fdf["primary_category"].map(CATEGORY_LABELS)
tab1, tab2 = st.tabs(["Category × lifecycle stage", "Category × stoppage type"])
for tab, col, order in [(tab1, "lifecycle_stage", C.LIFECYCLE_STAGES),
                        (tab2, "stoppage_type", C.STOPPAGE_TYPES)]:
    with tab:
        ct = pd.crosstab(fdf["Category"], fdf[col]).reindex(columns=[o for o in order if o in fdf[col].values])
        ct = ct.reindex([CATEGORY_LABELS[c] for c in cat_df["key"]]).fillna(0).astype(int)
        ct["Total"] = ct.sum(axis=1)
        st.dataframe(ct, width="stretch")
        st.caption("Counts of final records. Small cells are not reliable on their own.")

# --- Records explorer ------------------------------------------------------------------
st.header("Records")
c1, c2, c3, c4 = st.columns(4)
f_cat = c1.multiselect("Category", list(CATEGORY_LABELS.values()))
f_src = c2.multiselect("Source", list(SOURCE_LABELS.values()))
f_stage = c3.multiselect("Lifecycle stage", C.LIFECYCLE_STAGES)
f_text = c4.text_input("Search quotes")
view = fdf.assign(Source=fdf["source"].map(SOURCE_LABELS))
if f_cat:
    view = view[view["Category"].isin(f_cat)]
if f_src:
    view = view[view["Source"].isin(f_src)]
if f_stage:
    view = view[view["lifecycle_stage"].isin(f_stage)]
if f_text:
    view = view[view["evidence_quote"].str.contains(f_text, case=False, na=False)]
st.caption(f"{len(view)} of {len(fdf)} records. Quote check: ✓ exact or whitespace-only match, "
           "✗ not found verbatim in the source (flagged, kept visible).")
st.dataframe(
    view.assign(**{"Quote check": view["quote_verified"].map({True: "✓", False: "✗"})})[
        ["Category", "evidence_quote", "Source", "lifecycle_stage", "stoppage_type",
         "went_outside_app", "Quote check", "url"]],
    hide_index=True, width="stretch",
    column_config={"evidence_quote": st.column_config.TextColumn("Evidence quote", width="large"),
                   "lifecycle_stage": "Stage", "stoppage_type": "Stoppage",
                   "went_outside_app": "Went outside app",
                   "url": st.column_config.LinkColumn("Source link", display_text="open")})


# --- Ask the corpus ------------------------------------------------------------------
@st.cache_resource
def _index():
    from sklearn.feature_extraction.text import TfidfVectorizer
    docs = [f"{r['primary_category']} {r['lifecycle_stage']} {r['evidence_quote']} {r['raw_text'][:1500]}"
            for r in final]
    vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words="english")
    return vec, vec.fit_transform(docs)


def retrieve(question, k=12):
    from sklearn.metrics.pairwise import linear_kernel
    vec, m = _index()
    sims = linear_kernel(vec.transform([question]), m).ravel()
    top = sims.argsort()[::-1][:k]
    return [final[i] for i in top if sims[i] > 0.02]


def _groq_key():
    try:
        return st.secrets["GROQ_API_KEY"]
    except Exception:
        from dotenv import load_dotenv
        load_dotenv(C.ROOT / ".env")
        return os.getenv("GROQ_API_KEY")


ASK_SYSTEM = """You answer questions about a corpus of structured records drawn from public feedback by Indian SIP investors.
Use ONLY the aggregate table and the records given below. Do not use outside knowledge, and do not guess.
Cite every claim with record ids in square brackets, e.g. [play:abc]. Use the aggregate table for any share or count.
If the records and table do not answer the question, reply exactly: "The corpus doesn't answer this." and then, in one sentence, say what the records do cover that is closest.
Keep answers under 150 words. Remind the reader that shares come from a sample and describe people who post publicly, when you give a share."""


@st.cache_data(show_spinner=False)
def ask(question):
    hits = retrieve(question)
    if not hits:
        return "The corpus doesn't answer this. No record matches the question's terms.", []
    agg = {CATEGORY_LABELS[c]: {"records": v["n"], "share": round(v["pct"], 3), "moe": round(v["moe"], 3)}
           for c, v in cats.items()}
    ctx = "\n\n".join(
        f"[{r['id']}] source={r['source']} category={r['primary_category']} stage={r['lifecycle_stage']} "
        f"stoppage={r['stoppage_type']} outside_app={r['went_outside_app']}\nquote: {r['evidence_quote']}"
        for r in hits)
    from groq import Groq
    resp = Groq(api_key=_groq_key()).chat.completions.create(
        model=ASK_MODEL, temperature=0, reasoning_effort="low", include_reasoning=False,
        max_completion_tokens=1500,
        messages=[{"role": "system", "content": ASK_SYSTEM},
                  {"role": "user", "content": f"Aggregate table ({len(final)} records): {json.dumps(agg)}\n\n"
                                              f"Records:\n{ctx}\n\nQuestion: {question}"}])
    return resp.choices[0].message.content, hits


st.header("Ask the corpus")
st.caption("Answers come only from the structured records above, with record ids cited. "
           "If the records don't cover the question, it says so.")
q = st.text_input("Question", placeholder="e.g. What do people try when a SIP instalment fails?",
                  max_chars=300)
if q:
    if not _groq_key():
        st.error("No GROQ_API_KEY configured, so the question can't be answered.")
    else:
        try:
            with st.spinner("Searching the records…"):
                answer, hits = ask(q)
            st.markdown(answer)
            if hits:
                with st.expander(f"The {len(hits)} records the answer was allowed to use"):
                    for r in hits:
                        st.markdown(f"- **[{r['id']}]** {CATEGORY_LABELS.get(r['primary_category'])}: "
                                    f"“{r['evidence_quote']}” ([source]({r['url']}))")
        except Exception as e:
            st.error(f"The question couldn't be answered right now ({type(e).__name__}). "
                     "The free API tier may be rate-limited; try again in a minute.")

# --- Validation ----------------------------------------------------------------------
st.header("Validation")
v1 = validation.get("golden_30", {}).get("is_sip_related", {})
v2 = validation.get("retest_20", {}).get("is_sip_related", {})
leak = validation.get("filter_leak", {})
m1, m2, m3, m4 = st.columns(4)
if v1:
    m1.metric("Blind agreement, prompt v1", pct(v1["rate"]), help=f"{v1['agree']}/{v1['n']} golden items, "
              "is_sip_related. Labels authored before the model ran.")
if v2:
    m2.metric("Agreement after prompt revision", pct(v2["rate"]),
              help=f"{v2['agree']}/{v2['n']} retest items, is_sip_related, prompt v2.")
if leak:
    m3.metric("Keyword-filter leak (upper bound)", f"≤ {pct(leak['upper_bound_95'])}",
              help=f"{leak['relevant']} relevant of {leak['n']} rejected items. One-sided 95% bound on the share "
                   "of rejected items that were relevant; not a recall figure.")
qp = sum(r["quote_verified"] for r in final) / len(final) if final else 0
m4.metric("Evidence quotes verified verbatim", pct(qp), help="Exact or whitespace-only match against the source text.")

cat1 = validation.get("golden_30", {}).get("primary_category", {})
cat2 = validation.get("retest_20", {}).get("primary_category", {})
if cat1 or cat2:
    st.caption(" · ".join(x for x in [
        f"Category agreement, prompt v1: {pct(cat1['rate'])} ({cat1['agree']}/{cat1['n']})" if cat1 else "",
        f"after revision: {pct(cat2['rate'])} ({cat2['agree']}/{cat2['n']})" if cat2 else ""] if x)
        + ". Computed over items both human and model marked SIP-related.")

fill = {f: sum(r.get(f) not in (None, "unknown") for r in final) for f in
        ["start_motivation", "checking_behaviour", "influenced_by", "money_source",
         "segment_age_stated", "segment_income_stated"]}
st.markdown("**Fill rate of optional fields** (segment fields are filled only when explicitly stated "
            "and backed by the evidence quote; under ~15% is a documented limitation, not a result)")
st.dataframe(pd.DataFrame([{"Field": f, "Filled": n, "Fill rate": n / len(final) if final else 0}
                           for f, n in fill.items()]),
             hide_index=True, width="stretch",
             column_config={"Fill rate": st.column_config.NumberColumn(format="percent")})
st.caption(f"Full method, every disagreement and all corrections: [evidence log]({LOG}).")
