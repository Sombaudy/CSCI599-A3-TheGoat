---
name: a3-film-watch
description: Help an actor track US films now playing or coming soon, with notable cast, posters, TMDB ratings, and popularity changes.
version: 0.2.0
metadata:
  hermes:
    tags: [film, actor, releases, tmdb]
---

# Actor film watch

Use this skill when John asks what films are in theaters or coming soon, who
stars in them, how TMDB users rate them, or which titles have gained attention.
For a named movie, look it up with this skill rather than relying on model
memory. For industry news or reported box-office grosses, use sourced web
search as well: TMDB popularity is not revenue or news reporting.
Run one of these bundled commands with the terminal tool:

- `python "${HERMES_SKILL_DIR}/scripts/run.py" now_playing`
- `python "${HERMES_SKILL_DIR}/scripts/run.py" upcoming`

If the current conversation is the owner's private Telegram chat and the
owner asks to see posters, append `--send-posters` to one command. The helper
then sends up to two actual poster images to the configured Telegram home
channel and reports a count. Never use this flag from a public web chat or
another person's conversation.

The helper returns at most four US titles with release date, three cast names,
TMDB popularity, user rating/vote count, up to two TMDB user-review links,
movie page, and poster URL. It stores a small popularity snapshot in
`A3_STATE_DIR` (or a per-user default) and reports changes since the last
check. Present two or three useful titles, link to each TMDB page, and show
the actual poster URL when available. When reviews exist, identify them as
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
