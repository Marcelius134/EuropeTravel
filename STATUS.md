# Status

Last updated: 16 November 2026

## Done and working

- Flask app with a JSON API
- Dark map of 328 NUTS-2 regions (EU, EFTA, the United Kingdom, Turkey and the western Balkans)
- Filter panel: temperature, rainfall, sea and coast, mountains and wild nature, historic feel, crowds
- Month choice; without one, temperature and rainfall use June to August
- Fit threshold slider (70% by default); regions at or above it glow, brighter for a closer fit
- Region card: fit breakdown per filter, best months for the chosen filters, summary, climate chart, cities
- 1,238 city dots; city card with notes and ideas
- Place pins with a matching list; hovering or clicking one highlights the other
- Compare two or three regions side by side
- Save regions and cities; the list is kept in the browser
- The page address follows the view, so a copied link reopens the same filters, region or city
- Dark, terrain and satellite base maps
- Two colour themes for the panels, night and warm, switched with the moon and sun buttons; the choice is remembered
- Data build script with one step per source; downloads are cached, retried and resumable
- Start scripts: `run.bat` and `run.sh`
- 98 tests without a browser and 20 in a real browser

## Works, but on estimates until the data build has been run

Run `python -m scripts.build_data all` (see `README.md`) to replace most of these.

| What | Now | After the data build |
|---|---|---|
| Climate | Hand-written monthly figures for 46 regions; the other 282 have none and can't be scored on temperature or rainfall | Measured climate for all regions |
| Historic feel | Hand-written score for the same 46 regions; none for the rest | Wikidata counts for the rest. The 46 keep their hand-written score |
| City notes | Hand-written for 14 cities | Wikivoyage text for every city that has an article |
| Places | 71 hand-written places in 14 cities, positions typed from memory | Wikivoyage listings for other cities. The 14 keep their hand-written places |

The 46 regions and 14 cities with hand-written content are listed in `data/curated/`.

## Not verified

- **The download steps have never run against the real services.** The environment this was built in could only reach GitHub, so `climate`, `heritage` and `places` were written from knowledge of the APIs and tested with made-up sample responses. Expect to fix small things on the first real run. `boundaries`, `geometry` and `cities` did run for real.
- **`run.bat` has never run.** It was written on Linux. `run.sh` was tried on a fresh copy and works.
- **Most of the page has not been seen over its base map.** Map tiles could not load in the build environment. Only the terrain map was seen on a real computer. The dark map (now Esri's dark gray; the first choice, CARTO, turned out to need a key), the satellite map, the warm theme over a real map, and the compare tray over a real map have not been reviewed.
- Only Chromium was tried, at widths of 1280 and 1366 pixels. Firefox, Edge and Safari have not been.

## Known limits

- "Mountains and wild nature" is a proxy: the share of the region covered by Natural Earth mountain ranges, plus how thinly settled it is. Forests and lakes are not measured, so Finland or the Scottish Highlands score lower than they should unless hand-written.
- "Crowds" is the population living in towns over 15,000 per km². It ignores tourists, so a quiet region with a busy summer coast reads as quiet.
- The Wikidata heritage score counts World Heritage sites and castles. Larger regions have more of both.
- GeoNames sometimes lists a suburb or beach as a city (for example "Acilia-Castel Fusano-Ostia Antica" in Lazio).
- Region names are Eurostat's, in the local language, except for the 46 with hand-written English names.
- The Canary Islands and the French overseas regions are not in the outline file used.
- City names come from the base map itself, so small towns are only named when you hover their dot.
- Region outlines are simplified, so a coastal pin can sit slightly outside its region.
- Saved places live in one browser on one computer. A private window does not keep them.
- The app needs internet for the base map and the fonts. Without it the panels and outlines still work on an empty background.
- Built for a laptop screen. An early phone layout is still in the stylesheet, but compare, saved places and the tray were not designed or tested for it.
- The README screenshots were taken without map tiles, so their background is empty.

## What to do next

`docs/tasks.md` has fourteen tasks written as ready-to-paste issues, in a suggested order. The first is running the data build.
