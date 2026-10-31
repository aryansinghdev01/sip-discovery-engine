# Evidence Log: SIP Discovery Engine

**Live app:** https://sip-discovery-engine-pyp8nq3khe2u9wivvw9kmt.streamlit.app/ · **Code:** https://github.com/aryansinghdev01/sip-discovery-engine

This log records how the evidence behind the SIP discovery engine was gathered and checked: the sources and volumes, the validation against hand labels, where the model failed, and the corrections that were made. It is written for readers who were not involved in building it.

> Work in progress. The sections below are completed as each stage of the pipeline runs.

> **What this corpus can and cannot support.** It supports claims about **Indian SIP investors in general**: what goes wrong, at which stage, and in what proportions. It does **not** support claims that compare one app with another, for example "Groww has more mandate failures than Kuvera". The apps' samples cover very different periods, so a difference between apps can reflect *when* reviews were written as much as the apps themselves. See [What these volumes mean](#what-these-volumes-mean). Results in this log and in the app are pooled across apps for this reason.

## Sources and volume

The corpus comes from **four sources**: Google Play, the Apple App Store, YouTube comments and TradingQ&A. Reddit was planned as a fifth source, but Reddit blocked every request (see below).

### Raw volume (scraped 29 October 2026)

| Source | Raw items | Date range | Notes |
|---|---:|---|---|
| Google Play | 18,000 | Mar 2023 – Oct 2026 | Newest reviews: 6,000 for Groww (the focus app) and 2,000 for each peer app. Every app reached its target. |
| Apple App Store | 3,500 | May 2018 – Oct 2026 | 500 per app, the most Apple's public review feed returns. |
| YouTube comments | 7,734 | Oct 2018 – Oct 2026 | 47 videos from 13 search terms. Up to 400 comments per video, median 88. Two videos returned no comments. |
| TradingQ&A | 3,220 | Jun 2014 – Oct 2026 | 400 topics, 3,246 posts. 26 posts consisted only of a quote of another post, so they had no text of their own and were dropped. Of the remaining posts, 447 are by Zerodha staff or moderators. |
| Reddit | 0 | n/a | Blocked; see below. |
| **Total** | **32,454** | | 32,007 investor items once the 447 staff posts are set aside. |

**App store volume by app**

| App | Play reviews | Play date range | App Store reviews | App Store date range |
|---|---:|---|---:|---|
| Groww | 6,000 | 15 Sep – 28 Oct 2026 | 500 | 2 Sep – 27 Oct 2026 |
| Zerodha Kite | 2,000 | 2 Jul – 28 Oct 2026 | 500 | Jun 2025 – Oct 2026 |
| Zerodha Coin | 2,000 | Mar 2023 – Oct 2026 | 500 | Feb 2020 – Oct 2026 |
| INDmoney | 2,000 | 6 Jun – 28 Oct 2026 | 500 | Nov 2025 – Oct 2026 |
| Paytm Money | 2,000 | 5 Jun – 28 Oct 2026 | 500 | Feb 2025 – Oct 2026 |
| ET Money | 2,000 | Apr 2025 – Oct 2026 | 500 | Jan 2025 – Oct 2026 |
| Kuvera | 2,000 | Apr 2025 – Oct 2026 | 500 | May 2018 – Oct 2026 |

**What these volumes mean**

- **Groww's sample covers only about six weeks.** Groww gets so many reviews that its newest 6,000 Play reviews span only 15 September to 28 October 2026. Groww's sample is therefore a snapshot of the app as it is now; it cannot show trends. Of those 6,000 reviews, 3,882 (65%) are under 15 characters long, such as "good app" or "nice". The keyword filter removes almost all of them.
- **The apps' samples cover very different periods, so comparing apps is invalid.** Every app has the same 500-review cap on the App Store, but those 500 reviews cover 8 weeks for Groww and more than 8 years for Kuvera. Play shows the same pattern: Groww's 6,000 reviews cover six weeks, while Zerodha Coin's 2,000 go back to 2023. Busy apps fill their cap quickly and quiet apps fill it slowly. Any difference between apps mixes up two things: the apps themselves, and the period, app version and market conditions when the reviews were written. The data cannot separate them. **The consequence: this corpus is evidence about SIP investors in general, not a comparison of apps.** No finding here should be read as one app doing better or worse than another, and the analysis is never broken down by app to support such a claim. Peer apps were included to broaden the range of SIP experiences in the corpus, not to rank the apps.
- **TradingQ&A weights older material.** Its posts run from 2014 to 2026, and 2017–2018 are the busiest years. Its posts include 447 replies from Zerodha staff and moderators. These replies are answers given by the platform, not the words of investors.
- **TradingQ&A was scraped twice.** The forum rate-limited the first attempt during the topic search (HTTP 429). The scraper was changed to retry with exponential backoff, and the second run completed. The first attempt saved nothing, so the two runs did not mix.

