"""Scrape public feedback about SIPs from five sources and cache it as JSON.

Each unit (one app, one video, one forum topic) is cached in data/raw/<source>/,
so a re-run only fetches what is missing. Pass --force to re-scrape a source.

    python scrape.py                 # all sources
    python scrape.py play youtube    # just these
"""
import json
import sys
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

import config as C

SESSION = requests.Session()
SESSION.headers["User-Agent"] = C.USER_AGENT


def _cache_path(source, unit):
    d = C.RAW_DIR / source
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{unit}.json"


def _cached(source, unit, fetch, force=False):
    """Return cached items for a unit, or call fetch() and cache the result.
    fetch() returns None on a transient failure; that is not cached, so a
    rerun retries it."""
    path = _cache_path(source, unit)
    if path.exists() and not force:
        return json.loads(path.read_text())
    items = fetch()
    if items is None:
        return []
    path.write_text(json.dumps(items, ensure_ascii=False, indent=1, default=str))
    return items


def _get(url, **params):
    """GET with a polite delay and exponential backoff on 429/503."""
    for attempt in range(C.HTTP_MAX_RETRIES):
        time.sleep(C.REQUEST_DELAY_S)
        r = SESSION.get(url, params=params, timeout=30)
        if r.status_code not in (429, 503):
            break
        retry_after = r.headers.get("Retry-After", "")
        wait = float(retry_after) if retry_after.isdigit() else 2 ** (attempt + 2)
        print(f"    {r.status_code} from {url}; retrying in {wait:.0f}s")
        time.sleep(wait)
    r.raise_for_status()
    return r


def _item(source, id_, url, date, text, **meta):
    return {"id": f"{source}:{id_}", "source": source, "url": url,
            "date": date, "raw_text": text.strip(), **meta}


# --- Google Play ---------------------------------------------------------------
def scrape_play(force=False):
    from google_play_scraper import Sort, reviews

    out = []
    for name, pkg in C.PLAY_APPS.items():
        target = C.PLAY_REVIEWS_PER_APP.get(name, C.PLAY_REVIEWS_DEFAULT)

        def fetch():
            got, token = [], None
            while len(got) < target:
                batch, token = reviews(pkg, lang="en", country="in", sort=Sort.NEWEST,
                                       count=min(200, target - len(got)),
                                       continuation_token=token)
                if not batch:
                    break
                got += batch
                time.sleep(C.REQUEST_DELAY_S)
            return [_item("play", r["reviewId"],
                          f"https://play.google.com/store/apps/details?id={pkg}&reviewId={r['reviewId']}",
                          r["at"].isoformat(), r["content"] or "",
                          app=name, rating=r["score"], thumbs_up=r["thumbsUpCount"])
                    for r in got if r.get("content")]

        items = _cached("play", name, fetch, force)
        print(f"  play/{name}: {len(items)}")
        out += items
    return out


# --- Apple App Store (iTunes RSS) --------------------------------------------
def scrape_appstore(force=False):
    out = []
    for name, app_id in C.APPSTORE_APPS.items():

        def fetch():
            got = []
            for page in range(1, C.APPSTORE_PAGES + 1):
                url = (f"https://itunes.apple.com/in/rss/customerreviews/page={page}"
                       f"/id={app_id}/sortby=mostrecent/json")
                try:
                    entries = _get(url).json().get("feed", {}).get("entry", [])
                except (requests.RequestException, ValueError) as e:
                    print(f"    appstore/{name} page {page}: {e}")
                    break
                if isinstance(entries, dict):
                    entries = [entries]
                entries = [e for e in entries if "im:rating" in e]  # skip app-info entry
                if not entries:
                    break
                for e in entries:
                    title, body = e["title"]["label"], e["content"]["label"]
                    got.append(_item("appstore", e["id"]["label"],
                                     f"https://apps.apple.com/in/app/id{app_id}?see-all=reviews",
                                     e["updated"]["label"], f"{title}. {body}",
                                     app=name, rating=int(e["im:rating"]["label"])))
            return got

        items = _cached("appstore", name, fetch, force)
        print(f"  appstore/{name}: {len(items)}")
        out += items
    return out


# --- Reddit (public .json endpoints) ------------------------------------------
REDDIT = requests.Session()
REDDIT.headers["User-Agent"] = C.REDDIT_JSON_USER_AGENT
_reddit_last_call = [0.0]


