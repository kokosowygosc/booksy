# booksy-watch

Watch a [Booksy](https://booksy.com/) salon for **earlier** appointment slots and get
notified the moment a closer date opens up.

## What it does

You give it a salon URL and a service. It polls Booksy's public availability API
every few minutes, remembers the earliest known slot, and alerts you (sound +
desktop notification + on-screen banner) whenever an earlier slot appears.
If your "target" slot gets taken by someone else before you book it, it
silently rolls forward to the next-earliest slot and keeps watching.

Loops forever until you quit. No login required.

## Install

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone <this repo>
cd booksy
uv sync
```

## Run

```bash
uv run booksy-watch
```

First launch starts an interactive wizard:

1. Pick language (`en` / `pl`)
2. Paste a salon URL
3. Pick a service from the printed table
4. Set polling interval (default 10 min) and lookahead window (default 90 days)
5. Sound / desktop notifications on/off

Language can be changed later inside the TUI settings (press `s`). A language
change takes effect on the next restart.

Config is saved to `~/.config/booksy-watch/config.toml`. Re-run the wizard with:

```bash
uv run booksy-watch reconfigure
```

## TUI keys

| key | action |
|-----|--------|
| `q` | quit |
| `p` | pause / resume polling |
| `r` | reset target — next check sets a fresh one (use after you've booked) |
| `c` | check now — skip the wait until next poll |
| `s` | settings — edit interval / lookahead / notifications without restarting |

## How it works under the hood

Booksy's web app calls an unauthenticated read endpoint:

```
POST https://{country}.booksy.com/api/{country}/2/customer_api/me/businesses/{id}/time_slots/
body: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD", "service_variant_ids": [<id>]}
```

It returns minutes-since-midnight values per day. We poll it, sort, and
compare to the target stored in `~/.config/booksy-watch/state.json`.

## Files

```
src/booksy_watch/
  booksy.py    HTTP client (business + time_slots)
  config.py    TOML config + JSON state
  wizard.py    first-run setup
  watcher.py   polling loop + target state machine
  notify.py    afplay + osascript desktop notify
  tui.py       Textual dashboard
  __main__.py  entry point
```

## Caveats

- macOS-only notifications (`afplay`, `osascript`). Other platforms still get
  the in-TUI banner; sound/desktop are silently no-ops.
- Booksy may change the API or rotate the public `x-api-key` baked into the
  web app. If polling starts returning 401/403, grep the bundle at
  `dk2h3gy4kn9jw.cloudfront.net` for `apiClient:{apiUrl:` to find a new one.
- Don't hammer it — default interval is 10 min. Going below 1 min is rude.