### Reddit: attempted and blocked

Reddit was the planned fifth source: r/IndiaInvestments, r/personalfinanceindia, r/mutualfunds, r/IndianStreetBets and r/india. Three ways of collecting it were considered:

1. **Crawling the public pages.** Reddit's `robots.txt` disallows all crawling for any client that isn't specifically allowed (`User-agent: *` / `Disallow: /`).
2. **Reddit's official API, using the PRAW library.** Reddit's official Data API now requires manual approval for new apps, so access could not be set up on our own. The PRAW scraper is still in the repository, unused, in case access is granted later.
3. **Reddit's public `.json` endpoints.** This route was then tried. These endpoints are also covered by the `robots.txt` disallow rule; the project owner chose to proceed knowing that. Requests used a descriptive User-Agent (`python:sip-discovery-engine:v1.0 (academic research project)`), at least 2 seconds between requests, and exponential backoff.

**Result (29 October 2026):** every request returned **HTTP 403**, with Reddit's page "You've been blocked by network security". The search endpoint was tried on r/IndiaInvestments, r/personalfinanceindia and r/mutualfunds, and every subreddit still returned 403 after retries at 2, 4, 8 and 16 seconds. The comments endpoint returned 403 as well. This is a network-level block, so no Reddit data was collected and the corpus uses the other four sources.

**What this costs the analysis.** Reddit is where investors discuss their decisions at length, in their own words, outside any app. This makes Q6 ("what do people do *outside* the app when unsure?") harder to answer. YouTube comments and TradingQ&A, a forum run by Zerodha, are the remaining sources from outside the app stores.

### How items were selected, and why it matters

What the corpus contains depends on how each source was searched. **The choice of search terms shapes the corpus.** Searching for problems finds people with problems. Any share in the category distribution is a share of what these queries returned. It is not a share of all SIP investors.

The sources were gathered in two different ways, and each way has its own bias:

- **The app stores are a sample of the newest reviews, not a topic sample.** Google Play and App Store reviews were not searched by term at all. The scraper took the most recent reviews for each app, so this sample's bias comes from *who writes reviews* and *when*. People who write reviews are often reacting to a strong experience, and recent reviews reflect the app as it is now. The choice of search terms has no effect on this sample.
- **YouTube and TradingQ&A are topic samples.** Items were found by searching for the terms below, so this sample's bias comes from *which terms were chosen*. Reddit would also have been a topic sample. Its search terms are listed below for completeness, though no Reddit data was collected.

Neither bias is worse than the other; they are different, and the findings should be read with both in mind.

#### Search terms by source

| Source | Search terms |
|---|---|
| Reddit (planned; blocked, no data) | Search within r/IndiaInvestments, r/personalfinanceindia, r/mutualfunds, r/IndianStreetBets and r/india. Problem-framed: `SIP`, `stop SIP`, `pause SIP`, `SIP mandate`, `SIP loss`, `SIP returns`. Neutral: `first SIP`, `started SIP`, `SIP advice` |
| YouTube | Comments on the top 4 videos for each term. Original: `SIP for beginners mutual fund India`, `should I stop my SIP`, `SIP returns negative what to do`, `SIP mistakes to avoid`, `mutual fund SIP explained hindi`, `SIP band kare ya nahi`, `is SIP worth it`, `SIP vs FD`, `Groww SIP tutorial`, `step up SIP explained`. Neutral, added: `my SIP journey`, `SIP results after years`, `SIP for beginners` |
| TradingQ&A | Forum search. Original: `sip`, `stop sip`, `pause sip`, `cancel sip`, `sip mandate`, `sip failed`, `sip not deducted`, `enach`, `autopay sip`, `sip installment`, `step up sip`, `sip loss`, `sip returns`, `xirr`, `redeem sip`, `elss sip`. Neutral, added: `first sip`, `start sip`, `sip advice`, `continue sip` |

#### Why neutral terms were added

The first search lists leaned heavily toward problems. On Reddit, five of the six terms were about stopping, pausing, failed mandates or losses, and TradingQ&A was similar. Searching only for stopping would have filled the corpus with people who stopped. That would make it impossible to answer what separates people who continue from people who drop off. Neutral terms aimed at people who are starting or continuing were added to all three topic-searched sources *before* any of them were scraped.

