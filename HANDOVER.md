# Handover

For the teammate opening this project for the first time. It says what exists, where each thing lives, how to change it, and what is left to do.

Read this file, then `STATUS.md` (what is real data and what is an estimate), then pick a task from `docs/tasks.md`.

## Start here

1. Run the app: double-click `run.bat` on Windows, or run `./run.sh` on Mac and Linux. The first run sets everything up and opens http://127.0.0.1:5000. `README.md` has the manual steps if the script fails.
2. Click around for five minutes: choose two filters and a month, open a lit region, open one of its cities, compare two regions, save one, switch the theme.
3. Run the tests: `venv\Scripts\python -m pytest` (Windows) or `venv/bin/python -m pytest`. Everything should pass before you change anything.
4. Read "How a click travels" below, then open the one or two files your task touches.

The app needs internet while it runs, because the base map and the two fonts come from other servers. Without internet the panels and region outlines still work on an empty background.

## What the app does

A visitor chooses what they want from a trip. Every region of Europe gets a score from 0 to 100 against those choices, and the regions at or above the fit line glow on the map.

| Feature | Where the visitor sees it |
|---|---|
| Six filters, a month and a fit line | Right panel |
| Glowing regions and a ranked list | Map and right panel |
| Region card: fit, best months, climate, cities | Left panel after clicking a region |
| City card: notes, place pins and a list | Left panel after clicking a city |
| Compare two or three regions | "Compare" on a region card, then the tray over the map |
| Saved regions and cities | "Save" on a card, then the list in the right panel |
| A link that reopens the same view | The address bar, or "Copy a link to this view" |
| Night and warm themes | Moon and sun buttons, top right |
| Dark, terrain and satellite base maps | Buttons at the bottom of the map |

## How a click travels

```
 Browser (static/js)                  Flask (app.py)              Data (data/*.json)
 ───────────────────                  ──────────────              ──────────────────
 choose "Hot"                                                     regions.json
   app.js: toggleFilter()                                         cities.json
   app.js: runMatch()   ── POST /api/match ──▶ matcher.score_all  places.json
                        ◀── a score per region ──                    ▲
   app.js: restyleRegions(), renderResults()                         │ read once at start
   emit("match:updated")                                             │ by store.py
     share.js  rewrites the address
     saved.js  refreshes the scores in the saved list             scripts/build_data.py
     compare.js refreshes an open comparison                      writes these three files
```

The server holds no state between requests. Filters, month, fit line, the open card, saved places and the theme all live in the browser.

## Where things are

### Python

| File | What it holds |
|---|---|
| `app.py` | The Flask app: one page and the JSON API. No scoring logic. |
| `matcher.py` | The filter definitions and every scoring rule. No Flask code, so it can be read and tested alone. |
| `store.py` | Loads the three JSON files once and answers lookups. |
| `scripts/build_data.py` | Entry point of the data build; runs the steps below in order. |
| `scripts/common.py` | Shared helpers: `fetch` (download with cache and retries), JSON read and write, country names. |
| `scripts/geometry.py` | Region outlines, area, coast share, mountain share. |
| `scripts/cities.py` | Picks the main cities per region and measures how built-up each region is. |
| `scripts/climate.py` | Monthly temperature and rainfall from NASA POWER, with Open-Meteo as a fallback. |
| `scripts/heritage.py` | World Heritage sites and castles per region from Wikidata. |
| `scripts/places.py` | City notes and places from Wikivoyage. |
| `scripts/merge.py` | Combines `data/computed/` and `data/curated/` into the three files the app reads. |

### JavaScript

Plain scripts, no build step and no framework. `app.js` creates one shared object, `window.ET`. The other files add a feature each by listening to events on it. A feature can be removed by deleting its file and its `<script>` line in `templates/index.html`.

| File | What it holds |
|---|---|
| `static/js/app.js` | Map, base maps, theme, filter panel, matching, results list, the left panel ("drawer") and the region card. |
| `static/js/cities.js` | City dots, city names on the map, the city card. |
| `static/js/places.js` | Place pins and the place list inside a city card. |
| `static/js/year.js` | The "Best months" bars in the region card. |
| `static/js/compare.js` | The Compare button, the tray over the map and the comparison table. |
| `static/js/saved.js` | The Save button and the Saved list. Stored in the browser only. |
| `static/js/share.js` | Keeps the address in step with the view, reads it on load, and the copy-link button. |

### Events

Scripts talk through `ET.on(name, handler)` and `ET.emit(name, payload)`.

| Event | Sent when | Payload |
|---|---|---|
| `ready` | The map data has loaded | `state` |
| `match:updated` | Filters, month or the fit line changed and the scores are in | `state` |
| `region:render` | A region card is about to open. Add sections to `body` or buttons to `actions`. | `{ region, body, actions, changed }` |
| `region:opened` | The region card is on screen | `{ region, changed }` |
| `city:render` | A city card is about to open. Same idea as `region:render`. | `{ city, body, actions }` |
| `city:opened` | The city card is on screen | `{ city }` |
| `city:closed` | The visitor left a city | `{ cityId }` |
| `drawer:closed` | The left panel was closed | `{ regionId }` |
| `basemap:changed` | Dark, terrain or satellite was chosen | `{ name }` |
| `compare:changed` | The comparison list changed, or the comparison opened or closed | `{ ids }` |
| `saved:changed` | A place was saved or removed | `{ saved }` |

