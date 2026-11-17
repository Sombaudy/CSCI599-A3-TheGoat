# Actor film watch for Hermes

This public skill tap contains `skills/a3-film-watch/SKILL.md` and its portable
Python helper. It tracks US films now playing or coming soon using TMDB:
release dates, notable cast, poster links, user ratings, user-review links,
and popularity changes across checks. Popularity is not box-office revenue.

The helper uses Python's standard library. Set `TMDB_API_TOKEN` privately in
the Hermes runtime before using it; never put a token in this repository.
Optionally set `A3_STATE_DIR` to preserve popularity snapshots.
For an owner's private Telegram chat, `--send-posters` sends up to two actual
TMDB poster images when `TELEGRAM_BOT_TOKEN` and `TELEGRAM_HOME_CHANNEL`
are configured privately. The default command only returns sourced data.

After publishing this repository on GitHub, install it as a Hermes tap:

```sh
hermes skills tap add OWNER/REPO
hermes skills install OWNER/REPO/a3-film-watch
```

This product uses the TMDB API but is not endorsed or certified by TMDB.
Film data and poster links come from [TMDB](https://www.themoviedb.org).
