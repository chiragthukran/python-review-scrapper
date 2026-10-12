"""Pull the newest low-star Play Store reviews for an app, tag themes, count them.

Setup:   pip install google-play-scraper pandas
Run:     python scrape_moveinsync_reviews.py
Options: python scrape_moveinsync_reviews.py --app com.moveinsync.ets --per-star 400 --stars 1 2

Outputs (in the current folder):
  reviews.csv         every review fetched (date, stars, version, text, themes)
  theme_counts.csv    count and share per theme
Then READ a sample of reviews.csv yourself and fix any wrong tags before quoting numbers.
"""
import argparse
import re

import pandas as pd

THEMES = {
    "Launch failure / crash": r"crash|not (open|work)|won'?t open|not opening|app error|opens? and clos|force clos|reinstall|uninstall|stuck on|keeps? (closing|stopping)|not able to open",
    "ETA / live tracking": r"\beta\b|live track|tracking|\bgps\b|location|map (is |gets )?stuck|map|cab (arriv|location)|real.?time|arrival time",
    "Forced or blocking steps": r"force[ds]? (me|to)|no skip|can'?t skip|compulsor|policy accept|accept(ing)? policy|seat ?belt|otp (keeps|disappear|hidden)|every time i open|every ride",
    "Feedback / helpdesk / support": r"feedback|helpdesk|help desk|customer (care|support)|support|no response|not responding|call (disconnect|drop)|complain",
    "Routing / long commute": r"rout(e|ing)|detour|pick.?up (time|point)|drop.?(time|order)|hours? to reach|2 hours|long (commute|travel)|clubb",
    "Slow loading / offline": r"slow|load(ing)? time|takes? .{0,10}seconds|lag|offline|no (network|internet)|cache",
    "Booking clarity / no-show": r"book(ing)? (not|fail|confus|step)|2.?step|no.?show|check.?in|cancel|wrong (date|day)|next day",
    "Login / OTP / account": r"log.?in|sign.?in|\botp\b|password|register|verification",
    "Ads": r"\bads?\b|advertis",
}
OTHER = "Other / unclear"
COMPILED = {k: re.compile(v, re.I) for k, v in THEMES.items()}


def tag(text: str):
    hits = [k for k, rx in COMPILED.items() if rx.search(text or "")]
    return hits or [OTHER]


def fetch(app_id, stars, per_star, lang, country):
    from google_play_scraper import Sort, reviews

    rows = []
    for s in stars:
        got, token = 0, None
        while got < per_star:
            batch, token = reviews(
                app_id, lang=lang, country=country, sort=Sort.NEWEST,
                count=min(200, per_star - got), filter_score_with=s,
                continuation_token=token,
            )
            if not batch:
                break
            rows += batch
            got += len(batch)
            if token is None:
                break
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", default="com.moveinsync.ets")
    ap.add_argument("--stars", type=int, nargs="+", default=[1, 2])
    ap.add_argument("--per-star", type=int, default=300)
    ap.add_argument("--lang", default="en")
    ap.add_argument("--country", default="in")
    a = ap.parse_args()

    df = fetch(a.app, a.stars, a.per_star, a.lang, a.country)
    if df.empty:
        print("No reviews returned. Check the app id, your internet connection and the country/lang.")
        return
    df["at"] = pd.to_datetime(df["at"])
    df["content"] = df["content"].fillna("")
    df["themes"] = df["content"].apply(tag)
    keep = [c for c in ["at", "score", "appVersion", "thumbsUpCount", "content", "replyContent", "themes"] if c in df]
    out = df[keep].sort_values("at", ascending=False)
    out.to_csv("reviews.csv", index=False)

    exploded = df.explode("themes")
    counts = exploded["themes"].value_counts().rename("reviews").to_frame()
    counts["share_of_reviews"] = (counts["reviews"] / len(df) * 100).round(1)
    counts.to_csv("theme_counts.csv")

    print(f"App: {a.app}")
    print(f"Reviews: {len(df)} ({', '.join(str(s) + '-star' for s in a.stars)})")
    print(f"Date range: {df['at'].min().date()} to {df['at'].max().date()}")
    if "replyContent" in df:
        print(f"Developer replied to: {df['replyContent'].notna().mean() * 100:.1f}% of these reviews")
    print()
    print(counts.to_string())
    print("\nSaved reviews.csv and theme_counts.csv. Check a sample by hand before quoting these numbers.")


if __name__ == "__main__":
    main()