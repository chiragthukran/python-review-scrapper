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
    "Launch failure / crash": r"not (down)?loaded from play ?store|showing not installed|not installed|not installed (from|thru|through) play ?store|rooted device|blank screen|not (opening|opened)|not able to open|unable to open|(doesn'?t|wont|won'?t|can'?t|cannot) open|app (stopped|not) working|not working (properly|at all)|crash|force clos|reinstall|uninstall|stuck on|something went wrong|app error|opens? and clos|keeps? (closing|stopping)",
    "Login / OTP / logout": r"\botp\b|log.?(in|out)|sign.?(in|out)|logged out|logging out|verif|register|password|session expired",
    "ETA / live tracking": r"\beta\b|live (track|location)|tracking|\bgps\b|real.?time|map (is |gets )?(stuck|zoom)|zoom|location (not|is not|wrong|incorrect|update|has)|cab tracker|arrival time|(driver|cab|vehicle) location",
    "Blocking or intrusive prompts": r"pop.?ups?|excessively notif|permission|microphone|\bmic\b|seat ?belt|forc(e|ed|ing)|compulsor|no skip|skip|terms and conditions|policy accept|accept(ing)? policy|too many notifications|notification(s)? (spam|all day)|keeps? (asking|giving) (for )?(rating|notification)",
    "Cab / driver / service": r"driver|cab (is |was |are )?(late|not|never)|always late|late by|delay|rude|vendor|transport (team|management|help|desk)|cab management|service",
    "Feedback / helpdesk / support": r"feedback|helpdesk|help desk|customer (care|support)|support|no response|not responding|call (disconnect|drop)|complain|raise a",
    "Routing / pickup points": r"rout(e|ing)|detour|pick.?up (time|point|location)|nodal|clubb|hours? to reach|long (commute|travel)",
    "Slow loading / offline": r"slow|load(ing)? (time|forever)|takes? .{0,12}(seconds|forever)|lag|hang|offline|no (network|internet)|cache",
    "Booking / no-show / cancel": r"book(ing|ed)? (not|fail|confus|step)|2.?step|no.?show|check.?in|cancel|wrong (date|day)|next day|waitlist|unable to (book|schedule)",
    "New update / UI confusion": r"update|new (ui|version|feature)|\bui\b|\bux\b|confus|old version|redesign|user.?friendly",
    "Ads": r"\bads?\b|advertis",
}
GENERIC = "Generic / no detail"
OTHER = "Other / unclear"
COMPILED = {k: re.compile(v, re.I) for k, v in THEMES.items()}


def tag(text: str):
    hits = [k for k, rx in COMPILED.items() if rx.search(text or "")]
    if hits:
        return hits
    # short reviews with no keyword hit are usually "worst app" style: no detail to act on
    return [GENERIC] if len((text or "").split()) <= 8 else [OTHER]


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
    n_generic = int((df["themes"].apply(lambda t: t == [GENERIC])).sum())
    specific = max(len(df) - n_generic, 1)
    counts["share_of_specific"] = (counts["reviews"] / specific * 100).round(1)
    counts.loc[GENERIC, "share_of_specific"] = float("nan") if GENERIC in counts.index else None
    counts.to_csv("theme_counts.csv")

    print(f"App: {a.app}")
    print(f"Reviews: {len(df)} ({', '.join(str(s) + '-star' for s in a.stars)})")
    print(f"Date range: {df['at'].min().date()} to {df['at'].max().date()}")
    print(f"Reviews with no detail ('worst app' style): {n_generic}")
    if "replyContent" in df:
        print(f"Developer replied to: {df['replyContent'].notna().mean() * 100:.1f}% of these reviews")
    print()
    print(counts.to_string())
    print("\nSaved reviews.csv and theme_counts.csv. Check a sample by hand before quoting these numbers.")


if __name__ == "__main__":
    main()