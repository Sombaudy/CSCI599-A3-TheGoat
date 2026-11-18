"""Portable, read-only TMDB film watch for the Hermes skill tap.

Only Python's standard library is required. The caller supplies a private
TMDB_API_TOKEN; this file and its output never contain the token.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = "https://api.themoviedb.org/3"
ATTRIBUTION = "This product uses the TMDB API but is not endorsed or certified by TMDB."


def token_from_runtime() -> str:
    token = os.environ.get("TMDB_API_TOKEN", "").strip()
    if token:
        return token
    # The local A3 profile has an ignored .env. Fresh installations set the
    # token directly in their own private runtime.
    project = os.environ.get("A3_PROJECT_ROOT", "").strip()
    private_file = Path(project) / ".env" if project else None
    if private_file and private_file.is_file():
        for line in private_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("TMDB_API_TOKEN="):
                return line.partition("=")[2].strip().strip("\"'")
    raise RuntimeError("TMDB_API_TOKEN is missing from the private runtime")


def get_json(path: str, token: str, **params: object) -> dict:
    request = Request(
        f"{API}{path}?{urlencode(params)}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    with urlopen(request, timeout=12) as response:
        return json.load(response)


def watch(mode: str, limit: int, state_dir: Path, token: str) -> dict:
    if mode not in {"now_playing", "upcoming"} or not 1 <= limit <= 4:
        raise ValueError("mode must be now_playing or upcoming and limit must be 1..4")
    state_file = state_dir / f"tmdb-{mode}.json"
    try:
        previous = json.loads(state_file.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        previous = {}
    listing = get_json(f"/movie/{mode}", token, language="en-US", region="US", page=1)
    films: list[dict] = []
    next_state: dict[str, dict] = {}
    results = listing.get("results", [])
    if mode == "upcoming":
        today = datetime.now(timezone.utc).date().isoformat()
        results = [item for item in results if str(item.get("release_date") or "") >= today]
    for item in results[:limit]:
        movie_id = int(item["id"])
        cast_data = get_json(f"/movie/{movie_id}/credits", token, language="en-US")
        reviews_data = get_json(f"/movie/{movie_id}/reviews", token, language="en-US", page=1)
        cast = [p["name"] for p in cast_data.get("cast", [])[:3] if p.get("name")]
        reviews = []
        for review in reviews_data.get("results", [])[:2]:
            author_details = review.get("author_details") or {}
            reviews.append({
                "author": review.get("author") or "TMDB user",
                "rating": author_details.get("rating"),
                "url": review.get("url") or f"https://www.themoviedb.org/review/{review['id']}",
            })
        popularity = float(item.get("popularity") or 0)
        prior = previous.get(str(movie_id))
        change = None if prior is None else round(popularity - float(prior.get("popularity", 0)), 2)
        poster = item.get("poster_path")
        films.append({
            "title": item.get("title") or "(untitled)",
            "release_date": item.get("release_date") or "",
            "notable_cast": cast,
            "tmdb_popularity": popularity,
            "popularity_change_since_last_check": change,
            "tmdb_user_rating": item.get("vote_average"),
            "tmdb_user_vote_count": item.get("vote_count"),
            "tmdb_user_reviews": reviews,
            "review_count": int(reviews_data.get("total_results") or 0),
            "poster_url": f"https://image.tmdb.org/t/p/w500{poster}" if poster else None,
            "source_url": f"https://www.themoviedb.org/movie/{movie_id}",
        })
        next_state[str(movie_id)] = {"popularity": popularity}
    state_dir.mkdir(parents=True, exist_ok=True)
    temporary = state_file.with_suffix(".tmp")
    temporary.write_text(json.dumps(next_state, separators=(",", ":")), encoding="utf-8")
    os.replace(temporary, state_file)
    return {
        "mode": mode,
        "region": "US",
        "source": "TMDB",
        "films": films,
        "note": "Popularity is an engagement signal, not box-office gross; TMDB user ratings are not critic scores.",
        "attribution": ATTRIBUTION,
        "attribution_url": "https://www.themoviedb.org/about/logos-attribution",
    }


def send_posters_to_telegram(result: dict) -> int:
    """Send up to two actual image messages to the configured private home chat."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_HOME_CHANNEL", "").strip()
    if not bot_token or not chat_id:
        raise RuntimeError("Telegram home channel is not configured")
    sent = 0
    for movie in result["films"]:
        poster = movie.get("poster_url")
        if not poster:
            continue
        if not poster.startswith("https://image.tmdb.org/t/p/"):
            raise ValueError("Unexpected poster host")
        caption = (
            f"{movie['title']} — {movie.get('release_date') or 'date pending'}\n"
            f"Notable cast: {', '.join(movie.get('notable_cast') or []) or 'not listed'}\n"
            f"{movie['source_url']}\n{ATTRIBUTION}"
        )
        payload = urlencode({"chat_id": chat_id, "photo": poster, "caption": caption}).encode()
        request = Request(f"https://api.telegram.org/bot{bot_token}/sendPhoto", data=payload, method="POST")
        with urlopen(request, timeout=20) as response:
            outcome = json.load(response)
        if not outcome.get("ok"):
            raise RuntimeError("Telegram rejected the poster")
        sent += 1
        if sent >= 2:
            break
    return sent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("now_playing", "upcoming"))
    parser.add_argument("--limit", type=int, default=4)
    parser.add_argument("--send-posters", action="store_true", help="Send up to two real poster images to the private Telegram home chat")
    args = parser.parse_args()
    state_dir = Path(os.environ.get("A3_STATE_DIR") or Path.home() / ".a3-film-watch")
    try:
        result = watch(args.mode, args.limit, state_dir, token_from_runtime())
        if args.send_posters:
            result["posters_sent_to_telegram"] = send_posters_to_telegram(result)
    except Exception as exc:
        # Network exceptions may contain a bot-token URL. Never print details.
        print(json.dumps({"error_type": type(exc).__name__, "source": "TMDB"}), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