def _utc(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def _reddit_get(url, cache, force=False, **params):
    """GET a Reddit .json URL: cached to disk, >= REDDIT_DELAY_S between calls,
    exponential backoff on 429/503/403. A 403 that survives every retry is a
    hard block and raises; two blocked subreddits drop Reddit entirely."""
    if cache.exists() and not force:
        return json.loads(cache.read_text())
    for attempt in range(C.REDDIT_MAX_RETRIES):
        time.sleep(max(0.0, _reddit_last_call[0] + C.REDDIT_DELAY_S - time.time()))
        r = REDDIT.get(url, params={**params, "raw_json": 1}, timeout=30)
        _reddit_last_call[0] = time.time()
        if r.status_code not in (403, 429, 503):
            break
        retry_after = r.headers.get("Retry-After", "")
        wait = float(retry_after) if retry_after.isdigit() else C.REDDIT_DELAY_S * 2 ** (attempt + 1)
        print(f"    reddit {r.status_code}; retrying in {wait:.0f}s")
        time.sleep(wait)
    r.raise_for_status()
    data = r.json()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data))
    return data


def _top_comments(listing, n):
    """First n real comments, breadth-first (top-level before replies)."""
    queue, got = list(listing["data"]["children"]), []
    while queue and len(got) < n:
        c = queue.pop(0)
        if c["kind"] != "t1":  # "more" stubs
            continue
        c = c["data"]
        if c.get("body") not in (None, "[deleted]", "[removed]"):
            got.append(c)
        if c.get("replies"):
            queue += c["replies"]["data"]["children"]
    return got


def scrape_reddit(force=False):
    d = C.RAW_DIR / "reddit"
    found, failed = {}, []  # sub -> {post_id: (post, queries)}
    for sub in C.REDDIT_SUBREDDITS:
        posts = found[sub] = {}
        try:
            for q in C.REDDIT_QUERIES:
                listing = _reddit_get(f"https://www.reddit.com/r/{sub}/search.json",
                                      d / "_search" / f"{sub}__{q.replace(' ', '_')}.json",
                                      force, q=q, restrict_sr=1, sort="new",
                                      limit=C.REDDIT_SEARCH_LIMIT)
                for child in listing["data"]["children"]:
                    posts.setdefault(child["data"]["id"], (child["data"], []))[1].append(q)
        except requests.RequestException as e:
            print(f"  reddit/{sub}: FAILED - {e}")
        if not posts:
            print(f"  reddit/{sub}: no posts returned")
            failed.append(sub)
            if len(failed) >= 2:
                raise RuntimeError(f"blocked or empty on {failed}; dropping Reddit")

    out = []
    for sub, posts in found.items():
        items = []
        for pid, (p, queries) in posts.items():
            items.append(_item("reddit", pid, f"https://www.reddit.com{p['permalink']}",
                               _utc(p["created_utc"]), f"{p['title']}. {p.get('selftext', '')}",
                               subreddit=sub, kind="post", score=p.get("score"), queries=queries))
            if not p.get("num_comments"):
                continue
            try:
                thread = _reddit_get(f"https://www.reddit.com/comments/{pid}.json",
                                     d / "_comments" / f"{pid}.json", force, sort="top")
            except requests.RequestException as e:
                print(f"    reddit/{sub}/{pid}: {e}")
                continue
            for c in _top_comments(thread[1], C.REDDIT_COMMENTS_PER_POST):
                items.append(_item("reddit", c["id"], f"https://www.reddit.com{c['permalink']}",
                                   _utc(c["created_utc"]), c["body"], subreddit=sub,
                                   kind="comment", post_id=pid, post_title=p["title"],
                                   score=c.get("score"), queries=queries))
        _cache_path("reddit", sub).write_text(
            json.dumps(items, ensure_ascii=False, indent=1, default=str))
        print(f"  reddit/{sub}: {len(posts)} posts, {len(items) - len(posts)} comments")
        out += items
    return out


