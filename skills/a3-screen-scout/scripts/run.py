"""Portable, read-only TMDB movie and actor lookup for Hermes.

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


def lookup_movie(title: str, token: str) -> dict:
    """Look up a named movie even when it is outside current release lists."""
    title = " ".join(title.split())[:100]
    if len(title) < 2:
        raise ValueError("A movie title is required")
    search = get_json("/search/movie", token, query=title, include_adult="false", language="en-US", page=1)
    matches = search.get("results", [])
    selected = next((item for item in matches if str(item.get("title", "")).casefold() == title.casefold()), matches[0] if matches else None)
    films = []
    if selected:
        movie_id = int(selected["id"])
        details = get_json(f"/movie/{movie_id}", token, language="en-US")
        credits = get_json(f"/movie/{movie_id}/credits", token, language="en-US")
        reviews = get_json(f"/movie/{movie_id}/reviews", token, language="en-US", page=1)
        poster = details.get("poster_path") or selected.get("poster_path")
        films.append({
            "title": details.get("title") or selected.get("title"),
            "release_date": details.get("release_date") or selected.get("release_date"),
            "overview": str(details.get("overview") or "")[:500],
            "notable_cast": [p["name"] for p in credits.get("cast", [])[:5] if p.get("name")],
            "tmdb_popularity": details.get("popularity"),
            "tmdb_user_rating": details.get("vote_average"),
            "tmdb_user_vote_count": details.get("vote_count"),
            "tmdb_user_reviews": [
                {"author": r.get("author") or "TMDB user", "url": r.get("url") or f"https://www.themoviedb.org/review/{r['id']}"}
                for r in reviews.get("results", [])[:2]
            ],
            "poster_url": f"https://image.tmdb.org/t/p/w500{poster}" if poster else None,
            "source_url": f"https://www.themoviedb.org/movie/{movie_id}",
        })
    return {"mode": "movie", "query": title, "films": films, "source": "TMDB", "attribution": ATTRIBUTION}


def lookup_actor(name: str, token: str) -> dict:
    """Look up a named performer and their sourced movie credits."""
    name = " ".join(name.split())[:100]
    if len(name) < 2:
        raise ValueError("An actor name is required")
    search = get_json("/search/person", token, query=name, include_adult="false", language="en-US", page=1)
    matches = search.get("results", [])
    selected = next((item for item in matches if str(item.get("name", "")).casefold() == name.casefold()), matches[0] if matches else None)
    people = []
    if selected:
        person_id = int(selected["id"])
        details = get_json(f"/person/{person_id}", token, language="en-US")
        credits = get_json(f"/person/{person_id}/movie_credits", token, language="en-US")
        today = datetime.now(timezone.utc).date().isoformat()
        cast = [item for item in credits.get("cast", []) if item.get("release_date")]
        released = sorted((item for item in cast if item["release_date"] <= today), key=lambda item: float(item.get("popularity") or 0), reverse=True)[:5]
        upcoming = sorted((item for item in cast if item["release_date"] > today), key=lambda item: item["release_date"])[:3]
        def credit(item: dict) -> dict:
            return {
                "title": item.get("title"), "release_date": item.get("release_date"),
                "character": item.get("character"),
                "source_url": f"https://www.themoviedb.org/movie/{int(item['id'])}",
            }
        photo = details.get("profile_path")
        people.append({
            "name": details.get("name") or selected.get("name"),
            "known_for_department": details.get("known_for_department"),
            "biography_excerpt": str(details.get("biography") or "")[:400],
            "notable_films": [credit(item) for item in released],
            "upcoming_films": [credit(item) for item in upcoming],
            "profile_photo_url": f"https://image.tmdb.org/t/p/w500{photo}" if photo else None,
            "source_url": f"https://www.themoviedb.org/person/{person_id}",
        })
    return {"mode": "actor", "query": name, "people": people, "source": "TMDB", "attribution": ATTRIBUTION}


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
    parser.add_argument("mode", choices=("now_playing", "upcoming", "movie", "actor"))
    parser.add_argument("--limit", type=int, default=4)
    parser.add_argument("--title", help="Movie title for movie mode")
    parser.add_argument("--name", help="Performer name for actor mode")
    parser.add_argument("--send-posters", action="store_true", help="Send up to two real poster images to the private Telegram home chat")
    args = parser.parse_args()
    state_dir = Path(os.environ.get("A3_STATE_DIR") or Path.home() / ".a3-screen-scout")
    try:
        token = token_from_runtime()
        if args.mode == "movie":
            result = lookup_movie(args.title or "", token)
        elif args.mode == "actor":
            result = lookup_actor(args.name or "", token)
        else:
            result = watch(args.mode, args.limit, state_dir, token)
        if args.send_posters:
            if args.mode == "actor":
                raise ValueError("Poster sending is for movies only")
            result["posters_sent_to_telegram"] = send_posters_to_telegram(result)
    except Exception as exc:
        # Network exceptions may contain a bot-token URL. Never print details.
        print(json.dumps({"error_type": type(exc).__name__, "source": "TMDB"}), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
