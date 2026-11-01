# SIP Discovery Engine

**Live app:** https://sip-discovery-engine-pyp8nq3khe2u9wivvw9kmt.streamlit.app/
**Evidence log:** [evidence_log.md](evidence_log.md), covering sources, volumes, validation, every disagreement, and every correction.

A product-discovery engine for one question: **why do first-time mutual fund investors stop their SIPs?** The metric it serves is the percentage of first-time investors who still have an active SIP 12 months after starting.

The engine turns public feedback (Google Play and App Store reviews, YouTube comments, and TradingQ&A forum posts) into structured records. Each record carries a failure category, a lifecycle stage and a stoppage type, plus a **verbatim quote** that is checked programmatically against the source text. It quantifies where SIP continuation breaks down, with margins of error. It is not sentiment analysis, and it does not summarise.

## How to read the results

- Shares describe **Indian SIP investors who post publicly**. They are not comparisons between apps: each app's review sample spans a very different period.
- Public channels capture **app failures far better than private financial reasons**. In a primary survey, money reasons were behind 5 of 6 stopped SIPs, while affordability is about 2% of this corpus. See the divergence section of the evidence log.
- The LLM stages ran on a **seeded random sample** of the keyword-filtered pool (Groq free-tier limits), so every share is reported with its 95% margin of error.

## Pipeline

| Step | File | What it does |
|---|---|---|
| Scrape | `scrape.py` | Pulls Play, App Store (iTunes RSS), YouTube (yt-dlp search + comment downloader) and TradingQ&A (Discourse JSON). Each unit is cached, and requests use polite delays with backoff. Reddit was attempted and blocked; see the log. |
| Filter + extract | `pipeline.py` | Keyword pass, then an LLM relevance filter (`openai/gpt-oss-20b`), then structured extraction (`openai/gpt-oss-120b`) on Groq. Output is validated against a closed taxonomy, and every quote is checked against the source. Source composition is reported at every funnel stage. Prompts are frozen by fingerprint before any labelled item is scored. |
| Validate | `golden.py` | Seeded hand-label sets, a blind run on them, agreement scoring, and a bound on what the keyword filter discards. |
| App | `app.py` | Streamlit app that reads only `data/processed/`. Its one live LLM call is "Ask the corpus", which answers only from the records. |
| Settings | `config.py` | Sources, keywords, taxonomy, seeds, models, sample sizes. |

## Run it

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env            # add GROQ_API_KEY (free tier at console.groq.com)

python scrape.py                # cached; reruns fetch only what's missing
python pipeline.py keywords     # stage 1, deterministic
python pipeline.py freeze       # fingerprint the prompts
python pipeline.py corpus       # stages 2-3 on the seeded sample; resumable
python golden.py score          # agreement report -> data/processed/validation.json

streamlit run app.py
```

Raw scrapes and the LLM cache stay local (they are gitignored). `data/processed/` is committed so the app can run without scraping.

## Deploying

Streamlit Community Cloud, from this repo's `build` branch, with `app.py` as the main file and Python 3.13. Add `GROQ_API_KEY` under the app's **Secrets**. Never commit `.env`.