`ET.state` holds what is on screen: `filters`, `month`, `threshold`, `scores`, `ranked`, `selected` (open region id), `view` (`"region"`, `"city"` or `null`), `cityId`, `basemap`, `compare`, `compareOpen`.

### Styles

`static/css/style.css` is one file. Colours are variables at the top: the `:root` block is the night theme and `:root[data-theme="warm"]` is the warm one. Use the variables, never a fixed colour, or the warm theme breaks. Three variables (`--sea`, `--map-ink`, `--map-glow`) are for things drawn on the map and stay the same in both themes.

### Data

| Folder or file | Written by | Edit by hand? |
|---|---|---|
| `data/curated/*.json` | People | Yes. Hand-written names, summaries, estimates and places. |
| `data/computed/*.json` | Build steps | No. Re-run the step. |
| `data/regions.json`, `cities.json`, `places.json` | `merge` step | No. They are overwritten by the next build. |
| `data/cache/` | Downloads | Not in Git. Safe to delete; the next build downloads again. |
| `static/geo/nuts2.geojson` | `boundaries` step | No. |

`SCHEMA.md` describes every field.

## How to make common changes

### Add a filter

1. `matcher.py`: add an entry to `FILTERS` with a label and three level names. The panel draws itself from this list, so the buttons appear without touching JavaScript.
2. Give every region a value from 0 to 1 for it: either a new key in `features` (written by `scripts/merge.py`) or, for something that changes by month, a branch in `matcher.feature_value`.
3. Add a row to `compare.js` only if the default row is not enough; it lists all filters automatically.
4. Tests: `tests/test_matcher.py` for the scoring, `tests/test_data.py` so every region has the new value or `null`.

### Add a section to the region or city card

Listen for the render event in your own file and add to `body`:

```js
ET.on("region:render", ({ region, body }) => {
  body.push(ET.h("section", {}, ET.h("h3", {}, "Getting there"), ET.h("p", {}, "...")));
});
```

`ET.h(tag, attributes, ...children)` builds an element. Text is always inserted as text, never as HTML, so data from Wikivoyage cannot inject markup.

### Add a button under a card title

Push a button to `actions` in the same event. Use the class `action-button`. `saved.js` is the shortest example.

### Add a data source

1. Write `scripts/<name>.py` with pure parsing functions and one `build_<name>()` that downloads with `common.fetch` and writes `data/computed/<name>.json`.
2. Register it in `STEPS` in `scripts/build_data.py`.
3. Read the new file in `scripts/merge.py` and record where each value came from in `sources`.
4. Test the parsing functions with a small made-up answer. `tests/test_fetch.py` shows how to stand in for the network.

### Add an API address

Add a function in `app.py` inside `create_app`. Return `jsonify({"error": "..."})` with a 400 or 404 for bad input; the page shows that text to the visitor. Test it in `tests/test_app.py`.

## Tests

| Command | What runs |
|---|---|
| `pytest` | Everything that is installed. |
| `pytest tests/test_matcher.py` | Scoring rules. |
| `pytest tests/test_app.py` | The API. |
| `pytest tests/test_data.py` | The data files agree with each other. |
| `pytest tests/test_scripts.py tests/test_fetch.py` | Build-script parsing and download handling, with no network. |
| `pytest tests/browser` | The page in a real Chromium. |

The browser tests are skipped unless Playwright is installed:

```bash
pip install -r requirements-browser.txt
playwright install chromium
```

They block every request that is not to the local server, so they need no internet and never see the base map.

## What has not been checked

`STATUS.md` has the full list. The three that matter most:

1. **The data downloads have never run against the real services.** Climate, heritage and Wikivoyage steps were written and tested with made-up answers only. Until someone runs `python -m scripts.build_data all`, 282 of 328 regions cannot be scored on temperature or rainfall. This is the first task in `docs/tasks.md`.
2. **Nobody has tried `run.bat`.** It was written on Linux. `run.sh` was tried and works.
3. **The page was built without seeing the base map.** The environment it was built in could not load map tiles. Only the terrain map has since been seen on a real computer. The dark map (changed to Esri's after that), the satellite map and the warm theme over a real map have not been reviewed.

## Decisions already made

Change these only on purpose, as a team.

- English interface. Travel only, no "where to live".
- Filters are three buttons each, not sliders. No budget filter: prices change too much to keep honest.
- The map never zooms by itself when filters change. It moves only when the visitor opens something.
- A region with no data for a chosen filter gets no score and a dashed outline. It is not treated as a bad match.
- The app runs on a laptop for the demo. The phone layout from an earlier stage is still in the stylesheet (`@media (max-width: 820px)`) but the newer features were not designed or tested for it.
- No accounts and no database. Saved places stay in the visitor's browser.

## Working together

`CONTRIBUTING.md` has the Git workflow: one branch per task, small commits, a pull request, a teammate's review. Run `pytest` before you push.