# Unused: Reddit's official API now requires manual approval for new apps, so
# scrape_reddit() uses the public .json endpoints. Kept in case access is granted.
def scrape_reddit_praw(force=False):
    import os

    import praw
    from dotenv import load_dotenv

    load_dotenv(C.ROOT / ".env")
    cid, secret = os.getenv("REDDIT_CLIENT_ID"), os.getenv("REDDIT_CLIENT_SECRET")
    if not (cid and secret):
        print("  reddit: SKIPPED - REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET not set in .env")
        return []
    reddit = praw.Reddit(client_id=cid, client_secret=secret, user_agent=C.REDDIT_USER_AGENT)
    reddit.read_only = True

    out = []
    for sub in C.REDDIT_SUBREDDITS:

        def fetch():
            posts = {}  # id -> (submission, queries that found it)
            for q in C.REDDIT_QUERIES:
                for s in reddit.subreddit(sub).search(q, sort="relevance", time_filter="all",
                                                      limit=C.REDDIT_POSTS_PER_QUERY):
                    posts.setdefault(s.id, (s, []))[1].append(q)
            got = []
            for s, queries in posts.values():
                got.append(_item("reddit", s.id, f"https://www.reddit.com{s.permalink}",
                                 _utc(s.created_utc), f"{s.title}. {s.selftext}",
                                 subreddit=sub, kind="post", score=s.score, queries=queries))
                s.comment_sort = "top"
                s.comments.replace_more(limit=0)  # top-level + loaded replies only
                for c in s.comments.list()[:C.REDDIT_COMMENTS_PER_POST]:
                    got.append(_item("reddit", c.id, f"https://www.reddit.com{c.permalink}",
                                     _utc(c.created_utc), c.body, subreddit=sub,
                                     kind="comment", post_id=s.id, post_title=s.title,
                                     score=c.score, queries=queries))
            return got

        items = _cached("reddit", sub, fetch, force)
        print(f"  reddit/{sub}: {len(items)}")
        out += items
    return out