TradingQ&A is capped at 400 topics. The cap is filled by taking topics from each term in turn (see [Methodology corrections](#methodology-corrections)).

#### Items returned per search term

These counts come from `data/processed/query_counts.json`. One item can be found by more than one term, so the shares for each source add up to more than 100%.

**YouTube** (7,734 comments, 47 videos)

| Search term | Comments | Share |
|---|---:|---:|
| mutual fund SIP explained hindi | 1,444 | 18.7% |
| SIP for beginners *(neutral, added)* | 1,282 | 16.6% |
| is SIP worth it | 1,218 | 15.7% |
| SIP for beginners mutual fund India | 824 | 10.7% |
| my SIP journey *(neutral, added)* | 814 | 10.5% |
| SIP results after years *(neutral, added)* | 803 | 10.4% |
| Groww SIP tutorial | 685 | 8.9% |
| step up SIP explained | 653 | 8.4% |
| should I stop my SIP | 433 | 5.6% |
| SIP vs FD | 413 | 5.3% |
| SIP mistakes to avoid | 205 | 2.7% |
| SIP returns negative what to do | 184 | 2.4% |
| SIP band kare ya nahi | 161 | 2.1% |

No single term dominates YouTube; the largest brings in 18.7%. The skew runs the other way from what was feared: explainer and beginner videos supply most of the comments, while the three terms about stopping or losses (`should I stop my SIP`, `SIP returns negative what to do`, `SIP band kare ya nahi`) together supply about 10%. YouTube comments therefore lean toward people who are starting or curious, not toward people who stopped.

**TradingQ&A** (3,245 posts, 400 topics)

| Search term | Posts | Share |
|---|---:|---:|
| sip returns | 833 | 25.7% |
| continue sip *(neutral, added)* | 806 | 24.8% |
| stop sip | 804 | 24.8% |
| sip mandate | 802 | 24.7% |
| first sip *(neutral, added)* | 793 | 24.4% |
| start sip *(neutral, added)* | 656 | 20.2% |
| redeem sip | 623 | 19.2% |
| sip failed | 620 | 19.1% |
| sip loss | 610 | 18.8% |
| sip not deducted | 533 | 16.4% |
| sip | 527 | 16.2% |
| sip installment | 510 | 15.7% |
| xirr | 508 | 15.7% |
| step up sip | 455 | 14.0% |
| pause sip | 435 | 13.4% |
| cancel sip | 402 | 12.4% |
| elss sip | 359 | 11.1% |
| sip advice *(neutral, added)* | 357 | 11.0% |
| autopay sip | 223 | 6.9% |
| enach | 169 | 5.2% |

No single term dominates TradingQ&A either. However, many of the shares sit close together, around 20–25%, and that is a warning sign rather than reassurance. The forum's search seems to match broadly: a search for `continue sip` returns many of the same general SIP topics as `stop sip`. So the fact that a neutral term returned many topics does **not** show that those topics are about continuing. Whether the added terms changed the *content* of this sample is checked after extraction, by looking at lifecycle stage within TradingQ&A, and not from these counts.

**Google Play and the App Store** were not searched by term, so they have no per-term counts.

## Known divergence from primary research: why SIPs stop

The corpus and the primary survey disagree sharply about **why SIPs stop**:

| Source | Money-related cause |
|---|---|
| Public-feedback corpus | `affordability_cashflow` is **1.8%** of final records (interim figure, 169 records; ±2.0 points) |
| Primary survey of 21 investors | Money reasons were behind **5 of the 6** stopped SIPs |

**The likely mechanism is the channel, not a contradiction.** Public review channels capture *app failures*: a broken mandate, a pause button that won't work, a confusing screen. People write to an app store or a forum when the product has failed them, and the thing that failed is what they write about. They rarely post their *private financial circumstances* in public: a job loss, a family expense, money needed elsewhere. When finances are the reason, there is usually nothing to complain about, so there is no review. This fits the sample's other known characteristics: it over-represents people who write at length about problems they can attribute to someone else.

**How to read it:**

- The corpus is evidence about **what goes wrong inside the product and the payment chain**. It is **not** evidence that affordability is a minor cause of stopping. The low `affordability_cashflow` share describes what people say in public, not why people stop.
- This is recorded as a **known characteristic of the source**. It is not a contradiction to be resolved inside this data, and the category shares have not been adjusted for it.
- The survey figure rests on 6 stopped SIPs. It is a strong directional signal, but it is too small to give a precise share.
- **This divergence will be tested directly in the user interviews**, which can ask about financial circumstances that public channels never reveal.

## Filtering

### Staff and moderator posts

TradingQ&A replies written by Zerodha staff or moderators are **kept and marked `is_staff: true`**. They are the platform's answers, not the words of investors, so:

- they are **excluded by default from every failure-mode count**: the category distribution, the cross-tabs and the source composition all count investor items only;
- the number excluded is reported at every stage of the funnel;
- they remain in the data as evidence for Q6, *what answer people actually get when they ask*;
- they are not eligible for the golden set or the recall sample, because those test judgements about what investors say.

### Source composition at every stage

Source composition is reported at every stage of the funnel, as counts and percentages of investor items (staff excluded). The pipeline flags any source that exceeds **60%** of a stage, so that dominance by one source is noticed early rather than discovered at the end. The full numbers are in `data/processed/funnel.json`.

| Stage | Investor items | Play | App Store | YouTube | TradingQ&A | Staff excluded |
|---|---:|---:|---:|---:|---:|---:|
| Raw | 32,007 | 18,000 (56.2%) | 3,500 (10.9%) | 7,734 (24.2%) | 2,773 (8.7%) | 447 |
| Keyword-kept | 3,661 | 957 (26.1%) | 344 (9.4%) | 1,232 (33.7%) | 1,128 (30.8%) | 198 |
| Sampled for the LLM stages | _running_ | | | | | |
| LLM-kept | _running_ | | | | | |
| Final records | _running_ | | | | | |

#### Why the LLM stages run on a sample

Groq's free tier allows 200,000 tokens per model per day. Measured costs were about 320 tokens per item for the filter and about 2,000 per item for extraction. Processing all 3,661 kept items would take about 6 days of the filter model's budget and about 17 days of the extraction model's, which is too long for this build. So the LLM stages run on a **random sample of the keyword-kept pool**:

- **Design.** 1,000 investor items are drawn from the kept pool with seed 42, split across sources in proportion to their share of the pool. They are shuffled into one seeded processing order and handled in chunks of 40. The 20 retest items are held out of the sample. The full order is saved as `data/processed/corpus_sample_ids.json`.
- **Stopping rule.** Processing stops once **300 final records** exist. Because the order is random, whatever has been processed at any point is itself a random sample of the kept pool, so stopping early does not bias the category shares; it only widens their margins. The exact number of items processed is recorded in the funnel.
- **Margins of error.** Every category share is reported with its 95% margin of error. With about 300 records, a category near 20% carries about ±4.5 percentage points. These margins reflect sampling only. They do not cover the model's labelling error, which is measured separately in [Validation](#validation).

The raw pool is dominated by Play reviews (56.2%), because app reviews are plentiful and mostly short. The keyword filter removes most of them ("good app", "nice"), and the kept pool is spread fairly evenly across three sources. The App Store contributes least, at 9.4%. No source is close to the 60% limit after the keyword stage.

#### Known characteristic: the sample over-represents people who write at length

The keyword filter changes the mix of sources a great deal:

| Source | Share of raw | Share of keyword-kept |
|---|---:|---:|
| TradingQ&A | 8.7% | 30.8% |
| YouTube | 24.2% | 33.7% |
| Play | 56.2% | 26.1% |
| App Store | 10.9% | 9.4% |

This happens because the filter favours longer text. A long post is more likely to mention a SIP keyword, and the forum and comment sources carry the most long posts. The same favouring of long text shows up *within* every source, not just in the change of mix between sources:

| Source | Median length, raw | Median length, kept | Under 50 characters, raw | Under 50 characters, kept |
|---|---:|---:|---:|---:|
| Play | 21 | 181 | 64% | 12% |
| App Store | 132 | 227 | 18% | 2% |
| YouTube | 43 | 95 | 55% | 24% |
| TradingQ&A | 221 | 330 | 11% | 1% |
| **All sources** | **45** | **181** | **52%** | **12%** |

(Lengths are in characters, for investor items only.)

**The consequence:** the analysed corpus **over-represents people who write at length** and **under-represents the much larger group who leave short reviews**. Someone who writes 300 words on a forum about a failed mandate is more engaged, and possibly more financially literate, than someone who leaves "app bad" after a failed debit. The second person is still a real investor with a real problem, but they rarely say enough to be categorised. This is a characteristic of the sample, not an error. It means category shares describe *investors who explain their experience*, and they may not match the shares across all investors. The opposite choice, keeping short reviews, would have added thousands of items too short to support a verbatim evidence quote or a category.

### Stage 1: keyword filter

This stage is a deterministic pass over every raw item. An item is kept if it contains any keyword as a whole word. Whole-word matching stops `sip` from matching inside "gossip" and `nav` from matching inside "navigate".

**Seed keywords (given in the brief):** `sip`, `systematic investment`, `monthly investment`, `mandate`, `enach`, `e-nach`, `nach`, `autopay`, `auto debit`, `auto-pay`, `instalment`, `installment`, `emi date`, `bounced`, `failed`, `insufficient balance`, `stopped my sip`, `paused`, `cancel sip`, `discontinue`, `skipped`, `step up`, `elss`, `lock-in`, `redeem`, `exit load`, `xirr`, `nav`, `returns`, `folio`

**Keywords added.** Each candidate was tested on the items the seed keywords missed, and a sample of its matches was read before deciding:

| Added | Why |
|---|---|
| `sips` | Plural form. Whole-word `sip` does not match "SIPs", which appeared in 156 items the seeds missed. |
| `mandates`, `emandate`, `e-mandate` | Variant spellings of mandate. |
| `installments`, `instalments` | Plural forms. |
| `step-up`, `stepup`, `top up`, `top-up` | Ways of changing an existing SIP. These are common in Hinglish YouTube comments ("Top-up kese karte h"). |
| `every month`, `har mahine`, `invest monthly` | Describing regular investing without the word "SIP", in English and Hinglish. |
| `pause`, `stop investing`, `stopped investing` | Stopping behaviour, phrased without the word "SIP". |
| `एसआईपी` | "SIP" written in Devanagari script. |

**Tested and not added:**

| Rejected | Why |
|---|---|
| `mutual fund(s)`, `mf` | About 1,600 matches, mostly general comments about apps or funds, not SIP behaviour. |
| `stp`, `swp` | Systematic transfer and withdrawal plans, not SIP continuation. |
| `lumpsum`, `lump sum` | Concerns the way someone invests, not continuing a SIP. |
| `deducted`, `debited` | Mostly about tax and wallet top-ups in the samples read. |
| `monthly` | Too broad. |

Leaving out `mutual fund` is the riskiest of these decisions. An investor could describe stopping without using any of the keywords, for example "I stopped putting money in mutual funds". The recall sample (below) checks whether material like this is being thrown away.

**Result:** the keyword stage kept 3,661 of 32,007 investor items (11.4%). By source, it kept 5.3% of Play reviews, 9.8% of App Store reviews, 15.9% of YouTube comments and 40.7% of TradingQ&A investor posts. TradingQ&A keeps the most because it was found by searching for SIP terms. Play keeps the least because it is a sample of the newest reviews on every topic.

## Validation

### Design

- **Golden set:** 30 investor items from the keyword-**kept** pool, stratified across sources (Play 7, App Store 7, YouTube 8, TradingQ&A 8) and sampled with seed 42. It tests the model's judgement on the candidates it actually sees. If it were sampled from the raw pool, most items would be obviously irrelevant, and agreement would look high without testing anything difficult.
- **Recall sample:** investor items from the keyword-**rejected** pool, using the same seed and stratification. It tests whether the keyword filter discards relevant material. 30 items in total: 10, then 20 more, all with seed 42.
- **Staff posts** are excluded from both samples.
- **Order of work.** Every item was labelled by hand before the model was run on it. The prompts were tuned on a separate sample of 40 items that contains no labelled item. They were then frozen: a fingerprint of the prompts, models, settings and seed is saved in `data/processed/prompt_freeze.json`, and the scoring code refuses to run if anything has changed since. The model ran on the labelled items *after* the freeze and *before* the labels were read.

### Labelling criteria

These criteria were used for hand-labelling. They are taken from the labeller's notes in `golden_30.csv` and `recall_10.csv`.

- **`is_sip_related` = yes** only when the item describes the writer's own SIP experience, problem or decision, or comments directly on continuing SIPs. The following are **no**:
  - pre-start beginner questions where no SIP is held and no failure is described ("Sip matlab", "SIP Kaise Start Kare")
  - enthusiasm with no question or problem ("Ab mai bhi krunga sip 😊")
  - portfolio display features or bugs that do not involve a SIP
  - tax questions not about continuing a SIP
  - fund recommendation requests
  - US-stock threads
  - company auto-replies
- **Cause, not symptom.** When an app failure causes a missed payment, the label is `app_mechanics`, not `mandate_payment_failure`.
- **An eMandate is the SIP mandate**, so a failed eMandate counts as a mandate failure.
- **A feature request about creating SIPs** is `app_mechanics`, not `no_answer_available`.

### Headline numbers

| | Labelled set | Prompt | `is_sip_related` agreement | Category agreement |
|---|---|---|---|---|
| **Blind result, prompt v1** | golden 30 | v1 (`d4d008f2…`) | **63.3%** (19/30) | 63.6% (7/11) |
| **Agreement after prompt revision** | retest 20 | v2 (`3a503fbd…`) | **85.0%** (17/20; 95% interval 64%–95%) | 3/3. Only 3 items were marked SIP-related by both sides, too few to read |

The pre-revision figure is final and was not recalculated after the revision. The golden 30 were **not** used to score prompt v2, because the revision was written after the labeller had seen the model's answers on those items. A score on them would not be blind.

### Results before revision (blind run, prompt v1, fingerprint `d4d008f2…`)

| Measure | Result | 95% interval |
|---|---|---|
| `is_sip_related` agreement, golden set | **19 / 30 (63.3%)** | 46%–78% |
| `primary_category` agreement, on items **both** marked SIP-related | **7 / 11 (63.6%)** | 35%–85% |
| `is_sip_related` agreement, recall sample | **10 / 10 (100%)** | |
| Keyword-filter leak: relevant items in the rejected sample | **0 / 30** (the first 10 plus 20 more) | at most **9.5%** of rejected items are relevant (one-sided upper bound) |
| Quote check, 18 extracted items | 16 exact, 1 matched once spacing is normalised, **1 failed** | |
| Invalid categories rejected | 0 | |

Intervals for the agreement rates are Wilson intervals. The leak bound is an exact binomial bound: 0 relevant out of 30 bounds the leak rate at 9.5%. That is a bound, **not** a finding of "no leakage". The true rate could be anywhere from 0% to 9.5%.

**Evidence of precision in the rejected sample.** One rejected item, `tradingqna:292833`, is the reply "Hi Akshay, Thabk you for the reply". It sits in a thread titled "Is bank mandate- iSIP required for mutual funds". The thread is about SIP mandates, but this reply carries no content of its own. The filter correctly rejected an empty reply inside a relevant thread, which is evidence of precision, not leakage. The filter judges each post on its own text, which contains no keyword, and not on the thread's title.

**The leak bound is not a recall figure.** It limits the share of *rejected* items that are relevant. The rejected pool (28,346 investor items) is about eight times the size of the kept pool, so even a small leak rate would mean many relevant items were lost. A 2% leak, for example, would be about 570 items. The correct claim is "at most X% of what the filter discarded was relevant", not "the filter keeps Y% of relevant items".

### Every disagreement

**`is_sip_related`, golden set (11):**

| Item | Text (start) | Human | Model | Human note |
|---|---|---|---|---|
| play:47b96ce4 | "Pathetic service. They don't give NAV of current date even when you make payment before the cut off time." | yes | no (filter: "NAV missing, not SIP") | |
| appstore:14137979258 | "Mutual Fund Sync Broken Since Feb 2026 – No Resolution Yet…" | yes | no (filter: "Mutual fund sync issue, no SIP") | |
| youtube:Ugw9OqWJ | "…brainwash Small Retail Investors to Continue they're SIPs, Without Any returns…" | yes | no (filter: "Comment on others, no personal SIP") | commentary rather than personal experience, but squarely about continuing SIPs with poor returns |
| tradingqna:487518 | "1 feature request - Is it possible to bring in XIRR calculator for F&O position?" | yes | no (filter: "Feature request unrelated to SIP") | |
| youtube:UgwabLyZ | "Step up kaise hoga isme" | no | yes → app_mechanics | |
| youtube:UgxT37Yl | "Ab mai bhi krunga sip😊 thanks sir" | no | yes → no_answer_available | enthusiasm, not a question or a problem |
| youtube:Ugx_PuHr | "Sip matlab" | no | yes → no_answer_available | pre-start beginner question — no SIP held, no failure described |
| youtube:UgzJ-H2y | "SIP Kaise Start Kare" | no | yes → no_answer_available | pre-start beginner question — no SIP held, no failure described |
| youtube:Ugw7rXyd | "Whats your present XIRR ?" | no | yes → no_answer_available | |
| youtube:UgxIXER- | "Jharkhand gramin Bank ka mutual fund SIP bataiye" | no | yes → no_answer_available | |
| tradingqna:92442 | "…difference between SBI Blue Chip Fund - Direct Plan - Growth and … Dividend? As I am already investing 2500…" | no | yes → app_mechanics | |

**`primary_category`, items both marked SIP-related (4):**

| Item | Text (start) | Human | Model (confidence; secondary) | Human note |
|---|---|---|---|---|
| play:4122adf9 | "SCAM ALERT..DO NOT START DAILY SIP ON PAYTM, THEY WILL NOT INVEST FULL AMOUNT, AMOUNT DEDUCTED … MUCH HIGHER THAN AMOUNT INVESTED…" | fees_trust | mandate_payment_failure (0.97; fees_trust) | |
| appstore:12019373475 | "SIP payment via upi app is not happening. Since December 2024…" | app_mechanics | mandate_payment_failure (0.97) | |
| tradingqna:381928 | "I'm Willing to Do a Small Sip for Next 4 Months… How Many Number of Amc sips…" | no_answer_available | app_mechanics (0.96) | can't find the cancellation rules — nothing about returns |
| tradingqna:30090 | "Hello, Once all the installments in your MF are complete, you can re-enter the same MF…" | no_answer_available | app_mechanics (0.95) | |

**Recall sample:** no disagreements.

### What the disagreements show

- **Most of the `is_sip_related` gap comes from a difference in definition, not from random error.** Six of the seven items the model kept but the human excluded are short pre-start YouTube questions or statements of intent. The frozen filter prompt explicitly told the model to keep "starting a SIP, or why / whether to start one" and "confusion or unanswered questions about how a SIP works". The labelling criterion excludes pre-start items where no SIP is held. The model followed its instruction, but the instruction did not match the labelling standard.
- **The model leans towards labelling by symptom.** In two of the four category disagreements, a payment problem went to `mandate_payment_failure` where the human labelled the cause (`app_mechanics`) or the platform behaviour (`fees_trust`). In the Paytm case the model gave `fees_trust` as a secondary category.
- **The category agreement is based on only 11 items.** Its interval runs from 35% to 85%, so it should be read as indicative only.

### Two golden labels are inconsistent with the labeller's own criteria, and were left uncorrected

Reviewing the disagreements showed that two of the human labels contradict the labelling criteria above:

- **tradingqna:487518** ("1 feature request - Is it possible to bring in XIRR calculator for F&O position?") is labelled SIP-related. Under the criteria it is off-topic: it concerns F&O trading, not a SIP.
- **appstore:14137979258** ("Mutual Fund Sync Broken Since Feb 2026…") is labelled SIP-related. Under the criteria it is a portfolio-sync problem with no SIP mentioned, the same kind of item that was labelled "off-topic — portfolio display bug, not about a SIP" elsewhere.

**The labeller deliberately chose not to correct them.** By then the labeller had seen the model's answers, and changing labels after seeing them would contaminate the ground truth and invalidate the blind test. The 63.3% figure therefore includes two disagreements in which the model's answer matches the written criteria. They are recorded here as a finding about how consistent hand-labelling is, not hidden by editing.

### Revision after the blind test (prompt v1 → v2)

The blind result showed that the v1 filter prompt did not match the labelling criteria: it kept pre-start items, and it labelled by symptom. The prompts were rewritten **to the written criteria, not item by item**:

- **Filter and `is_sip_related`:** exclude pre-start items where no SIP is held and no problem is described (beginner questions, statements of intent or enthusiasm, asking which fund to choose). Also exclude portfolio display features or bugs that do not involve a SIP, tax questions not about continuing a SIP, and company auto-replies.
- **Category:** label by cause, not symptom. An e-mandate is the SIP mandate. A request for a missing SIP feature is `app_mechanics`.

No text from the golden set was copied into the prompts. v2 was checked on the 40-item dev sample, which contains no labelled item: every quote passed the verbatim check, and pre-start items were now rejected. It was then frozen as fingerprint `3a503fbd…`. The v1 freeze record is kept as `prompt_freeze_v1_pre_revision.json`.

**Post-revision score.** v2 is scored on 20 fresh items (`retest_20.csv`). They are drawn from the keyword-kept pool with seed 44, 5 per source. They exclude all 40 labelled items and the 40 dev items v2 was checked on, and they are held out of the corpus run.

### Results after revision (prompt v2, fingerprint `3a503fbd…`)

`is_sip_related` agreement was **17 / 20 (85.0%)**, with a 95% Wilson interval of 64%–95%. Category agreement was 3 / 3, but only 3 retest items were marked SIP-related by both sides, so that figure carries almost no information. Every disagreement:

| Item | Text | Human | Model |
|---|---|---|---|
| play:940f6e0e | "No details in mutual fund. I you investment in sip when will your amount will add in portfolio" | yes | no (passed the filter; extraction judged it `not_relevant`) |
| appstore:12276619905 | "Very very slow NAV update/allotment.. Very very slow NAV update/allotment." | yes | no (filter: "No SIP mention") |
| play:c4564dc8 | "SIP debit has never been delayed by even a single day" | no | yes → `no_answer_available` |

The third disagreement shows the taxonomy's known gap. The post describes a SIP that is working well, and the closed taxonomy has no label for "SIP-related, no problem". The model pushed it into the nearest failure category with low confidence instead of marking it not relevant. Posts like this inflate failure-category counts slightly. The effect is small in this corpus because public feedback is dominated by complaints, but it is a limitation of using a closed failure-mode taxonomy.

### Fill rates in the validation run

Out of 18 extracted items, **0** had any of the six optional fields filled (`start_motivation`, `checking_behaviour`, `influenced_by`, `money_source`, `segment_age_stated`, `segment_income_stated`). Fill rates for the whole corpus are reported under [Field fill rates](#field-fill-rates).

### Labeller's exclusion notes

These are counts of the notes the labeller left on items marked `is_sip_related = no`, exactly as written. "No content" is a separate category from "unintelligible" and is kept apart from it. A blank note means the item was straightforward.

| Note | Recall sample | Golden set |
|---|---:|---:|
| off-topic | 6 | 0 |
| no content | 2 | 0 |
| not a user (company auto-reply) | 1 | 0 |
| portfolio feature wishlist, no SIP | 0 | 2 |
| pre-start beginner question | 0 | 2 |
| enthusiasm, not a question or problem | 0 | 1 |
| tax question, not SIP continuation | 0 | 1 |
| no note (straightforward) | 1 | 9 |

### Keyword-tightening candidates

**A hypothesis that was checked and found wrong.** During labelling, the labeller suspected that several exclusions came from the keyword `failed` matching generic app errors ("request failed"). The data did not support this. For each of the 15 golden items the labeller excluded, these are the keywords that kept it: `sip` alone in 7 items (mostly passing mentions), `xirr` alone in 3, and `failed`, `nav`, `step up` and `redeem` alone in 1 each. One item matched `folio`, `sip` and `xirr` together. `failed` accounted for **one** item, a generic app error ("Holdings: Request failed").

**The real candidates for tightening are bare `sip` and `xirr`.** A bare `sip` keeps items that only mention the word in passing. `xirr` keeps portfolio-display complaints that have nothing to do with SIPs. A possible fix would be to require a SIP-action word nearby (start, stop, pause, debit, mandate, instalment) for a bare `sip`, and to require `sip` within the same item for `xirr`. The filter was **not** changed, because that would alter the pools the labelled samples were drawn from. It is listed as a candidate for a future version.

## Methodology corrections

These were errors in the pipeline itself: in the code or in how the data was collected. They are not errors in the model's output, which are recorded separately under [Corrections to model output](#corrections-to-model-output).

### 0. Prompt changes before the freeze, tested on the dev sample only

Two changes were made while tuning on the dev sample. Neither involved a labelled item.

- **Filter reasoning effort raised from `low` to `medium`.** At `low`, the filter rejected four App Store reviews that plainly discuss SIPs, giving the reason "no SIP mention". One of them described SIPs failing because funds were shared with the stock-trading account. At `medium`, all four were kept, and two items that had been wrongly kept were dropped. It costs about 39% more tokens per item (316 instead of 228).
- **Wording of the quote instruction.** The first attempt to stop quotes being taken from the context line told the model to quote "from the text between <<< and >>>". The model then copied the markers into its quotes, and 7 of 21 quotes failed the verbatim check. After the wording was changed, all 21 dev quotes passed.

### 1. The TradingQ&A topic cap crowded out the neutral search terms

- **The problem.** TradingQ&A is capped at 400 topics. The first version of the scraper filled that cap in the order the search terms were listed. The 16 original terms, most of them about problems, came first and found more than enough topics to fill all 400 places. The 4 neutral terms added later (`first sip`, `start sip`, `sip advice`, `continue sip`) would have contributed almost nothing. Adding them would have changed the list of search terms but not what was collected.
- **The fix.** The cap is now filled one topic at a time from each term in turn: the first result of every term, then the second result of every term, and so on until 400 topics are reached. Every term gets a fair share, wherever it sits in the list. The scraper also records which terms found each topic, so the number of items returned per term can be reported.
- **When it was found.** The error was found before TradingQ&A was scraped, so no data was ever collected with the faulty cap.

### 2. The loader silently skipped YouTube videos whose ID starts with "_"

- **The problem.** Each source keeps an index file (`_videos.json` for YouTube and `_topic_ids.json` for TradingQ&A) next to its item files. To leave the index files out, the loader skipped every file whose name began with an underscore. But YouTube video IDs can also begin with an underscore, and each video's comments are saved in a file named after its ID. Three of the 47 videos were affected, and their 558 comments were dropped without any warning. The scraper reported 7,734 YouTube comments, but the loader passed on only 7,176.
- **How it was found.** The scraper's count and the loader's count did not match. Cross-checking the totals from each stage exposed the gap.
- **The fix.** The loader now skips only the two index files, by exact name. It loads all 7,734 comments, and no item ID appears twice. The gap was found before filtering began, so no later stage was affected.

### 3. TradingQ&A replies included the posts they were quoting

- **The problem.** When someone replies on TradingQ&A, the forum (Discourse) embeds a quote of the post being answered. The scraper turned each post's HTML into plain text, quotes included, so a reply's text contained another person's words, often the original question or a staff answer. 786 of 3,246 posts (24%) contained a quote. A keyword in quoted text could therefore keep the reply in the corpus, and a later evidence quote could put someone else's words on the reply's author.
- **How it was found.** It showed up while reading the first golden-set sample, before any labelling: several TradingQ&A items began with a username followed by a colon (for example `nithin:` or `neha1101:`).
- **The fix.** Quote blocks are now removed before the text is extracted, so each post contains only its author's words. The quoted usernames are kept in a `quotes_users` field. All 400 topics were fetched again with the fix in place, and the keyword stage and both label samples were regenerated from the corrected text. No labels had been collected, so none had to be redone.
- **What it changed.** 26 posts turned out to be nothing but a quote and now have no text, so they were dropped. 57 TradingQ&A investor posts had passed the keyword filter *only* because of words they quoted, and they no longer pass: the kept count fell from 1,185 to 1,128.

### 4. Failed downloads were saved as empty results

- **The problem.** When a TradingQ&A topic failed to download (for example, it timed out), the scraper saved an empty result for it. Because saved results are reused, a rerun would never try that topic again, and it would silently drop out of the corpus.
- **How it was found.** During the re-fetch for correction 3, one topic timed out, and its saved file turned out to be empty.
- **The fix.** A failed download is no longer saved, so the next run retries it. The affected topic was fetched again successfully, returning 2 posts. All 400 topics are now present.

## Where the model failed

## Corrections to model output

The 2–3 places where the model's extraction output was wrong and was corrected by hand, with the reason in each case. Errors in the pipeline itself are listed under [Methodology corrections](#methodology-corrections).

## Field fill rates
