---
name: a3-screen-scout
description: Look up named movies and actors, or track US films now playing and coming soon, with cast, posters, TMDB ratings, and popularity changes.
version: 0.3.0
metadata:
  hermes:
    tags: [film, actor, movie, cast, releases, tmdb]
---

# Screen Scout: movies and actors

# When to use this skill

Use Screen Scout when John asks about a named movie, a performer, what is in
theaters or coming soon, cast, posters, TMDB ratings, or popularity changes.
Look up named movie and actor facts here rather than relying on model memory.
For industry news or reported box-office grosses, use sourced web search as
well: TMDB popularity is not revenue or news reporting.
Run one of these bundled commands with the terminal tool:

- `python "${HERMES_SKILL_DIR}/scripts/run.py" now_playing`
- `python "${HERMES_SKILL_DIR}/scripts/run.py" upcoming`
- `python "${HERMES_SKILL_DIR}/scripts/run.py" movie --title "Movie title"`
- `python "${HERMES_SKILL_DIR}/scripts/run.py" actor --name "Actor name"`

If the current conversation is the owner's private Telegram chat and the
owner asks to see posters, append `--send-posters` to one command. The helper
then sends up to two actual poster images to the configured Telegram home
channel and reports a count. Never use this flag from a public web chat or
another person's conversation.

The release-list helper returns at most four US titles with release date, three cast names,
TMDB popularity, user rating/vote count, up to two TMDB user-review links,
movie page, and poster URL. It stores a small popularity snapshot in
`A3_STATE_DIR` (or a per-user default) and reports changes since the last
check. The named-movie lookup includes up to five cast members; actor lookup
includes a short biography excerpt, notable released credits, and upcoming
credits. Present useful facts with the corresponding TMDB page link and show
the actual poster or profile URL when available. When reviews exist, identify them as
TMDB user reviews and link to them; do not quote full review text. Treat
popularity as an engagement signal, never as box-office revenue. TMDB user
ratings and reviews are not critic scores or Rotten Tomatoes scores. Do not
invent revenue, ratings, cast, or release dates. Include the returned TMDB
attribution notice when presenting its data.

The skill is read-only with respect to TMDB. Its helper uses only Python's
standard library and does not depend on the Assignment 3 project directory.
It needs `TMDB_API_TOKEN` in the private runtime environment. If missing or
unavailable, say so plainly. The A3 local profile may instead set
`A3_PROJECT_ROOT` to locate its ignored private `.env`; a fresh install
should set `TMDB_API_TOKEN` directly. Do not paste credentials into chat.