# --- YouTube ------------------------------------------------------------------
def _youtube_videos(force=False):
    """Top N videos per query via yt-dlp search (no API key)."""
    import yt_dlp

    def fetch():
        vids = {}
        opts = {"quiet": True, "extract_flat": True, "skip_download": True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            for q in C.YOUTUBE_QUERIES:
                res = ydl.extract_info(f"ytsearch{C.YOUTUBE_VIDEOS_PER_QUERY}:{q}", download=False)
                for e in res.get("entries", []):
                    vids.setdefault(e["id"], {"id": e["id"], "title": e.get("title"),
                                              "channel": e.get("channel"), "queries": []}
                                    )["queries"].append(q)
        return list(vids.values())

    return _cached("youtube", "_videos", fetch, force)


def scrape_youtube(force=False):
    from youtube_comment_downloader import SORT_BY_POPULAR, YoutubeCommentDownloader

    dl = YoutubeCommentDownloader()
    out = []
    for v in _youtube_videos(force):
        url = f"https://www.youtube.com/watch?v={v['id']}"

        def fetch():
            got = []
            try:
                for c in dl.get_comments_from_url(url, sort_by=SORT_BY_POPULAR):
                    ts = c.get("time_parsed")
                    got.append(_item("youtube", c["cid"], f"{url}&lc={c['cid']}",
                                     datetime.fromtimestamp(ts, timezone.utc).isoformat() if ts else None,
                                     c["text"], video_id=v["id"], video_title=v["title"],
                                     likes=c.get("votes")))
                    if len(got) >= C.YOUTUBE_COMMENTS_PER_VIDEO:
                        break
            except Exception as e:  # comments disabled, removed video, etc.
                print(f"    youtube/{v['id']}: {type(e).__name__}: {e}")
            return got

        items = _cached("youtube", v["id"], fetch, force)
        print(f"  youtube/{v['id']} ({(v['title'] or '')[:50]}): {len(items)}")
        out += items
    return out


# --- TradingQ&A (Discourse JSON endpoints; allowed by robots.txt) -------------
def _tradingqna_topics(force=False):
    """Topics per query, capped round-robin so every query gets a fair share."""
    def fetch():
        per_query = {}
        for q in C.TRADINGQNA_QUERIES:
            ids = per_query[q] = []
            for page in range(1, C.TRADINGQNA_SEARCH_PAGES + 1):
                data = _get("https://tradingqna.com/search.json", q=q, page=page).json()
                ids += [t["id"] for t in data.get("topics", []) if t["id"] not in ids]
                if not data.get("topics"):
                    break
        chosen = []
        for rank in range(max(map(len, per_query.values()), default=0)):
            for ids in per_query.values():
                if rank < len(ids) and ids[rank] not in chosen:
                    chosen.append(ids[rank])
        return [{"id": t, "queries": [q for q, ids in per_query.items() if t in ids]}
                for t in chosen[:C.TRADINGQNA_MAX_TOPICS]]

    return _cached("tradingqna", "_topic_ids", fetch, force)


def _post_text(cooked):
    """Post text without embedded quotes of other posts (Discourse <aside class="quote">),
    so a reply's text is only its author's words. Returns (text, quoted usernames)."""
    soup = BeautifulSoup(cooked, "html.parser")
    quotes = soup.select("aside.quote")
    quoted = [q.get("data-username") for q in quotes]  # read before any decompose
    for q in quotes:
        if not q.decomposed:  # nested quotes go with their parent
            q.decompose()
    return soup.get_text(" "), [u for u in quoted if u]


def scrape_tradingqna(force=False):
    out = []
    for tid in (t["id"] for t in _tradingqna_topics(force)):

        def fetch():
            try:
                t = _get(f"https://tradingqna.com/t/{tid}.json").json()
            except requests.RequestException as e:
                print(f"    tradingqna/{tid}: {e} (not cached; rerun to retry)")
                return None
            got = []
            for p in t["post_stream"]["posts"]:
                text, quoted = _post_text(p["cooked"])
                got.append(_item("tradingqna", p["id"],
                                 f"https://tradingqna.com/t/{t['slug']}/{tid}/{p['post_number']}",
                                 p["created_at"], text,
                                 topic_title=t["title"], post_number=p["post_number"],
                                 quotes_users=quoted,
                                 is_staff=bool(p.get("staff") or p.get("moderator") or p.get("admin"))))
            return got

        out += _cached("tradingqna", str(tid), fetch, force)
    print(f"  tradingqna: {len(out)} posts")
    return out


SCRAPERS = {"play": scrape_play, "appstore": scrape_appstore, "reddit": scrape_reddit,
            "youtube": scrape_youtube, "tradingqna": scrape_tradingqna}


INDEX_FILES = {"_videos", "_topic_ids"}  # search indexes, not items


def load_raw():
    """All cached raw items across sources (no network)."""
    items = []
    for f in sorted(C.RAW_DIR.glob("*/*.json")):
        # Match index names exactly: YouTube IDs can start with "_" too.
        if f.stem not in INDEX_FILES:
            items += json.loads(f.read_text())
    return items


QUERIES = {"reddit": C.REDDIT_QUERIES, "youtube": C.YOUTUBE_QUERIES,
           "tradingqna": C.TRADINGQNA_QUERIES}


def query_report():
    """Items each search query returned, per source. One item can match several
    queries, so the shares sum to more than 100%."""
    report = {}
    for source, index in [("youtube", "_videos"), ("tradingqna", "_topic_ids")]:
        idx = C.RAW_DIR / source / f"{index}.json"
        if not idx.exists():
            continue
        counts, total = dict.fromkeys(QUERIES[source], 0), 0
        for unit in json.loads(idx.read_text()):
            f = C.RAW_DIR / source / f"{unit['id']}.json"
            n = len(json.loads(f.read_text())) if f.exists() else 0
            total += n
            for q in unit["queries"]:
                counts[q] += n
        report[source] = {"total": total, "queries": counts}
    reddit = [i for i in load_raw() if i["source"] == "reddit"]
    if reddit:
        counts = dict.fromkeys(QUERIES["reddit"], 0)
        for i in reddit:
            for q in i["queries"]:
                counts[q] += 1
        report["reddit"] = {"total": len(reddit), "queries": counts}

    C.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    (C.PROCESSED_DIR / "query_counts.json").write_text(json.dumps(report, indent=1))
    for source, r in report.items():
        print(f"\n[{source}] {r['total']} items")
        for q, n in sorted(r["queries"].items(), key=lambda kv: -kv[1]):
            print(f"  {n:6d}  {n / max(r['total'], 1):6.1%}  {q}")
    return report


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    counts = {}
    for name in args or SCRAPERS:
        print(f"[{name}]")
        try:
            counts[name] = len(SCRAPERS[name](force))
        except Exception as e:
            print(f"  {name}: FAILED - {type(e).__name__}: {e}")
            counts[name] = f"FAILED: {e}"
    print("\nRaw counts:", json.dumps(counts, indent=1))
    print("\nItems per search query:")
    query_report()
